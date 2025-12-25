# 🐍🎶 Serpentone

This began life as a hack of some [Supriya example code](https://github.com/supriya-project/supriya/tree/v25.11b0/examples/keyboard_input),
and is slowly evolving into … something or other.
We’ve got a few synthdefs, like one that’s loosely inspired by the Mockingboard sound card from the 1980s.
We’ve got pluggable tuning systems with both equal temperament and just intonation.
We’ve got a [Textual](https://github.com/Textualize/textual) UI.

## Prerequisites

Install [Supercollider](https://github.com/supercollider/supercollider). Install [uv](https://github.com/astral-sh/uv) (or manage the project yourself).

## Usage

Just `uv sync` and then `uv run main.py --querty` for keyboard input or `uv run main.py --midi=0` for input from MIDI device #0 (or whatever).

With keyboard controls, `z` and `x` shift octave. `c`, `v`, and `b` select synthdefs. `n`, `m`, `,`, `.`, and `/` switch between tuning systems.

## Tuning Systems

Switch between tuning systems with these keys:
- `m`: Equal Temperament
- `n`: Just Intonation (key of A)
- `,`: Just Intonation (key of C)
- `.`: Pythagorean (key of C)
- `/`: Pythagorean (key of A)

### Equal Temperament

Standard 12-tone equal temperament where each semitone is equally spaced at a ratio of 2^(1/12). This is the modern standard tuning system used in most Western music.

### Just Intonation

The just intonation implementation uses 5-limit tuning with frequency ratios based on small whole numbers (using prime factors 2, 3, and 5). This creates harmonically pure intervals that sound more consonant than equal temperament, especially for major and minor thirds.

The ratios are applied relative to a configurable key. The system:
- Uses A4 (440 Hz) as the reference pitch
- Applies just intonation ratios to all 12 chromatic pitches
- Properly handles octave transposition across the entire MIDI range
- Maintains harmonic purity within the selected key

The specific ratios used are:
- Unison: 1/1
- Minor second: 16/15
- Major second: 9/8
- Minor third: 6/5
- Major third: 5/4 (a pure major third, ~14 cents flatter than equal temperament)
- Perfect fourth: 4/3
- Tritone: 45/32
- Perfect fifth: 3/2 (a pure perfect fifth)
- Minor sixth: 8/5
- Major sixth: 5/3
- Minor seventh: 9/5
- Major seventh: 15/8

### Pythagorean Tuning

Pythagorean tuning is built using only powers of 2 and 3 (octaves and perfect fifths). It was the primary tuning system in Western music during the Middle Ages and Renaissance. This tuning produces very pure perfect fifths and fourths, but major and minor thirds are less consonant than in just intonation.

The ratios are applied relative to a configurable key. Key characteristics:
- Perfect fifths (3/2) are identical to just intonation
- Major thirds (81/64) are sharper than equal temperament (~8 cents sharp)
- Major thirds are noticeably sharper than just intonation (~22 cents difference)
- Creates the characteristic “bright“ sound of medieval and early Renaissance music

The specific ratios used are:
- Unison: 1/1
- Minor second: 256/243 (Pythagorean limma)
- Major second: 9/8 (whole tone)
- Minor third: 32/27
- Major third: 81/64 (Pythagorean ditone, ~8 cents sharp)
- Perfect fourth: 4/3
- Tritone: 729/512 (augmented fourth)
- Perfect fifth: 3/2 (pure perfect fifth)
- Minor sixth: 128/81
- Major sixth: 27/16
- Minor seventh: 16/9
- Major seventh: 243/128
