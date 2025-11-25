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

import contextlib
from dataclasses import dataclass, field
import functools
import random
from typing import Callable, Generator

import pynput
import rtmidi
import rtmidi.midiconstants
import supriya


@dataclass
class NoteOn:
    """
    A note on event.
    """

    note_number: int
    velocity: int


@dataclass
class NoteOff:
    """
    A note off event.
    """

    note_number: int


@dataclass
class PolyphonyManager:
    """
    A polyphony manager.

    Translates :py:class:`NoteOn` or :py:class:`NoteOff` events into actions
    against a :py:class:`~supriya.contexts.core.Context`.
    """

    # the server to act on
    server: supriya.Context
    # a dictionary of MIDI note numbers to synths
    notes: dict[int, supriya.Synth] = field(default_factory=dict)
    # a synthdef to use when making new synths
    synthdef: supriya.SynthDef = field(default=supriya.default)
    # target node to add relative to
    target_node: supriya.Node | None = None
    # add action to use
    add_action: supriya.AddAction = supriya.AddAction.ADD_TO_HEAD

    def free_all(self) -> None:
        """
        Free all currently playing :py:class:`~supriya.contexts.entities.Synth`
        instances.
        """
        with self.server.at():
            for synth in self.notes.values():
                synth.free()

    def perform(self, event: NoteOn | NoteOff) -> None:
        """
        Perform a :py:class:`NoteOn` or :py:class:`NoteOff` event.
        """
        # if we're starting a note ...
        if isinstance(event, NoteOn):
            # bail if we already started this note
            if event.note_number in self.notes:
                return
            # convert MIDI 0-127 to frequency in Hertz
            frequency = supriya.conversions.midi_note_number_to_frequency(
                event.note_number
            )
            # convert MIDI 0-127 to amplitude
            amplitude = supriya.conversions.midi_velocity_to_amplitude(event.velocity)
            # create a synth and store a reference by MIDI note number in the
            # dictionary ...
            self.notes[event.note_number] = self.server.add_synth(
                add_action=self.add_action,
                amplitude=amplitude,
                frequency=frequency,
                synthdef=self.synthdef,
                target_node=self.target_node,
            )
        # if we're stopping a note ...
        elif isinstance(event, NoteOff):
            # bail if we already stopped this note:
            if event.note_number not in self.notes:
                return
            # pop the synth out of the dictionary and free it ...
            self.notes.pop(event.note_number).free()


@dataclass
class InputHandler:
    """
    Base class for input handlers.
    """

    @contextlib.contextmanager
    def listen(
        self, callback: Callable[[NoteOn | NoteOff], None]
    ) -> Generator[None, None, None]:
        # subclasses must implement this method!
        # 1) start the handler's listener
        # 2) yield to the with block body
        # 3) stop the handler's listener
        raise NotImplementedError


@dataclass
class MidiHandler(InputHandler):
    """
    A MIDI input handler.
    """

    port: int | str

    @contextlib.contextmanager
    def listen(
        self, callback: Callable[[NoteOn | NoteOff], None]
    ) -> Generator[None, None, None]:
        """
        Context manager for listening to MIDI input events.
        """
        self.midi_input = rtmidi.MidiIn()  # create the MIDI input
        # set the MIDI event callback to this class's __call__
        self.midi_input.set_callback(functools.partial(self.handle, callback))
        self.midi_input.open_port(self.port)  # open the port for listening
        print('Listening for MIDI keyboard events ...')  # let the user know
        yield  # yield to the with block body
        self.midi_input.close_port()  # close the port

    def handle(
        self,
        callback: Callable[[NoteOn | NoteOff], None],
        event: tuple[tuple[int, int, int], float],
        *args,
    ) -> None:
        """
        Handle a MIDI input event.
        """
        # the raw MIDI event is a 2-tuple of MIDI data and time delta, so
        # unpack it, keep the data and discard the time delta ...
        data, _ = event
        if data[0] == rtmidi.midiconstants.NOTE_ON + 1:  # if we received a note-on ...
            # grab the note number and velocity
            _, note_number, velocity = data
            # perform a "note on" event
            callback(NoteOn(note_number=note_number, velocity=velocity))
        elif (
            data[0] == rtmidi.midiconstants.NOTE_OFF + 1
        ):  # if we received a note-off ...
            # grab the note number
            _, note_number, _ = data
            # perform a "note off" event
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
        self, callback: Callable[[NoteOn | NoteOff], None]
    ) -> Generator[None, None, None]:
        """
        Context manager for listening to QWERTY input events.
        """
        # setup the QWERTY keybord listener
        self.listener = pynput.keyboard.Listener(
            on_press=functools.partial(self.on_press, callback),
            on_release=functools.partial(self.on_release, callback),
        )
        self.listener.start()  # start the listener
        print('Listening for QWERTY keyboard events ...')  # let the user know
        yield  # yield to the with block body
        self.listener.stop()  # stop the listener

    @staticmethod
    def qwerty_key_to_pitch_number(key: str) -> int | None:
        """
        Translate a QWERTY key event into a pitch number.
        """
        # dict lookups are faster, but this is soooo much shorter
        try:
            return "awsedftgyhujkolp;'".index(key)
        except ValueError:
            return None

    def on_press(
        self,
        callback: Callable[[NoteOn | NoteOff], None],
        key: pynput.keyboard.Key | pynput.keyboard.KeyCode | None,
    ) -> None:
        """
        Handle a QWERTY key press.
        """
        if not isinstance(key, pynput.keyboard.KeyCode):
            return  # bail if we didn't get a keycode object
        if key.char is None:
            return
        if key.char == 'z':  # decrement our octave setting
            self.octave = max(self.octave - 1, 0)
            return
        if key.char == 'x':  # increment our octave setting
            self.octave = min(self.octave + 1, 10)
            return
        if key in self.presses_to_note_numbers:
            return  # already pressed
        if (pitch := self.qwerty_key_to_pitch_number(key.char)) is None:
            return  # not a valid key, ignore it
        # calculate the note number from the pitch and octave
        note_number = pitch + self.octave * 12
        # QWERTY keyboards aren't pressure-sensitive, so let's create a random
        # velocity to simulate expressivity
        velocity = random.randint(32, 128)
        # stash the note number with the key for releasing later
        # so that changing the octave doesn't prevent releasing
        self.presses_to_note_numbers[key.char] = note_number
        # perform a "note on" event
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
            return  # bail if we didn't get a keycode object
        # bail if the key isn't currently held down
        if key.char not in self.presses_to_note_numbers:
            return
        # grab the note number out of the stash
        note_number = self.presses_to_note_numbers.pop(key.char)
        # perform a "note off" event
        callback(NoteOff(note_number=note_number))
