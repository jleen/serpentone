import contextlib
import functools
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator

import pynput
import rtmidi
import rtmidi.midiutil

from tui import AppDispatch


def list_midi_ports():
    """
    Print out available MIDI input ports.
    """
    rtmidi.midiutil.list_input_ports()


@dataclass
class InputHandler(ABC):
    """
    Base class for input handlers.
    """

    @contextlib.contextmanager
    @abstractmethod
    def listen(
        self, app_dispatch: AppDispatch
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
        self, app_dispatch: AppDispatch
    ) -> Generator[None, None, None]:
        """
        Context manager for listening to MIDI input events.
        """
        self.midi_input = rtmidi.MidiIn()  # type:ignore
        self.midi_input.set_callback(functools.partial(self.handle, app_dispatch))
        self.midi_input.open_port(self.port)
        print('Listening for MIDI keyboard events ...')
        yield
        self.midi_input.close_port()

    def handle(
        self,
        app_dispatch: AppDispatch,
        event: tuple[tuple[int, int, int], float],
        *args,
    ) -> None:
        """
        Handle a MIDI input event.
        """
        # The raw MIDI event is a 2-tuple of MIDI data and time delta.
        # Unpack it, keep the data and discard the time delta.
        [func, note_number, velocity], _ = event
        app_dispatch.handle_midi_event(func, note_number, velocity)


@dataclass
class QwertyHandler(InputHandler):
    """
    A QWERTY input handler.
    """

    octave: int = 5
    presses_to_note_numbers: dict[str, int] = field(default_factory=dict)

    @contextlib.contextmanager
    def listen(
        self, app_dispatch: AppDispatch
    ) -> Generator[None, None, None]:
        """
        Context manager for listening to QWERTY input events.
        """
        self.listener = pynput.keyboard.Listener(
            on_press=functools.partial(self.on_press, app_dispatch),
            on_release=functools.partial(self.on_release, app_dispatch),
        )
        self.listener.start()
        print('Listening for QWERTY keyboard events ...')
        yield
        self.listener.stop()

    def on_press(
        self,
        app_dispatch: AppDispatch,
        key: pynput.keyboard.Key | pynput.keyboard.KeyCode | None,
    ) -> None:
        """
        Handle a QWERTY key press.
        """
        if not isinstance(key, pynput.keyboard.KeyCode):
            return
        if key.char is None:
            return
        app_dispatch.handle_key_press(key.char, self)

    def on_release(
        self,
        app_dispatch: AppDispatch,
        key: pynput.keyboard.Key | pynput.keyboard.KeyCode | None,
    ) -> None:
        """
        Handle a QWERTY key release.
        """
        if not isinstance(key, pynput.keyboard.KeyCode):
            return  # Bail if we didn't get a keycode object.
        if key.char is None:
            return
        app_dispatch.handle_key_release(key.char, self)
