import argparse
import functools
import time

import supriya

from play import (
    EqualTemperament,
    MusicTheory,
    list_midi_ports,
    InputHandler,
    MidiHandler,
    PolyphonyManager,
    QwertyHandler,
)
import synths
from tui import SerpentoneApp


def run(input_handler: InputHandler, synth) -> None:
    """
    Run the script with TUI.
    """
    def on_boot(*args) -> None:  # Run this during server.boot().
        server.add_synthdefs(synths.simple_sine, synths.mockingboard, synths.default)
        server.sync()  # Wait for the synthdef to load before moving on.
        app.add_status('Server booted successfully')

    def on_quitting(*args) -> None:
        """
        Callback that occurs *before* Supercollider quits via server.quit.
        """
        polyphony.free_all()  # Free all the synths.
        time.sleep(0.5)  # Wait for them to fade out before moving on.
        print('Supercollider shutting down')
        listener.__exit__(None, None, None)
        print('Input listener stopped')

    def start_server_and_listener() -> None:
        server.register_lifecycle_callback('BOOTED', on_boot)
        server.register_lifecycle_callback('QUITTING', on_quitting)
        server.boot()
        app.add_status('Server online. Press C-q to exit.')
        input_type = type(input_handler).__name__.replace('Handler', '')
        app.add_status(f'Listening for {input_type} keyboard events...')
        listener.__enter__()

    # First we wire up some objects. Nothing exciting happens yet.
    server = supriya.Server()
    theory = MusicTheory(tuning=EqualTemperament(), synthdef=synth)
    app = SerpentoneApp(start_server_and_listener)
    polyphony = PolyphonyManager(
        server=server,
        theory=theory,
        note_on_callback=functools.partial(app.call_from_thread, app.add_note),
        note_off_callback=functools.partial(app.call_from_thread, app.remove_note),
        synth_change_callback=functools.partial(app.call_from_thread, app.update_synth)
    )
    listener = input_handler.listen(polyphony)

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
        run(MidiHandler(port=parsed_args.midi), synth)
    elif parsed_args.qwerty:
        run(QwertyHandler(), synth)


if __name__ == "__main__":
    main()