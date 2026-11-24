#!/usr/bin/env python3
"""news-image-20261124 — front page of THE WORLD TODAY for Tuesday 24 November 2026.

Pure standard library. Draws a 1024x1024 broadsheet front page with a hand-made
5x7 stroke font and a hand-encoded PNG (zlib + struct, no Pillow).
Deterministic: no time, no randomness, fixed iteration order.

Stories (all verified from reporting on 24 Nov 2026):
- Lead: Nvidia reinstates Jensen Huang as CEO; shares jump 31 percent.
- Libya: Ukrainian sea drones sink the Russian corvette Merkury at Benghazi.
- Indonesia: 24 dead confirmed in the Cikande candy factory fire, about 30 missing.
- EU: 22nd sanctions package on Russia presented in Brussels.
- Hormuz: three tankers struck; attacks at their highest level since the war began.
- Chess: World Championship Game 1 begins in Geneva, Gukesh vs Sindarov.
- FIFA: 2031 Women's World Cup to USA/Mexico/Costa Rica/Jamaica; 2035 to the UK.
- UN: autonomous-weapons talks end with no binding treaty.
"""
import math
import os
import struct
import tempfile
import zlib

W, H = 1024, 1024

PAPER = (247, 243, 232)
INK = (17, 17, 17)
RED = (163, 30, 34)
BLUE = (51, 80, 107)
MUTED = (90, 107, 122)
PANEL = (216, 223, 227)
PANEL2 = (233, 227, 211)
DARK = (38, 48, 58)
GREY = (122, 122, 116)
ORANGE = (214, 110, 30)
GOLD = (198, 146, 0)
GREEN = (46, 125, 50)
SEA = (72, 112, 148)
SKY = (168, 190, 206)
WHITE = (250, 248, 242)
YELLOW = (232, 196, 64)


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self):
        self.buf = bytearray(bytes(PAPER) * (W * H))

    def set(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            i = (y * W + x) * 3
            self.buf[i] = c[0]
            self.buf[i + 1] = c[1]
            self.buf[i + 2] = c[2]

    def fill_rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(W, x + w)
        y1 = min(H, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * W + x0) * 3
            self.buf[i:i + len(row)] = row

    def rect_outline(self, x, y, w, h, c, t=1):
        self.fill_rect(x, y, w, t, c)
        self.fill_rect(x, y + h - t, w, t, c)
        self.fill_rect(x, y, t, h, c)
        self.fill_rect(x + w - t, y, t, h, c)

    def hline(self, x, y, w, c):
        self.fill_rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.fill_rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            self.fill_rect(x - t // 2, y - t // 2, t, t, c)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, c):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.hline(cx - dx, cy + dy, 2 * dx + 1, c)

    def ring(self, cx, cy, r, c, t=2):
        for a in range(0, 360, 1):
            rad = math.radians(a)
            for k in range(t):
                self.set(int(cx + (r - k) * math.cos(rad)),
                         int(cy + (r - k) * math.sin(rad)), c)

    def ellipse(self, cx, cy, rx, ry, c):
        for dy in range(-ry, ry + 1):
            if ry == 0:
                continue
            dx = int(rx * math.sqrt(max(0.0, 1.0 - (dy * dy) / float(ry * ry))))
            self.hline(cx - dx, cy + dy, 2 * dx + 1, c)

    def poly(self, pts, c):
        ys = [p[1] for p in pts]
        for y in range(min(ys), max(ys) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if y0 == y1:
                    continue
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.hline(int(xs[i]), y, int(xs[i + 1]) - int(xs[i]) + 1, c)

    def triangle(self, x0, y0, x1, y1, x2, y2, c):
        self.poly([(x0, y0), (x1, y1), (x2, y2)], c)


# ---------------------------------------------------------------- 5x7 font
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    'a': ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    'b': ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    'c': ("00000", "00000", "01110", "10000", "10000", "10001", "01110"),
    'd': ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    'e': ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    'f': ("00110", "01001", "01000", "11110", "01000", "01000", "01000"),
    'g': ("00000", "01111", "10001", "10001", "01111", "00001", "01110"),
    'h': ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    'i': ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    'j': ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    'k': ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    'l': ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    'm': ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    'n': ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    'o': ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    'p': ("00000", "00000", "11110", "10001", "10001", "11110", "10000"),
    'q': ("00000", "00000", "01111", "10001", "10001", "01111", "00001"),
    'r': ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    's': ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    't': ("01000", "01000", "11110", "01000", "01000", "01001", "00110"),
    'u': ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    'v': ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    'w': ("00000", "00000", "10001", "10101", "10101", "10101", "01010"),
    'x': ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    'y': ("00000", "00000", "10001", "10001", "01111", "00001", "01110"),
    'z': ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    '0': ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    '3': ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    '4': ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    '5': ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    '7': ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    '8': ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    '9': ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '.': ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ',': ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '-': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    ':': ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '?': ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    '(': ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ')': ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    '/': ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    '%': ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    '+': ("00000", "00100", "00100", "01110", "00100", "00100", "00000"),
    '=': ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
}


def text_width(s, scale):
    return len(s) * 6 * scale


def draw_text(cv, x, y, s, scale, color, bold=False):
    dx = 1 if scale < 6 else 2
    cx = x
    for ch in s:
        g = FONT.get(ch, FONT[' '])
        for r in range(7):
            row = g[r]
            for cc in range(5):
                if row[cc] == '1':
                    cv.fill_rect(cx + cc * scale, y + r * scale, scale, scale, color)
                    if bold:
                        cv.fill_rect(cx + cc * scale + dx, y + r * scale, scale, scale, color)
        cx += 6 * scale
    return cx - x


def draw_centered(cv, cx, y, s, scale, color, bold=False):
    w = text_width(s, scale)
    draw_text(cv, cx - w // 2, y, s, scale, color, bold)


def wrap(text, scale, maxw):
    lines = []
    for para in text.split('\n'):
        words = para.split(' ')
        cur = ''
        for wd in words:
            trial = wd if not cur else cur + ' ' + wd
            if text_width(trial, scale) <= maxw or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
    return lines


def draw_block(cv, x, y, text, scale, maxw, color, line_h, bold=False):
    lines = wrap(text, scale, maxw)
    for ln in lines:
        draw_text(cv, x, y, ln, scale, color, bold)
        y += line_h
    return y


# ---------------------------------------------------------------- scenes
def flame(cv, x, y, w, h):
    cv.triangle(x, y + h, x + w // 2, y, x + w, y + h, ORANGE)
    cv.triangle(x + w // 4, y + h, x + w // 2, y + h // 3, x + 3 * w // 4, y + h, YELLOW)


def smoke(cv, x, y, r, color=GREY):
    cv.circle(x, y, r, color)
    cv.circle(x + r, y - r // 2, int(r * 0.8), color)
    cv.circle(x - r, y - r // 2, int(r * 0.7), color)


def draw_lead_panel(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PANEL)
    cv.rect_outline(x, y, w, h, INK, 2)
    # --- chip on the left
    chip_x, chip_y, chip_s = x + 24, y + 30, 84
    cv.fill_rect(chip_x, chip_y, chip_s, chip_s, DARK)
    cv.rect_outline(chip_x, chip_y, chip_s, chip_s, INK, 2)
    cv.fill_rect(chip_x + 16, chip_y + 16, chip_s - 32, chip_s - 32, GREEN)
    cv.rect_outline(chip_x + 16, chip_y + 16, chip_s - 32, chip_s - 32, INK, 1)
    draw_centered(cv, chip_x + chip_s // 2, chip_y + chip_s // 2 - 7, "NVDA", 2, WHITE, bold=True)
    for px in (chip_x + 10, chip_x + chip_s // 2 - 3, chip_x + chip_s - 16):
        cv.fill_rect(px, chip_y - 10, 6, 10, INK)
        cv.fill_rect(px, chip_y + chip_s, 6, 10, INK)
    for py in (chip_y + 10, chip_y + chip_s // 2 - 3, chip_y + chip_s - 16):
        cv.fill_rect(chip_x - 10, py, 10, 6, INK)
        cv.fill_rect(chip_x + chip_s, py, 10, 6, INK)
    # --- rising chart on the right
    cx0, cx1 = x + 170, x + w - 150
    cy_top, cy_bot = y + 18, y + h - 44
    for gy in (cy_top, (cy_top + cy_bot) // 2, cy_bot):
        cv.hline(cx0, gy, cx1 - cx0, (200, 206, 210))
    cv.vline(cx0, cy_top, cy_bot - cy_top, INK)
    cv.hline(cx0, cy_bot, cx1 - cx0, INK)
    pts = [(cx0 + 10, cy_bot - 8), (cx0 + 90, cy_bot - 22),
           (cx0 + 170, cy_bot - 18), (cx0 + 250, cy_bot - 52),
           (cx0 + 330, cy_bot - 48), (cx0 + 410, cy_bot - 78),
           (cx0 + 480, cy_bot - 96), (cx0 + 540, cy_bot - 118)]
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], GREEN, 4)
    ex, ey = pts[-1]
    cv.triangle(ex - 4, ey + 14, ex + 16, ey - 2, ex - 2, ey - 12, GREEN)
    cv.circle(ex, ey, 5, GREEN)
    draw_text(cv, cx1 + 8, cy_top + 6, "+31%", 4, GREEN, bold=True)
    draw_text(cv, cx1 + 8, cy_top + 42, "IN ONE", 2, INK, bold=True)
    draw_text(cv, cx1 + 8, cy_top + 58, "DAY", 2, INK, bold=True)
    # --- caption strip
    cv.fill_rect(x, y + h - 26, w, 26, INK)
    draw_centered(cv, x + w // 2, y + h - 21,
                  "Wall Street roars back: Nasdaq up 6.5% as AI stocks rally.",
                  2, WHITE)


def icon_frame(cv, x, y, s, bg):
    cv.fill_rect(x, y, s, s, bg)
    cv.rect_outline(x, y, s, s, INK, 2)


def icon_warship(cv, x, y, s):
    icon_frame(cv, x, y, s, (58, 84, 108))
    cv.fill_rect(x + 3, y + s - 24, s - 6, 21, SEA)
    cv.line(x + 6, y + s - 16, x + s - 6, y + s - 16, WHITE, 1)
    cv.line(x + 6, y + s - 10, x + s - 10, y + s - 10, WHITE, 1)
    # grey hull and tower
    cv.poly([(x + 8, y + 38), (x + s - 8, y + 38), (x + s - 16, y + 54),
             (x + 16, y + 54)], DARK)
    cv.fill_rect(x + 24, y + 24, 24, 14, DARK)
    cv.fill_rect(x + 28, y + 16, 5, 8, DARK)
    cv.fill_rect(x + 40, y + 18, 5, 6, DARK)
    # explosion on deck
    flame(cv, x + 44, y + 8, 16, 28)
    smoke(cv, x + 56, y + 6, 6)
    # small drone boat approaching
    cv.fill_rect(x + 6, y + s - 30, 12, 4, INK)


def icon_factory(cv, x, y, s):
    icon_frame(cv, x, y, s, PANEL2)
    cv.fill_rect(x + 12, y + 34, 46, 28, GREY)
    cv.poly([(x + 12, y + 34), (x + 24, y + 22), (x + 36, y + 34)], INK)
    cv.poly([(x + 36, y + 34), (x + 48, y + 22), (x + 58, y + 34)], INK)
    cv.fill_rect(x + 16, y + 42, 8, 8, INK)
    cv.fill_rect(x + 30, y + 42, 8, 8, INK)
    cv.fill_rect(x + 44, y + 42, 8, 8, INK)
    cv.fill_rect(x + 58, y + 16, 8, 46, DARK)
    smoke(cv, x + 62, y + 10, 6)
    flame(cv, x + 14, y + 48, 16, 16)
    flame(cv, x + 38, y + 52, 12, 12)


def icon_eu(cv, x, y, s):
    icon_frame(cv, x, y, s, (38, 56, 120))
    cx, cy, r = x + s // 2, y + s // 2, 22
    for i in range(12):
        ang = -math.pi / 2 + i * math.pi / 6
        sx = int(cx + r * math.cos(ang))
        sy = int(cy + r * math.sin(ang))
        cv.circle(sx, sy, 3, GOLD)
    draw_centered(cv, cx, cy - 7, "EU", 2, WHITE, bold=True)


def icon_tanker(cv, x, y, s):
    icon_frame(cv, x, y, s, (44, 62, 84))
    cv.fill_rect(x + 3, y + s - 24, s - 6, 21, SEA)
    cv.line(x + 6, y + s - 16, x + s - 6, y + s - 16, WHITE, 1)
    # tanker hull and containers
    cv.poly([(x + 8, y + 40), (x + s - 8, y + 40), (x + s - 16, y + 56),
             (x + 16, y + 56)], DARK)
    cv.fill_rect(x + 14, y + 28, 14, 12, RED)
    cv.fill_rect(x + 30, y + 28, 14, 12, GOLD)
    cv.fill_rect(x + 46, y + 28, 12, 12, WHITE)
    cv.fill_rect(x + 52, y + 18, 8, 10, DARK)
    flame(cv, x + 18, y + 8, 14, 20)
    smoke(cv, x + 58, y + 8, 6)


def icon_chess(cv, x, y, s):
    icon_frame(cv, x, y, s, PANEL2)
    bx, by = x + 12, y + 12
    cell = 12
    for r in range(4):
        for c in range(4):
            col = WHITE if (r + c) % 2 == 0 else DARK
            cv.fill_rect(bx + c * cell, by + r * cell, cell, cell, col)
    cv.rect_outline(bx, by, 48, 48, INK, 1)
    # white king on the left, black queen on the right
    cv.circle(bx + 12, by + 12, 7, WHITE)
    cv.fill_rect(bx + 6, by + 18, 12, 6, WHITE)
    cv.circle(bx + 36, by + 36, 7, INK)
    cv.fill_rect(bx + 30, by + 42, 12, 6, INK)


def icon_soccer(cv, x, y, s):
    icon_frame(cv, x, y, s, (40, 52, 78))
    cx, cy = x + s // 2, y + s // 2
    cv.circle(cx, cy, 24, WHITE)
    cv.ring(cx, cy, 24, INK, 2)
    pts = []
    for i in range(5):
        ang = -math.pi / 2 + i * 2 * math.pi / 5
        pts.append((int(cx + 9 * math.cos(ang)), int(cy + 9 * math.sin(ang))))
    cv.poly(pts, INK)
    for ang in (-math.pi / 2, -math.pi / 2 + 2 * math.pi / 5,
                -math.pi / 2 + 4 * math.pi / 5, -math.pi / 2 + 6 * math.pi / 5,
                -math.pi / 2 + 8 * math.pi / 5):
        cv.line(cx + int(9 * math.cos(ang)), cy + int(9 * math.sin(ang)),
                cx + int(22 * math.cos(ang)), cy + int(22 * math.sin(ang)), INK, 1)


def icon_robot(cv, x, y, s):
    icon_frame(cv, x, y, s, PANEL2)
    # robot head, no deal: red slash across it
    cv.fill_rect(x + 16, y + 18, 40, 34, GREY)
    cv.rect_outline(x + 16, y + 18, 40, 34, INK, 2)
    cv.vline(x + s // 2, y + 8, 10, INK)
    cv.circle(x + s // 2, y + 7, 3, RED)
    cv.circle(x + 26, y + 32, 4, RED)
    cv.circle(x + 46, y + 32, 4, RED)
    cv.fill_rect(x + 26, y + 42, 20, 3, INK)
    cv.line(x + 12, y + 56, x + s - 12, y + 12, RED, 3)


# ---------------------------------------------------------------- layout
M = 36
CW = W - 2 * M


def build():
    cv = Canvas()

    # ---- masthead
    draw_centered(cv, W // 2, 26, "THE WORLD TODAY", 10, INK, bold=True)
    cv.fill_rect(M, 106, CW, 4, INK)
    cv.fill_rect(M, 114, CW, 1, INK)

    # ---- date line
    draw_centered(cv, W // 2, 126, "TUESDAY 24 NOVEMBER 2026", 4, RED, bold=True)
    draw_text(cv, M, 132, "WORLD EDITION", 2, MUTED)
    draw_text(cv, W - M - text_width("NO. 24 NOV", 2), 132, "NO. 24 NOV", 2, MUTED)

    # ---- lead story
    draw_centered(cv, W // 2, 166, "MARKETS - NEW YORK", 3, RED, bold=True)
    draw_centered(cv, W // 2, 194, "HUANG IS BACK", 9, INK, bold=True)
    draw_centered(cv, W // 2, 258, "NVIDIA SOARS 31%", 9, RED, bold=True)
    draw_block(cv, M, 332,
               "Nvidia reinstated Jensen Huang as chief executive on Monday, "
               "11 days after he resigned. Shares jumped 31 percent and lifted "
               "markets worldwide.",
               3, CW, INK, 25)

    # ---- lead picture panel
    draw_lead_panel(cv, M, 418, CW, 140)
    cv.fill_rect(M, 570, CW, 2, INK)

    # ---- supporting stories: 2 columns x 4 rows
    stories = [
        ("LIBYA: WARSHIP SUNK",
         "Ukrainian sea drones sink the Russian corvette Merkury at Benghazi; Angara hit too.",
         icon_warship),
        ("INDONESIA: 24 DEAD IN FACTORY FIRE",
         "Rescuers search the burned factory in Cikande; about 30 still missing.",
         icon_factory),
        ("EU: 22ND SANCTIONS PACKAGE",
         "Brussels unveils new curbs on Russia: 60 banks off SWIFT and 70 shadow-fleet ships listed.",
         icon_eu),
        ("HORMUZ: THREE TANKERS HIT",
         "Shipping attacks in the Strait of Hormuz at their highest level since the war began.",
         icon_tanker),
        ("CHESS: WORLD TITLE MATCH BEGINS",
         "Gukesh defends his crown against Sindarov in Geneva, the youngest title match ever.",
         icon_chess),
        ("FIFA: WOMEN'S WORLD CUP HOSTS",
         "2031 goes to the USA, Mexico, Costa Rica and Jamaica; the UK hosts in 2035.",
         icon_soccer),
        ("ROBOT RULES: NO DEAL IN GENEVA",
         "UN talks on autonomous weapons end with no binding treaty; talks run on to 2028.",
         icon_robot),
        (None, None, None),  # by-the-numbers box
    ]
    col_w = (CW - 24) // 2
    row_h = 96
    gy0 = 582
    for idx, (head, body, icon) in enumerate(stories):
        col = idx % 2
        row = idx // 2
        bx = M + col * (col_w + 24)
        by = gy0 + row * row_h
        if head is None:
            cv.fill_rect(bx, by, col_w, row_h - 4, PANEL2)
            cv.rect_outline(bx, by, col_w, row_h - 4, INK, 2)
            draw_text(cv, bx + 12, by + 8, "BY THE NUMBERS", 3, RED, bold=True)
            nums = [("24", "dead in the Cikande factory fire"),
                    ("31%", "rise in Nvidia shares in a day"),
                    ("7", "sea drones in the Benghazi raid"),
                    ("60", "banks cut from SWIFT by the EU")]
            ny = by + 32
            for n, t in nums:
                draw_text(cv, bx + 12, ny, n, 2, RED, bold=True)
                draw_text(cv, bx + 12 + 48, ny, t, 2, INK)
                ny += 13
            continue
        icon(cv, bx, by, 72)
        tx = bx + 72 + 10
        tw = col_w - 72 - 10
        y = draw_block(cv, tx, by + 1, head, 3, tw, INK, 23, bold=True)
        draw_block(cv, tx, y + 2, body, 2, tw, INK, 15)

    # ---- footer
    fy = 976
    cv.fill_rect(M, fy, CW, 2, INK)
    draw_centered(cv, W // 2, fy + 8,
                  "THE WORLD TODAY - TUESDAY 24 NOVEMBER 2026", 2, INK, bold=True)
    return cv


def encode_png(cv):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += cv.buf[y * W * 3:(y + 1) * W * 3]

    def chunk(ctype, data):
        c = ctype + data
        return (struct.pack('>I', len(data)) + c +
                struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))

    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    png += chunk(b'IEND', b'')
    return png


def main():
    outdir = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, 'entry.png')
    cv = build()
    data = encode_png(cv)
    fd, tmp = tempfile.mkstemp(dir=outdir, prefix='.entry-', suffix='.png')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


if __name__ == '__main__':
    main()
