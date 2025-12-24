# Based upon https://github.com/supriya-project/supriya/blob/v25.9b1/examples/keyboard_input/__init__.py
"""
Keyboard input.

Let's play live with either a MIDI keyboard or our QWERTY keyboard.

Invoke with:

..  shell::
    :cwd: ..
    :rel: ..
    :user: josephine
    :host: laptop

    python -m examples.keyboard_input --help

... to see complete options.

See the :doc:`example documentation </examples/keyboard_input>` for a complete
explanation.
"""

from abc import ABC, abstractmethod
import contextlib
from dataclasses import dataclass, field
import functools
from typing import Callable, Generator

import pynput
import rtmidi
import rtmidi.midiconstants
import rtmidi.midiutil
import supriya
import supriya.conversions

import synths


def list_midi_ports():
    """
    Print out available MIDI input ports.
    """
    rtmidi.midiutil.list_input_ports()


@dataclass
class PolyphonyManager:
    """
    A polyphony manager.

    Translates note on/off events into actions
    against a :py:class:`~supriya.contexts.core.Context`.
    """

    # The server to act on.
    server: supriya.Context
    theory: MusicTheory
    # A dictionary of MIDI note numbers to synths.
    notes: dict[int, supriya.Synth] = field(default_factory=dict)
    # Target node to add relative to.
    target_node: supriya.Node | None = None
    # Add action to use.
    add_action: supriya.AddAction = supriya.AddAction.ADD_TO_HEAD
    # Optional callback for note on events (note_number, frequency, velocity).
    note_on_callback: Callable[[int, float, int], None] | None = None
    # Optional callback for note off events (note_number).
    note_off_callback: Callable[[int], None] | None = None
    # Optional callback for synth change events (synth_name).
    synth_change_callback: Callable[[str], None] | None = None

    def free_all(self) -> None:
        """
        Free all currently playing :py:class:`~supriya.contexts.entities.Synth`
        instances.
        """
        with self.server.at():
            for synth in self.notes.values():
                synth.free()

    def note_on(self, note_number: int, velocity: int) -> None:
        """
        Start a note.
        """
        # Bail if we already started this note.
        if note_number in self.notes:
            return
        frequency = self.theory.tuning.midi_note_number_to_frequency(note_number)
        amplitude = supriya.conversions.midi_velocity_to_amplitude(velocity)
        # Create a synth and store a reference by MIDI note number in the dictionary.
        self.notes[note_number] = self.server.add_synth(
            add_action=self.add_action,
            amplitude=amplitude,
            frequency=frequency,
            synthdef=self.theory.synthdef,
            target_node=self.target_node,
        )
        if self.note_on_callback:
            self.note_on_callback(note_number, frequency, velocity)

    def note_off(self, note_number: int) -> None:
        """
        Stop a note.
        """
        # Bail if we already stopped this note.
        if note_number not in self.notes:
            return
        # Pop the synth out of the dictionary and free it.
        self.notes.pop(note_number).free()
        # Call the callback if provided.
        if self.note_off_callback:
            self.note_off_callback(note_number)


@dataclass
class InputHandler(ABC):
    """
    Base class for input handlers.
    """

    @contextlib.contextmanager
    @abstractmethod
    def listen(
        self, polyphony_manager: PolyphonyManager
    ) -> Generator[None, None, None]:
        # Subclasses must implement this method.
        # 1) Start the handler's listener.
        # 2) Yield to the with block body.
        # 3) Stop the handler's listener.
        pass


@dataclass
class MidiHandler(InputHandler):
    """
    A MIDI input handler.
    """

    port: int | str

    @contextlib.contextmanager
    def listen(
        self, polyphony_manager: PolyphonyManager
    ) -> Generator[None, None, None]:
        """
        Context manager for listening to MIDI input events.
        """
        self.midi_input = rtmidi.MidiIn()  # type: ignore
        self.midi_input.set_callback(functools.partial(self.handle, polyphony_manager))
        self.midi_input.open_port(self.port)
        print('Listening for MIDI keyboard events ...')
        yield
        self.midi_input.close_port()

    def handle(
        self,
        polyphony_manager: PolyphonyManager,
        event: tuple[tuple[int, int, int], float],
        *args,
    ) -> None:
        """
        Handle a MIDI input event.
        """
        # The raw MIDI event is a 2-tuple of MIDI data and time delta.
        # Unpack it, keep the data and discard the time delta.
        [func, note_number, velocity], _ = event
        if rtmidi.midiconstants.NOTE_ON <= func < rtmidi.midiconstants.NOTE_ON + 16:
            if velocity == 0:
                polyphony_manager.note_off(note_number=note_number)
            else:
                polyphony_manager.note_on(note_number=note_number, velocity=velocity)
        elif rtmidi.midiconstants.NOTE_OFF <= func < rtmidi.midiconstants.NOTE_OFF + 16:
            polyphony_manager.note_off(note_number=note_number)


@dataclass
class QwertyHandler(InputHandler):
    """
    A QWERTY input handler.
    """

    octave: int = 5
    presses_to_note_numbers: dict[str, int] = field(default_factory=dict)

    @contextlib.contextmanager
    def listen(
        self, polyphony_manager: PolyphonyManager
    ) -> Generator[None, None, None]:
        """
        Context manager for listening to QWERTY input events.
        """
        self.listener = pynput.keyboard.Listener(
            on_press=functools.partial(self.on_press, polyphony_manager),
            on_release=functools.partial(self.on_release, polyphony_manager),
        )
        self.listener.start()
        print('Listening for QWERTY keyboard events ...')
        yield
        self.listener.stop()

    @staticmethod
    def qwerty_key_to_pitch_number(key: str) -> int | None:
        """
        Translate a QWERTY key event into a pitch number.
        """
        # Dict lookups are faster, but this is soooo much shorter.
        try:
            return "awsedftgyhujkolp;'".index(key)
        except ValueError:
            return None

    def on_press(
        self,
        polyphony_manager: PolyphonyManager,
        key: pynput.keyboard.Key | pynput.keyboard.KeyCode | None,
    ) -> None:
        """
        Handle a QWERTY key press.
        """
        if not isinstance(key, pynput.keyboard.KeyCode):
            return
        if key.char is None:
            return
        if key.char == 'z':
            self.octave = max(self.octave - 1, 0)
            return
        if key.char == 'x':
            self.octave = min(self.octave + 1, 10)
            return
        if key.char == 'c':
            polyphony_manager.theory.synthdef = synths.default
            if polyphony_manager.synth_change_callback:
                polyphony_manager.synth_change_callback('default')
        if key.char == 'v':
            polyphony_manager.theory.synthdef = synths.simple_sine
            if polyphony_manager.synth_change_callback:
                polyphony_manager.synth_change_callback('simple_sine')
        if key.char == 'b':
            polyphony_manager.theory.synthdef = synths.mockingboard
            if polyphony_manager.synth_change_callback:
                polyphony_manager.synth_change_callback('mockingboard')
        if key.char == 'n':
            polyphony_manager.theory.tuning = JustIntonation(key='A')
        if key.char == 'm':
            polyphony_manager.theory.tuning = EqualTemperament()

        if key in self.presses_to_note_numbers:
            return  # Already pressed.
        if (pitch := self.qwerty_key_to_pitch_number(key.char)) is None:
            return  # Not a valid key, ignore it.
        # Calculate the note number from the pitch and octave.
        note_number = pitch + self.octave * 12
        velocity = 64
        # Stash the note number with the key for releasing later.
        # This ensures that changing the octave doesn't prevent releasing.
        self.presses_to_note_numbers[key.char] = note_number
        polyphony_manager.note_on(note_number=note_number, velocity=velocity)

    def on_release(
        self,
        polyphony_manager: PolyphonyManager,
        key: pynput.keyboard.Key | pynput.keyboard.KeyCode | None,
    ) -> None:
        """
        Handle a QWERTY key release.
        """
        if not isinstance(key, pynput.keyboard.KeyCode):
            return  # Bail if we didn't get a keycode object.
        # Bail if the key isn't currently held down.
        if key.char not in self.presses_to_note_numbers:
            return
        # Grab the note number out of the stash.
        note_number = self.presses_to_note_numbers.pop(key.char)
        polyphony_manager.note_off(note_number=note_number)


@dataclass
class Tuning(ABC):
    @abstractmethod
    def midi_note_number_to_frequency(self, note_number: float) -> float: pass


@dataclass
class EqualTemperament(Tuning):
    def midi_note_number_to_frequency(self, note_number: float) -> float:
        return supriya.conversions.midi_note_number_to_frequency(note_number)


@dataclass
class JustIntonation(Tuning):
    key: str
    def midi_note_number_to_frequency(self, note_number: float) -> float:
        if note_number == 69:
            return 440
        elif note_number == 73:
            return 550
        elif note_number == 76:
            return 660
        else:
            return 0


@dataclass
class MusicTheory:
    tuning: Tuning
    synthdef: supriya.SynthDef