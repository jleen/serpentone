"""
TUI components.
"""
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Static


class StatusPanel(Static):
    """Panel for displaying status messages."""

    messages = reactive[list[str]](list)

    def add_message(self, message: str) -> None:
        """Add a status message to the panel."""
        self.messages.append(message)
        # Keep only the last 20 messages.
        if len(self.messages) > 20:
            self.messages[:] = self.messages[-20:]
        self.mutate_reactive(StatusPanel.messages)

    def watch_messages(self, messages: list[str]) -> None:
        """Called when messages changes."""
        self.update("\n".join(messages))


class SynthPanel(Static):
    """Panel for displaying the currently selected synth."""

    synth_name = reactive("")

    def update_synth(self, synth_name: str) -> None:
        """Update the displayed synth name."""
        self.synth_name = synth_name

    def watch_synth_name(self, synth_name: str) -> None:
        """Called when synth_name changes."""
        display_text = f"Current Synth: {synth_name}"
        self.update(display_text)


class NotePanel(Static):
    """Panel for displaying currently playing notes."""

    active_notes = reactive[dict](dict)

    def add_note(self, note_number: int, frequency: float, velocity: int) -> None:
        """Add a note to the display."""
        self.active_notes[note_number] = {
            'frequency': frequency,
            'velocity': velocity
        }
        self.mutate_reactive(NotePanel.active_notes)

    def remove_note(self, note_number: int) -> None:
        """Remove a note from the display."""
        if note_number in self.active_notes:
            del self.active_notes[note_number]
        self.mutate_reactive(NotePanel.active_notes)

    def watch_active_notes(self, active_notes: dict) -> None:
        """Called when active_notes changes."""
        if not active_notes:
            self.update("No notes playing")
        else:
            lines = ["Currently playing notes:"]
            for note_num, info in sorted(active_notes.items()):
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

    def __init__(self, init):
        super().__init__()
        self.synth_panel = None
        self.status_panel = None
        self.note_panel = None
        self.init = init

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Container(id="synth-container"):
            self.synth_panel = SynthPanel()
            yield self.synth_panel
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

    def update_synth(self, synth_name: str) -> None:
        """Update the currently selected synth."""
        if self.synth_panel:
            self.synth_panel.update_synth(synth_name)