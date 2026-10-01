#!/usr/bin/env python3
"""
validate_seq.py - walk a .seq file the way the game's sequence player will.

Once a .seq is inside an .o2r you cannot see whether it is any good: a broken
script rarely crashes, the player just reads garbage, plays silence, or runs off
the end of the buffer. This decodes the byte stream with the same rules as
soh/src/code/audio_seqplayer.c so those mistakes are caught here instead.

Checked, per script:

  root    commands the sequence player implements, with the operand width it
          reads (0xD6/0xD7 and 0x90|channel take plain 16 bit values, 0xCC-0xE9
          take bytes), every ldchan offset inside the file and pointing at
          something that parses as a channel script, and the 0xFB loop target
          inside the file.

  channel 0x88|layer (ldlayer) takes a plain 16 bit offset while note delays
          take the *compressed* encoding - swapping those two is the classic
          way to write a song nobody can hear - and 0x90|layer is "free layer",
          not "enable channel".

  layer   a note is a pitch byte below 0x40, then a compressed delay, a
          velocity and a gate time; 0xC0 is a rest, 0xC6 sets the instrument.
          Note values of 0x40 and up would be read as commands.

usage:
    python tools/validate_seq.py music/*.seq
"""

import os
import sys

CH_LEGATO = 0xC4
CH_END = 0xFF
LAYER_LEGATO = 0xC4
LAYER_SHORT = 0xC5
LAYER_INSTRUMENT = 0xC6
LAYER_REST = 0xC0
LAYER_END = 0xFF

# Flow control, only reachable for commands >= 0xF2. The widths are the ones
# AudioSeq_GetScriptControlFlowArgument reads through D_80130520.
FLOW_WIDTH = {
    0xF2: 1, 0xF3: 1, 0xF4: 1, 0xF5: 2, 0xF6: 0, 0xF7: 0, 0xF8: 1,
    0xF9: 2, 0xFA: 2, 0xFB: 2, 0xFC: 0, 0xFD: None, 0xFE: 0, 0xFF: 0,
}

# Sequence player commands this generator knows, and the width of their operand.
ROOT_WIDTH = {
    0xD0: 1, 0xD1: 2, 0xD2: 2, 0xD3: 1, 0xD4: 0, 0xD5: 1, 0xD6: 2, 0xD7: 2,
    0xD8: 1, 0xD9: 1, 0xDA: 2, 0xDB: 1, 0xDC: 1, 0xDD: 1, 0xDE: 2, 0xDF: 2,
    0xE0: 1, 0xE1: 1, 0xE2: 1, 0xE3: 1, 0xE4: 2, 0xE5: 2, 0xE6: 2, 0xE7: 2,
    0xE8: 2, 0xE9: 1, 0xEA: 0, 0xEB: 1,
}
for _ch in range(16):
    ROOT_WIDTH[0x40 | _ch] = 0          # disablechan
    ROOT_WIDTH[0x90 | _ch] = 2          # ldchan: plain s16 (AudioSeq_ScriptReadS16)

# Channel commands this generator knows.
CHANNEL_WIDTH = {
    0xC1: 1, 0xC2: 1, 0xC3: 1, 0xC4: 0, 0xC5: 0, 0xC6: 1, 0xC7: 2, 0xC8: 0,
    0xC9: 1, 0xCA: 1, 0xCB: 0, 0xCC: 1, 0xCD: 2, 0xCE: 1, 0xCF: 1,
    0xD0: 1, 0xD1: 2, 0xD2: 2, 0xD3: 1, 0xD4: 1, 0xD5: 0, 0xD7: 2, 0xD8: 1,
    0xD9: 1, 0xDA: 2, 0xDB: 1, 0xDC: 1, 0xDD: 1, 0xDE: 2, 0xDF: 1, 0xE0: 1,
    0xE1: 1, 0xE2: 1, 0xE3: 1, 0xE4: 1, 0xE5: 1, 0xE6: 1, 0xE7: 1, 0xE8: 1,
    0xE9: 1, 0xEA: 0, 0xEB: 1, 0xEC: 1, 0xED: 1, 0xEE: 1, 0xF0: 0, 0xF1: 0,
}
for _layer in range(8):
    CHANNEL_WIDTH[0x80 | _layer] = 0    # layer finished -> value
    CHANNEL_WIDTH[0x88 | _layer] = 2    # ldlayer: plain s16
    CHANNEL_WIDTH[0x90 | _layer] = 0    # free layer
    CHANNEL_WIDTH[0x98 | _layer] = 0    # dynamic ldlayer
    CHANNEL_WIDTH[0x70 | _layer] = 1


class Problem(Exception):
    pass


def read_u8(data, pc, what):
    if pc >= len(data):
        raise Problem("%s runs off the end of the %d byte file" % (what, len(data)))
    return data[pc], pc + 1


def read_s16(data, pc, what):
    """AudioSeq_ScriptReadS16: plain two byte big endian, not compressed."""
    if pc + 2 > len(data):
        raise Problem("%s runs off the end of the file reading a 16 bit value" % what)
    return (data[pc] << 8) | data[pc + 1], pc + 2


def read_c16(data, pc, what):
    """AudioSeq_ScriptReadCompressedU16: one byte, or 0x80|hi then lo."""
    b, pc = read_u8(data, pc, what)
    if b & 0x80:
        lo, pc = read_u8(data, pc, what)
        return ((b << 8) & 0x7F00) | lo, pc
    return b, pc


def script_target(data, offset, what):
    if offset >= len(data):
        raise Problem("%s points at offset %d, past the end of the %d byte file"
                      % (what, offset, len(data)))
    if offset == 0:
        raise Problem("%s points at offset 0, which cannot be a script" % what)
    return offset


class Root(object):
    def __init__(self):
        self.channels = []       # (channel index, offset)
        self.jumps = []
        self.typo = 0
        self.ticks = 0
        self.tempo = 100


def walk_root(data):
    root = Root()
    pc = 0
    steps = 0
    while pc < len(data):
        steps += 1
        if steps > 4096:
            raise Problem("the root script never ends")
        here = pc
        cmd, pc = read_u8(data, pc, "root script")
        if cmd == CH_END:
            return root
        if cmd == 0xFD:
            value, pc = read_c16(data, pc, "root delay")
            if value == 0:
                raise Problem("a zero length delay at offset %d would spin the player" % here)
            root.ticks += value
            continue
        if cmd == 0xFB:
            arg, pc = read_s16(data, pc, "root jump")
            target = script_target(data, arg, "the 0xFB jump at offset %d" % here)
            root.jumps.append(target)
            if target <= here:      # a loop back: following it proves nothing new
                continue
            pc = target
            continue
        if cmd in FLOW_WIDTH:
            if cmd == 0xFC:
                raise Problem("0xFC at offset %d: the player reads no operand for it and "
                              "jumps to offset 0 - use 0xFB" % here)
            raise Problem("control flow command 0x%02X at offset %d is not written by "
                          "this generator" % (cmd, here))
        if (cmd & 0xF0) == 0x90:
            arg, pc = read_s16(data, pc, "ldchan")
            root.channels.append((cmd & 0xF, script_target(data, arg, "ldchan at offset %d" % here)))
            continue
        if cmd == 0xDD:
            value, pc = read_u8(data, pc, "tempo")
            root.tempo = value
            continue
        width = ROOT_WIDTH.get(cmd)
        if width is None:
            raise Problem("0x%02X at offset %d is not a sequence player command"
                          % (cmd, here))
        pc += width
    raise Problem("the root script has no 0xFF terminator")


class Layer(object):
    def __init__(self):
        self.notes = 0
        self.rests = 0
        self.ticks = 0
        self.program = None


def walk_channel(data, pc, index):
    layers = []
    steps = 0
    while pc < len(data):
        steps += 1
        if steps > 4096:
            raise Problem("channel %d never ends" % index)
        here = pc
        cmd, pc = read_u8(data, pc, "channel %d" % index)
        if cmd == CH_END:
            return layers
        if (cmd & 0xF8) == 0x88:
            arg, pc = read_s16(data, pc, "ldlayer")
            layers.append(script_target(data, arg, "ldlayer in channel %d (offset %d)"
                                        % (index, here)))
            continue
        if cmd == 0xFD:
            _, pc = read_c16(data, pc, "channel %d delay" % index)
            continue
        if cmd == 0xFB:
            arg, pc = read_s16(data, pc, "channel %d jump" % index)
            script_target(data, arg, "the jump in channel %d at offset %d" % (index, here))
            continue
        if cmd in FLOW_WIDTH:
            raise Problem("channel %d uses control flow 0x%02X at offset %d, which this "
                          "generator never writes" % (index, cmd, here))
        width = CHANNEL_WIDTH.get(cmd)
        if width is None:
            raise Problem("0x%02X at offset %d is not a channel command" % (cmd, here))
        pc += width
    raise Problem("channel %d has no 0xFF terminator" % index)


def walk_layer(data, pc, index):
    layer = Layer()
    cmd, pc = read_u8(data, pc, "layer %d" % index)
    if cmd != LAYER_LEGATO:
        raise Problem("layer %d does not start with 0xC4 (legato/large notes)" % index)
    steps = 0
    while pc < len(data):
        steps += 1
        if steps > 65536:
            raise Problem("layer %d never ends" % index)
        here = pc
        cmd, pc = read_u8(data, pc, "layer %d" % index)
        if cmd == LAYER_END:
            return layer
        if cmd == LAYER_REST:
            value, pc = read_c16(data, pc, "rest in layer %d" % index)
            if value == 0:
                raise Problem("a zero length rest at offset %d in layer %d" % (here, index))
            layer.ticks += value
            layer.rests += 1
            continue
        if cmd == LAYER_INSTRUMENT:
            program, pc = read_u8(data, pc, "instrument in layer %d" % index)
            if program >= 0x7E:
                raise Problem("layer %d asks for instrument 0x%02X: 0x7E is a sound "
                              "effect, 0x7F is a drum and 0x80+ is a raw wave; a real "
                              "instrument program is 0x00-0x7D" % (index, program))
            layer.program = program
            continue
        if cmd == LAYER_SHORT:
            continue
        if cmd >= 0x40:
            raise Problem("0x%02X at offset %d in layer %d is neither a command nor a "
                          "note (notes are 0x00-0x3F)" % (cmd, here, index))
        # a note: pitch byte, compressed delay, velocity, gate time
        value, pc = read_c16(data, pc, "note in layer %d" % index)
        if value == 0:
            raise Problem("the note at offset %d in layer %d has a zero delay"
                          % (here, index))
        pc += 2
        layer.notes += 1
        layer.ticks += value
    raise Problem("layer %d has no 0xFF terminator" % index)


def validate(path):
    data = open(path, "rb").read()
    if len(data) < 8:
        raise Problem("file is too short to be a sequence")

    root = walk_root(data)
    if not root.channels:
        raise Problem("the root script never enables a channel - nothing would play")
    if not root.jumps:
        raise Problem("no 0xFB loop: the song would play once and stop")
    if root.ticks == 0:
        raise Problem("the root script never waits, so it would restart the song "
                      "as fast as the player runs")

    layers = []
    notes = 0
    song_ticks = 0
    for (channel, start) in root.channels:
        found = walk_channel(data, start, channel)
        if not found:
            raise Problem("channel %d never loads a layer - it would stay silent" % channel)
        for start in found:
            layer = walk_layer(data, start, channel)
            if layer.notes == 0:
                raise Problem("channel %d has a layer with no notes at all" % channel)
            notes += layer.notes
            layers.append(layer)
            song_ticks = max(song_ticks, layer.ticks)

    if song_ticks != root.ticks:
        raise Problem("the root script waits %d ticks but the melody lasts %d, so the "
                      "loop would restart the song in the wrong place"
                      % (root.ticks, song_ticks))

    return dict(size=len(data), channels=len(root.channels), layers=len(layers),
                notes=notes, ticks=song_ticks, tempo=root.tempo,
                programs=sorted(set(l.program for l in layers if l.program is not None)))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    failed = 0
    for path in argv[1:]:
        if not os.path.exists(path):
            print("  MISSING  %s" % path)
            failed += 1
            continue
        try:
            info = validate(path)
            seconds = info["ticks"] * 60.0 / 48.0 / max(1, info["tempo"])
            print("  ok  %-24s %4d bytes  %d channel(s)  %d layer(s)  %3d notes  "
                  "%5d ticks  %.1fs  program(s) %s"
                  % (os.path.basename(path), info["size"], info["channels"],
                     info["layers"], info["notes"], info["ticks"], seconds,
                     ",".join(str(p) for p in info["programs"]) or "-"))
        except Problem as problem:
            print("  FAIL  %s: %s" % (path, problem))
            failed += 1
    if failed:
        print("validate_seq: %d file(s) failed" % failed)
        return 1
    print("validate_seq: all %d sequence(s) decode cleanly" % (len(argv) - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
