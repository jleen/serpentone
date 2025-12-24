"""
TUI components.
"""
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


class StatusPanel(Static):
    """Panel for displaying status messages."""

    def __init__(self, **kwargs):
        super().__init__("Initializing...", **kwargs)
        self.messages: list[str] = []

    class AddMessage(Message):
        """Message to add a status update."""

        def __init__(self, message: str) -> None:
            self.message = message
            super().__init__()

    def on_status_panel_add_message(self, event: AddMessage) -> None:
        """Handle incoming status message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {event.message}"
        self.messages.append(formatted_message)
        # Keep only the last 20 messages.
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]
        # Update display
        self.update("\n".join(self.messages))


class SynthPanel(Static):
    """Panel for displaying the currently selected synth."""

    synth_name = reactive("(none)")

    class UpdateSynth(Message):
        """Message to update the current synth."""

        def __init__(self, synth_name: str) -> None:
            self.synth_name = synth_name
            super().__init__()

    def watch_synth_name(self, synth_name: str) -> None:
        """React to synth name changes."""
        self.update(f"Current Synth: {synth_name}")

    def on_synth_panel_update_synth(self, event: UpdateSynth) -> None:
        """Handle synth update message."""
        self.synth_name = event.synth_name


class NotePanel(Static):
    """Panel for displaying currently playing notes."""

    def __init__(self, **kwargs):
        super().__init__("No notes playing", **kwargs)
        self.active_notes: dict[int, dict[str, float | int]] = {}

    class AddNote(Message):
        """Message to add a playing note."""

        def __init__(self, note_number: int, frequency: float, velocity: int) -> None:
            self.note_number = note_number
            self.frequency = frequency
            self.velocity = velocity
            super().__init__()

    class RemoveNote(Message):
        """Message to remove a playing note."""

        def __init__(self, note_number: int) -> None:
            self.note_number = note_number
            super().__init__()

    def _update_display(self) -> None:
        """Update the panel display."""
        if not self.active_notes:
            self.update("No notes playing")
        else:
            count = len(self.active_notes)
            plural = "s" if count != 1 else ""
            lines = [f"Playing {count} note{plural}:"]
            for note_num, info in sorted(self.active_notes.items()):
                # Create a simple velocity bar
                velocity = int(info['velocity'])
                velocity_bar = "█" * (velocity // 16)
                lines.append(
                    f"  Note {note_num:3d}: {info['frequency']:7.2f} Hz │ {velocity_bar}"
                )
            self.update("\n".join(lines))

    def on_note_panel_add_note(self, event: AddNote) -> None:
        """Handle add note message."""
        self.active_notes[event.note_number] = {
            'frequency': event.frequency,
            'velocity': event.velocity
        }
        self._update_display()

    def on_note_panel_remove_note(self, event: RemoveNote) -> None:
        """Handle remove note message."""
        if event.note_number in self.active_notes:
            del self.active_notes[event.note_number]
        self._update_display()


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
        self.init = init

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Container(id="synth-container"):
            yield SynthPanel()
        with Container(id="status-container"):
            yield StatusPanel()
        with Container(id="note-container"):
            yield NotePanel()

    def on_mount(self) -> None:
        """Handle app mount."""
        self.title = "Serpentone"
        self.init()