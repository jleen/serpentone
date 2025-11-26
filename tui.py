"""
TUI components.
"""
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Static


class StatusPanel(Static):
    """Panel for displaying status messages."""

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self.messages = []

    def add_message(self, message: str) -> None:
        """Add a status message to the panel."""
        self.messages.append(message)
        # Keep only the last 20 messages.
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]
        self.update("\n".join(self.messages))


class NotePanel(Static):
    """Panel for displaying currently playing notes."""

    def __init__(self, **kwargs):
        super().__init__("No notes playing", **kwargs)
        self.active_notes = {}

    def add_note(self, note_number: int, frequency: float, velocity: int) -> None:
        """Add a note to the display."""
        self.active_notes[note_number] = {
            'frequency': frequency,
            'velocity': velocity
        }
        self._update_display()

    def remove_note(self, note_number: int) -> None:
        """Remove a note from the display."""
        if note_number in self.active_notes:
            del self.active_notes[note_number]
        self._update_display()

    def _update_display(self) -> None:
        """Update the panel display."""
        if not self.active_notes:
            self.update("No notes playing")
        else:
            lines = ["Currently playing notes:"]
            for note_num, info in sorted(self.active_notes.items()):
                lines.append(
                    f"  Note {note_num}: {info['frequency']:.2f} Hz "
                    f"(velocity: {info['velocity']})"
                )
            self.update("\n".join(lines))


class SerpentoneApp(App):
    """Main Textual application for Serpentone."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #status-container {
        height: 60%;
        border: solid green;
        padding: 1;
    }

    #note-container {
        height: 40%;
        border: solid blue;
        padding: 1;
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

    def __init__(self, init):
        super().__init__()
        self.status_panel = None
        self.note_panel = None
        self.init = init

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Container(id="status-container"):
            self.status_panel = StatusPanel()
            yield self.status_panel
        with Container(id="note-container"):
            self.note_panel = NotePanel()
            yield self.note_panel

    def on_mount(self) -> None:
        """Handle app mount."""
        self.title = "Serpentone"
        self.init()

    def add_status(self, message: str) -> None:
        """Add a status message."""
        if self.status_panel:
            self.status_panel.add_message(message)

    def add_note(self, note_number: int, frequency: float, velocity: int) -> None:
        """Add a playing note."""
        if self.note_panel:
            self.note_panel.add_note(note_number, frequency, velocity)

    def remove_note(self, note_number: int) -> None:
        """Remove a playing note."""
        if self.note_panel:
            self.note_panel.remove_note(note_number)