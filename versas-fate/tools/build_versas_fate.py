"""
build_versas_fate.py - packs mod_src/ into VersasFate.o2r, the mod archive you
drop into Ship of Harkinian's `mods` folder.

Run:
    python tools/build_versas_fate.py

Inputs (all produced by the other scripts in tools/, or edited by hand):

    mod_src/textures/versas_fate/<name>.<fmt>.png   -> texture resources
    mod_src/scenes/shared/versa_scene/*             -> scene, room, collision (XML)
    mod_src/objects/versas_fate/*                   -> display lists and vertex buffers (XML)
    music/<name>.seq                                -> sequence resources (built by audio_to_seq.py)
    music/<name>.json                               -> optional per-track settings

Output:
    VersasFate.o2r          the mod: scene, objects, textures.  Vanilla music only.
    VersasFate-Music.o2r    OPTIONAL extra pack: the three custom tracks.  Install it
                            only if you want the custom music; the mod itself never
                            plays a custom sequence, so the game is unaffected by it.

Archive layout produced (this is what the engine looks for at runtime):

    scenes/shared/versa_scene/versa_scene                     scene header
    scenes/shared/versa_scene/versa_room_0                    the one room
    scenes/shared/versa_scene/versa_collision                 collision header
    objects/versas_fate/versa_room_0_dl_opa                   opaque display list
    objects/versas_fate/versa_room_0_dl_xlu                   translucent display list
    objects/versas_fate/versa_room_0_vtx_opa                  opaque vertex buffer
    objects/versas_fate/versa_room_0_vtx_xlu                  translucent vertex buffer
    textures/versas_fate/moss.i4                              textures, no file extension
    textures/versas_fate/bark.i8
    textures/versas_fate/vine.ia8
    textures/versas_fate/leaf.ia4
    textures/versas_fate/stone.i8
    textures/versas_fate/rune.ia8
    portVersion                                              archive format marker

VersasFate-Music.o2r (optional, separate archive):

    custom/music/versasfate/Versas Vine Forest_bgm            custom sequences
    custom/music/versasfate/Versa Gohma_bgm
    custom/music/versasfate/Versas Lullaby_fanfare
    portVersion

The custom sequences live in their own archive on purpose: with only
VersasFate.o2r installed, nothing in the game ever loads a .seq this mod wrote,
so every note you hear (the warp jingle, the forest theme, the boss theme) is a
vanilla sequence. The C++ hook looks the melody up by name and falls back to the
vanilla Minuet jingle when the music pack is absent, so no code change is needed
to switch between the two.

Nothing here needs the ROM, ZAPD, Blender or the C++ toolchain. Textures are
PNG files converted with the same arithmetic the official packer uses
(soh/assets/tools/soh-o2r-packer/PngTexture.cpp), and every other resource is
either plain XML the engine parses at runtime or a raw .seq wrapped in the
Sequence resource header.
"""

import json
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MOD_SRC = os.path.join(ROOT, "mod_src")
MUSIC_DIR = os.path.join(ROOT, "music")
OUT_PATH = os.path.join(ROOT, "VersasFate.o2r")

sys.path.insert(0, HERE)
from pnglite import read_png   # noqa: E402  (stdlib-only PNG reader)

# --------------------------------------------------------------------------
# resource type magics (see soh/soh/resource/type/SohResourceType.h and
# libultraship's include/fast/resource/ResourceType.h)
# --------------------------------------------------------------------------

TYPE_TEXTURE = 0x4F544558          # OTEX
TYPE_VERTEX = 0x4F565458           # OVTX
TYPE_DISPLAYLIST = 0x4F444C54      # ODLT
TYPE_SEQUENCE = 0x4F534551         # OSEQ

OTR_HEADER_SIZE = 0x40
ID_MAGIC = 0xDEADBEEFDEADBEEF

# texture type enum, same order as libultraship's Fast::TextureType
TEX_RGBA32, TEX_RGBA16, TEX_CI4, TEX_CI8, TEX_I4, TEX_I8, TEX_IA4, TEX_IA8, TEX_IA16 = range(1, 10)

FORMATS = {
    "rgba32": (TEX_RGBA32, 4),
    "rgb5a1": (TEX_RGBA16, 2),
    "i4": (TEX_I4, 0.5),
    "i8": (TEX_I8, 1),
    "ia4": (TEX_IA4, 0.5),
    "ia8": (TEX_IA8, 1),
    "ia16": (TEX_IA16, 2),
}

# The sequence names, and the label the SFX Editor shows. The last `_part` of
# the archive file name decides what kind of sequence it is: `_bgm` for music
# and `_fanfare` for the short jingles, exactly like a .ootrs music pack.
SEQUENCES = [
    dict(file="versas_vine_forest.seq", label="Versas Vine Forest", part="bgm",
         default=dict(font=0, description="Vine Forest theme")),
    dict(file="versa_gohma.seq", label="Versa Gohma", part="bgm",
         default=dict(font=0, description="Boss theme")),
    dict(file="versas_lullaby.seq", label="Versas Lullaby", part="fanfare",
         default=dict(font=0, description="Ocarina melody fanfare")),
]

MUSIC_ARCHIVE_DIR = "custom/music/versasfate"


# --------------------------------------------------------------------------
# resource writers
# --------------------------------------------------------------------------

def resource_header(res_type, version):
    """The 64 byte header every binary resource in an .o2r carries.

    Layout from torch's BaseExporter::WriteHeader, which is what the official
    packer uses (soh/assets/tools/soh-o2r-packer calls into the same code).
    """
    out = bytearray()
    out.append(0)                        # 0x00 endianness: 0 = little endian
    out.append(0)                        # 0x01 isCustom
    out.append(0)                        # 0x02 reserved
    out.append(0)                        # 0x03 reserved
    out += struct.pack("<I", res_type)   # 0x04 resource type magic
    out += struct.pack("<I", version)    # 0x08 version
    out += struct.pack("<Q", ID_MAGIC)   # 0x0C id
    out += struct.pack("<I", 0)          # 0x14
    out += struct.pack("<Q", 0)          # 0x18 ROM crc
    out += struct.pack("<I", 0)          # 0x20 ROM enum
    while len(out) < OTR_HEADER_SIZE:
        out += struct.pack("<I", 0)
    return bytes(out)


def encode_texture(rgba, width, height, fmt):
    """PNG pixels -> N64 texture bytes.

    The quantisation matches ZAPD's ZTexture (and therefore the official
    packer): `x >> 4` for 4 bit channels, `x >> 3` for 5 bit ones, no scaling.
    """
    out = bytearray()

    for y in range(height):
        for x in range(width):
            i = (y * width + x) * 4
            r, g, b, a = rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]

            if fmt == TEX_RGBA32:
                out += bytes((r, g, b, a))
            elif fmt == TEX_RGBA16:
                px = ((r >> 3) << 11) | ((g >> 3) << 6) | ((b >> 3) << 1) | (1 if a else 0)
                out += bytes(((px >> 8) & 0xFF, px & 0xFF))
            elif fmt == TEX_I4:
                if x % 2 == 0:
                    hi = (r // 16) & 0xF
                    j = (y * width + min(x + 1, width - 1)) * 4
                    lo = (rgba[j] // 16) & 0xF
                    out.append((hi << 4) | lo)
            elif fmt == TEX_I8:
                out.append(r)
            elif fmt == TEX_IA4:
                if x % 2 == 0:
                    hi = (((r >> 5) & 0x7) << 1) | (1 if a else 0)
                    j = (y * width + min(x + 1, width - 1)) * 4
                    lo = (((rgba[j] >> 5) & 0x7) << 1) | (1 if rgba[j + 3] else 0)
                    out.append((hi << 4) | lo)
            elif fmt == TEX_IA8:
                out.append((((r >> 4) & 0xF) << 4) | ((a >> 4) & 0xF))
            elif fmt == TEX_IA16:
                out += bytes((r, a))
            else:
                raise ValueError("unsupported texture format %d" % fmt)

    return bytes(out)


def build_texture_resource(png_path, fmt):
    width, height, rgba = read_png(png_path)
    data = encode_texture(rgba, width, height, FORMATS[fmt][0])
    expected = int(width * height * FORMATS[fmt][1])
    if len(data) != expected:
        raise ValueError("%s: encoded %d bytes, expected %d" % (png_path, len(data), expected))

    body = struct.pack("<IIII", FORMATS[fmt][0], width, height, len(data)) + data
    return resource_header(TYPE_TEXTURE, 0) + body


def build_sequence_resource(seq_bytes, font_index):
    """Wrap a raw .seq in the Sequence (V2, OSEQ) resource an archive expects.

    Field layout from soh/soh/resource/importer/AudioSequenceFactory.cpp and
    the .ootrs loader (OotrsArchive::BuildSequenceResource), which does exactly
    this for music packs.
    """
    body = bytearray()
    body += struct.pack("<I", len(seq_bytes))   # seqDataSize
    body += seq_bytes
    body.append(0)                              # seqNumber (the game assigns one)
    body.append(2)                              # medium
    body.append(2)                              # cachePolicy
    body += struct.pack("<I", 1)                # numFonts
    body.append(font_index & 0xFF)              # fonts[0]

    header = bytearray(resource_header(TYPE_SEQUENCE, 2))
    header[1] = 1                               # isCustom = 1
    return bytes(header) + bytes(body)


def port_version_entry(major=9, minor=2, patch=3):
    """7 byte 'portVersion' trailer: 1 byte endianness marker then three
    big endian version words (torch's ParseVersionString)."""
    return bytes([1]) + struct.pack(">HHH", major, minor, patch)


# --------------------------------------------------------------------------
# packing
# --------------------------------------------------------------------------

def collect_mod_src(entries):
    for dirpath, _dirnames, filenames in os.walk(MOD_SRC):
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, MOD_SRC).replace(os.sep, "/")

            if rel.endswith(".png"):
                stem, _, fmt = name[:-4].rpartition(".")
                if fmt not in FORMATS:
                    print("  skip   %s (unknown texture format '%s')" % (rel, fmt))
                    continue
                # "<name>.<fmt>.png" becomes the texture resource "<name>" - the
                # format lives in the resource header, exactly like the official
                # packer (soh/assets/tools/soh-o2r-packer/main.cpp).
                arc = rel[: -len(fmt) - 5]
                entries[arc] = build_texture_resource(full, fmt)
                print("  texture %-45s <- %s (%dx%d)" %
                      (arc, rel, *read_png(full)[:2]))
                continue

            with open(full, "rb") as f:
                entries[rel] = f.read()
            print("  xml     %s (%d bytes)" % (rel, len(entries[rel])))


def collect_music(entries):
    if not os.path.isdir(MUSIC_DIR):
        print("  (no music/ folder - skipping custom sequences)")
        return

    for spec in SEQUENCES:
        path = os.path.join(MUSIC_DIR, spec["file"])
        if not os.path.isfile(path):
            print("  missing music/%s (run tools/audio_to_seq.py)" % spec["file"])
            continue

        settings = dict(spec["default"])
        json_path = os.path.splitext(path)[0] + ".json"
        if os.path.isfile(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                settings.update(json.load(f))

        with open(path, "rb") as f:
            seq = f.read()

        arc = "%s/%s_%s" % (MUSIC_ARCHIVE_DIR, spec["label"], spec["part"])
        entries[arc] = build_sequence_resource(seq, int(settings.get("font", 0)))
        print("  music   %-45s <- music/%s (%d bytes, font %d)"
              % (arc, spec["file"], len(seq), int(settings.get("font", 0))))


# Fixed timestamp for every zip entry: zip stores a DOS date/time per file, so
# without this two builds of identical inputs would produce different bytes.
# The mod never reads it; it only makes the build reproducible so a committed
# .o2r can be verified against a fresh build (see VERIFY below).
ZIP_DATE_TIME = (2025, 1, 1, 0, 0, 0)


def write_archive(entries, out_path):
    tmp = out_path + ".tmp"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(entries):
            data = entries[name]
            if not data:
                raise SystemExit("refusing to write empty archive entry: %s" % name)
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        info = zipfile.ZipInfo("portVersion", date_time=ZIP_DATE_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        z.writestr(info, port_version_entry(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    if os.path.exists(out_path):
        os.remove(out_path)
    os.rename(tmp, out_path)


def validate(archive=None):
    """Refuse to package (or hand over) resources the engine cannot load.

    See tools/validate_mod.py: it re-checks the XML against the engine's own
    readers. A resource that fails there is a crash in game, and the crash it
    was written for (a collision header with a mismatched closing tag) is
    exactly the kind that looks like "the game froze when I warped".
    """
    import validate_mod

    if archive:
        argv = sys.argv
        sys.argv = [argv[0], "--o2r", archive]
        try:
            return validate_mod.main()
        finally:
            sys.argv = argv
    return validate_mod.main()


def validate_music():
    """Refuse to ship .seq files the sequence player cannot follow.

    See tools/validate_seq.py: it decodes the bytecode with the same rules as
    soh/src/code/audio_seqplayer.c. A script with a wrong offset does not
    always crash - it just plays silence (or walks off the end of the data),
    which is impossible to debug from inside the game.
    """
    import validate_seq

    music_dir = os.path.join(ROOT, "music")
    paths = sorted(os.path.join(music_dir, name) for name in os.listdir(music_dir)
                   if name.endswith(".seq"))
    if not paths:
        print("  (no .seq files in music/ - skipping sequence validation)")
        return 0
    print("validating music/ ...")
    return validate_seq.main(["validate_seq"] + paths)


def main():
    if not os.path.isdir(MOD_SRC):
        raise SystemExit("mod_src/ not found - run tools/make_textures.py and tools/make_scene.py first")

    print("validating mod_src/ ...")
    if validate() != 0:
        raise SystemExit("refusing to pack: fix the problems above first")

    if validate_music() != 0:
        raise SystemExit("refusing to pack: fix the sequences in music/ first")

    entries = {}
    print("collecting assets from mod_src/ ...")
    collect_mod_src(entries)

    music_entries = {}
    print("collecting music (separate archive) ...")
    collect_music(music_entries)

    write_archive(entries, OUT_PATH)
    if validate(OUT_PATH) != 0:
        raise SystemExit("the packed archive failed validation")

    size = os.path.getsize(OUT_PATH)
    print("")
    print("wrote %s (%.1f KB, %d entries) - vanilla music only" % (OUT_PATH, size / 1024.0, len(entries) + 1))
    print("copy it to:  <Ship of Harkinian>/mods/VersasFate.o2r")
    print("then start the game and check Help -> Mods, or read the log for 'Versa'.")

    if music_entries:
        music_path = os.path.join(ROOT, "VersasFate-Music.o2r")
        write_archive(music_entries, music_path)
        if validate(music_path) != 0:
            raise SystemExit("the music pack failed validation")
        size = os.path.getsize(music_path)
        print("")
        print("wrote %s (%.1f KB, %d entries) - the three custom tracks, OPTIONAL"
              % (music_path, size / 1024.0, len(music_entries) + 1))
        print("install it in mods/ as well only if you want custom music instead of")
        print("the vanilla themes: the melody lesson then uses it, otherwise it plays")
        print("the vanilla Minuet jingle.")


if __name__ == "__main__":
    main()
