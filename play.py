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

from dataclasses import dataclass, field

import supriya
import supriya.conversions

from tuning import Tuning


@dataclass
class PolyphonyManager:
    """
    A polyphony manager.

    Translates note on/off events into actions
    against a :py:class:`~supriya.contexts.core.Context`.
    """

    # The server to act on.
    server: supriya.Context
    theory: MusicTheory
    # A dictionary of MIDI note numbers to synths.
    notes: dict[int, supriya.Synth] = field(default_factory=dict)
    # Target node to add relative to.
    target_node: supriya.Node | None = None
    # Add action to use.
    add_action: supriya.AddAction = supriya.AddAction.ADD_TO_HEAD

    def free_all(self) -> None:
        """
        Free all currently playing :py:class:`~supriya.contexts.entities.Synth`
        instances.
        """
        with self.server.at():
            for synth in self.notes.values():
                synth.free()

    def note_on(self, note_number: int, velocity: int) -> None:
        """
        Start a note.
        """
        # Bail if we already started this note.
        if note_number in self.notes:
            return
        frequency = self.theory.tuning.midi_note_number_to_frequency(note_number)
        amplitude = supriya.conversions.midi_velocity_to_amplitude(velocity)
        # Create a synth and store a reference by MIDI note number in the dictionary.
        self.notes[note_number] = self.server.add_synth(
            add_action=self.add_action,
            amplitude=amplitude,
            frequency=frequency,
            synthdef=self.theory.synthdef,
            target_node=self.target_node,
        )

    def note_off(self, note_number: int) -> None:
        """
        Stop a note.
        """
        # Bail if we already stopped this note.
        if note_number not in self.notes:
            return
        # Pop the synth out of the dictionary and free it.
        self.notes.pop(note_number).free()


@dataclass
class MusicTheory:
    tuning: Tuning
    synthdef: supriya.SynthDef