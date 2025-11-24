import argparse
import concurrent.futures
import signal
import time

import rtmidi
import supriya

from play import (
    InputHandler,
    MidiHandler,
    NoteOff,
    NoteOn,
    PolyphonyManager,
    QwertyHandler,
    simple_sine,
)


def run(input_handler: InputHandler) -> None:
    """
    Run the script.
    """

    def on_boot(*args) -> None:  # run this during server.boot()
        server.add_synthdefs(polyphony.synthdef)  # add the polyphony's synthdef
        server.sync()  # wait for the synthdef to load before moving on

    def on_quitting(*args) -> None:  # run this during server.quit()
        polyphony.free_all()  # free all the synths
        time.sleep(0.5)  # wait for them to fade out before moving on

    def signal_handler(*args) -> None:
        exit_future.set_result(True)  # set the exit future flag

    def input_callback(event: NoteOn | NoteOff) -> None:
        # just play the event via polyphony directly
        polyphony.perform(event)

    # create a future we can wait on to quit the script
    exit_future: concurrent.futures.Future[bool] = concurrent.futures.Future()
    # create a server and polyphony manager
    server = supriya.Server()
    polyphony = PolyphonyManager(server=server, synthdef=simple_sine)
    # setup lifecycle callbacks
    server.register_lifecycle_callback("BOOTED", on_boot)
    server.register_lifecycle_callback("QUITTING", on_quitting)
    # hook up Ctrl-C so we can gracefully shutdown the server
    signal.signal(signal.SIGINT, signal_handler)
    # boot the server and let the user know we're ready to play
    server.boot()
    print("Server online. Press Ctrl-C to exit.")
    # turn on the input handler and teach it to callback against the polyphony manager
    with input_handler.listen(callback=input_callback):
        exit_future.result()  # wait for Ctrl-C
    # stop the input handler and quit the server
    server.quit()


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """
    Parse CLI arguments.
    """
    parser = argparse.ArgumentParser(
        description="Play notes via your QWERTY or MIDI keyboards"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list-midi-inputs", action="store_true", help="list available MIDI inputs"
    )
    group.add_argument(
        "--use-midi", help="play via MIDI keyboard", type=int, metavar="PORT_NUMBER"
    )
    group.add_argument(
        "--use-qwerty", action="store_true", help="play via QWERTY keyboard"
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> None:
    """
    The example entry-point function.
    """
    parsed_args = parse_args(args)
    if parsed_args.list_midi_inputs:
        # print out available MIDI input ports
        rtmidi.midiutil.list_input_ports()
    elif parsed_args.use_midi is not None:
        run(MidiHandler(port=parsed_args.use_midi))
    elif parsed_args.use_qwerty:
        run(QwertyHandler())


if __name__ == "__main__":
    main()