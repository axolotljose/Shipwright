"""
make_song_sheet.py - draws a song sheet for "Versa's Lullaby" as a PNG.

    python tools/make_song_sheet.py

Writes docs/versas_lullaby_song_sheet.png: the six buttons in order, the note
each one sounds, the default keyboard key for each, and the two rules that
matter (no modifiers, order not timing).

Uses only pnglite (this project's dependency-free PNG writer) and a 5x7 bitmap
font defined below, so there is nothing to install and the sheet can be
regenerated on any machine that can run the rest of tools/.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from pnglite import write_png   # noqa: E402

OUT = os.path.join(ROOT, "docs", "versas_lullaby_song_sheet.png")

W, H = 1280, 620

BG = (18, 24, 26, 255)
CARD = (30, 42, 44, 255)
CARD_EDGE = (58, 84, 80, 255)
TITLE = (232, 240, 226, 255)
DIM = (150, 172, 164, 255)
ACCENT = (140, 220, 150, 255)      # the green of an N64 "A" button
WOOD = (176, 132, 86, 255)
FADE = (206, 168, 96, 255)

BG_RGBA = BG
TITLE_RGBA = TITLE

# --------------------------------------------------------------------------
# a 5x7 bitmap font, only the glyphs this sheet needs
# --------------------------------------------------------------------------

_GLYPHS = {
    "A": (".###.",
          "#...#",
          "#...#",
          "#####",
          "#...#",
          "#...#",
          "#...#"),
    "B": ("####.",
          "#...#",
          "#...#",
          "####.",
          "#...#",
          "#...#",
          "####."),
    "C": (".###.",
          "#...#",
          "#....",
          "#....",
          "#....",
          "#...#",
          ".###."),
    "D": ("####.",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          "####."),
    "E": ("#####",
          "#....",
          "#....",
          "####.",
          "#....",
          "#....",
          "#####"),
    "F": ("#####",
          "#....",
          "#....",
          "####.",
          "#....",
          "#....",
          "#...."),
    "G": (".###.",
          "#...#",
          "#....",
          "#.###",
          "#...#",
          "#...#",
          ".###."),
    "H": ("#...#",
          "#...#",
          "#...#",
          "#####",
          "#...#",
          "#...#",
          "#...#"),
    "I": (".###.",
          "..#..",
          "..#..",
          "..#..",
          "..#..",
          "..#..",
          ".###."),
    "K": ("#...#",
          "#..#.",
          "#.#..",
          "##...",
          "#.#..",
          "#..#.",
          "#...#"),
    "L": ("#....",
          "#....",
          "#....",
          "#....",
          "#....",
          "#....",
          "#####"),
    "M": ("#...#",
          "##.##",
          "#.#.#",
          "#...#",
          "#...#",
          "#...#",
          "#...#"),
    "N": ("#...#",
          "##..#",
          "#.#.#",
          "#..##",
          "#...#",
          "#...#",
          "#...#"),
    "O": (".###.",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          ".###."),
    "P": ("####.",
          "#...#",
          "#...#",
          "####.",
          "#....",
          "#....",
          "#...."),
    "R": ("####.",
          "#...#",
          "#...#",
          "####.",
          "#.#..",
          "#..#.",
          "#...#"),
    "S": (".###.",
          "#...#",
          "#....",
          ".###.",
          "....#",
          "#...#",
          ".###."),
    "T": ("#####",
          "..#..",
          "..#..",
          "..#..",
          "..#..",
          "..#..",
          "..#.."),
    "U": ("#...#",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          ".###."),
    "V": ("#...#",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          ".#.#.",
          "..#.."),
    "W": ("#...#",
          "#...#",
          "#...#",
          "#.#.#",
          "#.#.#",
          "##.##",
          "#...#"),
    "X": ("#...#",
          "#...#",
          ".#.#.",
          "..#..",
          ".#.#.",
          "#...#",
          "#...#"),
    "Y": ("#...#",
          "#...#",
          ".#.#.",
          "..#..",
          "..#..",
          "..#..",
          "..#.."),
    "0": (".###.",
          "#...#",
          "#..##",
          "#.#.#",
          "##..#",
          "#...#",
          ".###."),
    "1": ("..#..",
          ".##..",
          "..#..",
          "..#..",
          "..#..",
          "..#..",
          ".###."),
    "2": (".###.",
          "#...#",
          "....#",
          "..##.",
          ".#...",
          "#....",
          "#####"),
    "3": (".###.",
          "#...#",
          "....#",
          "..##.",
          "....#",
          "#...#",
          ".###."),
    "4": ("#...#",
          "#...#",
          "#...#",
          ".####",
          "....#",
          "....#",
          "....#"),
    "5": ("#####",
          "#....",
          "#....",
          "####.",
          "....#",
          "#...#",
          ".###."),
    "6": (".###.",
          "#....",
          "#....",
          "####.",
          "#...#",
          "#...#",
          ".###."),
    "-": (".....",
          ".....",
          ".....",
          "#####",
          ".....",
          ".....",
          "....."),
    ".": (".....",
          ".....",
          ".....",
          ".....",
          ".....",
          ".....",
          "..#.."),
    "'": ("..#..",
          "..#..",
          ".....",
          ".....",
          ".....",
          ".....",
          "....."),
}

# Flatten to one 35 character string per glyph and check the shapes are sane.
FONT = {}
for _ch, _rows in _GLYPHS.items():
    if len(_rows) != 7 or any(len(r) != 5 for r in _rows):
        raise ValueError("glyph %r is not 7 rows of 5" % _ch)
    FONT[_ch] = "".join(_rows)


def draw_text(buf, x, y, text, scale=2, color=TITLE):
    """Blit `text` at (x, y) top-left. Unknown characters are skipped."""
    cx = x
    for ch in text.upper():
        bits = FONT.get(ch)
        if bits is None:
            cx += 6 * scale
            continue
        for row in range(7):
            for col in range(5):
                if bits[row * 5 + col] == "#":
                    fill_rect(buf, cx + col * scale, y + row * scale, scale, scale, color)
        cx += 6 * scale
    return cx


def text_width(text, scale=2):
    return len(text) * 6 * scale


def fill_rect(buf, x, y, w, h, color):
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(W, int(x + w)), min(H, int(y + h))
    for yy in range(y0, y1):
        base = (yy * W + x0) * 4
        for _ in range(x1 - x0):
            buf[base:base + 4] = bytes(color)
            base += 4


def stroke_rect(buf, x, y, w, h, color, t=3):
    fill_rect(buf, x, y, w, t, color)
    fill_rect(buf, x, y + h - t, w, t, color)
    fill_rect(buf, x, y, t, h, color)
    fill_rect(buf, x + w - t, y, t, h, color)


def fill_circle(buf, cx, cy, r, color):
    for y in range(int(cy - r), int(cy + r) + 1):
        dy = y - cy
        if abs(dy) > r:
            continue
        half = int((r * r - dy * dy) ** 0.5)
        fill_rect(buf, cx - half, y, half * 2 + 1, 1, color)


def fill_poly(buf, points, color):
    ys = [p[1] for p in points]
    for y in range(int(min(ys)), int(max(ys)) + 1):
        xs = []
        n = len(points)
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(x1 + (y - y1) * (x2 - x1) / float(y2 - y1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            fill_rect(buf, xs[i], y, xs[i + 1] - xs[i], 1, color)


def draw_arrow(buf, cx, cy, size, direction, color):
    """The C-button symbol: a fat arrow inside a rounded square."""
    s = size
    stem = int(s * 0.30)
    head = int(s * 0.55)

    if direction == "up":
        fill_poly(buf, [(cx, cy - head), (cx - s // 2, cy - head + int(s * 0.45)),
                        (cx + s // 2, cy - head + int(s * 0.45))], color)
        fill_rect(buf, cx - stem // 2, cy - head + int(s * 0.45), stem, s - int(s * 0.45), color)
    elif direction == "down":
        fill_poly(buf, [(cx, cy + head), (cx - s // 2, cy + head - int(s * 0.45)),
                        (cx + s // 2, cy + head - int(s * 0.45))], color)
        fill_rect(buf, cx - stem // 2, cy + head - (s - int(s * 0.45)), stem, s - int(s * 0.45), color)
    elif direction == "left":
        fill_poly(buf, [(cx - head, cy), (cx - head + int(s * 0.45), cy - s // 2),
                        (cx - head + int(s * 0.45), cy + s // 2)], color)
        fill_rect(buf, cx - head + int(s * 0.45), cy - stem // 2, s - int(s * 0.45), stem, color)
    else:
        fill_poly(buf, [(cx + head, cy), (cx + head - int(s * 0.45), cy - s // 2),
                        (cx + head - int(s * 0.45), cy + s // 2)], color)
        fill_rect(buf, cx + head - (s - int(s * 0.45)), cy - stem // 2, s - int(s * 0.45), stem, color)


# --------------------------------------------------------------------------
# the sheet
# --------------------------------------------------------------------------

STEPS = [
    dict(btn="A", note="D4", key="X", kind="a"),
    dict(btn="C-UP", note="D5", key="UP", kind="up"),
    dict(btn="C-DOWN", note="F4", key="DOWN", kind="down"),
    dict(btn="C-LEFT", note="B4", key="LEFT", kind="left"),
    dict(btn="C-RIGHT", note="A4", key="RIGHT", kind="right"),
    dict(btn="A", note="D4", key="X", kind="a"),
]


def draw_button_symbol(buf, cx, cy, kind):
    if kind == "a":
        fill_circle(buf, cx, cy, 46, ACCENT)
        draw_text(buf, cx - 3 * 6, cy - 7, "A", scale=2, color=(20, 30, 22, 255))
        return
    draw_arrow(buf, cx, cy, 86, kind, FADE)


def main():
    buf = bytearray(bytes(BG_RGBA) * (W * H))

    # header ---------------------------------------------------------------
    title = "VERSA'S LULLABY"
    draw_text(buf, (W - text_width(title, 3)) // 2, 34, title, scale=3, color=TITLE)
    sub = "PLAY THESE SIX NOTES IN ORDER"
    draw_text(buf, (W - text_width(sub, 2)) // 2, 84, sub, scale=2, color=DIM)

    # cards ----------------------------------------------------------------
    card_w, card_h = 186, 300
    gap = 12
    total = len(STEPS) * card_w + (len(STEPS) - 1) * gap
    x0 = (W - total) // 2
    top = 140

    for i, step in enumerate(STEPS):
        x = x0 + i * (card_w + gap)
        fill_rect(buf, x, top, card_w, card_h, CARD)
        stroke_rect(buf, x, top, card_w, card_h, CARD_EDGE, t=2)

        # step number
        draw_text(buf, x + 16, top + 14, "%d" % (i + 1), scale=2, color=DIM)

        # the button itself
        draw_button_symbol(buf, x + card_w // 2, top + 108, step["kind"])

        # label + note + key
        lbl = step["btn"]
        draw_text(buf, x + (card_w - text_width(lbl, 2)) // 2, top + 178, lbl, scale=2, color=TITLE)

        note = "NOTE " + step["note"]
        draw_text(buf, x + (card_w - text_width(note, 1)) // 2, top + 214, note, scale=1, color=ACCENT)

        key = "KEY " + step["key"]
        draw_text(buf, x + (card_w - text_width(key, 1)) // 2, top + 240, key, scale=1, color=DIM)

    # the two phrases, bracketed ------------------------------------------
    half = (card_w + gap) * 3 - gap
    draw_text(buf, x0, top + card_h + 18, "FIRST HALF", scale=1, color=DIM)
    draw_text(buf, x0 + half + gap, top + card_h + 18, "SECOND HALF", scale=1, color=DIM)
    fill_rect(buf, x0, top + card_h + 32, half, 3, CARD_EDGE)
    fill_rect(buf, x0 + half + gap, top + card_h + 32, half, 3, CARD_EDGE)

    # rules ----------------------------------------------------------------
    y = top + card_h + 62
    draw_text(buf, x0, y, "1. DO NOT HOLD R OR Z - THEY SHARPEN AND FLATTEN NOTES", scale=1, color=WOOD)
    draw_text(buf, x0, y + 26, "2. ORDER MATTERS. SPEED DOES NOT - GO AS SLOW AS YOU LIKE", scale=1, color=WOOD)
    draw_text(buf, x0, y + 52, "3. PLAY IT WITH THE OCARINA OUT IN THE OPEN, NOT NEXT TO AN ACTOR",
              scale=1, color=WOOD)

    note = "KEYBOARD KEYS ARE THE PORT'S DEFAULTS; REMAP THEM IN CONTROLLER BINDINGS"
    draw_text(buf, (W - text_width(note, 1)) // 2, H - 40, note, scale=1, color=DIM)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    write_png(OUT, W, H, buf, color_type=6)
    print("wrote %s (%dx%d)" % (OUT, W, H))


if __name__ == "__main__":
    main()
