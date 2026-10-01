"""
make_textures.py - generates the placeholder "Vine Forest" texture set.

Run:  python tools/make_textures.py

Writes 64x64 (and one 32x32) PNGs into mod_src/textures/versas_fate/.
These are tileable and deliberately dark/mossy so the area reads as "dark
forest" out of the box. Replace any of them with your own art - just keep the
file name and the `.fmt` suffix, which is what the build script reads:

    moss.i4.png     -> Grayscale4bpp    (forest floor)
    bark.i8.png     -> Grayscale8bpp    (tree trunks, walls)
    vine.ia8.png    -> GrayscaleAlpha8bpp (hanging vines, alpha cut-out)
    leaf.ia4.png    -> GrayscaleAlpha4bpp (canopy blobs, alpha cut-out)
    stone.i8.png    -> Grayscale8bpp    (boss arena floor)
    rune.ia8.png    -> GrayscaleAlpha8bpp (glowing rune plate, 32x32)

Format suffixes understood by the build script:
    i4 i8 ia4 ia8 ia16 rgb5a1 rgba32      (see mod_src/README-ASSETS.txt)
"""

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pnglite  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "mod_src", "textures", "versas_fate")


def blank(w, h, rgba=(0, 0, 0, 0)):
    return bytearray(bytes(rgba) * (w * h))


def put(buf, w, x, y, r, g, b, a=255):
    i = (y * w + x) * 4
    buf[i] = max(0, min(255, int(r)))
    buf[i + 1] = max(0, min(255, int(g)))
    buf[i + 2] = max(0, min(255, int(b)))
    buf[i + 3] = max(0, min(255, int(a)))


def tileable_waves(x, y, w, h, terms):
    """Sum of integer-frequency sines: wraps exactly at the tile edges."""
    v = 0.0
    for freq, amp, phase in terms:
        v += amp * math.sin(2 * math.pi * (freq * x / w) + phase)
        v += amp * math.cos(2 * math.pi * (freq * y / h) + phase * 1.7)
    return v


def clampi(v, lo=0, hi=255):
    return max(lo, min(hi, int(round(v))))


def make_moss(w=64, h=64):
    buf = blank(w, h)
    rng = random.Random(1337)
    jitter = [[rng.random() for _ in range(w)] for _ in range(h)]
    for y in range(h):
        for x in range(w):
            n = tileable_waves(x, y, w, h, [(1, 0.35, 0.0), (3, 0.22, 1.1), (7, 0.12, 2.3), (13, 0.06, 0.4)])
            v = 0.55 + n * 0.35 + (jitter[y][x] - 0.5) * 0.22
            v = max(0.0, min(1.0, v))
            # moss: dark desaturated green, 4bpp greyscale in the archive so keep the ramp smooth
            put(buf, w, x, y, 26 + 70 * v * 0.55, 40 + 110 * v, 30 + 60 * v * 0.6)
    return buf


def make_bark(w=64, h=64):
    buf = blank(w, h)
    rng = random.Random(4242)
    streaks = [rng.uniform(0.0, 1.0) for _ in range(w)]
    for y in range(h):
        for x in range(w):
            s = streaks[x]
            grain = math.sin(2 * math.pi * (x / w) * 9 + s * 6.0) * 0.5 + 0.5
            n = tileable_waves(x, y, w, h, [(2, 0.30, s), (6, 0.18, 0.9), (11, 0.10, 2.0)])
            v = 0.35 + grain * 0.30 + n * 0.30
            # deep brown bark, darker than the moss so trunks read as silhouettes
            put(buf, w, x, y, 46 + 70 * v, 34 + 52 * v, 24 + 34 * v)
    return buf


def make_vine(w=64, h=64):
    """Vertical vine strands with alpha cut-out (ia8)."""
    buf = blank(w, h)
    rng = random.Random(99)
    strands = []
    for _ in range(3):
        cx = rng.uniform(4, w - 4)
        thick = rng.uniform(1.6, 2.8)
        phase = rng.uniform(0.0, 6.28)
        strands.append((cx, thick, phase))
    for y in range(h):
        for x in range(w):
            a = 0.0
            lum = 0.0
            for (cx, thick, phase) in strands:
                off = math.sin(2 * math.pi * y / h * 2 + phase) * 3.0
                d = abs((x + w / 2) % w - (cx + off + w / 2) % w)
                d = min(d, w - d)
                if d < thick:
                    a = max(a, 1.0 - (d / thick) ** 2)
                    lum = max(lum, 0.55 + 0.45 * math.cos(d / thick * 1.57))
            if a > 0.02:
                # leaves: little blobs along the strands
                blob = math.sin(2 * math.pi * y / h * 3 + x * 0.4) * 0.5 + 0.5
                put(buf, w, x, y, 30 + 60 * lum, 60 + 120 * lum * (0.6 + 0.4 * blob), 34 + 50 * lum,
                    a * 255 * (0.65 + 0.35 * blob))
    return buf


def make_leaf(w=64, h=64):
    """Canopy clump: soft blobs, alpha 0..1 (ia4 = 4 bits of intensity + 4 of alpha)."""
    buf = blank(w, h)
    rng = random.Random(7)
    blobs = [(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(8, 18)) for _ in range(9)]
    for y in range(h):
        for x in range(w):
            a = 0.0
            for (bx, by, br) in blobs:
                # wrap the distance so the clump tiles
                dx = min(abs(x - bx), w - abs(x - bx))
                dy = min(abs(y - by), h - abs(y - by))
                d = math.hypot(dx, dy)
                if d < br:
                    a = max(a, (1.0 - d / br) ** 1.4)
            n = tileable_waves(x, y, w, h, [(3, 0.25, 0.2), (8, 0.15, 1.9)])
            put(buf, w, x, y, 34 + 40 * (0.5 + n), 58 + 70 * (0.5 + n), 34 + 36 * (0.5 + n), a * 235)
    return buf


def make_stone(w=64, h=64):
    buf = blank(w, h)
    rng = random.Random(2024)
    jitter = [[rng.random() for _ in range(w)] for _ in range(h)]
    for y in range(h):
        for x in range(w):
            n = tileable_waves(x, y, w, h, [(1, 0.30, 0.0), (4, 0.20, 1.4), (9, 0.10, 2.9)])
            crack = abs(math.sin(2 * math.pi * (x / w) * 2 + n * 2.0))
            v = 0.45 + n * 0.30 + (jitter[y][x] - 0.5) * 0.18 - (0.25 if crack < 0.12 else 0.0)
            v = max(0.05, min(1.0, v))
            g = 60 + 90 * v
            put(buf, w, x, y, g * 0.92, g * 0.95, g * 0.88)
    return buf


def make_rune(w=32, h=32):
    buf = blank(w, h)
    cx = cy = (w - 1) / 2.0
    for y in range(h):
        for x in range(w):
            dx, dy = x - cx, y - cy
            r = math.hypot(dx, dy)
            ang = math.atan2(dy, dx)
            ring = 1.0 - min(1.0, abs(r - 11.0) / 1.6)
            spoke = 0.0
            for k in range(6):
                a = k * math.pi / 3.0
                dd = abs(math.sin(ang - a)) * r
                if r < 12.0:
                    spoke = max(spoke, 1.0 - min(1.0, dd / 1.2))
            core = max(0.0, 1.0 - r / 4.0)
            a = max(ring, spoke, core)
            if a > 0.03:
                put(buf, w, x, y, 90 + 165 * a, 200 + 55 * a, 170 + 85 * a, a * 255)
    return buf


TEXTURES = {
    "moss.i4.png": make_moss,
    "bark.i8.png": make_bark,
    "vine.ia8.png": make_vine,
    "leaf.ia4.png": make_leaf,
    "stone.i8.png": make_stone,
    "rune.ia8.png": make_rune,
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, fn in TEXTURES.items():
        # size is the first two args of the factory functions; the rune is the odd one out
        w = h = 32 if name.startswith("rune") else 64
        rgba = fn()
        path = os.path.join(OUT_DIR, name)
        pnglite.write_png(path, w, h, bytes(rgba), color_type=(2 if name.endswith(".i4.png") or name.endswith(".i8.png") else 6))
        print("wrote %-16s %dx%d" % (name, w, h))


if __name__ == "__main__":
    main()
