"""
TUI components.
"""
from play import PolyphonyManager
from dataclasses import dataclass
from typing import Protocol

import rtmidi.midiconstants
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

import synths
from tuning import EqualTemperament, JustIntonation, Pythagorean


class QwertyState(Protocol):
    octave: int
    presses_to_note_numbers: dict


class AppDispatch:
    """Dispatches input events the Serpentone app, handling thread-safety."""

    def __init__(self, app: 'SerpentoneApp'):
        self.app = app

    def handle_midi_event(self, func: int, note_number: int, velocity: int) -> None:
        """Handle a raw MIDI event (thread-safe)."""
        self.app.post_message(SerpentoneApp.HandleMidiEvent(func, note_number, velocity))

    def handle_key_press(self, key_char: str, input_handler: QwertyState) -> None:
        """Handle a QWERTY key press (thread-safe)."""
        self.app.post_message(SerpentoneApp.HandleKeyPress(key_char, input_handler))

    def handle_key_release(self, key_char: str, input_handler: QwertyState) -> None:
        """Handle a QWERTY key release (thread-safe)."""
        self.app.post_message(SerpentoneApp.HandleKeyRelease(key_char, input_handler))


class StatusPanel(Widget):
    """Panel for displaying status messages."""

    messages = reactive[list[str]](list, recompose=True)

    def compose(self) -> ComposeResult:
        yield Static('\n'.join(self.messages))


class SynthPanel(Widget):
    """Panel for displaying the currently selected synth."""

    synth_name = reactive("", recompose=True)

    def compose(self) -> ComposeResult:
        yield Static(f'Current Synth: {self.synth_name}')


class SynthListPanel(Widget):
    """Panel for displaying the list of available synths with current selection highlighted."""

    available_synths = reactive[list[str]](list, recompose=True)
    current_synth = reactive("", recompose=False)

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="synth-scroll"):
            if not self.available_synths:
                yield Static('No synths available')
            else:
                for synth_name in self.available_synths:
                    # Add initial highlighting class if this is the current synth.
                    classes = 'selected-synth' if synth_name == self.current_synth else ''
                    yield Static(f'  {synth_name}', id=f'synth-{synth_name}', classes=classes)

    def watch_available_synths(self, available_synths: list[str]) -> None:
        """When synths list changes, ensure current selection is highlighted."""
        # After recomposition, apply highlighting to current synth.
        if self.current_synth:
            self.call_after_refresh(self._scroll_to_current)

    def watch_current_synth(self, old_synth: str, current_synth: str) -> None:
        """Update highlighting when selection changes."""
        # If this is the initial setting (old_synth is empty), scroll to it.
        if not old_synth and current_synth:
            self.call_after_refresh(self._scroll_to_current)
            return

        # Remove highlight from old selection.
        if old_synth:
            try:
                old_widget = self.query_one(f'#synth-{old_synth}', Static)
                old_widget.remove_class('selected-synth')
            except Exception:
                pass  # Old synth widget might not exist.

        # Add highlight to new selection and scroll to it.
        if current_synth:
            try:
                new_widget = self.query_one(f'#synth-{current_synth}', Static)
                new_widget.add_class('selected-synth')
                new_widget.scroll_visible()
            except Exception:
                pass  # New synth widget might not exist yet.

    def _scroll_to_current(self) -> None:
        """Scroll to make the current synth visible."""
        if self.current_synth:
            try:
                selected_widget = self.query_one(f'#synth-{self.current_synth}', Static)
                selected_widget.add_class('selected-synth')
                selected_widget.scroll_visible()
            except Exception:
                pass  # Widget might not exist yet.


class TuningPanel(Widget):
    """Panel for displaying the currently selected tuning."""

    tuning_name = reactive("", recompose=True)

    def compose(self) -> ComposeResult:
        yield Static(f'Current Tuning: {self.tuning_name}')


class OctavePanel(Widget):
    """Panel for displaying the current octave."""

    octave = reactive(0, recompose=True)

    def compose(self) -> ComposeResult:
        yield Static(f'Octave: {self.octave}')


class NotePanel(Widget):
    """Panel for displaying currently playing notes."""

    active_notes = reactive[dict](dict, recompose=True)

    def compose(self) -> ComposeResult:
        """Called when active_notes changes."""
        if not self.active_notes:
            content = 'No notes playing'
        else:
            lines = ['Currently playing notes:']
            for note_num, info in sorted(self.active_notes.items()):
                lines.append(
                    f"  Note {note_num}: {info['frequency']:.2f} Hz "
                    f"(velocity: {info['velocity']})"
                )
            if len(self.active_notes.values()) == 2:
                vals = list(self.active_notes.values())
                first = vals[0]['frequency']
                second = vals[1]['frequency']
                if first < second:
                    first, second = second, first
                lines.append(f'ratio {first/second}')
            content = '\n'.join(lines)
        yield Static(content)


class SerpentoneApp(App):
    """Main Textual application for Serpentone."""

    @dataclass
    class HandleMidiEvent(Message):
        """Message to handle a raw MIDI input event."""
        func: int
        note_number: int
        velocity: int

    @dataclass
    class HandleKeyPress(Message):
        """Message to handle a QWERTY key press."""
        key_char: str
        input_handler: QwertyState

    @dataclass
    class HandleKeyRelease(Message):
        """Message to handle a QWERTY key release."""
        key_char: str
        input_handler: QwertyState

    CSS = """
    Screen {
        layout: vertical;
    }

    #synth-tuning-row {
        layout: horizontal;
        height: 5;
    }

    #synth-container {
        width: 1fr;
        border: solid #ff6b9d;
        padding: 1;
    }

    #tuning-container {
        width: 1fr;
        border: solid #ffa07a;
        padding: 1;
    }

    #octave-container {
        width: 1fr;
        border: solid #ffb86c;
        padding: 1;
    }

    #status-container {
        height: 1fr;
        border: solid #50fa7b;
        padding: 1;
    }

    #bottom-row {
        layout: horizontal;
        height: 1fr;
    }

    #note-container {
        width: 1fr;
        border: solid #8be9fd;
        padding: 1;
    }

    #synth-list-container {
        width: 1fr;
        border: solid #bd93f9;
        padding: 1;
    }

    SynthPanel {
        width: 100%;
        height: 100%;
    }

    TuningPanel {
        width: 100%;
        height: 100%;
    }

    OctavePanel {
        width: 100%;
        height: 100%;
    }

    StatusPanel {
        width: 100%;
        height: 100%;
    }

    NotePanel {
        width: 100%;
        height: 100%;
    }

    SynthListPanel {
        width: 100%;
        height: 100%;
    }

    .selected-synth {
        background: $accent;
    }
    """

    current_synth = reactive[str]('')
    current_tuning = reactive[str]('')
    current_octave = reactive[int](0)
    status_messages = reactive[list[str]](list)
    notes = reactive[dict](dict)
    available_synths = reactive[list[str]](list)
    synth_index = reactive[int](0)

    def __init__(self, init, polyphony_manager: PolyphonyManager, available_synths: list[str]):
        super().__init__()
        self.init = init
        self.polyphony_manager = polyphony_manager
        self.available_synths = available_synths
        self.current_synth = polyphony_manager.theory.synthdef.name or '(none)'
        # Find the index of the current synth.
        try:
            self.synth_index = available_synths.index(self.current_synth)
        except ValueError:
            self.synth_index = 0

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Container(id="synth-tuning-row"):
            with Container(id="synth-container"):
                yield SynthPanel().data_bind(synth_name=type(self).current_synth)
            with Container(id="tuning-container"):
                yield TuningPanel().data_bind(tuning_name=type(self).current_tuning)
            with Container(id="octave-container"):
                yield OctavePanel().data_bind(octave=type(self).current_octave)
        with Container(id="status-container"):
            yield StatusPanel().data_bind(messages=type(self).status_messages)
        with Container(id="bottom-row"):
            with Container(id="note-container"):
                yield NotePanel().data_bind(active_notes=type(self).notes)
            with Container(id="synth-list-container"):
                yield SynthListPanel().data_bind(
                    available_synths=type(self).available_synths,
                    current_synth=type(self).current_synth
                )

    def on_mount(self) -> None:
        """Handle app mount."""
        self.title = "Serpentone"
        self.init()

    def add_status(self, message: str) -> None:
        """Add a status message."""
        self.status_messages.append(message)
        # Keep only the last 20 messages.
        if len(self.status_messages) > 20:
            self.status_messages[:] = self.status_messages[-20:]
        self.mutate_reactive(SerpentoneApp.status_messages)

    def on_serpentone_app_handle_midi_event(self, message: HandleMidiEvent) -> None:
        """Handle raw MIDI input event."""
        if self.polyphony_manager is None:
            return

        # Handle NOTE_ON events
        if rtmidi.midiconstants.NOTE_ON <= message.func < rtmidi.midiconstants.NOTE_ON + 16:
            if message.velocity == 0:
                # Velocity 0 means note off
                self.polyphony_manager.note_off(message.note_number)
                if message.note_number in self.notes:
                    del self.notes[message.note_number]
                self.mutate_reactive(SerpentoneApp.notes)
            else:
                # Note on
                self.polyphony_manager.note_on(message.note_number, message.velocity)
                frequency = self.polyphony_manager.theory.tuning.midi_note_number_to_frequency(message.note_number)
                self.notes[message.note_number] = {
                    'frequency': frequency,
                    'velocity': message.velocity
                }
                self.mutate_reactive(SerpentoneApp.notes)
        # Handle NOTE_OFF events
        elif rtmidi.midiconstants.NOTE_OFF <= message.func < rtmidi.midiconstants.NOTE_OFF + 16:
            self.polyphony_manager.note_off(message.note_number)
            if message.note_number in self.notes:
                del self.notes[message.note_number]
            self.mutate_reactive(SerpentoneApp.notes)

    def on_serpentone_app_handle_key_press(self, message: HandleKeyPress) -> None:
        """Handle QWERTY key press."""

        if self.polyphony_manager is None:
            return

        # Handle octave changes
        if message.key_char == 'z':
            message.input_handler.octave = max(message.input_handler.octave - 1, 0)
            self.current_octave = message.input_handler.octave
            return
        if message.key_char == 'x':
            message.input_handler.octave = min(message.input_handler.octave + 1, 10)
            self.current_octave = message.input_handler.octave
            return

        # Handle synth changes (cycling through available synths)
        if message.key_char == 'c':
            # Cycle backward
            self.synth_index = (self.synth_index - 1) % len(self.available_synths)
            synth_name = self.available_synths[self.synth_index]
            self.polyphony_manager.theory.synthdef = getattr(synths, synth_name)
            self.current_synth = synth_name
            return
        if message.key_char == 'v':
            # Cycle forward
            self.synth_index = (self.synth_index + 1) % len(self.available_synths)
            synth_name = self.available_synths[self.synth_index]
            self.polyphony_manager.theory.synthdef = getattr(synths, synth_name)
            self.current_synth = synth_name
            return

        # Handle tuning changes
        if message.key_char == 'n':
            self.polyphony_manager.theory.tuning = JustIntonation(key='A')
            self.current_tuning = 'JustA'
        if message.key_char == 'm':
            self.polyphony_manager.theory.tuning = EqualTemperament()
            self.current_tuning = 'EqualTemperament'
        if message.key_char == ',':
            self.polyphony_manager.theory.tuning = JustIntonation(key='C')
            self.current_tuning = 'JustC'
        if message.key_char == '.':
            self.polyphony_manager.theory.tuning = Pythagorean(key='C')
            self.current_tuning = 'PythC'
        if message.key_char == '/':
            self.polyphony_manager.theory.tuning = Pythagorean(key='A')
            self.current_tuning = 'PythA'

        # Handle note playing
        if message.key_char in message.input_handler.presses_to_note_numbers:
            return  # Already pressed.

        # Translate QWERTY key to pitch number
        try:
            pitch = "awsedftgyhujkolp;'".index(message.key_char)
        except ValueError:
            return  # Not a valid key, ignore it.

        # Calculate the note number from the pitch and octave.
        note_number = pitch + message.input_handler.octave * 12
        velocity = 64
        # Stash the note number with the key for releasing later.
        message.input_handler.presses_to_note_numbers[message.key_char] = note_number

        # Start the note
        self.polyphony_manager.note_on(note_number, velocity)
        frequency = self.polyphony_manager.theory.tuning.midi_note_number_to_frequency(note_number)
        self.notes[note_number] = {
            'frequency': frequency,
            'velocity': velocity
        }
        self.mutate_reactive(SerpentoneApp.notes)

    def on_serpentone_app_handle_key_release(self, message: HandleKeyRelease) -> None:
        """Handle QWERTY key release."""
        if self.polyphony_manager is None:
            return

        # Bail if the key isn't currently held down.
        if message.key_char not in message.input_handler.presses_to_note_numbers:
            return

        # Grab the note number out of the stash.
        note_number = message.input_handler.presses_to_note_numbers.pop(message.key_char)

        # Stop the note
        self.polyphony_manager.note_off(note_number)
        if note_number in self.notes:
            del self.notes[note_number]
        self.mutate_reactive(SerpentoneApp.notes)