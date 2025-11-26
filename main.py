import argparse
import threading
import time

from concurrent.futures import Future
import supriya

from play import (
    list_midi_ports,
    InputHandler,
    MidiHandler,
    NoteOff,
    NoteOn,
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
        server.add_synthdefs(polyphony.synthdef)  # Add the polyphony's synthdef.
        server.sync()  # Wait for the synthdef to load before moving on.
        app.call_from_thread(app.add_status, 'Server booted successfully')

    def on_quitting(*args) -> None:
        """
        Callback that occurs *before* Supercollider quits via server.quit.
        """
        polyphony.free_all()  # Free all the synths.
        time.sleep(0.5)  # Wait for them to fade out before moving on.
        print('Supercollider shutting down')
        exit_future.set_result(True)

    def note_callback(event: NoteOn | NoteOff, frequency: float) -> None:
        # Update the TUI with note information.
        if isinstance(event, NoteOn):
            app.call_from_thread(app.add_note, event.note_number, frequency, event.velocity)
        elif isinstance(event, NoteOff):
            app.call_from_thread(app.remove_note, event.note_number)

    def input_callback(event: NoteOn | NoteOff) -> None:
        # Play the event via polyphony directly.
        polyphony.perform(event)

    def run_server() -> None:
        server.register_lifecycle_callback('BOOTED', on_boot)
        server.register_lifecycle_callback('QUITTING', on_quitting)
        server.boot()
        app.add_status('Server online. Press Ctrl-C to exit.')
        input_type = type(input_handler).__name__.replace('Handler', '')
        app.add_status(f'Listening for {input_type} keyboard events...')
        with input_handler.listen(callback=input_callback):
            exit_future.result()  # Wait for exit.
        print('Input listener stopped')

    def spawn_server_thread() -> None:
        # The input handler needs to run in a separate thread,
        # so that it doesn’t block the Textual event pump.
        # Additionally, server.boot needs to not be on the Textual thread,
        # for reasons that are not clear to me.
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

    server = supriya.Server()
    polyphony = PolyphonyManager(server=server, synthdef=synth, note_callback=note_callback)
    exit_future = Future()

    app = SerpentoneApp(spawn_server_thread)
    # app.run starts an async event pump on the main thread, and mounts the Textual app.
    # The app itself, on mount, is configured to call back to spawn_server_thread to initialize
    # Supercollider and the input listener thread.
    #
    # This listener thread is actually spawned on yet another thread which is internal to rtmidi,
    # but our Python thread hands out and babysits the listener, and waits for a Future which is 
    # how the Textual app (in the main thread) tells it when it’s time to shut down.
    #
    # Meanwhile, the main thread will run the actual app logic, and will block here until the app quits.
    #
    # I am fairly confident that there are no race conditions at this point,
    # because the initialization thread is not spawned until the app is mounted,
    # and the input listener is not started until Supercollider is booted.
    app.run()
    # Okay, at this point the Textual event pump has been shut down, so we’re back to synchronous execution
    # on the main thread. Supercollider, the listener, and the babysitter are still running.
    #
    # server.quit directly stops Supercollider, which in turn calls back to on_quitting,
    # which will resolve the Future and thereby tell the listener babysitter thread to shut down the listener.
    #
    # Everything gets shut down cleanly, but the order seems a bit nondeterministic.
    # The Future is resolved before Supercollider is allowed to quit, which is good.
    # And server.quit blocks until the on_quitting callback has completed, which is also good.
    #
    # But the Future is being awaited (and the listener will be torn down) on a different thread,
    # so there is potentially a race condition whereby the listener might briefly linger
    # after Supercollider has been shut down.  The most obvious symptom would be a listener shutdown display
    # that appears after the Supercollider shutdown display (or not at all, if the process exits without waiting).
    #
    # This seems fairly benign, yet annoying.
    # If we really cared, I suppose we could use another future to wait here until the babysitter is done.
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