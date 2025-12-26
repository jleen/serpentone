"""Pytest test suite for tuning systems."""

import pytest
import math
from tuning import JustIntonation, EqualTemperament, Pythagorean
import supriya.conversions


def cents_difference(freq1: float, freq2: float) -> float:
    """Calculate the difference between two frequencies in cents."""
    if freq1 == 0 or freq2 == 0:
        return 0
    return 1200 * math.log2(freq1 / freq2)


class TestEqualTemperament:
    """Test Equal Temperament tuning."""

    @pytest.fixture
    def tuning(self):
        return EqualTemperament()

    def test_matches_supriya_conversion(self, tuning):
        """Equal temperament should exactly match Supriya's conversion."""
        test_notes = [60, 61, 62, 64, 65, 67, 69, 71, 72]
        for midi_note in test_notes:
            expected = supriya.conversions.midi_note_number_to_frequency(midi_note)
            actual = tuning.midi_note_number_to_frequency(midi_note)
            assert actual == pytest.approx(expected), f"MIDI {midi_note} mismatch"

    def test_a4_is_440hz(self, tuning):
        """A4 (MIDI 69) should be exactly 440 Hz."""
        assert tuning.midi_note_number_to_frequency(69) == pytest.approx(440.0)

    def test_octave_doubling(self, tuning):
        """Going up an octave should double the frequency."""
        for midi_note in [60, 62, 64, 69]:
            freq1 = tuning.midi_note_number_to_frequency(midi_note)
            freq2 = tuning.midi_note_number_to_frequency(midi_note + 12)
            assert freq2 == pytest.approx(freq1 * 2.0)


class TestJustIntonation:
    """Test Just Intonation tuning."""

    def test_tonic_matches_equal_temperament_key_a(self):
        """The tonic of the key should match equal temperament."""
        tuning = JustIntonation(key='A')
        expected = supriya.conversions.midi_note_number_to_frequency(69)  # A4
        actual = tuning.midi_note_number_to_frequency(69)
        assert actual == pytest.approx(expected)

    def test_tonic_matches_equal_temperament_key_c(self):
        """The tonic of the key should match equal temperament."""
        tuning = JustIntonation(key='C')
        expected = supriya.conversions.midi_note_number_to_frequency(60)  # C4
        actual = tuning.midi_note_number_to_frequency(60)
        assert actual == pytest.approx(expected)

    def test_frequencies_are_close_to_equal_temperament(self):
        """All frequencies should be within ±50 cents of equal temperament."""
        tuning = JustIntonation(key='C')
        test_notes = [60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72]

        for midi_note in test_notes:
            expected = supriya.conversions.midi_note_number_to_frequency(midi_note)
            actual = tuning.midi_note_number_to_frequency(midi_note)
            cents = abs(cents_difference(actual, expected))
            assert cents < 50, f"MIDI {midi_note}: {cents:.1f} cents difference (too large)"

    def test_major_third_is_flat_in_c_major(self):
        """The major third (E) in C major should be flatter than equal temperament."""
        tuning = JustIntonation(key='C')
        expected = supriya.conversions.midi_note_number_to_frequency(64)  # E4
        actual = tuning.midi_note_number_to_frequency(64)
        cents = cents_difference(actual, expected)
        # Just intonation major third (5/4) is about 13.7 cents flat
        assert -15 < cents < -12, f"Major third should be ~14 cents flat, got {cents:.1f}"

    def test_perfect_fifth_is_close(self):
        """The perfect fifth should be very close to equal temperament."""
        tuning = JustIntonation(key='C')
        expected = supriya.conversions.midi_note_number_to_frequency(67)  # G4
        actual = tuning.midi_note_number_to_frequency(67)
        cents = abs(cents_difference(actual, expected))
        # Just intonation perfect fifth (3/2) is about 2 cents sharp
        assert cents < 3, f"Perfect fifth should be within 3 cents, got {cents:.1f}"

    def test_octave_doubling(self):
        """Going up an octave should double the frequency."""
        tuning = JustIntonation(key='C')
        for midi_note in [60, 62, 64, 67]:
            freq1 = tuning.midi_note_number_to_frequency(midi_note)
            freq2 = tuning.midi_note_number_to_frequency(midi_note + 12)
            assert freq2 == pytest.approx(freq1 * 2.0)

    def test_different_keys_produce_different_frequencies(self):
        """Different keys should produce different frequency adjustments."""
        tuning_c = JustIntonation(key='C')
        tuning_a = JustIntonation(key='A')

        # E4 (MIDI 64) is a major third in C but a perfect fifth in A
        freq_in_c = tuning_c.midi_note_number_to_frequency(64)
        freq_in_a = tuning_a.midi_note_number_to_frequency(64)

        # They should be different
        assert freq_in_c != pytest.approx(freq_in_a)


class TestPythagorean:
    """Test Pythagorean tuning."""

    def test_tonic_matches_equal_temperament_key_a(self):
        """The tonic of the key should match equal temperament."""
        tuning = Pythagorean(key='A')
        expected = supriya.conversions.midi_note_number_to_frequency(69)  # A4
        actual = tuning.midi_note_number_to_frequency(69)
        assert actual == pytest.approx(expected)

    def test_tonic_matches_equal_temperament_key_c(self):
        """The tonic of the key should match equal temperament."""
        tuning = Pythagorean(key='C')
        expected = supriya.conversions.midi_note_number_to_frequency(60)  # C4
        actual = tuning.midi_note_number_to_frequency(60)
        assert actual == pytest.approx(expected)

    def test_frequencies_are_close_to_equal_temperament(self):
        """All frequencies should be within ±50 cents of equal temperament."""
        tuning = Pythagorean(key='C')
        test_notes = [60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72]

        for midi_note in test_notes:
            expected = supriya.conversions.midi_note_number_to_frequency(midi_note)
            actual = tuning.midi_note_number_to_frequency(midi_note)
            cents = abs(cents_difference(actual, expected))
            assert cents < 50, f"MIDI {midi_note}: {cents:.1f} cents difference (too large)"

    def test_major_third_is_sharp_in_c_major(self):
        """The major third (E) in C major should be sharper than equal temperament."""
        tuning = Pythagorean(key='C')
        expected = supriya.conversions.midi_note_number_to_frequency(64)  # E4
        actual = tuning.midi_note_number_to_frequency(64)
        cents = cents_difference(actual, expected)
        # Pythagorean major third (81/64) is about 8 cents sharp
        assert 7 < cents < 9, f"Major third should be ~8 cents sharp, got {cents:.1f}"

    def test_perfect_fifth_is_close(self):
        """The perfect fifth should be very close to equal temperament."""
        tuning = Pythagorean(key='C')
        expected = supriya.conversions.midi_note_number_to_frequency(67)  # G4
        actual = tuning.midi_note_number_to_frequency(67)
        cents = abs(cents_difference(actual, expected))
        # Pythagorean perfect fifth (3/2) is about 2 cents sharp
        assert cents < 3, f"Perfect fifth should be within 3 cents, got {cents:.1f}"

    def test_octave_doubling(self):
        """Going up an octave should double the frequency."""
        tuning = Pythagorean(key='C')
        for midi_note in [60, 62, 64, 67]:
            freq1 = tuning.midi_note_number_to_frequency(midi_note)
            freq2 = tuning.midi_note_number_to_frequency(midi_note + 12)
            assert freq2 == pytest.approx(freq1 * 2.0)


class TestTuningComparison:
    """Compare different tuning systems."""

    def test_major_third_comparison(self):
        """Compare the major third (E in C major) across all tuning systems."""
        et = EqualTemperament()
        ji = JustIntonation(key='C')
        pyth = Pythagorean(key='C')

        et_freq = et.midi_note_number_to_frequency(64)  # E4
        ji_freq = ji.midi_note_number_to_frequency(64)
        pyth_freq = pyth.midi_note_number_to_frequency(64)

        # Just intonation should be flatter, Pythagorean should be sharper
        assert ji_freq < et_freq < pyth_freq

    def test_perfect_fifth_similar_across_systems(self):
        """The perfect fifth should be similar across JI and Pythagorean."""
        ji = JustIntonation(key='C')
        pyth = Pythagorean(key='C')

        ji_freq = ji.midi_note_number_to_frequency(67)  # G4
        pyth_freq = pyth.midi_note_number_to_frequency(67)

        # Both use 3/2 ratio for perfect fifth
        assert ji_freq == pytest.approx(pyth_freq)
