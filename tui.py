"""
TUI components.
"""
from textual.message import Message
from textual.widget import Widget
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Static


class StateManager:
    """Manages state updates for the Serpentone app, handling thread-safety."""

    def __init__(self, app: 'SerpentoneApp'):
        self.app = app

    def add_note(self, note_number: int, frequency: float, velocity: int) -> None:
        """Add a playing note (thread-safe)."""
        self.app.post_message(SerpentoneApp.AddNote(note_number, frequency, velocity))

    def remove_note(self, note_number: int) -> None:
        """Remove a playing note (thread-safe)."""
        self.app.post_message(SerpentoneApp.RemoveNote(note_number))

    def update_synth(self, synth_name: str) -> None:
        """Update the currently selected synth (thread-safe)."""
        self.app.post_message(SerpentoneApp.UpdateSynth(synth_name))

    def update_tuning(self, tuning_name: str) -> None:
        """Update the currently selected tuning (thread-safe)."""
        self.app.post_message(SerpentoneApp.UpdateTuning(tuning_name))

    def update_octave(self, octave: int) -> None:
        """Update the current octave (thread-safe)."""
        self.app.post_message(SerpentoneApp.UpdateOctave(octave))


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

    class AddNote(Message):
        """Message to add a playing note."""
        def __init__(self, note_number: int, frequency: float, velocity: int):
            super().__init__()
            self.note_number = note_number
            self.frequency = frequency
            self.velocity = velocity

    class RemoveNote(Message):
        """Message to remove a playing note."""
        def __init__(self, note_number: int):
            super().__init__()
            self.note_number = note_number

    class UpdateSynth(Message):
        """Message to update the currently selected synth."""
        def __init__(self, synth_name: str):
            super().__init__()
            self.synth_name = synth_name

    class UpdateTuning(Message):
        """Message to update the currently selected tuning."""
        def __init__(self, tuning_name: str):
            super().__init__()
            self.tuning_name = tuning_name

    class UpdateOctave(Message):
        """Message to update the current octave."""
        def __init__(self, octave: int):
            super().__init__()
            self.octave = octave

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
        border: solid yellow;
        padding: 1;
    }

    #tuning-container {
        width: 1fr;
        border: solid yellow;
        padding: 1;
    }

    #octave-container {
        width: 1fr;
        border: solid yellow;
        padding: 1;
    }

    #status-container {
        height: 1fr;
        border: solid green;
        padding: 1;
    }

    #note-container {
        height: 1fr;
        border: solid blue;
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
    """

    current_synth = reactive[str]('')
    current_tuning = reactive[str]('')
    current_octave = reactive[int](0)
    status_messages = reactive[list[str]](list)
    notes = reactive[dict](dict)

    def __init__(self, init):
        super().__init__()
        self.init = init

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
        with Container(id="note-container"):
            yield NotePanel().data_bind(active_notes=type(self).notes)

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

    def on_serpentone_app_add_note(self, message: AddNote) -> None:
        """Handle AddNote message."""
        self.notes[message.note_number] = {
            'frequency': message.frequency,
            'velocity': message.velocity
        }
        self.mutate_reactive(SerpentoneApp.notes)

    def on_serpentone_app_remove_note(self, message: RemoveNote) -> None:
        """Handle RemoveNote message."""
        if message.note_number in self.notes:
            del self.notes[message.note_number]
        self.mutate_reactive(SerpentoneApp.notes)

    def on_serpentone_app_update_synth(self, message: UpdateSynth) -> None:
        """Handle UpdateSynth message."""
        self.current_synth = message.synth_name

    def on_serpentone_app_update_tuning(self, message: UpdateTuning) -> None:
        """Handle UpdateTuning message."""
        self.current_tuning = message.tuning_name

    def on_serpentone_app_update_octave(self, message: UpdateOctave) -> None:
        """Handle UpdateOctave message."""
        self.current_octave = message.octave