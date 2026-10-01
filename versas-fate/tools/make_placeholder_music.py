"""
make_placeholder_music.py - writes three stand-in .seq files into music/ so the
mod is audible the moment you build it.

They are simple monophonic melodies played with the game's own instruments,
built with the same Seq64 writer audio_to_seq.py uses. Replace them with your
own tracks at any time:

    python tools/audio_to_seq.py "your_theme.mp3" -o music/versas_vine_forest.seq --bpm 96
    python tools/audio_to_seq.py "your_boss.mp3"  -o music/versa_gohma.seq       --bpm 140
    python tools/audio_to_seq.py "your_song.wav"  -o music/versas_lullaby.seq    --bpm 80

The melodies below are deliberately the same shapes the scene docs describe:
the lullaby is the six note sequence the C++ patch listens for
(A, C-Up, C-Down, C-Left, C-Right, A), so this file doubles as a cheat sheet
for the notes you have to play in game.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from audio_to_seq import Seq64   # noqa: E402

MUSIC = os.path.join(ROOT, "music")

# MIDI numbers: D4=62, F4=65, G4=67, A4=69, B4=71, C5=72, D5=74, F5=77, A5=81
D4, F4, G4, A4, B4, C5, D5, F5, A5 = 62, 65, 67, 69, 71, 72, 74, 77, 81
C3, D3, F3, G3, A3, C4 = 48, 50, 53, 55, 57, 60

# The six buttons of "Versa's Lullaby" on the ocarina, in order.
LULLABY = [D4, D5, F4, B4, A4, D4]


def write(name, seq_bytes):
    os.makedirs(MUSIC, exist_ok=True)
    path = os.path.join(MUSIC, name)
    with open(path, "wb") as f:
        f.write(seq_bytes)
    print("wrote music/%s (%d bytes)" % (name, len(seq_bytes)))


def lullaby():
    """The ocarina song: what the player plays, played back as a fanfare."""
    runs = []
    for midi in LULLABY[:-1]:
        runs.append((midi, 2, 96))
    runs.append((LULLABY[-1], 12, 110))     # hold the last note
    seq = Seq64(bpm=72)
    seq.add_channel(1, runs, volume=110, gate=0xE0)
    return seq.build()


def vine_forest():
    """A slow, wandering minor theme for the forest."""
    melody = [
        (D4, 3), (F4, 2), (A4, 3), (G4, 2),
        (F4, 3), (D4, 3), (C4, 2), (D4, 4),
        (A4, 3), (C5, 2), (D5, 3), (A4, 2),
        (F4, 3), (G4, 2), (F4, 3), (D4, 4),
    ]
    runs = [(m, s, 88) for (m, s) in melody]
    seq = Seq64(bpm=88)
    seq.add_channel(1, runs, volume=100, gate=0xD0)
    return seq.build()


def vera_gohma():
    """A faster, heavier theme for the hollow."""
    bass = [(D3, 1), (D3, 1), (F3, 1), (D3, 1),
            (G3, 1), (G3, 1), (A3, 1), (F3, 1)]
    lead = [(D4, 2), (F4, 1), (A4, 1), (G4, 2), (F4, 2),
            (C5, 2), (A4, 2), (F4, 2), (D4, 2)]
    runs = [(m, s, 96) for (m, s) in lead]
    bass_runs = [(m, s, 100) for (m, s) in bass * 2]
    seq = Seq64(bpm=140)
    seq.add_channel(1, runs, volume=105, gate=0xC0)
    seq.add_channel(4, bass_runs, volume=110, gate=0xA0, transpose=-12)
    return seq.build()


def main():
    write("versas_lullaby.seq", lullaby())
    write("versas_vine_forest.seq", vine_forest())
    write("versa_gohma.seq", vera_gohma())
    print("")
    print("These are placeholders. See docs/CUSTOM_MUSIC.md to use your own audio.")


if __name__ == "__main__":
    main()
