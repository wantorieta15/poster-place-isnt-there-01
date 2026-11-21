#!/usr/bin/env python3
"""LUMARA — Isle of the Glass Arch.

A travel poster for a place that does not exist, drawn entirely with the
Python standard library. The program paints a 1024x1024 sunset scene —
a giant natural stone arch framing a low sun over a glass-calm sea —
and writes it to /output/entry.png as a PNG.

No third-party packages are used: the image is built in a bytearray and
encoded with struct + zlib, and the lettering uses a small bitmap font
defined below.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024
OUT = "/output/entry.png"

# ---------------------------------------------------------------- palette
# Sky gradient stops (y fraction -> RGB), top of the sky down to horizon.
SKY_STOPS = [
    (0.00, (27, 16, 64)),     # deep indigo night at the top
    (0.35, (96, 40, 122)),    # violet
    (0.60, (198, 74, 112)),   # magenta dusk
    (0.82, (247, 122, 72)),   # burning orange
    (1.00, (255, 184, 96)),   # gold at the horizon
]
# Sea gradient stops (y fraction below the horizon -> RGB).
SEA_STOPS = [
    (0.00, (238, 138, 88)),   # sunset reflected at the horizon
    (0.22, (128, 92, 122)),   # mauve water
    (0.55, (34, 74, 112)),    # deep teal blue
    (1.00, (12, 30, 70)),     # dark water at the bottom
]
HORIZON = 560            # y of the horizon line
SUN_CX, SUN_CY, SUN_R = 512, 470, 85
SUN_CORE = (255, 243, 196)
SUN_GLOW = (255, 178, 84)
SILHOUETTE = (36, 22, 51)    # dark plum for arch, palms, islands
BEACH = (30, 18, 38)
TEXT_MAIN = (255, 242, 216)  # warm cream lettering
TEXT_SHADOW = (36, 22, 51)

# ------------------------------------------------------------- bitmap font
# 5x7 pixel capitals, digits and a little punctuation. Each glyph is seven
# rows of five cells; '#' is ink, '.' is empty. Drawn big, the blocky
# letterforms read as a bold retro poster face.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
}


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def gradient(stops, t):
    """Colour at position t (0..1) along a list of (pos, rgb) stops."""
    if t <= stops[0][0]:
        return stops[0][1]
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            return lerp(c0, c1, (t - p0) / (p1 - p0))
    return stops[-1][1]


class Canvas:
    """A plain RGB bytearray image with fast row-span fills."""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def hspan(self, y, x0, x1, color):
        """Fill pixels x0..x1 on row y with one colour (clipped)."""
        if y < 0 or y >= self.h:
            return
        x0 = max(0, x0)
        x1 = min(self.w - 1, x1)
        if x1 < x0:
            return
        n = x1 - x0 + 1
        self.px[(y * self.w + x0) * 3:(y * self.w + x1 + 1) * 3] = bytes(color) * n

    def hspan_blend(self, y, x0, x1, color, alpha):
        """Fill pixels x0..x1 on row y, blending colour over what is there."""
        if y < 0 or y >= self.h or alpha <= 0:
            return
        x0 = max(0, x0)
        x1 = min(self.w - 1, x1)
        if x1 < x0:
            return
        if alpha >= 1:
            self.hspan(y, x0, x1, color)
            return
        base = (y * self.w + x0) * 3
        for x in range(x0, x1 + 1):
            o = base + (x - x0) * 3
            for i in range(3):
                self.px[o + i] = int(round(self.px[o + i] * (1 - alpha) + color[i] * alpha))

    def disc(self, cx, cy, r, color, alpha=1.0):
        """Filled circle, row by row."""
        r2 = r * r
        for y in range(max(0, cy - r), min(self.h, cy + r + 1)):
            dy = y - cy
            dx = int(math.sqrt(max(0, r2 - dy * dy)))
            self.hspan_blend(y, cx - dx, cx + dx, color, alpha)

    def ring_arc(self, cx, cy, r_out, r_in, color):
        """Upper half of a thick ring (an arch), row by row."""
        for y in range(max(0, cy - r_out), min(self.h, cy + 1)):
            dy = y - cy
            dxo = int(math.sqrt(max(0, r_out * r_out - dy * dy)))
            if abs(dy) < r_in:
                dxi = int(math.sqrt(max(0, r_in * r_in - dy * dy)))
                self.hspan(y, cx - dxo, cx - dxi, color)
                self.hspan(y, cx + dxi, cx + dxo, color)
            else:
                self.hspan(y, cx - dxo, cx + dxo, color)

    def stamp(self, cx, cy, r, color):
        """Small filled disc used to draw thick lines dot by dot."""
        self.disc(cx, cy, r, color)

    def thick_line(self, x0, y0, x1, y1, width, color):
        steps = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
        r = max(1, width // 2)
        for i in range(steps + 1):
            t = i / steps
            x = int(round(x0 + (x1 - x0) * t))
            y = int(round(y0 + (y1 - y0) * t))
            self.stamp(x, y, r, color)

    def text(self, s, cx, y_top, scale, color, shadow=None):
        """Draw centred text in the bitmap font; returns the text width."""
        adv = 6 * scale
        total = len(s) * adv - scale
        x = cx - total // 2
        for ch in s:
            glyph = FONT.get(ch.upper(), FONT[" "])
            for row_i, row in enumerate(glyph):
                for col_i, cell in enumerate(row):
                    if cell != "1":
                        continue
                    px = x + col_i * scale
                    py = y_top + row_i * scale
                    if shadow is not None:
                        self.hspan(py + 4, px + 4, px + scale - 1 + 4, shadow)
                        for yy in range(py + 5, py + scale + 4):
                            self.hspan(yy, px + 4, px + scale - 1 + 4, shadow)
                    for yy in range(py, py + scale):
                        self.hspan(yy, px, px + scale - 1, color)
            x += adv
        return total


def write_png(canvas, path):
    """Encode the canvas as a PNG (filter 0 scanlines, zlib)."""
    raw = bytearray()
    stride = canvas.w * 3
    for y in range(canvas.h):
        raw.append(0)
        raw += canvas.px[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", canvas.w, canvas.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", comp) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ------------------------------------------------------------------- scene
def paint_sky(c):
    for y in range(HORIZON):
        c.hspan(y, 0, W - 1, gradient(SKY_STOPS, y / HORIZON))


def paint_sun(c):
    # Wide soft glow, then a tighter halo, then the solid disc.
    c.disc(SUN_CX, SUN_CY, 210, SUN_GLOW, 0.16)
    c.disc(SUN_CX, SUN_CY, 150, SUN_GLOW, 0.28)
    c.disc(SUN_CX, SUN_CY, 112, (255, 214, 130), 0.38)
    c.disc(SUN_CX, SUN_CY, SUN_R, SUN_CORE)


def paint_sea(c):
    for y in range(HORIZON, H):
        c.hspan(y, 0, W - 1, gradient(SEA_STOPS, (y - HORIZON) / (H - HORIZON)))
    # The sun's path on the water: a shimmering column that widens and
    # breaks up as it runs toward the viewer.
    for y in range(HORIZON + 4, H):
        t = (y - HORIZON) / (H - HORIZON)
        half = int(26 + 150 * t + 26 * math.sin(y * 0.11))
        wobble = int(18 * math.sin(y * 0.045))
        bright = 0.55 * (1 - t) + 0.08
        # A few broken sparkle bands instead of one flat column.
        if int(y * 0.35) % 3 == 0:
            c.hspan_blend(y, SUN_CX - half + wobble, SUN_CX + half + wobble,
                          (255, 206, 130), bright * 0.55)
        else:
            c.hspan_blend(y, SUN_CX - half + wobble, SUN_CX + half + wobble,
                          (255, 196, 120), bright)


def paint_arch(c):
    # One landmark: a giant natural stone arch, its feet in the sea, its
    # opening framing the low sun. Drawn after the sun so the silhouette
    # covers the disc's edges and the sun shines through the opening.
    cx, cy = 512, 648
    c.ring_arc(cx, cy, 340, 252, SILHOUETTE)
    # Feet of the arch, down deep into the water.
    for y in range(649, 852):
        c.hspan(y, 512 - 340, 512 - 260, SILHOUETTE)
        c.hspan(y, 512 + 260, 512 + 340, SILHOUETTE)


def paint_islands(c):
    # Low dark islands sitting on the horizon, left and right of the arch.
    for cx, rx, ry in ((150, 150, 26), (880, 130, 22)):
        for y in range(HORIZON - ry, HORIZON + 1):
            dy = y - HORIZON
            dx = int(rx * math.sqrt(max(0.0, 1 - (dy / ry) ** 2))) if ry else 0
            c.hspan(y, cx - dx, cx + dx, SILHOUETTE)


def paint_sailboat(c):
    # A tiny white sail far out on the water, clear of the arch's feet.
    bx, by = 118, 722
    c.thick_line(bx, by, bx, by - 46, 3, (245, 238, 220))
    for y in range(by - 46, by - 2):
        t = (y - (by - 46)) / 44.0
        c.hspan(y, bx + 2, bx + 2 + int(30 * t), (250, 244, 228))
    c.hspan(by, bx - 26, bx + 30, (38, 26, 44))
    c.hspan(by + 1, bx - 22, bx + 26, (38, 26, 44))


def paint_birds(c):
    # Kept clear of the lettering zone (x 250..775, y 92..260).
    for bx, by, s in ((170, 300, 14), (232, 264, 11), (830, 290, 14),
                      (892, 250, 11), (862, 332, 9)):
        c.thick_line(bx - s, by, bx, by - s // 2, 3, SILHOUETTE)
        c.thick_line(bx, by - s // 2, bx + s, by, 3, SILHOUETTE)


def paint_beach(c):
    # A dark sand curve sweeping in from the bottom-left corner.
    for y in range(872, H):
        t = (y - 872) / (H - 872)
        bx = int(640 * t * t + 60 * t)
        c.hspan(y, 0, bx, BEACH)
    # Two leaning palms on the sand, bottom right.
    for tx, ty, lean, hgt in ((830, 1010, -70, 190), (920, 1024, -46, 150)):
        top_x, top_y = tx + lean, ty - hgt
        c.thick_line(tx, ty + 14, top_x, top_y, 12, SILHOUETTE)
        for ang in (-150, -110, -70, -30, 10):
            rad = math.radians(ang)
            ex = top_x + int(74 * math.cos(rad))
            ey = top_y + int(46 * math.sin(rad)) + 26
            mx = top_x + int(38 * math.cos(rad))
            my = top_y + int(30 * math.sin(rad)) + 10
            c.thick_line(top_x, top_y, mx, my, 6, SILHOUETTE)
            c.thick_line(mx, my, ex, ey, 4, SILHOUETTE)


def main():
    c = Canvas(W, H)
    paint_sky(c)
    paint_sun(c)
    paint_sea(c)
    paint_islands(c)
    paint_sailboat(c)
    paint_arch(c)
    paint_birds(c)
    paint_beach(c)
    # Lettering: the invented place name, big and high in the sky, with a
    # smaller line beneath it naming the landmark. Both sit in the calm
    # upper sky so they stay legible against the smooth gradient.
    c.text("LUMARA", W // 2, 92, 15, TEXT_MAIN, shadow=TEXT_SHADOW)
    c.text("ISLE OF THE GLASS ARCH", W // 2, 216, 6, TEXT_MAIN,
           shadow=TEXT_SHADOW)
    for yy in (276, 277):
        c.hspan_blend(yy, 342, 682, TEXT_MAIN, 0.85)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    size = write_png(c, OUT)
    print(f"wrote {OUT} ({size} bytes)")


if __name__ == "__main__":
    main()


