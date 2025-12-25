"""
TUI components.
"""
from textual.widget import Widget
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Static


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
            content = '\n'.join(lines)
        yield Static(content)


class SerpentoneApp(App):
    """Main Textual application for Serpentone."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #synth-container {
        height: 5;
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
    status_messages = reactive[list[str]](list)
    notes = reactive[dict](dict)

    def __init__(self, init):
        super().__init__()
        self.init = init

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Container(id="synth-container"):
            yield SynthPanel().data_bind(synth_name=type(self).current_synth)
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

    def add_note(self, note_number: int, frequency: float, velocity: int) -> None:
        """Add a playing note."""
        self.notes[note_number] = {
            'frequency': frequency,
            'velocity': velocity
        }
        self.mutate_reactive(SerpentoneApp.notes)

    def remove_note(self, note_number: int) -> None:
        """Remove a playing note."""
        if note_number in self.notes:
            del self.notes[note_number]
        self.mutate_reactive(SerpentoneApp.notes)

    def update_synth(self, synth_name: str) -> None:
        """Update the currently selected synth."""
        self.current_synth = synth_name