from supriya import Envelope, synthdef
from supriya.ugens import EnvGen, Out, SinOsc


@synthdef()
def simple_sine(frequency=440, amplitude=0.1, gate=1):
    sine = SinOsc.ar(frequency=frequency) * amplitude
    envelope = EnvGen.kr(envelope=Envelope.adsr(), gate=gate, done_action=2)
    Out.ar(bus=0, source=[sine * envelope] * 2)