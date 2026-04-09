"""
Classes for managing polyphonic synth events.

Incorporates code from https://github.com/supriya-project/supriya/blob/v25.9b1/examples/keyboard_input/__init__.py
Copyright (c) 2014-2024 Joséphine Wolf Oberholtzer, MIT License.
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
    # Music theory state (tuning and such).
    theory: MusicTheory
    # A dictionary of currently sounding MIDI note numbers to synths.
    notes: dict[int, supriya.Synth] = field(default_factory=dict)
    # A dictionary of pedal-sustained MIDI note numbers to synths.
    sustained_notes: dict[int, supriya.Synth] = field(default_factory=dict)
    # Target node to add relative to.
    target_node: supriya.Node | None = None
    # Add action to use.
    add_action: supriya.AddAction = supriya.AddAction.ADD_TO_HEAD
    # The current state of the damper pedal.
    sustain: bool = False

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
        # Remove the note from the sustained list so we don’t get multiple copies.
        if note_number in self.sustained_notes:
            self.sustained_notes.pop(note_number).free()

    def note_off(self, note_number: int) -> None:
        """
        Stop a note.
        """
        # Bail if we already stopped this note.
        if note_number not in self.notes:
            return
        # Pop the synth out of the dictionary and free it
        # (or shunt it to the sustained list if the pedal is down).
        if self.sustain:
            self.sustained_notes[note_number] = self.notes.pop(note_number)
        else:
            self.notes.pop(note_number).free()

    def sustain_on(self) -> None:
        self.sustain = True

    def sustain_off(self) -> None:
        self.sustain = False
        for note_number in list(self.sustained_notes.keys()):
            self.sustained_notes.pop(note_number).free()
        


@dataclass
class MusicTheory:
    tuning: Tuning
    synthdef: supriya.SynthDef