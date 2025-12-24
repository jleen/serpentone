"""
TUI components.
"""
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


# Application-level messages (posted to the app, not specific widgets)
class StatusMessage(Message):
    """Message to add a status update."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__()


class NoteOn(Message):
    """Message when a note starts playing."""

    def __init__(self, note_number: int, frequency: float, velocity: int) -> None:
        self.note_number = note_number
        self.frequency = frequency
        self.velocity = velocity
        super().__init__()


class NoteOff(Message):
    """Message when a note stops playing."""

    def __init__(self, note_number: int) -> None:
        self.note_number = note_number
        super().__init__()


class SynthChanged(Message):
    """Message when the synth changes."""

    def __init__(self, synth_name: str) -> None:
        self.synth_name = synth_name
        super().__init__()


class StatusPanel(Static):
    """Panel for displaying status messages."""

    def __init__(self, **kwargs):
        super().__init__("Initializing...", **kwargs)
        self.messages: list[str] = []

    def on_status_message(self, event: StatusMessage) -> None:
        """Handle status message from the app."""
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

    def watch_synth_name(self, synth_name: str) -> None:
        """React to synth name changes."""
        self.update(f"Current Synth: {synth_name}")

    def on_synth_changed(self, event: SynthChanged) -> None:
        """Handle synth change message from the app."""
        self.synth_name = event.synth_name


class NotePanel(Static):
    """Panel for displaying currently playing notes."""

    def __init__(self, **kwargs):
        super().__init__("No notes playing", **kwargs)
        self.active_notes: dict[int, dict[str, float | int]] = {}

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

    def on_note_on(self, event: NoteOn) -> None:
        """Handle note on message from the app."""
        self.active_notes[event.note_number] = {
            'frequency': event.frequency,
            'velocity': event.velocity
        }
        self._update_display()

    def on_note_off(self, event: NoteOff) -> None:
        """Handle note off message from the app."""
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

    # Message handlers that re-broadcast to all widgets
    def on_status_message(self, message: StatusMessage) -> None:
        """Broadcast status message to widgets."""
        for widget in self.query(StatusPanel):
            widget.post_message(message)

    def on_note_on(self, message: NoteOn) -> None:
        """Broadcast note on message to widgets."""
        for widget in self.query(NotePanel):
            widget.post_message(message)

    def on_note_off(self, message: NoteOff) -> None:
        """Broadcast note off message to widgets."""
        for widget in self.query(NotePanel):
            widget.post_message(message)

    def on_synth_changed(self, message: SynthChanged) -> None:
        """Broadcast synth changed message to widgets."""
        for widget in self.query(SynthPanel):
            widget.post_message(message)

    # Public API for posting app-level messages (thread-safe)
    def add_status(self, message: str) -> None:
        """Add a status message (thread-safe)."""
        self.post_message(StatusMessage(message))

    def add_note(self, note_number: int, frequency: float, velocity: int) -> None:
        """Add a playing note (thread-safe)."""
        self.post_message(NoteOn(note_number, frequency, velocity))

    def remove_note(self, note_number: int) -> None:
        """Remove a playing note (thread-safe)."""
        self.post_message(NoteOff(note_number))

    def update_synth(self, synth_name: str) -> None:
        """Update the current synth (thread-safe)."""
        self.post_message(SynthChanged(synth_name))