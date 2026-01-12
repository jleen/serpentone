import argparse
import importlib
import time
from pathlib import Path

import supriya
from watchfiles import awatch

import synths
from input import InputHandler, MidiHandler, QwertyHandler, list_midi_ports
from play import MusicTheory, PolyphonyManager
from tui import SerpentoneApp, AppDispatch
from tuning import EqualTemperament


def get_available_synths() -> list[str]:
    """
    Get the canonical list of available synth names by introspecting the synths module.
    Returns all SynthDef objects found in the module.
    """
    synth_names = []
    for name in dir(synths):
        # Skip private/magic attributes.
        if name.startswith('_'):
            continue
        attr = getattr(synths, name)
        # Check if it's a SynthDef instance.
        if isinstance(attr, supriya.SynthDef):
            synth_names.append(name)
    return synth_names


def run(input_handlers: list[InputHandler], synth) -> None:
    """
    Run the script with TUI.
    """
    # Get the canonical list of available synths.
    available_synths = get_available_synths()

    def load_synthdefs() -> None:
        """Load all synthdefs from the synths module into SuperCollider."""
        current_synths = get_available_synths()
        synthdef_objects = [getattr(synths, name) for name in current_synths]
        server.add_synthdefs(*synthdef_objects)
        server.sync()  # Wait for the synthdef to load before moving on.

    def on_boot(*args) -> None:  # Run this during server.boot().
        load_synthdefs()
        app.add_status('Server booted successfully')

    def on_synths_changed() -> None:
        """Callback when synths.py file changes - hot reload the module."""
        try:
            # Reload the synths module.
            importlib.reload(synths)
            # Get the updated list of available synths.
            new_available_synths = get_available_synths()
            # Reload synthdefs into SuperCollider.
            load_synthdefs()
            # Update the current synthdef reference if it was reloaded.
            current_synth_name = polyphony.theory.synthdef.name
            if current_synth_name and hasattr(synths, current_synth_name):
                polyphony.theory.synthdef = getattr(synths, current_synth_name)
            else:
                # Current synth no longer exists, fall back to "default".
                polyphony.theory.synthdef = synths.default
                current_synth_name = 'default'
                app.current_synth = 'default'
            # Update the TUI's list of available synths.
            app.available_synths = new_available_synths
            # Update the synth index to match the current synth.
            try:
                app.synth_index = new_available_synths.index(current_synth_name)
            except ValueError:
                app.synth_index = 0
            app.add_status('Synths reloaded from synths.py')
        except Exception as e:
            app.add_status(f'Error reloading synths: {e}')

    def on_quitting(*args) -> None:
        """
        Callback that occurs *before* Supercollider quits via server.quit.
        """
        polyphony.free_all()  # Free all the synths.
        time.sleep(0.5)  # Wait for them to fade out before moving on.
        print('Supercollider shutting down')
        for listener in listeners:
            listener.__exit__(None, None, None)
        print('Input listener stopped')

    async def watch_synths() -> None:
        """Watch synths.py for changes and reload when modified."""
        synths_path = Path(__file__).parent / 'synths.py'
        async for _changes in awatch(synths_path):
            on_synths_changed()

    def start_server_and_listener() -> None:
        server.register_lifecycle_callback('BOOTED', on_boot)
        server.register_lifecycle_callback('QUITTING', on_quitting)
        server.boot()
        app.add_status('Server online. Press C-q to exit.')
        # Start watching synths.py for changes in a worker.
        app.run_worker(watch_synths(), exclusive=True)
        app.add_status('Watching synths.py for changes...')
        for input_handler in input_handlers:
            input_type = type(input_handler).__name__.replace('Handler', '')
            app.add_status(f'Listening for {input_type} keyboard events...')
        for listener in listeners:
            listener.__enter__()

    # First we wire up some objects. Nothing exciting happens yet.
    server = supriya.Server()
    theory = MusicTheory(tuning=EqualTemperament(), synthdef=synth)
    polyphony = PolyphonyManager(
        server=server,
        theory=theory,
    )
    app = SerpentoneApp(start_server_and_listener, polyphony, available_synths)
    app_dispatch = AppDispatch(app)
    app.current_tuning = 'EqualTemperament'
    # Set initial octave if using QwertyHandler
    app.current_octave = 5
    app.polyphony_manager = polyphony
    listeners = [input_handler.listen(app_dispatch) for input_handler in input_handlers]

    # Now we run the Textual app, which starts the event pump.
    # The app has an on_mount callback that will start Supercollider and the input listener.
    app.run()

    # Okay, at this point the Textual event pump has been shut down, so we’re back to synchronous execution
    # on the main thread. Supercollider and the input listener are still running.
    # So now we directly stop Supercollider, which in turn calls back to on_quitting,
    # which will shut down the listener.
    server.quit()
    print('That’s all, folks!')


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """
    Parse CLI arguments.
    """
    parser = argparse.ArgumentParser(
        description='Play notes via your QWERTY or MIDI keyboards'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--list-midi-inputs', action='store_true', help='list available MIDI inputs'
    )
    group.add_argument(
        '--midi', help='play via MIDI keyboard', type=int, metavar='PORT_NUMBER'
    )
    group.add_argument(
        '--qwerty', action='store_true', help='play via QWERTY keyboard'
    )
    parser.add_argument(
        '--synth', type=str, metavar='SYNTH_NAME', help='name of synthdef to play',
        default='simple_sine'
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> None:
    """
    The example entry-point function.
    """
    parsed_args = parse_args(args)
    synth = getattr(synths, parsed_args.synth)
    if parsed_args.list_midi_inputs:
        list_midi_ports()
    elif parsed_args.midi is not None:
        run([MidiHandler(port=parsed_args.midi), QwertyHandler()], synth)
    elif parsed_args.qwerty:
        run([QwertyHandler()], synth)


if __name__ == "__main__":
    main()