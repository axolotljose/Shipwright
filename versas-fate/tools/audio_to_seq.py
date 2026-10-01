"""
audio_to_seq.py - turns one of your own .wav / .mp3 / .flac / .ogg tracks into a
Seq64 `.seq`, the format SoH's audio engine actually plays.

Run:
    python tools/audio_to_seq.py "my_theme.mp3" -o music/versas_vine_forest.seq --bpm 100
    python tools/audio_to_seq.py "boss.mp3"      -o music/versa_gohma.seq       --bpm 140
    python tools/audio_to_seq.py "lullaby.wav"   -o music/versas_lullaby.seq   --bpm 90

What it does
------------
The N64/SoH sequence player is a *note* player: a .seq file is a script of
note events plus a program (instrument) number, and the sound comes out of the
vanilla sound fonts that ship with the game. It is not a sample player, so
there is no way to drop a recorded mix into it. The only honest conversion is
therefore transcription:

  1. decode the source to mono PCM (.wav is handled with Python's own `wave`
     module; .mp3/.flac/.ogg are handed to ffmpeg if it is on your PATH - see
     README.md for how to install it),
  2. cut the audio into one slice per 1/8 note at the given BPM,
  3. find the dominant pitch of each slice with a bank of Goertzel filters,
     one per semitone from C2 to B6,
  4. quantise that onto a piano-roll grid, merge repeated pitches into held
     notes, drop anything too quiet to be a real note,
  5. write the result as a single-channel Seq64 file.

You get the melody and rhythm of your track, played by the game's own
instruments. Chords, vocals, distortion and reverb are gone - see
docs/CUSTOM_MUSIC.md for what to do if you want the exact recording instead.

The file format written here is the one soh/src/code/audio_seqplayer.c
implements: a "root" script that enables channels, one or more "channel"
scripts, and one note "layer" per channel that loops forever.
"""

import argparse
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import wave

# --------------------------------------------------------------------------
# Seq64 opcodes, all verified against soh/src/code/audio_seqplayer.c
# --------------------------------------------------------------------------

# root (sequence) script
SEQ_MUTE_BEHAVIOUR = 0xD3     # + u8
SEQ_MUTE_VOLUME = 0xD5        # + u8 (scale 0..127)
SEQ_INIT_CHANNELS = 0xD7      # + s16 channel bitmask; MUST come before Ldchan
SEQ_VOLUME = 0xDB             # + u8
SEQ_TEMPO = 0xDD              # + u8 (BPM)
SEQ_ENABLE_CHANNEL = 0x90     # | channel, + compressed u16 absolute offset
SEQ_DISABLE_CHANNEL = 0x40    # | channel
SEQ_JUMP = 0xFB               # + s16 absolute offset
SEQ_END = 0xFF

# channel script
CH_LEGATO = 0xC4              # largeNotes = true, required by our note encoding
CH_SET_LAYER = 0x88           # | layer index, + compressed u16 absolute offset
CH_PAN = 0xDD                 # + u8 (0..127)
CH_VOLUME = 0xDF              # + u8 (0..127)
CH_END = 0xFF

# layer (note) script - "large notes" encoding, i.e. delay + velocity + gate
LAYER_SHORT = 0xC4            # continuous notes on (legato)
LAYER_INSTRUMENT = 0xC6       # + u8 sound font program (instrument)
LAYER_REST = 0xC0             # + compressed u16 delay (rest / tie)
LAYER_JUMP = 0xFB             # + s16 absolute offset
LAYER_END = 0xFF

TATUMS_PER_BEAT = 48          # ticks per beat in the sequence player
TICKS_PER_SLICE = TATUMS_PER_BEAT // 2   # one 1/8 note

MAX_NOTE = 0x3F               # note values are 6 bit; 0x40 and up are commands

# The note byte written into a layer is an *index* into gNoteFrequencies
# (soh/src/code/audio_data.c), and entry 0 of that table is NOTE_A0.  The table
# has 0x53 entries (A0..G7), so a MIDI note is written as (midi - 21).
# In "large notes" mode the top two bits of the note byte select the note
# variant, so only indices 0x00..0x3F can be used directly - that is A0..C6.
# Higher notes need the layer's transpose command (layer_settranspose).
MIN_MIDI = 21                 # A0, index 0
MAX_MIDI = 21 + 0x3F          # C6, index 0x3F - the highest encodable note


# --------------------------------------------------------------------------
# decoding
# --------------------------------------------------------------------------

def read_wav(path):
    """Return (samples, rate) with samples as floats in [-1, 1]."""
    with wave.open(path, "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())

    if width == 1:
        raw = struct.unpack("<%dB" % len(frames), frames)
        samples = [(v - 128) / 128.0 for v in raw]
    elif width == 2:
        raw = struct.unpack("<%dh" % (len(frames) // 2), frames)
        samples = [v / 32768.0 for v in raw]
    elif width == 3:
        samples = []
        for i in range(0, len(frames) - 2, 3):
            v = frames[i] | (frames[i + 1] << 8) | (frames[i + 2] << 16)
            if v & 0x800000:
                v -= 0x1000000
            samples.append(v / 8388608.0)
    elif width == 4:
        raw = struct.unpack("<%di" % (len(frames) // 4), frames)
        samples = [v / 2147483648.0 for v in raw]
    else:
        raise ValueError("unsupported WAV sample width: %d bytes" % width)

    if channels > 1:
        mono = []
        for i in range(0, len(samples) - channels + 1, channels):
            mono.append(sum(samples[i:i + channels]) / channels)
        samples = mono

    return samples, rate


def decode_with_ffmpeg(path, workdir):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit(
            "%s is not a .wav file and ffmpeg was not found on PATH.\n"
            "Either install ffmpeg (see README.md) or convert the file yourself:\n"
            "    ffmpeg -i \"%s\" -ac 1 -ar 32000 working.wav" % (path, path))
    out = os.path.join(workdir, "decoded.wav")
    subprocess.check_call([ffmpeg, "-y", "-loglevel", "error", "-i", path,
                           "-ac", "1", "-ar", "32000", out])
    return out


def load_mono(path):
    workdir = tempfile.mkdtemp(prefix="versasfate_")
    try:
        if path.lower().endswith(".wav"):
            return read_wav(path)
        return read_wav(decode_with_ffmpeg(path, workdir))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# --------------------------------------------------------------------------
# pitch detection
# --------------------------------------------------------------------------

def goertzel(samples, start, length, freq, rate):
    k = 2.0 * math.cos(2.0 * math.pi * freq / rate)
    s1 = 0.0
    s2 = 0.0
    for i in range(start, start + length):
        s0 = samples[i] + k * s1 - s2
        s2 = s1
        s1 = s0
    return math.sqrt(abs(s1 * s1 + s2 * s2 - k * s1 * s2)) / length


def midi_to_freq(note):
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def detect_notes(samples, rate, slice_len, quiet_db=-46.0):
    notes = []
    freqs = [(n, midi_to_freq(n)) for n in range(MIN_MIDI, MAX_MIDI + 1)]

    for start in range(0, max(0, len(samples) - slice_len), slice_len):
        window = samples[start:start + slice_len]
        rms = math.sqrt(sum(v * v for v in window) / max(1, len(window)))
        if rms <= 1e-6 or 20.0 * math.log10(rms) < quiet_db:
            notes.append((None, 0))
            continue

        best = None
        best_mag = 0.0
        for midi, freq in freqs:
            mag = goertzel(window, 0, len(window), freq, rate)
            if mag > best_mag:
                best_mag = mag
                best = midi

        if best is None or best_mag < rms * 6.0:
            notes.append((None, 0))
        else:
            velocity = min(127, max(30, int(127 * (rms ** 0.5) * 3.2)))
            notes.append((best, velocity))

    return notes


def compress(notes, min_run=2):
    """Merge consecutive equal pitches into [midi, slices, velocity] runs."""
    runs = []
    for midi, vel in notes:
        if runs and midi is not None and runs[-1][0] == midi:
            runs[-1][1] += 1
        else:
            runs.append([midi, 1, vel])
    runs = [r for r in runs if r[0] is None or r[1] >= min_run]
    while runs and runs[0][0] is None:
        runs.pop(0)
    while runs and runs[-1][0] is None:
        runs.pop()
    return runs


# --------------------------------------------------------------------------
# Seq64 writer
# --------------------------------------------------------------------------

def _c16(value):
    """Compressed u16: 1 byte if it fits in 7 bits, else 2 bytes with 0x80 set."""
    value = max(0, min(0x7FFF, value))
    if value > 0x7F:
        return bytes([0x80 | ((value >> 8) & 0x7F), value & 0xFF])
    return bytes([value])


def _s16(value):
    """Plain 16 bit big endian value, as read by AudioSeq_ScriptReadS16."""
    return struct.pack(">H", value & 0xFFFF)


def _ptr(value):
    """Address argument for ldchan / ldlayer, read with
    AudioSeq_ScriptReadCompressedU16: one byte if the top bit is clear,
    otherwise 0x80|hi7 followed by the low byte.  Always emitting the two byte
    form keeps the offsets a fixed width, which makes patching them easy.
    """
    value &= 0x7FFF
    return bytes([0x80 | ((value >> 8) & 0x7F), value & 0xFF])


class Seq64(object):
    """Builds a sequence: one note layer per channel, each looping forever."""

    def __init__(self, bpm=100):
        self.tempo = max(16, min(255, int(round(bpm))))
        self.channels = []

    def add_channel(self, program, runs, pan=64, volume=100, gate=0xF0, transpose=0):
        self.channels.append(dict(program=program & 0xFF, runs=runs, pan=pan & 0x7F,
                                  volume=volume & 0x7F, gate=gate & 0xFF,
                                  transpose=max(-64, min(63, transpose))))

    def build(self):
        if not self.channels:
            raise ValueError("sequence has no channels")

        # ---- layers ------------------------------------------------------
        layers = []
        for ch in self.channels:
            layer = bytearray([LAYER_SHORT, LAYER_INSTRUMENT, ch["program"]])
            for (midi, slices, velocity) in ch["runs"]:
                if midi is None:
                    layer.append(LAYER_REST)
                    layer.extend(_c16(slices * TICKS_PER_SLICE))
                else:
                    pitch = max(0, min(MAX_NOTE, midi - MIN_MIDI))
                    layer.append(pitch)
                    layer.extend(_c16(slices * TICKS_PER_SLICE))
                    layer.append(velocity & 0x7F)
                    layer.append(ch["gate"])
            # loop the melody: jump back to the start of this layer
            layers.append(layer)

        # ---- channels ----------------------------------------------------
        channels = []
        for ch in self.channels:
            body = bytearray()
            body.append(CH_LEGATO)
            body.append(CH_SET_LAYER | 0)
            body.extend(b"\x80\x00")           # patched below: layer offset
            body.append(CH_PAN)
            body.append(ch["pan"])
            body.append(CH_VOLUME)
            body.append(ch["volume"])
            body.append(CH_END)
            channels.append(body)

        # ---- root --------------------------------------------------------
        root = bytearray()
        root.append(SEQ_MUTE_BEHAVIOUR)
        root.append(0x20)
        root.append(SEQ_MUTE_VOLUME)
        root.append(0x32)
        # Channels have to be initialised before they can be enabled/loaded.
        root.append(SEQ_INIT_CHANNELS)
        root.extend(_s16((1 << len(self.channels)) - 1))

        channel_ptr_pos = []
        for i in range(len(self.channels)):
            root.append(SEQ_ENABLE_CHANNEL | i)
            channel_ptr_pos.append(len(root))
            root.extend(b"\x80\x00")           # patched below: channel offset
        root.append(SEQ_VOLUME)
        root.append(127)
        root.append(SEQ_TEMPO)
        root.append(self.tempo)
        # Keep the sequence player alive forever: delay, then jump back to the
        # delay. The channels loop on their own inside their note layer.
        loop_point = len(root)
        root.append(0xFD)
        root.extend(_c16(0x7FFF))
        root.append(SEQ_JUMP)
        root.extend(_s16(loop_point))
        root.append(SEQ_END)

        # ---- assemble with absolute offsets ------------------------------
        # Layout: [root][channel 0..n][layer 0..n]
        root_len = len(root)
        ch_offsets = []
        pos = root_len
        for body in channels:
            ch_offsets.append(pos)
            pos += len(body)
        layer_offsets = []
        for layer in layers:
            layer_offsets.append(pos)
            pos += len(layer)

        for i, p in enumerate(channel_ptr_pos):
            root[p:p + 2] = _ptr(ch_offsets[i])

        out = bytearray()
        out.extend(root)
        for idx, body in enumerate(channels):
            # patch the layer pointer inside each channel
            lp = 3   # 0xC4, 0x88 | layer, then the 2 byte offset
            body[lp:lp + 2] = _ptr(layer_offsets[idx])
            out.extend(body)

        for idx, layer in enumerate(layers):
            # append the loop-back jump, now that the layer's own offset is known
            layer.append(LAYER_JUMP)
            layer.extend(_s16(layer_offsets[idx]))
            layer.append(LAYER_END)
            out.extend(layer)

        return bytes(out)


# --------------------------------------------------------------------------

def build_sequence(runs, bpm, program, voices):
    seq = Seq64(bpm=bpm)

    if voices <= 1:
        seq.add_channel(program, runs)
        return seq.build()

    midi_notes = sorted(m for (m, s, v) in runs if m is not None)
    if len(midi_notes) < 8:
        seq.add_channel(program, runs)
        return seq.build()

    low_cut = midi_notes[len(midi_notes) // 4]
    high_cut = midi_notes[(len(midi_notes) * 3) // 4]

    def band(lo, hi):
        out = []
        for (m, s, v) in runs:
            if m is not None and lo <= m < hi:
                out.append((m, s, v))
            else:
                out.append((None, s, v))
        while out and out[0][0] is None:
            out.pop(0)
        while out and out[-1][0] is None:
            out.pop()
        return out

    seq.add_channel(program, band(high_cut, 128), volume=110)
    if voices >= 2:
        mid = band(low_cut, high_cut)
        if mid:
            seq.add_channel(program, mid, volume=85)
    if voices >= 3:
        low = band(0, low_cut)
        if low:
            seq.add_channel((program + 1) & 0xFF, low, volume=95)
    return seq.build()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert a track into a Seq64 .seq for SoH")
    parser.add_argument("input", help="source .wav/.mp3/.flac/.ogg")
    parser.add_argument("-o", "--output", required=True, help="destination .seq")
    parser.add_argument("--bpm", type=float, default=100.0, help="tempo of the source track (default 100)")
    parser.add_argument("--program", type=int, default=1,
                        help="sound font program (instrument) number; 1 = piano")
    parser.add_argument("--voices", type=int, default=1, choices=(1, 2, 3),
                        help="1 = melody only (default), 2 = + middle, 3 = + bass")
    parser.add_argument("--quiet-db", type=float, default=-46.0,
                        help="slices quieter than this are rests")
    args = parser.parse_args(argv)

    samples, rate = load_mono(args.input)
    slice_len = max(64, int(rate * (60.0 / args.bpm) / 2.0))   # one 1/8 note
    print("decoded %s: %.1f s at %d Hz" % (args.input, len(samples) / float(rate), rate))
    print("slice = %d samples (1/8 note at %.1f BPM)" % (slice_len, args.bpm))

    detected = detect_notes(samples, rate, slice_len, quiet_db=args.quiet_db)
    runs = compress(detected)
    played = [r for r in runs if r[0] is not None]
    if not played:
        raise SystemExit("no pitched notes found - try a lower --quiet-db or another track")
    pitches = sorted(set(r[0] for r in played))
    print("transcribed %d note events from %d slices, pitch range MIDI %d..%d"
          % (len(played), len(detected), pitches[0], pitches[-1]))

    data = build_sequence(runs, args.bpm, args.program, args.voices)
    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes)" % (args.output, len(data)))


if __name__ == "__main__":
    main()
