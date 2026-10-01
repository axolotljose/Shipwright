"""
preview_lullaby.py - renders the mod's ocarina melody to a .wav so you can learn
it by ear before you play it in game.

    python tools/preview_lullaby.py

Writes music/versas_lullaby_preview.wav: the six notes of "Versa's Lullaby",
twice, with a soft tick on each note onset so the rhythm is audible.

The notes and their lengths are imported from make_placeholder_music.py, so
this preview can never drift out of sync with the .seq the mod actually ships.
The tone is a plain synthesised one (sine + two harmonics, plucked envelope) -
it is a practice aid, not the in-game instrument, which is the game's own
piano/harp sound font.

Buttons, for reference while listening:

    A  ->  C-Up  ->  C-Down  ->  C-Left  ->  C-Right  ->  A
    D4     D5        F4          B4          A4          D4

or on a keyboard, with the port's default bindings:

    X  ->  Up arrow -> Down arrow -> Left arrow -> Right arrow -> X
"""

import math
import os
import struct
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from make_placeholder_music import LULLABY   # noqa: E402  (the note list)

RATE = 22050          # plenty for a preview; keeps the file small
BPM = 72              # the tempo the placeholder .seq is authored at
SLICE = 0.5 * 60.0 / BPM      # one slice = one 1/8 note, as in Seq64
ON_SLICES = [2, 2, 2, 2, 2, 12]   # how long each note is held


def midi_to_freq(note):
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def render_note(freq, seconds):
    """A plucked tone: fundamental plus two harmonics, quick attack, decay."""
    n = int(seconds * RATE)
    out = []
    for i in range(n):
        t = i / float(RATE)
        # envelope: 4 ms attack, exponential decay, 30 ms release at the end
        env = min(1.0, t / 0.004)
        env *= math.exp(-2.2 * t / max(seconds, 0.2))
        tail = n - i
        if tail < int(0.03 * RATE):
            env *= tail / (0.03 * RATE)
        # slight vibrato so it sounds like an instrument, not a test tone
        vib = 1.0 + 0.003 * math.sin(2.0 * math.pi * 5.0 * t)
        w = 2.0 * math.pi * freq * vib * t
        out.append(env * (math.sin(w) + 0.35 * math.sin(2 * w) + 0.12 * math.sin(3 * w)) / 1.47)
    return out


def render_click():
    """A very short, quiet noise burst: marks a note onset for the ear."""
    n = int(0.008 * RATE)
    out = []
    seed = 12345
    for i in range(n):
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        noise = (seed / float(0x7FFFFFFF)) * 2.0 - 1.0
        out.append(0.12 * noise * (1.0 - i / float(n)))
    return out


def silence(seconds):
    return [0.0] * int(seconds * RATE)


def count_in(slices=4):
    """A woodblock-ish tick on beats: the four 1/8 notes of a count-in so you
    know when to start playing. Higher pitch on the first tick."""
    samples = []
    for i in range(slices):
        freq = 1600.0 if i == 0 else 1100.0
        n = int(0.045 * RATE)
        for k in range(n):
            t = k / float(RATE)
            env = math.exp(-55.0 * t)
            samples.append(0.30 * env * math.sin(2.0 * math.pi * freq * t))
        samples.extend(silence(2 * SLICE - 0.045))
    return samples


def melody(with_clicks=True):
    samples = []
    for midi, slices in zip(LULLABY, ON_SLICES):
        dur = slices * SLICE
        note = render_note(midi_to_freq(midi), dur)
        if with_clicks:
            click = render_click()
            for i, s in enumerate(click):
                note[i] += s
        samples.extend(note)
    return samples


def write_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32000)) for s in samples)
        w.writeframes(frames)


def main():
    out_dir = os.path.join(ROOT, "music")
    os.makedirs(out_dir, exist_ok=True)

    # reference: the melody twice, with a tick on each note onset
    track = silence(0.4) + melody() + silence(1.0) + melody() + silence(0.6)
    path = os.path.join(out_dir, "versas_lullaby_preview.wav")
    write_wav(path, track)
    print("wrote %s (%.1f s, %d notes x2)" % (path, len(track) / float(RATE), len(LULLABY)))

    # practice track: count-in, melody, then a gap the same length as the
    # melody for you to play along, twice
    gap = silence(len(melody()) / float(RATE))
    practice = (count_in() + melody() + gap) * 2
    path = os.path.join(out_dir, "versas_lullaby_practice.wav")
    write_wav(path, practice)
    print("wrote %s (%.1f s: 4 ticks, the melody, then your turn - x2)"
          % (path, len(practice) / float(RATE)))

    print("listen, then play:  X, up, down, left, right, X")


if __name__ == "__main__":
    main()
