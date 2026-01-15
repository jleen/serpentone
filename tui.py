"""
TUI components.
"""
from textual.events import Key
from play import PolyphonyManager
from dataclasses import dataclass
from typing import Protocol

import rtmidi.midiconstants
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ListView, ListItem, Label, Static

import synths
from tuning import EqualTemperament, JustIntonation, Pythagorean


class QwertyState(Protocol):
    octave: int
    presses_to_note_numbers: dict


class AppDispatch:
    """Dispatches input events to the Serpentone app, handling thread-safety."""

    def __init__(self, app: SerpentoneApp):
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
    """Panel for displaying the list of available synths with current selection highlighted.

    ListView is the single source of truth for the current selection.
    """

    available_synths = reactive[list[str]](list)
    app: SerpentoneApp

    @staticmethod
    def make_synth_list_item(synth_name: str) -> ListItem:
        return ListItem(Label(synth_name), id=f'synth-{synth_name}')
    
    def compose(self) -> ComposeResult:
        self.synth_list = ListView(id="synth-list")
        with self.synth_list:
            for synth_name in sorted(self.available_synths):
                yield self.make_synth_list_item(synth_name)
    
    async def watch_available_synths(self, old, new):
        """
        When a new synth list comes in, transform the ListView items into the new list,
        performing a minimal series of edits so as to mostly not mess up the integrity of the UI state.
        """
        old = sorted(old)
        new = sorted(new)

        removes = []
        inserts = []
        
        i, j = 0, 0
        # Track the current index in "old after removals"
        insert_index = 0
        
        while i < len(old) or j < len(new):
            if i >= len(old):
                # Only new items left - insert at end
                inserts.append((insert_index, new[j]))
                insert_index += 1
                j += 1
            elif j >= len(new):
                # Only old items left - remove them
                removes.append(i)
                i += 1
                # insert_index unchanged (we're removing, not keeping)
            elif old[i] == new[j]:
                # Items match - this stays in the list
                i += 1
                j += 1
                insert_index += 1
            elif old[i] < new[j]:
                # Item removed from old
                removes.append(i)
                i += 1
                # insert_index unchanged
            else:  # old[i] > new[j]
                # Item added in new
                inserts.append((insert_index, new[j]))
                insert_index += 1
                j += 1
        
        # Remember the currently highlighted synth name before modifications.
        current_highlight = None
        if self.synth_list.highlighted_child:
            item_id = self.synth_list.highlighted_child.id
            if item_id and item_id.startswith('synth-'):
                current_highlight = item_id[6:]  # Remove 'synth-' prefix.

        # Clear the index before modifications to prevent ListView from auto-adjusting during removals.
        self.synth_list.index = None

        await self.synth_list.remove_items(removes)
        for (idx, item) in inserts:
            await self.synth_list.insert(idx, [self.make_synth_list_item(item)])

        # Restore highlight to the same synth if it still exists.
        if current_highlight and current_highlight in new:
            target_index = new.index(current_highlight)
        else:
            # Highlighted synth was removed, find closest valid index.
            # Since we cleared the index, we can't rely on self.synth_list.index here.
            # Use the index of the removed item if it was in the middle of the list.
            if removes:
                target_index = min(removes[0], len(new) - 1)
            else:
                target_index = 0

        # Restore the index to the target position.
        self.synth_list.index = target_index

        # Sync the synth panel with whatever is now highlighted.
        if self.synth_list.highlighted_child:
            self.app.activate_synth(self.synth_list.highlighted_child)


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

    ListView {
        height: 100%;
    }
    """

    current_tuning = reactive[str]('')
    current_octave = reactive[int](0)
    status_messages = reactive[list[str]](list)
    notes = reactive[dict](dict)
    available_synths = reactive[list[str]](list)

    def __init__(self, init, polyphony_manager: PolyphonyManager, available_synths: list[str]):
        super().__init__()
        self.init = init
        self.polyphony_manager = polyphony_manager
        self.available_synths = available_synths

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Container(id="synth-tuning-row"):
            with Container(id="synth-container"):
                yield SynthPanel()
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
                    available_synths=type(self).available_synths
                )

    def on_mount(self) -> None:
        """Handle app mount."""
        self.title = "Serpentone"
        # Initialize SynthPanel with the current synth from the polyphony manager.
        synth_panel = self.query_one(SynthPanel)
        synth_panel.synth_name = self.polyphony_manager.theory.synthdef.name or '(none)'
        self.init()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle synth selection from ListView."""
        if not event.item:
            return

        # Get the synth name from the ListItem's id.
        self.activate_synth(event.item)

    def activate_synth(self, item: ListItem):
        item_id = item.id
        if item_id and item_id.startswith('synth-'):
            synth_name = item_id[6:]  # Remove 'synth-' prefix.
            # Update the actual synth being used.
            self.polyphony_manager.theory.synthdef = getattr(synths, synth_name)
            # Update the SynthPanel display.
            synth_panel = self.query_one(SynthPanel)
            synth_panel.synth_name = synth_name

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

    def on_key(self, event: Key):
        """Handle configuration keypresses through the normal Textual path (not pynput)."""
        # Handle synth changes (cycling through available synths).
        if event.character == 'c':
            synth_list = self.query_one('#synth-list', ListView)
            synth_list.action_cursor_up()
            return
        if event.character == 'v':
            synth_list = self.query_one('#synth-list', ListView)
            synth_list.action_cursor_down()
            return

        # Handle tuning changes.
        if event.character == 'n':
            self.polyphony_manager.theory.tuning = JustIntonation(key='A')
            self.current_tuning = 'JustA'
        if event.character == 'm':
            self.polyphony_manager.theory.tuning = EqualTemperament()
            self.current_tuning = 'EqualTemperament'
        if event.character == ',':
            self.polyphony_manager.theory.tuning = JustIntonation(key='C')
            self.current_tuning = 'JustC'
        if event.character == '.':
            self.polyphony_manager.theory.tuning = Pythagorean(key='C')
            self.current_tuning = 'PythC'
        if event.character == '/':
            self.polyphony_manager.theory.tuning = Pythagorean(key='A')
            self.current_tuning = 'PythA'


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