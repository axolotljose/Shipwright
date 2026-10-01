"""
apply_patch.py - copies the one C++ file and appends the two table rows that
"Versa's Fate" needs, then tells you how to build.

Run it from the versas-fate folder, pointing at your Ship of Harkinian source
checkout (the folder that contains `soh/`, `README.md` and `CMakeLists.txt`):

    python tools/apply_patch.py --soh-src C:\\src\\Shipwright

What it changes (and nothing else):

    soh/soh/VersasFateWarp.cpp                  new file: song detection + warp
    soh/include/tables/scene_table.h            +1 line: SCENE_VERSAS_FATE
    soh/include/tables/entrance_table.h         +1 line: ENTR_VERSAS_FATE

It is safe to run twice: it detects its own edits and skips them.
Pass --revert to undo all three changes.
"""

import argparse
import os
import shutil
import sys

SCENE_LINE = "/* 0x6E */ DEFINE_SCENE(versa_scene, none, SCENE_VERSAS_FATE, SDC_DEFAULT, 0, 0)"
# If you already added scenes to your fork, the index in the comment above is
# wrong but harmless - it is a comment. The order of the include file is what
# matters, and the new line always goes last.

ENTRANCE_LINE = ("/* 0x614 */ DEFINE_ENTRANCE(ENTR_VERSAS_FATE, SCENE_VERSAS_FATE, 0, false, true, "
                 "TRANS_TYPE_FADE_WHITE, TRANS_TYPE_FADE_WHITE)")

WARP_FILE = "VersasFateWarp.cpp"


def read(path):
    with open(path, "r", encoding="utf-8", errors="surrogateescape") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(text)


def backup(path):
    bak = path + ".versasfate.bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)


def append_line(path, marker, line):
    text = read(path)
    if marker in text:
        return False
    if not text.endswith("\n"):
        text += "\n"
    text += line + "\n"
    write(path, text)
    return True


def remove_line(path, marker):
    text = read(path)
    if marker not in text:
        return False
    out = "\n".join(l for l in text.split("\n") if marker not in l)
    if not out.endswith("\n"):
        out += "\n"
    write(path, out)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apply the Versa's Fate source patch")
    parser.add_argument("--soh-src", required=True,
                        help="root of your Ship of Harkinian source checkout (contains soh/)")
    parser.add_argument("--revert", action="store_true", help="undo the patch")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.soh_src)
    scene_table = os.path.join(root, "soh", "include", "tables", "scene_table.h")
    entrance_table = os.path.join(root, "soh", "include", "tables", "entrance_table.h")
    warp_dest = os.path.join(root, "soh", "soh", WARP_FILE)

    if not os.path.isfile(scene_table) or not os.path.isfile(entrance_table):
        raise SystemExit(
            "That does not look like a Ship of Harkinian source checkout:\n"
            "  expected %s\n"
            "  expected %s\n"
            "Point --soh-src at the folder that contains both soh/ and CMakeLists.txt."
            % (scene_table, entrance_table))

    warp_src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "patch", "soh", "soh", WARP_FILE)

    if args.revert:
        removed = []
        if os.path.isfile(warp_dest):
            os.remove(warp_dest)
            removed.append(warp_dest)
        if remove_line(scene_table, "SCENE_VERSAS_FATE"):
            removed.append(scene_table + " (row)")
        if remove_line(entrance_table, "ENTR_VERSAS_FATE"):
            removed.append(entrance_table + " (row)")
        for p in (scene_table, entrance_table):
            bak = p + ".versasfate.bak"
            if os.path.exists(bak):
                shutil.copy2(bak, p)
                os.remove(bak)
                removed.append(p + " (restored from backup)")
        print("reverted:")
        for r in removed:
            print("  -", r)
        return

    if not os.path.isfile(warp_src):
        raise SystemExit("missing %s - run this script from the versas-fate folder" % warp_src)

    shutil.copy2(warp_src, warp_dest)
    print("copied  %s" % warp_dest)

    backup(scene_table)
    backup(entrance_table)

    if append_line(scene_table, "SCENE_VERSAS_FATE", SCENE_LINE):
        print("patched %s\n          + %s" % (scene_table, SCENE_LINE))
    else:
        print("already patched: %s" % scene_table)

    if append_line(entrance_table, "ENTR_VERSAS_FATE", ENTRANCE_LINE):
        print("patched %s\n          + %s" % (entrance_table, ENTRANCE_LINE))
    else:
        print("already patched: %s" % entrance_table)

    print("")
    print("Now rebuild the game (Windows, from the repo root):")
    print("    cmake --build build --config Release")
    print("or, if you have not configured a build folder yet:")
    print("    cmake -S . -B build -G \"Visual Studio 17 2022\" -A x64")
    print("    cmake --build build --config Release")
    print("")
    print("Then put VersasFate.o2r in the mods folder next to oot.o2r and start the game.")


if __name__ == "__main__":
    main()
