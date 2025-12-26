from abc import ABC, abstractmethod
from dataclasses import dataclass

import supriya
import supriya.conversions


@dataclass
class Tuning(ABC):
    @abstractmethod
    def midi_note_number_to_frequency(self, note_number: float) -> float: pass


class RatioBasedTuning(Tuning):
    # Map note names to chromatic scale degrees
    NOTE_NAMES = {
        'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
    }

    key: str
    RATIOS: list[float]

    def midi_note_number_to_frequency(self, note_number: float) -> float:
        """
        Helper method to calculate frequency using ratio-based tuning systems.

        Args:
            note_number: MIDI note number
            key: Musical key (e.g., 'C', 'A')
            ratios: List of 12 ratios for chromatic scale degrees

        Returns:
            Frequency in Hz
        """
        # MIDI note 69 is A4 at 440 Hz (our reference pitch)
        reference_midi = 69  # A4
        reference_freq = 440.0

        # Get the chromatic pitch class (0-11) of the input note
        # MIDI 60 = C, 61 = C#, 62 = D, etc.
        pitch_class = int(note_number) % 12

        # Get the key's chromatic degree (where the key's tonic is in the chromatic scale)
        key_degree = self.NOTE_NAMES.get(self.key.upper(), 9)  # Default to A

        # Calculate the scale degree relative to the key (0-11)
        # 0 = tonic, 1 = minor second, 2 = major second, etc.
        scale_degree = (pitch_class - key_degree) % 12

        # Get the ratio for this scale degree
        ratio = self.RATIOS[scale_degree]

        # Calculate the base frequency for this note using equal temperament
        # This gives us the "expected" frequency for this MIDI note
        semitones_from_reference = note_number - reference_midi
        base_freq = reference_freq * (2 ** (semitones_from_reference / 12))

        # Calculate what the ET ratio would be for this scale degree
        et_ratio = 2 ** (scale_degree / 12)

        # Adjust the frequency: replace ET ratio with the custom ratio
        frequency = base_freq * (ratio / et_ratio)

        return frequency


@dataclass
class EqualTemperament(Tuning):
    def midi_note_number_to_frequency(self, note_number: float) -> float:
        return supriya.conversions.midi_note_number_to_frequency(note_number)


@dataclass
class JustIntonation(RatioBasedTuning):
    key: str

    # Just intonation ratios for the 12-tone chromatic scale
    # Using 5-limit just intonation ratios
    RATIOS = [
        1.0,        # Unison (C)
        16/15,      # Minor second (C#/Db)
        9/8,        # Major second (D)
        6/5,        # Minor third (Eb)
        5/4,        # Major third (E)
        4/3,        # Perfect fourth (F)
        45/32,      # Tritone (F#/Gb)
        3/2,        # Perfect fifth (G)
        8/5,        # Minor sixth (Ab)
        5/3,        # Major sixth (A)
        9/5,        # Minor seventh (Bb)
        15/8,       # Major seventh (B)
    ]


@dataclass
class Pythagorean(RatioBasedTuning):
    key: str

    # Pythagorean tuning ratios for the 12-tone chromatic scale
    # Built using only powers of 2 and 3 (perfect fifths and octaves)
    RATIOS = [
        1.0,        # Unison (C)
        256/243,    # Minor second (C#/Db) - Pythagorean limma
        9/8,        # Major second (D) - whole tone
        32/27,      # Minor third (Eb)
        81/64,      # Major third (E) - Pythagorean ditone
        4/3,        # Perfect fourth (F)
        729/512,    # Tritone (F#/Gb) - augmented fourth
        3/2,        # Perfect fifth (G)
        128/81,     # Minor sixth (Ab)
        27/16,      # Major sixth (A)
        16/9,       # Minor seventh (Bb)
        243/128,    # Major seventh (B)
    ]
