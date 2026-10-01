"""
pnglite - a tiny, dependency-free PNG reader/writer.

Why this exists: the mod folder is meant to be built on a stock Windows Python
install with no `pip install pillow`. Everything here uses only `zlib` and
`struct` from the standard library.

Supported on read : 8-bit greyscale / RGB / RGBA / palette, non-interlaced.
Supported on write: 8-bit greyscale / RGB / RGBA, non-interlaced.

This is deliberately not a general purpose image library. It is enough to
encode N64 textures (see build_versas_fate.py) and to generate the placeholder
texture set (see make_textures.py).
"""

import struct
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"


class PngError(Exception):
    pass


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png(path):
    """Read a PNG file and return (width, height, rgba_bytes).

    rgba_bytes is a flat `bytes` of width*height*4 (R, G, B, A per pixel).
    """
    with open(path, "rb") as f:
        data = f.read()

    if not data.startswith(PNG_SIG):
        raise PngError("%s: not a PNG file" % path)

    pos = len(PNG_SIG)
    idat = bytearray()
    width = height = None
    bit_depth = color_type = interlace = None
    palette = b""
    trns = b""

    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length  # length + type + body + crc

        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _comp, _filt, interlace = struct.unpack(">IIBBBBB", body)
        elif ctype == b"PLTE":
            palette = body
        elif ctype == b"tRNS":
            trns = body
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break

    if width is None:
        raise PngError("%s: missing IHDR" % path)
    if bit_depth != 8:
        raise PngError("%s: only 8-bit PNGs are supported (got %d)" % (path, bit_depth))
    if interlace != 0:
        raise PngError("%s: interlaced PNGs are not supported" % path)

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise PngError("%s: unsupported colour type %d" % (path, color_type))

    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    if len(raw) < (stride + 1) * height:
        raise PngError("%s: truncated image data" % path)

    out = bytearray(width * height * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(height):
        filt = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride

        if filt == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filt == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filt == 3:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif filt == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                c = prev[i - channels] if i >= channels else 0
                line[i] = (line[i] + _paeth(a, prev[i], c)) & 0xFF
        elif filt != 0:
            raise PngError("%s: bad filter type %d" % (path, filt))

        base = y * width * 4
        for x in range(width):
            s = x * channels
            d = base + x * 4
            if color_type == 0:
                g = line[s]
                out[d:d + 4] = bytes((g, g, g, 255))
            elif color_type == 2:
                out[d:d + 4] = bytes((line[s], line[s + 1], line[s + 2], 255))
            elif color_type == 3:
                idx = line[s]
                out[d:d + 4] = bytes((
                    palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2],
                    trns[idx] if idx < len(trns) else 255,
                ))
            elif color_type == 4:
                g, a = line[s], line[s + 1]
                out[d:d + 4] = bytes((g, g, g, a))
            else:
                out[d:d + 4] = bytes(line[s:s + 4])

        prev = line

    return width, height, bytes(out)


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------

def _chunk(ctype, body):
    return (struct.pack(">I", len(body)) + ctype + body +
            struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF))


def write_png(path, width, height, rgba, color_type=6):
    """Write a PNG. `rgba` is a flat bytes of width*height*4.

    color_type 6 = RGBA, 2 = RGB (alpha dropped), 0 = greyscale (luma of RGB).
    """
    channels = {0: 1, 2: 3, 6: 4}[color_type]
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: none
        base = y * width * 4
        for x in range(width):
            s = base + x * 4
            r, g, b, a = rgba[s], rgba[s + 1], rgba[s + 2], rgba[s + 3]
            if color_type == 6:
                raw += bytes((r, g, b, a))
            elif color_type == 2:
                raw += bytes((r, g, b))
            else:
                raw.append((r * 299 + g * 587 + b * 114) // 1000)

    body = PNG_SIG
    body += _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
    body += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    body += _chunk(b"IEND", b"")

    with open(path, "wb") as f:
        f.write(body)
