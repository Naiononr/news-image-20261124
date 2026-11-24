#!/usr/bin/env python3
"""news-image-20261124 — broadsheet front page of THE WORLD TODAY,
Tuesday 24 November 2026.

Draws a 1024x1024 newspaper front page using only the standard library:
a small raster surface, a 5x7 bitmap font encoded as integers, and a
hand-rolled PNG writer (zlib + struct, no Pillow).

Deterministic by construction: no clock, no randomness, and every loop
iterates in a fixed order, so two runs produce byte-identical output.

Stories (each verified against reporting on 24 November 2026):
- Lead: Nvidia reinstates Jensen Huang as CEO; shares jump 31 percent.
- Libya: Ukrainian sea drones sink the Russian corvette Merkury at Benghazi.
- Indonesia: 24 dead confirmed in the Cikande candy factory fire, ~30 missing.
- EU: 22nd sanctions package on Russia presented in Brussels.
- Hormuz: three tankers struck; attacks at their highest level since the war.
- Chess: World Championship Game 1 begins in Geneva, Gukesh vs Sindarov.
- FIFA: 2031 Women's World Cup to USA/Mexico/Costa Rica/Jamaica; 2035 to the UK.
- UN: autonomous-weapons talks end with no binding treaty.
"""
import math
import os
import struct
import tempfile
import zlib

PAGE_W = 1024
PAGE_H = 1024

# Palette: (red, green, blue) triples.
PAPER = (247, 243, 232)
INK = (17, 17, 17)
CRIMSON = (163, 30, 34)
NAVY = (51, 80, 107)
SLATE = (90, 107, 122)
PANEL_BLUE = (216, 223, 227)
PANEL_CREAM = (233, 227, 211)
CHARCOAL = (38, 48, 58)
ASH = (122, 122, 116)
EMBER = (214, 110, 30)
GILT = (198, 146, 0)
LEAF = (46, 125, 50)
WAVE = (72, 112, 148)
PALE_SKY = (168, 190, 206)
SNOW = (250, 248, 242)
FLAME_YELLOW = (232, 196, 64)
GRID_GREY = (200, 206, 210)
EU_BLUE = (38, 56, 120)
BALL_BLUE = (40, 52, 78)
SEA_BLUE = (44, 62, 84)
SHIP_BLUE = (58, 84, 108)


# ---------------------------------------------------------------- raster
class Sheet:
    """A flat RGB surface with simple drawing primitives."""

    def __init__(self, width, height, background):
        self.w = width
        self.h = height
        self.pixels = bytearray(bytes(background) * (width * height))

    def dot(self, x, y, colour):
        if 0 <= x < self.w and 0 <= y < self.h:
            off = (y * self.w + x) * 3
            self.pixels[off] = colour[0]
            self.pixels[off + 1] = colour[1]
            self.pixels[off + 2] = colour[2]

    def rect(self, x, y, w, h, colour):
        x0 = x if x > 0 else 0
        y0 = y if y > 0 else 0
        x1 = x + w
        if x1 > self.w:
            x1 = self.w
        y1 = y + h
        if y1 > self.h:
            y1 = self.h
        if x1 <= x0 or y1 <= y0:
            return
        span = bytes(colour) * (x1 - x0)
        for yy in range(y0, y1):
            off = (yy * self.w + x0) * 3
            self.pixels[off:off + len(span)] = span

    def border(self, x, y, w, h, colour, thick=1):
        self.rect(x, y, w, thick, colour)
        self.rect(x, y + h - thick, w, thick, colour)
        self.rect(x, y, thick, h, colour)
        self.rect(x + w - thick, y, thick, h, colour)

    def hseg(self, x, y, length, colour):
        self.rect(x, y, length, 1, colour)

    def vseg(self, x, y, length, colour):
        self.rect(x, y, 1, length, colour)

    def bres(self, x0, y0, x1, y1, colour, thick=1):
        """Bresenham segment, drawn as thick square stamps."""
        dx = x1 - x0
        dy = y1 - y0
        stepx = 1 if dx > 0 else -1
        stepy = 1 if dy > 0 else -1
        dx = abs(dx)
        dy = abs(dy)
        half = thick // 2
        if dx >= dy:
            err = 2 * dy - dx
            x, y = x0, y0
            for _ in range(dx + 1):
                self.rect(x - half, y - half, thick, thick, colour)
                if err >= 0:
                    y += stepy
                    err -= 2 * dx
                err += 2 * dy
                x += stepx
        else:
            err = 2 * dx - dy
            x, y = x0, y0
            for _ in range(dy + 1):
                self.rect(x - half, y - half, thick, thick, colour)
                if err >= 0:
                    x += stepx
                    err -= 2 * dy
                err += 2 * dx
                y += stepy

    def disc(self, cx, cy, radius, colour):
        for dy in range(-radius, radius + 1):
            half = int(math.sqrt(max(0, radius * radius - dy * dy)))
            self.hseg(cx - half, cy + dy, 2 * half + 1, colour)

    def ring(self, cx, cy, radius, colour, thick=2):
        steps = 360
        for i in range(steps):
            theta = 2.0 * math.pi * i / steps
            for k in range(thick):
                r = radius - k
                self.dot(int(cx + r * math.cos(theta)),
                         int(cy + r * math.sin(theta)), colour)

    def fillpoly(self, vertices, colour):
        """Scanline fill: for each scanline, gather edge crossings, fill pairs."""
        edges = []
        n = len(vertices)
        for i in range(n):
            ax, ay = vertices[i]
            bx, by = vertices[(i + 1) % n]
            if ay != by:
                edges.append((ax, ay, bx, by))
        top = min(v[1] for v in vertices)
        bottom = max(v[1] for v in vertices)
        for y in range(top, bottom + 1):
            cuts = []
            for ax, ay, bx, by in edges:
                if (ay <= y < by) or (by <= y < ay):
                    cuts.append(ax + (y - ay) * (bx - ax) / (by - ay))
            cuts.sort()
            for j in range(0, len(cuts) - 1, 2):
                xa = int(cuts[j])
                xb = int(cuts[j + 1])
                self.hseg(xa, y, xb - xa + 1, colour)

    def tri(self, x0, y0, x1, y1, x2, y2, colour):
        self.fillpoly([(x0, y0), (x1, y1), (x2, y2)], colour)


# ---------------------------------------------------------------- 5x7 font
# Each glyph is seven rows; each row is a five-bit integer (bit 4 = leftmost
# column). Written as binary literals so the bitmap is visible at a glance.
GLYPHS = {
    'A': (0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    'B': (0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110),
    'C': (0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110),
    'D': (0b11100, 0b10010, 0b10001, 0b10001, 0b10001, 0b10010, 0b11100),
    'E': (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111),
    'F': (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000),
    'G': (0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01111),
    'H': (0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    'I': (0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    'J': (0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100),
    'K': (0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001),
    'L': (0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111),
    'M': (0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001),
    'N': (0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001),
    'O': (0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    'P': (0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000),
    'Q': (0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101),
    'R': (0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001),
    'S': (0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110),
    'T': (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    'U': (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    'V': (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    'W': (0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010),
    'X': (0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001),
    'Y': (0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100),
    'Z': (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111),
    'a': (0b00000, 0b00000, 0b01110, 0b00001, 0b01111, 0b10001, 0b01111),
    'b': (0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b10001, 0b11110),
    'c': (0b00000, 0b00000, 0b01110, 0b10000, 0b10000, 0b10001, 0b01110),
    'd': (0b00001, 0b00001, 0b01111, 0b10001, 0b10001, 0b10001, 0b01111),
    'e': (0b00000, 0b00000, 0b01110, 0b10001, 0b11111, 0b10000, 0b01110),
    'f': (0b00110, 0b01001, 0b01000, 0b11110, 0b01000, 0b01000, 0b01000),
    'g': (0b00000, 0b01111, 0b10001, 0b10001, 0b01111, 0b00001, 0b01110),
    'h': (0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b10001, 0b10001),
    'i': (0b00100, 0b00000, 0b01100, 0b00100, 0b00100, 0b00100, 0b01110),
    'j': (0b00010, 0b00000, 0b00110, 0b00010, 0b00010, 0b10010, 0b01100),
    'k': (0b10000, 0b10000, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010),
    'l': (0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    'm': (0b00000, 0b00000, 0b11010, 0b10101, 0b10101, 0b10101, 0b10101),
    'n': (0b00000, 0b00000, 0b11110, 0b10001, 0b10001, 0b10001, 0b10001),
    'o': (0b00000, 0b00000, 0b01110, 0b10001, 0b10001, 0b10001, 0b01110),
    'p': (0b00000, 0b00000, 0b11110, 0b10001, 0b10001, 0b11110, 0b10000),
    'q': (0b00000, 0b00000, 0b01111, 0b10001, 0b10001, 0b01111, 0b00001),
    'r': (0b00000, 0b00000, 0b10110, 0b11001, 0b10000, 0b10000, 0b10000),
    's': (0b00000, 0b00000, 0b01111, 0b10000, 0b01110, 0b00001, 0b11110),
    't': (0b01000, 0b01000, 0b11110, 0b01000, 0b01000, 0b01001, 0b00110),
    'u': (0b00000, 0b00000, 0b10001, 0b10001, 0b10001, 0b10011, 0b01101),
    'v': (0b00000, 0b00000, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    'w': (0b00000, 0b00000, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010),
    'x': (0b00000, 0b00000, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001),
    'y': (0b00000, 0b00000, 0b10001, 0b10001, 0b01111, 0b00001, 0b01110),
    'z': (0b00000, 0b00000, 0b11111, 0b00010, 0b00100, 0b01000, 0b11111),
    '0': (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110),
    '1': (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    '2': (0b01110, 0b10001, 0b00001, 0b00110, 0b01000, 0b10000, 0b11111),
    '3': (0b11111, 0b00010, 0b00100, 0b00010, 0b00001, 0b10001, 0b01110),
    '4': (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010),
    '5': (0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110),
    '6': (0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110),
    '7': (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000),
    '8': (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110),
    '9': (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100),
    ' ': (0, 0, 0, 0, 0, 0, 0),
    '.': (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b01100, 0b01100),
    ',': (0b00000, 0b00000, 0b00000, 0b00000, 0b01100, 0b00100, 0b01000),
    ';': (0b00000, 0b01100, 0b01100, 0b00000, 0b01100, 0b00100, 0b01000),
    "'": (0b00100, 0b00100, 0b01000, 0b00000, 0b00000, 0b00000, 0b00000),
    '-': (0b00000, 0b00000, 0b00000, 0b01110, 0b00000, 0b00000, 0b00000),
    ':': (0b00000, 0b01100, 0b01100, 0b00000, 0b01100, 0b01100, 0b00000),
    '!': (0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00000, 0b00100),
    '?': (0b01110, 0b10001, 0b00001, 0b00110, 0b00100, 0b00000, 0b00100),
    '(': (0b00010, 0b00100, 0b01000, 0b01000, 0b01000, 0b00100, 0b00010),
    ')': (0b01000, 0b00100, 0b00010, 0b00010, 0b00010, 0b00100, 0b01000),
    '/': (0b00001, 0b00010, 0b00010, 0b00100, 0b01000, 0b01000, 0b10000),
    '%': (0b11001, 0b11010, 0b00010, 0b00100, 0b01000, 0b01011, 0b10011),
    '+': (0b00000, 0b00100, 0b00100, 0b01110, 0b00100, 0b00100, 0b00000),
    '=': (0b00000, 0b00000, 0b11111, 0b00000, 0b11111, 0b00000, 0b00000),
    '"': (0b01010, 0b01010, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000),
}
BLANK = (0, 0, 0, 0, 0, 0, 0)
CELL_W = 6          # glyph advance in font units (5 pixels + 1 gap)
CELL_H = 7


def measure(text, scale):
    """Pixel width of `text` at `scale` (no trailing gap after the last glyph)."""
    if not text:
        return 0
    return len(text) * CELL_W * scale - scale


def put_text(sh, x, y, text, scale, colour, bold=False):
    """Draw `text` with its top-left corner at (x, y); return pixels used."""
    pen = x
    for ch in text:
        rows = GLYPHS.get(ch, BLANK)
        for r in range(CELL_H):
            bits = rows[r]
            for c in range(5):
                if bits & (1 << (4 - c)):
                    sh.rect(pen + c * scale, y + r * scale, scale, scale, colour)
                    if bold:
                        sh.rect(pen + c * scale + 1, y + r * scale,
                                scale, scale, colour)
        pen += CELL_W * scale
    return pen - x - scale


def put_centred(sh, cx, y, text, scale, colour, bold=False):
    put_text(sh, cx - measure(text, scale) // 2, y, text, scale, colour, bold)


def split_lines(text, scale, maxw):
    """Greedy word wrap; returns a list of lines that fit inside maxw."""
    out = []
    for para in text.split('\n'):
        words = para.split(' ')
        current = ''
        for word in words:
            trial = word if not current else current + ' ' + word
            if measure(trial, scale) <= maxw or not current:
                current = trial
            else:
                out.append(current)
                current = word
        if current:
            out.append(current)
    return out


def put_para(sh, x, y, text, scale, maxw, colour, leading, bold=False):
    """Draw a wrapped paragraph; return the y just below the last line."""
    for line in split_lines(text, scale, maxw):
        put_text(sh, x, y, line, scale, colour, bold)
        y += leading
    return y


# ---------------------------------------------------------------- icons
def _flame(sh, x, y, w, h):
    sh.tri(x, y + h, x + w // 2, y, x + w, y + h, EMBER)
    sh.tri(x + w // 4, y + h, x + w // 2, y + h // 3,
           x + 3 * w // 4, y + h, FLAME_YELLOW)


def _puff(sh, x, y, r, colour=ASH):
    sh.disc(x, y, r, colour)
    sh.disc(x + r, y - r // 2, int(r * 0.8), colour)
    sh.disc(x - r, y - r // 2, int(r * 0.7), colour)


def _backdrop(sh, x, y, s, colour):
    sh.rect(x, y, s, s, colour)
    sh.border(x, y, s, s, INK, 2)


def pic_warship(sh, x, y, s):
    _backdrop(sh, x, y, s, SHIP_BLUE)
    # sea band along the bottom
    sh.rect(x + 3, y + s - 22, s - 6, 19, WAVE)
    sh.hseg(x + 6, y + s - 14, s - 12, SNOW)
    sh.hseg(x + 10, y + s - 8, s - 24, SNOW)
    # hull: a low trapezoid, bow to the right
    sh.fillpoly([(x + 10, y + 38), (x + s - 10, y + 38),
                 (x + s - 18, y + 52), (x + 18, y + 52)], CHARCOAL)
    # superstructure and mast
    sh.rect(x + 22, y + 24, 26, 14, CHARCOAL)
    sh.vseg(x + 34, y + 14, 10, CHARCOAL)
    sh.rect(x + 30, y + 12, 9, 3, CHARCOAL)
    # fire on deck and smoke above it
    _flame(sh, x + 46, y + 8, 15, 26)
    _puff(sh, x + 58, y + 6, 6)
    # a small drone boat closing in from the left
    sh.rect(x + 5, y + s - 30, 13, 4, INK)
    sh.vseg(x + 11, y + s - 36, 6, INK)


def pic_factory(sh, x, y, s):
    _backdrop(sh, x, y, s, PANEL_CREAM)
    # chimney with smoke
    sh.rect(x + 56, y + 14, 9, 48, CHARCOAL)
    _puff(sh, x + 60, y + 8, 6)
    # main hall with a sawtooth roof
    sh.rect(x + 10, y + 36, 44, 26, ASH)
    sh.tri(x + 10, y + 36, x + 21, y + 24, x + 32, y + 36, INK)
    sh.tri(x + 32, y + 36, x + 43, y + 24, x + 54, y + 36, INK)
    for wx in (14, 28, 42):
        sh.rect(x + wx, y + 44, 7, 8, INK)
    # flames licking the base
    _flame(sh, x + 12, y + 50, 14, 14)
    _flame(sh, x + 36, y + 52, 12, 12)


def pic_eu(sh, x, y, s):
    _backdrop(sh, x, y, s, EU_BLUE)
    cx, cy, radius = x + s // 2, y + s // 2, 21
    for i in range(12):
        theta = -math.pi / 2 + i * math.pi / 6
        sx = int(cx + radius * math.cos(theta))
        sy = int(cy + radius * math.sin(theta))
        sh.disc(sx, sy, 3, GILT)
    put_centred(sh, cx, cy - 7, "EU", 2, SNOW, bold=True)


def pic_tanker(sh, x, y, s):
    _backdrop(sh, x, y, s, SEA_BLUE)
    sh.rect(x + 3, y + s - 22, s - 6, 19, WAVE)
    sh.hseg(x + 6, y + s - 14, s - 12, SNOW)
    # hull and stacked containers
    sh.fillpoly([(x + 10, y + 40), (x + s - 10, y + 40),
                 (x + s - 18, y + 56), (x + 18, y + 56)], CHARCOAL)
    sh.rect(x + 14, y + 28, 13, 12, CRIMSON)
    sh.rect(x + 29, y + 28, 13, 12, GILT)
    sh.rect(x + 44, y + 28, 12, 12, SNOW)
    sh.rect(x + 52, y + 18, 8, 10, CHARCOAL)
    _flame(sh, x + 16, y + 8, 13, 20)
    _puff(sh, x + 58, y + 8, 6)


def pic_chess(sh, x, y, s):
    _backdrop(sh, x, y, s, PANEL_CREAM)
    bx, by, cell = x + 12, y + 12, 12
    for r in range(4):
        for c in range(4):
            shade = SNOW if (r + c) % 2 == 0 else CHARCOAL
            sh.rect(bx + c * cell, by + r * cell, cell, cell, shade)
    sh.border(bx, by, 48, 48, INK, 1)
    # white king, top left; black queen, bottom right
    sh.disc(bx + 12, by + 12, 7, SNOW)
    sh.rect(bx + 6, by + 18, 12, 6, SNOW)
    sh.disc(bx + 36, by + 36, 7, INK)
    sh.rect(bx + 30, by + 42, 12, 6, INK)


def pic_ball(sh, x, y, s):
    _backdrop(sh, x, y, s, BALL_BLUE)
    cx, cy = x + s // 2, y + s // 2
    sh.disc(cx, cy, 23, SNOW)
    sh.ring(cx, cy, 23, INK, 2)
    corners = []
    for i in range(5):
        theta = -math.pi / 2 + i * 2 * math.pi / 5
        corners.append((int(cx + 8 * math.cos(theta)),
                        int(cy + 8 * math.sin(theta))))
    sh.fillpoly(corners, INK)
    for i in range(5):
        theta = -math.pi / 2 + i * 2 * math.pi / 5
        sh.bres(int(cx + 8 * math.cos(theta)), int(cy + 8 * math.sin(theta)),
                int(cx + 21 * math.cos(theta)), int(cy + 21 * math.sin(theta)),
                INK, 1)


def pic_robot(sh, x, y, s):
    _backdrop(sh, x, y, s, PANEL_CREAM)
    # head with antenna, red eyes, straight mouth
    sh.rect(x + 16, y + 18, 40, 34, ASH)
    sh.border(x + 16, y + 18, 40, 34, INK, 2)
    sh.vseg(x + s // 2, y + 8, 10, INK)
    sh.disc(x + s // 2, y + 7, 3, CRIMSON)
    sh.disc(x + 26, y + 32, 4, CRIMSON)
    sh.disc(x + 46, y + 32, 4, CRIMSON)
    sh.rect(x + 26, y + 42, 20, 3, INK)
    # no-deal slash across the whole panel
    sh.bres(x + 12, y + 56, x + s - 12, y + 12, CRIMSON, 3)


# ---------------------------------------------------------------- lead art
def lead_picture(sh, x, y, w, h):
    """Nvidia chip on the left, a soaring line chart, caption strip below."""
    sh.rect(x, y, w, h, PANEL_BLUE)
    sh.border(x, y, w, h, INK, 2)

    # --- the chip
    chip = 88
    chip_x, chip_y = x + 22, y + 28
    sh.rect(chip_x, chip_y, chip, chip, CHARCOAL)
    sh.border(chip_x, chip_y, chip, chip, INK, 2)
    sh.rect(chip_x + 18, chip_y + 18, chip - 36, chip - 36, LEAF)
    sh.border(chip_x + 18, chip_y + 18, chip - 36, chip - 36, INK, 1)
    put_centred(sh, chip_x + chip // 2, chip_y + chip // 2 - 7,
                "NVDA", 2, SNOW, bold=True)
    # short connector ticks on all four sides of the chip
    mid = chip // 2 - 3
    for px in (chip_x + 12, chip_x + mid, chip_x + chip - 18):
        sh.rect(px, chip_y - 9, 6, 9, INK)
        sh.rect(px, chip_y + chip, 6, 9, INK)
    for py in (chip_y + 12, chip_y + mid, chip_y + chip - 18):
        sh.rect(chip_x - 9, py, 9, 6, INK)
        sh.rect(chip_x + chip, py, 9, 6, INK)

    # --- the chart
    ax0 = x + 152
    ax1 = x + w - 162
    top = y + 16
    bottom = y + h - 46
    for gy in (top, (top + bottom) // 2, bottom):
        sh.hseg(ax0, gy, ax1 - ax0, GRID_GREY)
    sh.vseg(ax0, top, bottom - top, INK)
    sh.hseg(ax0, bottom, ax1 - ax0, INK)
    points = [(ax0 + 8, bottom - 6), (ax0 + 82, bottom - 16),
              (ax0 + 152, bottom - 30), (ax0 + 222, bottom - 24),
              (ax0 + 300, bottom - 52), (ax0 + 372, bottom - 44),
              (ax0 + 442, bottom - 72), (ax0 + 512, bottom - 100),
              (ax0 + 562, bottom - 116)]
    for i in range(len(points) - 1):
        sh.bres(points[i][0], points[i][1],
                points[i + 1][0], points[i + 1][1], LEAF, 4)
    ex, ey = points[-1]
    sh.tri(ex - 4, ey + 14, ex + 16, ey - 2, ex - 2, ey - 12, LEAF)
    sh.disc(ex, ey, 5, LEAF)
    put_text(sh, ax1 + 8, top + 4, "+31%", 4, LEAF, bold=True)
    put_text(sh, ax1 + 8, top + 40, "IN ONE", 2, INK, bold=True)
    put_text(sh, ax1 + 8, top + 56, "DAY", 2, INK, bold=True)

    # --- caption strip
    sh.rect(x, y + h - 26, w, 26, INK)
    put_centred(sh, x + w // 2, y + h - 21,
                "Wall Street roars back: Nasdaq up 6.5% as AI stocks rally.",
                2, SNOW)


# ---------------------------------------------------------------- stories
# (kicker, body, icon painter) — the eighth slot is the by-the-numbers box.
STORIES = [
    ("LIBYA: WARSHIP SUNK",
     "Ukrainian sea drones sink the Russian corvette Merkury at Benghazi; Angara hit too.",
     pic_warship),
    ("INDONESIA: 24 DEAD IN FACTORY FIRE",
     "Rescuers search the burned factory in Cikande; about 30 still missing.",
     pic_factory),
    ("EU: 22ND SANCTIONS PACKAGE",
     "Brussels unveils new curbs on Russia: 60 banks off SWIFT and 70 shadow-fleet ships listed.",
     pic_eu),
    ("HORMUZ: THREE TANKERS HIT",
     "Shipping attacks in the Strait of Hormuz at their highest level since the war began.",
     pic_tanker),
    ("CHESS: WORLD TITLE MATCH BEGINS",
     "Gukesh defends his crown against Sindarov in Geneva, the youngest title match ever.",
     pic_chess),
    ("FIFA: WOMEN'S WORLD CUP HOSTS",
     "2031 goes to the USA, Mexico, Costa Rica and Jamaica; the UK hosts in 2035.",
     pic_ball),
    ("ROBOT RULES: NO DEAL IN GENEVA",
     "UN talks on autonomous weapons end with no binding treaty; talks run on to 2028.",
     pic_robot),
    (None, None, None),
]

NUMBERS = [
    ("24", "dead in the Cikande factory fire"),
    ("31%", "rise in Nvidia shares in a day"),
    ("7", "sea drones in the Benghazi raid"),
    ("60", "banks cut from SWIFT by the EU"),
]


def story_card(sh, x, y, w, h, kicker, body, painter):
    painter(sh, x, y, 72)
    tx = x + 72 + 10
    tw = w - 72 - 10
    after_head = put_para(sh, tx, y + 1, kicker, 3, tw, INK, 23, bold=True)
    put_para(sh, tx, after_head + 2, body, 2, tw, INK, 15)


def numbers_card(sh, x, y, w, h):
    sh.rect(x, y, w, h, PANEL_CREAM)
    sh.border(x, y, w, h, INK, 2)
    put_text(sh, x + 12, y + 8, "BY THE NUMBERS", 3, CRIMSON, bold=True)
    ny = y + 30
    for figure, label in NUMBERS:
        put_text(sh, x + 12, ny, figure, 2, CRIMSON, bold=True)
        put_text(sh, x + 12 + 48, ny, label, 2, INK)
        ny += 15


# ---------------------------------------------------------------- compose
MARGIN = 40
CONTENT_W = PAGE_W - 2 * MARGIN


def compose():
    sh = Sheet(PAGE_W, PAGE_H, PAPER)

    # ---- masthead
    put_centred(sh, PAGE_W // 2, 24, "THE WORLD TODAY", 10, INK, bold=True)
    sh.rect(MARGIN, 104, CONTENT_W, 4, INK)
    sh.rect(MARGIN, 112, CONTENT_W, 1, INK)

    # ---- date line
    put_centred(sh, PAGE_W // 2, 124, "TUESDAY 24 NOVEMBER 2026", 4,
                CRIMSON, bold=True)
    put_text(sh, MARGIN, 130, "WORLD EDITION", 2, SLATE)
    right_label = "NO. 24 NOV"
    put_text(sh, PAGE_W - MARGIN - measure(right_label, 2), 130,
             right_label, 2, SLATE)

    # ---- lead story
    put_centred(sh, PAGE_W // 2, 164, "MARKETS - NEW YORK", 3, CRIMSON, bold=True)
    put_centred(sh, PAGE_W // 2, 192, "HUANG IS BACK", 9, INK, bold=True)
    put_centred(sh, PAGE_W // 2, 256, "NVIDIA SOARS 31%", 9, CRIMSON, bold=True)
    put_para(sh, MARGIN, 330,
             "Nvidia reinstated Jensen Huang as chief executive on Monday, "
             "11 days after he resigned. Shares jumped 31 percent and lifted "
             "markets worldwide.",
             3, CONTENT_W, INK, 26)

    # ---- lead picture
    lead_picture(sh, MARGIN, 416, CONTENT_W, 142)
    sh.rect(MARGIN, 570, CONTENT_W, 2, INK)

    # ---- supporting stories: two columns, four rows
    col_w = (CONTENT_W - 24) // 2
    row_h = 96
    grid_y = 580
    for idx, (kicker, body, painter) in enumerate(STORIES):
        col = idx % 2
        row = idx // 2
        bx = MARGIN + col * (col_w + 24)
        by = grid_y + row * row_h
        if kicker is None:
            numbers_card(sh, bx, by, col_w, row_h - 4)
        else:
            story_card(sh, bx, by, col_w, row_h - 4, kicker, body, painter)

    # ---- footer
    sh.rect(MARGIN, 974, CONTENT_W, 2, INK)
    put_centred(sh, PAGE_W // 2, 982,
                "THE WORLD TODAY - TUESDAY 24 NOVEMBER 2026", 2, INK, bold=True)
    return sh


# ---------------------------------------------------------------- PNG writer
def _chunk(kind, payload):
    body = kind + payload
    return (struct.pack('>I', len(payload)) + body +
            struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF))


def encode_png(sh):
    scanlines = bytearray()
    for y in range(PAGE_H):
        scanlines.append(0)
        start = y * PAGE_W * 3
        scanlines += sh.pixels[start:start + PAGE_W * 3]
    header = struct.pack('>IIBBBBB', PAGE_W, PAGE_H, 8, 2, 0, 0, 0)
    png = b'\x89PNG\r\n\x1a\n'
    png += _chunk(b'IHDR', header)
    png += _chunk(b'IDAT', zlib.compress(bytes(scanlines), 9))
    png += _chunk(b'IEND', b'')
    return png


# ---------------------------------------------------------------- entry point
def main():
    outdir = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    os.makedirs(outdir, exist_ok=True)
    target = os.path.join(outdir, 'entry.png')
    data = encode_png(compose())
    fd, tmp = tempfile.mkstemp(dir=outdir, prefix='.entry-', suffix='.png')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


if __name__ == '__main__':
    main()
