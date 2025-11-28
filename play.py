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
class Command(ABC):
    pass


@dataclass
class NoteOn(Command):
    """
    A note on event.
    """

    note_number: int
    velocity: int


@dataclass
class NoteOff(Command):
    """
    A note off event.
    """

    note_number: int


@dataclass
class SelectSynthDef(Command):
    synthdef: supriya.SynthDef


@dataclass
class PolyphonyManager:
    """
    A polyphony manager.

    Translates :py:class:`NoteOn` or :py:class:`NoteOff` events into actions
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
    # Optional callback for note events.
    note_callback: Callable[[NoteOn | NoteOff, float], None] | None = None

    def free_all(self) -> None:
        """
        Free all currently playing :py:class:`~supriya.contexts.entities.Synth`
        instances.
        """
        with self.server.at():
            for synth in self.notes.values():
                synth.free()

    def perform(self, event: Command) -> None:
        """
        Perform a :py:class:`NoteOn` or :py:class:`NoteOff` event.
        """
        if isinstance(event, SelectSynthDef):
            self.theory.synthdef = event.synthdef
        # If we're starting a note.
        elif isinstance(event, NoteOn):
            # Bail if we already started this note.
            if event.note_number in self.notes:
                return
            # Convert MIDI 0-127 to frequency in Hertz.
            frequency = self.theory.tuning.midi_note_number_to_frequency(
                event.note_number
            )
            # Convert MIDI 0-127 to amplitude.
            amplitude = supriya.conversions.midi_velocity_to_amplitude(event.velocity)
            # Create a synth and store a reference by MIDI note number in the dictionary.
            self.notes[event.note_number] = self.server.add_synth(
                add_action=self.add_action,
                amplitude=amplitude,
                frequency=frequency,
                synthdef=self.theory.synthdef,
                target_node=self.target_node,
            )
            # Call the callback if provided.
            if self.note_callback:
                self.note_callback(event, frequency)
        # If we're stopping a note.
        elif isinstance(event, NoteOff):
            # Bail if we already stopped this note.
            if event.note_number not in self.notes:
                return
            # Pop the synth out of the dictionary and free it.
            self.notes.pop(event.note_number).free()
            # Call the callback if provided.
            if self.note_callback:
                self.note_callback(event, 0.0)


@dataclass
class InputHandler(ABC):
    """
    Base class for input handlers.
    """

    @contextlib.contextmanager
    @abstractmethod
    def listen(
        self, callback: Callable[[Command], None]
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
        self, callback: Callable[[Command], None]
    ) -> Generator[None, None, None]:
        """
        Context manager for listening to MIDI input events.
        """
        self.midi_input = rtmidi.MidiIn()  # type: ignore
        # Set the MIDI event callback to this class's handle method.
        self.midi_input.set_callback(functools.partial(self.handle, callback))
        self.midi_input.open_port(self.port)  # Open the port for listening.
        print('Listening for MIDI keyboard events ...')  # Let the user know.
        yield  # Yield to the with block body.
        self.midi_input.close_port()  # Close the port.

    def handle(
        self,
        callback: Callable[[NoteOn | NoteOff], None],
        event: tuple[tuple[int, int, int], float],
        *args,
    ) -> None:
        """
        Handle a MIDI input event.
        """
        # The raw MIDI event is a 2-tuple of MIDI data and time delta.
        # Unpack it, keep the data and discard the time delta.
        data, _ = event
        if data[0] == rtmidi.midiconstants.NOTE_ON + 1:  # If we received a note-on.
            # Grab the note number and velocity.
            _, note_number, velocity = data
            # Perform a "note on" event.
            callback(NoteOn(note_number=note_number, velocity=velocity))
        elif (
            data[0] == rtmidi.midiconstants.NOTE_OFF + 1
        ):  # If we received a note-off.
            # Grab the note number.
            _, note_number, _ = data
            # Perform a "note off" event.
            callback(NoteOff(note_number=note_number))


@dataclass
class QwertyHandler(InputHandler):
    """
    A QWERTY input handler.
    """

    octave: int = 5
    presses_to_note_numbers: dict[str, int] = field(default_factory=dict)

    @contextlib.contextmanager
    def listen(
        self, callback: Callable[[Command], None]
    ) -> Generator[None, None, None]:
        """
        Context manager for listening to QWERTY input events.
        """
        # Set up the QWERTY keyboard listener.
        self.listener = pynput.keyboard.Listener(
            on_press=functools.partial(self.on_press, callback),
            on_release=functools.partial(self.on_release, callback),
        )
        self.listener.start()  # Start the listener.
        print('Listening for QWERTY keyboard events ...')  # Let the user know.
        yield  # Yield to the with block body.
        self.listener.stop()  # Stop the listener.

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
        callback: Callable[[Command], None],
        key: pynput.keyboard.Key | pynput.keyboard.KeyCode | None,
    ) -> None:
        """
        Handle a QWERTY key press.
        """
        if not isinstance(key, pynput.keyboard.KeyCode):
            return  # Bail if we didn't get a keycode object.
        if key.char is None:
            return
        if key.char == 'z':  # Decrement our octave setting.
            self.octave = max(self.octave - 1, 0)
            return
        if key.char == 'x':  # Increment our octave setting.
            self.octave = min(self.octave + 1, 10)
            return
        if key.char == 'c':
            callback(SelectSynthDef(synthdef=synths.default))
        if key.char == 'v':
            callback(SelectSynthDef(synthdef=synths.simple_sine))
        if key.char == 'b':
            callback(SelectSynthDef(synthdef=synths.mockingboard))

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
        # Perform a "note on" event.
        callback(NoteOn(note_number=note_number, velocity=velocity))

    def on_release(
        self,
        callback: Callable[[NoteOn | NoteOff], None],
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
        # Perform a "note off" event.
        callback(NoteOff(note_number=note_number))


@dataclass
class Tuning(ABC):
    @abstractmethod
    def midi_note_number_to_frequency(self, note_number: float) -> float: pass


@dataclass
class EqualTemperament(Tuning):
    def midi_note_number_to_frequency(self, note_number: float) -> float:
        return supriya.conversions.midi_note_number_to_frequency(note_number)


@dataclass
class MusicTheory:
    tuning: Tuning
    synthdef: supriya.SynthDef