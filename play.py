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
from typing import Generator

import pynput
import rtmidi
import rtmidi.midiconstants
import rtmidi.midiutil
import supriya
import supriya.conversions

import synths
from tui import StateManager


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
    # State manager for UI updates.
    state_manager: StateManager
    # A dictionary of MIDI note numbers to synths.
    notes: dict[int, supriya.Synth] = field(default_factory=dict)
    # Target node to add relative to.
    target_node: supriya.Node | None = None
    # Add action to use.
    add_action: supriya.AddAction = supriya.AddAction.ADD_TO_HEAD

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
        self.state_manager.add_note(note_number, frequency, velocity)

    def note_off(self, note_number: int) -> None:
        """
        Stop a note.
        """
        # Bail if we already stopped this note.
        if note_number not in self.notes:
            return
        # Pop the synth out of the dictionary and free it.
        self.notes.pop(note_number).free()
        self.state_manager.remove_note(note_number)


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
            polyphony_manager.state_manager.update_octave(self.octave)
            return
        if key.char == 'x':
            self.octave = min(self.octave + 1, 10)
            polyphony_manager.state_manager.update_octave(self.octave)
            return
        if key.char == 'c':
            polyphony_manager.theory.synthdef = synths.default
            polyphony_manager.state_manager.update_synth('default')
        if key.char == 'v':
            polyphony_manager.theory.synthdef = synths.simple_sine
            polyphony_manager.state_manager.update_synth('simple_sine')
        if key.char == 'b':
            polyphony_manager.theory.synthdef = synths.mockingboard
            polyphony_manager.state_manager.update_synth('mockingboard')
        if key.char == 'n':
            polyphony_manager.theory.tuning = JustIntonation(key='A')
            polyphony_manager.state_manager.update_tuning('JustA')
        if key.char == 'm':
            polyphony_manager.theory.tuning = EqualTemperament()
            polyphony_manager.state_manager.update_tuning('EqualTemperament')
        if key.char == ',':
            polyphony_manager.theory.tuning = JustIntonation(key='C')
            polyphony_manager.state_manager.update_tuning('JustC')
        if key.char == '.':
            polyphony_manager.theory.tuning = Pythagorean(key='C')
            polyphony_manager.state_manager.update_tuning('PythC')
        if key.char == '/':
            polyphony_manager.theory.tuning = Pythagorean(key='A')
            polyphony_manager.state_manager.update_tuning('PythA')

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


class RatioBasedTuning(Tuning):
    # Map note names to chromatic scale degrees
    NOTE_NAMES = {
        'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
    }

    def midi_note_number_to_frequency(self, note_number: float) -> float:
        """
        Helper method to calculate frequency using ratio-based tuning systems.

        Args:
            note_number: MIDI note number
            key: Musical key (e.g., 'C', 'A')
            ratios: List of 12 ratios for chromatic scale degrees

        Returns:
            Frequency in Hz
        """
        # MIDI note 69 is A4 at 440 Hz (our reference pitch)
        reference_midi = 69  # A4
        reference_freq = 440.0

        # Get the chromatic pitch class (0-11) of the input note
        # MIDI 60 = C, 61 = C#, 62 = D, etc.
        pitch_class = int(note_number) % 12

        # Get the key's chromatic degree (where the key's tonic is in the chromatic scale)
        key_degree = self.NOTE_NAMES.get(self.key.upper(), 9)  # Default to A

        # Calculate the scale degree relative to the key (0-11)
        # 0 = tonic, 1 = minor second, 2 = major second, etc.
        scale_degree = (pitch_class - key_degree) % 12

        # Get the ratio for this scale degree
        ratio = self.RATIOS[scale_degree]

        # Calculate the base frequency for this note using equal temperament
        # This gives us the "expected" frequency for this MIDI note
        semitones_from_reference = note_number - reference_midi
        base_freq = reference_freq * (2 ** (semitones_from_reference / 12))

        # Calculate what the ET ratio would be for this scale degree
        et_ratio = 2 ** (scale_degree / 12)

        # Adjust the frequency: replace ET ratio with the custom ratio
        frequency = base_freq * (ratio / et_ratio)

        return frequency


@dataclass
class EqualTemperament(Tuning):
    def midi_note_number_to_frequency(self, note_number: float) -> float:
        return supriya.conversions.midi_note_number_to_frequency(note_number)


@dataclass
class JustIntonation(RatioBasedTuning):
    key: str

    # Just intonation ratios for the 12-tone chromatic scale
    # Using 5-limit just intonation ratios
    RATIOS = [
        1.0,        # Unison (C)
        16/15,      # Minor second (C#/Db)
        9/8,        # Major second (D)
        6/5,        # Minor third (Eb)
        5/4,        # Major third (E)
        4/3,        # Perfect fourth (F)
        45/32,      # Tritone (F#/Gb)
        3/2,        # Perfect fifth (G)
        8/5,        # Minor sixth (Ab)
        5/3,        # Major sixth (A)
        9/5,        # Minor seventh (Bb)
        15/8,       # Major seventh (B)
    ]


@dataclass
class Pythagorean(RatioBasedTuning):
    key: str

    # Pythagorean tuning ratios for the 12-tone chromatic scale
    # Built using only powers of 2 and 3 (perfect fifths and octaves)
    RATIOS = [
        1.0,        # Unison (C)
        256/243,    # Minor second (C#/Db) - Pythagorean limma
        9/8,        # Major second (D) - whole tone
        32/27,      # Minor third (Eb)
        81/64,      # Major third (E) - Pythagorean ditone
        4/3,        # Perfect fourth (F)
        729/512,    # Tritone (F#/Gb) - augmented fourth
        3/2,        # Perfect fifth (G)
        128/81,     # Minor sixth (Ab)
        27/16,      # Major sixth (A)
        16/9,       # Minor seventh (Bb)
        243/128,    # Major seventh (B)
    ]


@dataclass
class MusicTheory:
    tuning: Tuning
    synthdef: supriya.SynthDef