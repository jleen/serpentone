# 🐍🎶 Serpentone

This began life as a hack of some [Supriya example code](https://github.com/supriya-project/supriya/tree/v25.11b0/examples/keyboard_input),
and is slowly evolving into … something or other.
We’ve got a few synthdefs, like one that’s loosely inspired by the Mockingboard sound card from the 1980s.
We’ve got some stubs for pluggable tuning systems.
We’ve got a [Textual](https://github.com/Textualize/textual) UI.

## Prerequisites

Install [Supercollider](https://github.com/supercollider/supercollider). Install [uv](https://github.com/astral-sh/uv) (or manage the project yourself).

## Usage

Just `uv sync` and then `uv run main.py --querty` for keyboard input or `uv run main.py --midi=0` for input from MIDI device #0 (or whatever).

With keyboard controls, `z` and `x` shift octave. `c`, `v`, and `b` select synthdefs. `n` and `m` switch between tuning systems.
