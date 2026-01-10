# CLAUDE.md - Serpentone Project Guide

## Quick Start Context

**What is this?** Musical synthesizer app - play notes via QWERTY keyboard or MIDI controller using SuperCollider audio engine with pluggable tuning systems.

**Tech stack:** Python 3.14 + Supriya (SuperCollider interface) + Textual (TUI) + pynput/rtmidi (input)

**Entry point:** [main.py](main.py) - Run with `python main.py --qwerty` or `python main.py --midi=0`

## File Map (What Lives Where)

| File | Responsibility | Key Classes/Functions |
|------|---------------|----------------------|
| [main.py](main.py) | Entry point, orchestration, lifecycle, hot reload | `main()`, `run()`, `watch_synths()` |
| [input.py](input.py) | Input handling (QWERTY/MIDI) | `InputHandler`, `QwertyHandler`, `MidiHandler` |
| [play.py](play.py) | Polyphony & music theory | `PolyphonyManager`, `MusicTheory` |
| [tui.py](tui.py) | Terminal UI (Textual) | `SerpentoneApp`, panels, message handlers |
| [tuning.py](tuning.py) | Tuning systems (ET, Just, Pythagorean) | `TuningSystem`, `EqualTemperament`, etc. |
| [synths.py](synths.py) | Synthdef definitions (hot-reloadable) | `default`, `simple_sine`, `mockingboard` |
| [test_tuning.py](test_tuning.py) | Comprehensive tuning tests | Test functions for all tuning systems |

## Architecture Patterns You'll See

1. **Message Passing (Erlang-inspired):** Input handlers → `AppDispatch` → Textual messages → UI event handlers
   - Thread-safe communication between input threads and UI thread
   - See [tui.py:25-39](tui.py#L25-L39) for message dataclasses

2. **Strategy Pattern:** Pluggable tuning systems via `TuningSystem` ABC
   - [tuning.py](tuning.py) defines interface + 3 implementations
   - Swappable at runtime via keyboard shortcuts (m/n/,/.//)

3. **Manager Pattern:** `PolyphonyManager` tracks active synths
   - Maps MIDI note numbers → Synth instances
   - Handles note_on/note_off lifecycle

4. **Reactive UI:** Textual reactive properties with manual mutation
   - `reactive` properties auto-update bound UI components
   - Must call `.mutate_reactive()` after in-place modifications

5. **Context Managers:** Input handlers use `with` protocol for cleanup
   - See [input.py:10](input.py#L10) for `InputHandler` ABC

## Data Flow for Playing a Note

```
QWERTY key press (pynput)
  ↓
QwertyHandler.on_press() [input.py:94]
  ↓
AppDispatch.handle_key_press() [tui.py:18]
  ↓
Textual message posted to event loop
  ↓
SerpentoneApp.on_serpentone_app_handle_key_press() [tui.py:144]
  ↓
Key → MIDI note number conversion [tui.py:149-159]
  ↓
PolyphonyManager.note_on() [play.py:24]
  ↓
TuningSystem.midi_to_frequency() [tuning.py]
  ↓
Create Synth on SuperCollider server
  ↓
Update UI reactive state (notes_panel)
```

## Important Implementation Details

### Dual Control Support
- **Recent change:** Both QWERTY and MIDI can be active simultaneously (commit 3241265)
- Input handlers run in separate threads, message-passing keeps them decoupled

### Hot Reloading
- [synths.py](synths.py) watched using **watchfiles** (Rust-based, instant notifications)
- Simple async worker: `app.run_worker(watch_file(path, callback))` via Textual
- Uses OS-native file system events (inotify on Linux, ReadDirectoryChangesW on Windows, FSEvents on macOS)
- On change: `importlib.reload()` → re-register synthdefs → update `MusicTheory.synthdef`
- Handles atomic saves correctly (editors that write temp files then rename)
- Enables live coding workflow without restarting app

### Tuning System Implementation
- **Base:** `TuningSystem` ABC with `midi_to_frequency(int) → float` method
- **Equal Temperament:** Delegates to Supriya's built-in conversion (A4=440Hz)
- **Just/Pythagorean:**
  - Inherit from `RatioBasedTuning` which handles key transposition
  - Define ratios for 12 chromatic scale degrees
  - See [tuning.py:36-92](tuning.py#L36-L92) for ratio definitions
- **Testing:** [test_tuning.py](test_tuning.py) has comprehensive validation (reference pitches, intervals, octaves, cents)

### QWERTY Key Mapping
- Keys `awsedftgyhujkolp;'` map to chromatic scale starting from current octave
- `z`/`x` shift octave down/up
- Octave state stored in `SerpentoneApp.octave` reactive property
- See [tui.py:149-159](tui.py#L149-L159) for mapping logic

### Thread Safety
- Input handlers run in background threads (daemon threads)
- **Never** call UI methods directly from input threads
- Always use `AppDispatch` to post Textual messages
- Textual's event loop ensures single-threaded UI updates

### Lifecycle Management
- Boot callback [main.py:107]: Load synthdefs, start watcher/listeners
- Quit callback [main.py:117]: Free synths, 0.5s fade delay, cleanup
- SuperCollider server must be running before creating synths

## Common Tasks

### Adding a New Tuning System
1. Create class inheriting from `TuningSystem` in [tuning.py](tuning.py)
2. Implement `midi_to_frequency(note_number: int) -> float`
3. Add keyboard shortcut in [tui.py:186-199](tui.py#L186-L199)
4. Add tests to [test_tuning.py](test_tuning.py)

### Adding a New Synthdef
1. Add `@synthdef()` function to [synths.py](synths.py)
2. Must have `amplitude` and `frequency` parameters
3. Use envelope with `gate` parameter and `done_action=2`
4. Add keyboard shortcut in [tui.py:178-184](tui.py#L178-L184)
5. Hot reload will pick it up automatically

### Debugging Audio Issues
- Check SuperCollider server is running: `server.is_running`
- Verify synthdefs loaded: happens in boot callback [main.py:113]
- Check polyphony manager: `manager.note_number_to_synth` dict
- Use status panel messages for debugging (add `self.post_status()` calls)

### Modifying Input Handling
- QWERTY: [input.py:94-122](input.py#L94-L122) - `QwertyHandler` class
- MIDI: [input.py:44-75](input.py#L44-L75) - `MidiHandler` class
- Must use `app_dispatch` for thread-safe communication
- Remember to handle both press/on and release/off events

## Gotchas and Quirks

1. **Python 3.14 Required:** Uses bleeding-edge features, won't run on older versions
2. **Supriya Type Stubs:** Custom stubs in `supriya-stubs/` because `ty` can’t handle UGen types automatically
3. **Manual Reactive Mutation:** After modifying reactive dicts/lists in-place, must call `.mutate_reactive(Model.property_name)`
4. **SuperCollider External Dependency:** Must have `scsynth` installed and accessible
5. **Polling File Watcher:** Uses simple mtime polling instead of OS events (good enough for this use case)

## Recent Refactoring History

The codebase underwent major architectural improvements:
- **Dual control** (3241265): Simultaneous QWERTY + MIDI input
- **Detangle app init** (deed0dc): Simplified initialization
- **Dataclass messages** (19e7661): Message passing using dataclasses
- **Clean up cyclic dependencies** (2bda077): Eliminated circular imports
- **Separate responsibilities** (5aa0cea): Split into focused modules

## Testing

Run tests: `pytest test_tuning.py`

Test coverage:
- Comprehensive tuning system validation (all 3 systems)
- Reference pitch verification (A4 = 440Hz)
- Interval accuracy (thirds, fifths)
- Octave doubling
- Cents deviation from equal temperament

**Note:** No tests for UI, input handlers, or polyphony manager yet (could be added)

## Dependencies Cheat Sheet

- **Supriya:** SuperCollider interface (`Server`, `SynthDef`, `@synthdef`)
- **Textual:** TUI framework (`App`, `reactive`, `DockView`, `Static`)
- **pynput:** Keyboard input (`keyboard.Listener`)
- **python-rtmidi:** MIDI device access (`rtmidi.MidiIn`)
- **mido:** MIDI message parsing (`mido.Message`)
- **watchfiles:** File system monitoring (Rust-based, async, cross-platform)

## Configuration

- **pyproject.toml:** Minimal config, Python 3.14+ requirement
- **uv.lock:** Dependency lockfile (managed by uv package manager)
- **.devcontainer:** VS Code dev container with Python 3.14 + ALSA libs

## Things to Keep in Mind When Working on This

- **Preserve hot reload:** Don't break the file watcher or reload mechanism
- **Thread safety:** Never skip message passing from input threads
- **Type hints:** Keep the codebase fully typed
- **Music theory accuracy:** Tuning systems must be mathematically correct (use cents tests)
- **Resource cleanup:** Always free synths properly to avoid audio glitches
- **Reactive updates:** Remember to mutate reactive properties when changing state

## Style Guidelines

- Prefer formatting comments as sentences, starting with a capital and ending with a period. Do this even for short comments that are not grammatical sentences.

## Code Quality Checks (ALWAYS RUN THESE)

**Before considering any code change complete:**

1. **Linting with Ruff:** `uv run ruff check .`
   - Catches unused imports, variables, and common Python mistakes
   - Auto-fix most issues with: `uv run ruff check --fix .`
   - Fast and comprehensive linter

2. **Type Checking with ty:** `uv run ty check`
   - Validates type annotations across the entire codebase
   - Catches type mismatches and potential runtime errors
   - Extremely fast type checker

3. **Syntax Check (fallback):** `uv run python -m py_compile <modified_files.py>`
   - Quick sanity check for syntax errors
   - Useful when ruff/ty aren't available

**Workflow:**
1. Make your code changes
2. Run `uv run ruff check .` and fix any errors
3. Run `uv run ty check` and fix any type errors
4. Commit only after both pass

**Why this matters:** Clean, well-typed code prevents bugs and makes collaboration easier. Running these tools takes seconds but catches issues that could take hours to debug later.
