#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PATITAS YA - Video de presentacion de 15 segundos
Vertical 1080x1920 - 30 fps - sin audio

Todo (fondos, perritos, gatitos, iconos y textos) se dibuja con codigo usando
Cairo y se une en un MP4 con FFmpeg. No usa imagenes ni clips externos.

Como usarlo:
    python3 patitas_video.py              -> crea patitas-ya-15s.mp4
    python3 patitas_video.py --preview    -> guarda fotogramas de control en previews/
"""

# =====================================================================
#  NUMERO DE WHATSAPP  ->  cambia solo lo que esta entre comillas
# =====================================================================
WHATSAPP_NUMERO = "[ACÁ VA EL NÚMERO]"

# =====================================================================
#  TEXTOS DEL VIDEO  ->  podes editarlos libremente.
#  Si una frase queda mas larga, la letra se achica sola para no cortarse.
# =====================================================================
TEXTOS = {
    # Escena 1 (0-3 s)
    "marca_1": "Patitas",
    "marca_2": "Ya",
    "sello": "NUEVO",
    "frase_intro": "La forma nueva de cuidar a tu mascota.",
    "palabra_resaltada": "nueva",            # palabra marcada con resaltador
    # Escena 2 (3-9 s): (linea grande, linea en etiqueta). Usa "" si no va etiqueta.
    "titulo_servicios": "NUESTROS SERVICIOS",
    "servicio_1": ("Veterinaria", "a domicilio"),
    "servicio_2": ("Baños", ""),
    "servicio_3": ("Peluquería", "animal"),
    # Escena 3 (9-12 s)
    "contacto_1": "Un solo contacto,",
    "contacto_2": "todo resuelto.",
    "opcion_1": ("Lo buscamos", "nosotros"),
    "opcion_2": ("Vos nos lo", "llevás"),
    "separador": "o",
    "pronto": "Muy pronto: paseos y petshop",
    # Escena 4 (12-15 s)
    "web": "patitasya.com.ar",
    "whatsapp": "WhatsApp: " + WHATSAPP_NUMERO,
}

ARCHIVO_SALIDA = "patitas-ya-15s.mp4"

# =====================================================================
#  De aca para abajo esta el motor del video (no hace falta tocarlo).
# =====================================================================
import argparse
import math
import os
import random
import subprocess
import sys
import time
from contextlib import contextmanager

import cairo
import uharfbuzz as hb

W, H, FPS = 1080, 1920, 30
TOTAL = 15 * FPS                      # 450 fotogramas = 15 s exactos
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
SAFE = (100, 240, 980, 1560)          # zona segura para textos (x0, y0, x1, y1)

# Paleta
DARK, MID, LIGHT, MINT, WHITE = "#14532D", "#22A559", "#86EFAC", "#DCFCE7", "#FFFFFF"
DEEP = "#0B3A1E"                      # verde muy oscuro, solo para sombras

TAU = 2 * math.pi


# ---------------------------------------------------------------- utilidades
def rgba(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def src(ctx, color, a=1.0):
    ctx.set_source_rgba(*rgba(color, a))


def fill(ctx, color, a=1.0):
    src(ctx, color, a)
    ctx.fill()


def stroke(ctx, color, width, a=1.0, cap=cairo.LINE_CAP_ROUND):
    src(ctx, color, a)
    ctx.set_line_width(width)
    ctx.set_line_cap(cap)
    ctx.stroke()


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def lerp(a, b, k):
    return a + (b - a) * k


def prog(t, start, dur):
    """Progreso 0..1 de una animacion que arranca en `start` y dura `dur` fotogramas."""
    return clamp((t - start) / dur)


def ease_out_cubic(x):
    return 1 - (1 - x) ** 3


def ease_in_out_cubic(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x, s=1.9):
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def spring(x, damping=5.5, freq=1.6):
    """0 -> 1 con rebote elastico."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    return 1 - math.exp(-damping * x) * math.cos(freq * TAU * x)


def pop(t, start, dur=10):
    p = prog(t, start, dur)
    return ease_out_back(p) if p > 0 else 0.0


def bump(t, t0, dur):
    p = (t - t0) / dur
    return math.sin(math.pi * p) if 0 < p < 1 else 0.0


def blinks(t, times, dur=6):
    return max([bump(t, b, dur) for b in times] + [0.0])


@contextmanager
def saved(ctx):
    ctx.save()
    try:
        yield
    finally:
        ctx.restore()


@contextmanager
def group(ctx, alpha=1.0):
    ctx.push_group()
    try:
        yield
    finally:
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(clamp(alpha))


def about(ctx, px, py, sx, sy=None, rot=0.0):
    """Escala/rota alrededor del punto (px, py)."""
    ctx.translate(px, py)
    if rot:
        ctx.rotate(rot)
    ctx.scale(sx, sx if sy is None else sy)
    ctx.translate(-px, -py)


# ---------------------------------------------------------------- formas
def rrect(ctx, x, y, w, h, r):
    r = max(0.0, min(r, w / 2, h / 2))
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def circle(ctx, x, y, r):
    ctx.new_sub_path()
    ctx.arc(x, y, max(r, 0.01), 0, TAU)
    ctx.close_path()


def ellipse(ctx, x, y, rx, ry):
    with saved(ctx):
        ctx.translate(x, y)
        ctx.scale(max(rx, 0.01), max(ry, 0.01))
        ctx.new_sub_path()
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.close_path()


def rounded_poly(ctx, pts):
    """Poligono con todas las esquinas suavizadas (sirve para sellos y estrellas)."""
    n = len(pts)
    mids = [((pts[i][0] + pts[(i + 1) % n][0]) / 2, (pts[i][1] + pts[(i + 1) % n][1]) / 2) for i in range(n)]
    ctx.move_to(*mids[-1])
    for i in range(n):
        p0, c, p1 = mids[i - 1], pts[i], mids[i]
        ctx.curve_to(p0[0] + 2 / 3 * (c[0] - p0[0]), p0[1] + 2 / 3 * (c[1] - p0[1]),
                     p1[0] + 2 / 3 * (c[0] - p1[0]), p1[1] + 2 / 3 * (c[1] - p1[1]), *p1)
    ctx.close_path()


def star4(ctx, x, y, r, rot=0.0, k=0.16):
    """Destello de 4 puntas."""
    if r <= 0.5:
        return
    with saved(ctx):
        ctx.translate(x, y)
        ctx.rotate(rot)
        pts = [(0, -r), (r, 0), (0, r), (-r, 0)]
        ctrl = [(k * r, -k * r), (k * r, k * r), (-k * r, k * r), (-k * r, -k * r)]
        ctx.move_to(*pts[0])
        for i in range(4):
            c = ctrl[i]
            ctx.curve_to(c[0], c[1], c[0], c[1], *pts[(i + 1) % 4])
        ctx.close_path()


def heart(ctx, x, y, s):
    ctx.move_to(x, y + 0.36 * s)
    ctx.curve_to(x - 0.62 * s, y - 0.02 * s, x - 0.36 * s, y - 0.62 * s, x, y - 0.22 * s)
    ctx.curve_to(x + 0.36 * s, y - 0.62 * s, x + 0.62 * s, y - 0.02 * s, x, y + 0.36 * s)
    ctx.close_path()


def sparkle(ctx, x, y, r, color, t=0.0, a=1.0):
    star4(ctx, x, y, r, rot=0.0)
    fill(ctx, color, a)


def polyline_partial(ctx, pts, p):
    """Dibuja (solo el trazo) los primeros p*100 % de una polilinea."""
    if p <= 0:
        return False
    lens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(lens) * p
    ctx.move_to(*pts[0])
    for i, L in enumerate(lens):
        if total >= L:
            ctx.line_to(*pts[i + 1])
            total -= L
        else:
            k = total / L if L else 0
            ctx.line_to(lerp(pts[i][0], pts[i + 1][0], k), lerp(pts[i][1], pts[i + 1][1], k))
            break
    return True


# ---------------------------------------------------------------- texto (Poppins + HarfBuzz)
QA = {"on": False, "boxes": []}


class _Pen:
    """Convierte el contorno de cada letra en curvas para Cairo."""

    def __init__(self):
        self.ops, self.cur, self.start = [], (0, 0), (0, 0)

    def moveTo(self, p):
        self.ops.append(("M", p))
        self.cur = self.start = p

    def lineTo(self, p):
        self.ops.append(("L", p))
        self.cur = p

    def curveTo(self, *pts):
        if len(pts) == 3:
            self.ops.append(("C",) + tuple(pts))
        else:
            for p in pts:
                self.ops.append(("L", p))
        self.cur = pts[-1]

    def qCurveTo(self, *pts):
        offs, end, p0 = pts[:-1], pts[-1], self.cur
        for i, c in enumerate(offs):
            nxt = end if i == len(offs) - 1 else ((c[0] + offs[i + 1][0]) / 2, (c[1] + offs[i + 1][1]) / 2)
            c1 = (p0[0] + 2 / 3 * (c[0] - p0[0]), p0[1] + 2 / 3 * (c[1] - p0[1]))
            c2 = (nxt[0] + 2 / 3 * (c[0] - nxt[0]), nxt[1] + 2 / 3 * (c[1] - nxt[1]))
            self.ops.append(("C", c1, c2, nxt))
            p0 = nxt
        self.cur = end

    def closePath(self):
        self.ops.append(("Z",))
        self.cur = self.start

    def endPath(self):
        pass


class Font:
    def __init__(self, path):
        self.face = hb.Face(hb.Blob.from_file_path(path))
        self.hb = hb.Font(self.face)
        self.upem = self.face.upem
        self._outl, self._shape = {}, {}

    def outline(self, gid):
        if gid not in self._outl:
            pen = _Pen()
            self.hb.draw_glyph_with_pen(gid, pen)
            self._outl[gid] = pen.ops
        return self._outl[gid]

    def shape(self, text):
        if text not in self._shape:
            buf = hb.Buffer()
            buf.add_codepoints([ord(c) for c in text])
            buf.guess_segment_properties()
            hb.shape(self.hb, buf, {"kern": True, "liga": True})
            self._shape[text] = [(i.codepoint, i.cluster, p.x_advance, p.x_offset, p.y_offset)
                                 for i, p in zip(buf.glyph_infos, buf.glyph_positions)]
        return self._shape[text]


_FONT_FILES = {
    "regular": "Poppins-Regular.ttf", "medium": "Poppins-Medium.ttf", "semibold": "Poppins-SemiBold.ttf",
    "bold": "Poppins-Bold.ttf", "extrabold": "Poppins-ExtraBold.ttf", "black": "Poppins-Black.ttf",
}
_FONTS = {}


def get_font(weight):
    if weight not in _FONTS:
        path = os.path.join(FONT_DIR, _FONT_FILES[weight])
        if not os.path.exists(path):
            sys.exit(f"Falta la tipografia {path}. Ver README.md (carpeta fonts/).")
        _FONTS[weight] = Font(path)
    return _FONTS[weight]


def _emit(ctx, ops, ox, oy, sc):
    for op in ops:
        k = op[0]
        if k == "M":
            ctx.move_to(ox + op[1][0] * sc, oy - op[1][1] * sc)
        elif k == "L":
            ctx.line_to(ox + op[1][0] * sc, oy - op[1][1] * sc)
        elif k == "C":
            ctx.curve_to(ox + op[1][0] * sc, oy - op[1][1] * sc, ox + op[2][0] * sc, oy - op[2][1] * sc,
                         ox + op[3][0] * sc, oy - op[3][1] * sc)
        else:
            ctx.close_path()


class Txt:
    """Una linea de texto ya acomodada (con kerning). Se dibuja con efectos por letra o por palabra."""

    def __init__(self, text, weight="black", size=100.0, tracking=0.0):
        self.text, self.size, self.font = text, size, get_font(weight)
        sc = self.sc = size / self.font.upem
        self.glyphs, x = [], 0.0
        for gid, cl, xa, xo, yo in self.font.shape(text):
            self.glyphs.append((gid, x + xo * sc, -yo * sc, cl, xa * sc))
            x += xa * sc + tracking
        self.width = (x - tracking) if self.glyphs else 0.0
        widx, w, prev_space = [], -1, True
        for ch in text:
            if ch.isspace():
                widx.append(-1)
                prev_space = True
            else:
                if prev_space:
                    w += 1
                widx.append(w)
                prev_space = False
        self.nwords = w + 1
        self.gword = [widx[g[3]] if g[3] < len(widx) else -1 for g in self.glyphs]
        self.wspan = {}
        for (gid, gx, gy, cl, adv), wi in zip(self.glyphs, self.gword):
            if wi >= 0:
                a, b = self.wspan.get(wi, (1e9, -1e9))
                self.wspan[wi] = (min(a, gx), max(b, gx + adv))

    def left(self, x, align):
        return x - self.width / 2 if align == "center" else (x - self.width if align == "right" else x)

    def draw(self, ctx, x, y, color, align="center", alpha=1.0, fx=None, pivot="word", label=None):
        """fx(i_letra, i_palabra) -> (escala, dx, dy, alpha, rotacion)."""
        left = self.left(x, align)
        cy = y - 0.36 * self.size
        box = None
        for i, (gid, gx, gy, cl, adv) in enumerate(self.glyphs):
            ops = self.font.outline(gid)
            if not ops:
                continue
            wi = self.gword[i]
            s, dx, dy, a, rot = fx(i, wi) if fx else (1.0, 0.0, 0.0, 1.0, 0.0)
            a *= alpha
            if a <= 0.004 or s <= 0.002:
                continue
            if pivot == "word" and wi in self.wspan:
                px = left + sum(self.wspan[wi]) / 2
            elif pivot == "glyph":
                px = left + gx + adv / 2
            else:
                px = left + self.width / 2
            with saved(ctx):
                ctx.translate(px + dx, cy + dy)
                if rot:
                    ctx.rotate(rot)
                ctx.scale(s, s)
                ctx.translate(-px, -cy)
                ctx.new_path()
                _emit(ctx, ops, left + gx, y + gy, self.sc)
            if QA["on"] and label and a > 0.97 and abs(s - 1) < 0.02:
                with saved(ctx):
                    ctx.identity_matrix()
                    e = ctx.fill_extents()
                box = e if box is None else (min(box[0], e[0]), min(box[1], e[1]), max(box[2], e[2]), max(box[3], e[3]))
            fill(ctx, color, a)
        if box:
            QA["boxes"].append((label, box))


_TXT_CACHE = {}


def T(text, weight="black", size=100.0, tracking=0.0):
    key = (text, weight, round(size, 2), tracking)
    if key not in _TXT_CACHE:
        _TXT_CACHE[key] = Txt(text, weight, size, tracking)
    return _TXT_CACHE[key]


def fit(text, weight, size, max_w, tracking=0.0):
    """Tamano de letra que entra en max_w (achica si hace falta, nunca agranda)."""
    w = T(text, weight, size, tracking).width
    return size if w <= max_w else math.floor(size * max_w / w)


def wrap_fit(text, weight, size, max_w, max_lines):
    """Parte la frase en lineas parejas que entren en max_w (y achica si no entra)."""
    words = text.split()
    while True:
        best = None
        for n in range(1, min(max_lines, len(words)) + 1):
            for cuts in _splits(len(words), n):
                lines = [" ".join(words[a:b]) for a, b in cuts]
                widest = max(T(l, weight, size).width for l in lines)
                if widest <= max_w and (best is None or widest < best[0]):
                    best = (widest, lines)
            if best:
                return best[1], size
        size *= 0.95


def _splits(m, n):
    if n == 1:
        yield [(0, m)]
        return
    for first in range(1, m - n + 2):
        for rest in _splits(m - first, n - 1):
            yield [(0, first)] + [(a + first, b + first) for a, b in rest]


def word_pop(t, start, step, dur=9, rise=26):
    """Efecto: cada palabra aparece con un 'pop' escalonado."""
    def fx(i, wi):
        p = prog(t, start + max(wi, 0) * step, dur)
        return (ease_out_back(p) if p > 0 else 0.0, 0.0, (1 - ease_out_cubic(p)) * rise, clamp(p * 2.5), 0.0)
    return fx


def letter_drop(t, start, step, dur=11, drop=-90):
    def fx(i, wi):
        p = prog(t, start + i * step, dur)
        return (ease_out_back(p) if p > 0 else 0.0, 0.0, (1 - ease_out_cubic(p)) * drop, clamp(p * 3), 0.0)
    return fx


# ---------------------------------------------------------------- fondos y decoracion
def glow(ctx, x, y, r, color, a):
    c = rgba(color)
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    g.add_color_stop_rgba(0, c[0], c[1], c[2], a)
    g.add_color_stop_rgba(1, c[0], c[1], c[2], 0)
    ctx.set_source(g)
    ctx.paint()


def dot_grid(ctx, t, color, a, gap=58, r=2.6, speed=0.6):
    off = (t * speed) % (2 * gap)
    for yy in range(-2, int(H / gap) + 3):
        y = yy * gap - off
        for xx in range(0, int(W / gap) + 1):
            x = xx * gap + (gap / 2 if yy % 2 else 0) + 12
            ctx.new_sub_path()
            ctx.arc(x, y, r, 0, TAU)
    fill(ctx, color, a)


def floaters(ctx, t, color, a, seed, n=10):
    """Formitas geometricas flotando cerca de los bordes."""
    rnd = random.Random(seed)
    for i in range(n):
        kind = ["ring", "plus", "tri", "dot", "sq"][i % 5]
        side = i % 2
        x = rnd.uniform(40, 150) if side == 0 else rnd.uniform(930, 1040)
        y = rnd.uniform(200, 1780)
        sz = rnd.uniform(14, 30)
        ph = rnd.uniform(0, TAU)
        sp = rnd.choice([-1, 1]) * rnd.uniform(0.02, 0.05)
        y += 16 * math.sin(t * 0.08 + ph)
        with saved(ctx):
            ctx.translate(x, y)
            ctx.rotate(ph + t * sp)
            if kind == "ring":
                circle(ctx, 0, 0, sz * 0.7)
                stroke(ctx, color, 5, a)
            elif kind == "plus":
                ctx.move_to(-sz * 0.6, 0); ctx.line_to(sz * 0.6, 0)
                ctx.move_to(0, -sz * 0.6); ctx.line_to(0, sz * 0.6)
                stroke(ctx, color, 6, a)
            elif kind == "tri":
                rounded_poly(ctx, [(0, -sz * 0.7), (sz * 0.65, sz * 0.5), (-sz * 0.65, sz * 0.5)])
                stroke(ctx, color, 5, a)
            elif kind == "dot":
                circle(ctx, 0, 0, sz * 0.35)
                fill(ctx, color, a)
            else:
                rrect(ctx, -sz * 0.5, -sz * 0.5, sz, sz, 5)
                stroke(ctx, color, 5, a)


def dashed_ring(ctx, x, y, r, color, a, w, rot, dash=(16, 20)):
    with saved(ctx):
        ctx.translate(x, y)
        ctx.rotate(rot)
        ctx.set_dash(list(dash))
        circle(ctx, 0, 0, r)
        stroke(ctx, color, w, a, cap=cairo.LINE_CAP_BUTT)
        ctx.set_dash([])


def arc_draw(ctx, x, y, r, start, sweep, color, a, w):
    if sweep <= 0.001:
        return
    ctx.new_sub_path()
    ctx.arc(x, y, r, start, start + sweep)
    stroke(ctx, color, w, a)


def rays(ctx, x, y, n, rot, color, a):
    for i in range(n):
        a0 = rot + i * TAU / n
        ctx.move_to(x, y)
        ctx.arc(x, y, 1500, a0, a0 + TAU / n / 2)
        ctx.close_path()
    fill(ctx, color, a)


def sparkles(ctx, t, pts, color, start=0):
    """Destellos que titilan. pts = [(x, y, radio, fase), ...]"""
    for (x, y, r, ph) in pts:
        p = prog(t, start + ph * 6, 8)
        if p <= 0:
            continue
        tw = 0.65 + 0.35 * math.sin(t * 0.25 + ph * 3)
        star4(ctx, x, y, r * ease_out_back(p) * tw, rot=0.0)
        fill(ctx, color, 1.0)


# ---------------------------------------------------------------- iconos tipo app
def icon_check(ctx, s, color, p=1.0, w=0.14):
    pts = [(-0.30 * s, 0.02 * s), (-0.08 * s, 0.24 * s), (0.32 * s, -0.22 * s)]
    if polyline_partial(ctx, pts, p):
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        stroke(ctx, color, w * s)


def icon_cross(ctx, s, color):
    rrect(ctx, -0.15 * s, -0.42 * s, 0.30 * s, 0.84 * s, 0.08 * s)
    rrect(ctx, -0.42 * s, -0.15 * s, 0.84 * s, 0.30 * s, 0.08 * s)
    fill(ctx, color)


def icon_pin(ctx, s, color, hole=WHITE, paw=False):
    r = 0.30 * s
    cy = -0.10 * s
    ctx.move_to(0, 0.46 * s)
    ctx.curve_to(-0.10 * s, 0.30 * s, -r, 0.14 * s, -r, cy)
    ctx.arc(0, cy, r, math.pi, TAU)
    ctx.curve_to(r, 0.14 * s, 0.10 * s, 0.30 * s, 0, 0.46 * s)
    ctx.close_path()
    fill(ctx, color)
    if paw:
        icon_paw(ctx, 0.36 * s, hole, oy=cy)
    else:
        circle(ctx, 0, cy, 0.12 * s)
        fill(ctx, hole)


def icon_house(ctx, s, color, door=WHITE):
    ctx.move_to(-0.30 * s, 0.38 * s)
    ctx.line_to(-0.30 * s, -0.02 * s)
    ctx.line_to(0, -0.30 * s)
    ctx.line_to(0.30 * s, -0.02 * s)
    ctx.line_to(0.30 * s, 0.38 * s)
    ctx.close_path()
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    src(ctx, color)
    ctx.fill_preserve()
    stroke(ctx, color, 0.08 * s)
    ctx.move_to(-0.44 * s, 0.02 * s)
    ctx.line_to(0, -0.40 * s)
    ctx.line_to(0.44 * s, 0.02 * s)
    stroke(ctx, color, 0.12 * s)
    rrect(ctx, -0.09 * s, 0.12 * s, 0.18 * s, 0.30 * s, 0.05 * s)
    fill(ctx, door)


def icon_house_pin(ctx, s, house, pin, bg=WHITE):
    with saved(ctx):
        ctx.translate(-0.08 * s, 0.06 * s)
        icon_house(ctx, 0.85 * s, house, door=bg)
    with saved(ctx):
        ctx.translate(0.28 * s, -0.24 * s)
        icon_pin(ctx, 0.62 * s, bg)          # contorno blanco
        ctx.scale(0.80, 0.80)
        icon_pin(ctx, 0.62 * s, pin, hole=bg)


def icon_drop(ctx, s, color, hl=WHITE):
    ctx.move_to(0, -0.44 * s)
    ctx.curve_to(0.14 * s, -0.24 * s, 0.32 * s, -0.04 * s, 0.32 * s, 0.14 * s)
    ctx.arc(0, 0.14 * s, 0.32 * s, 0, math.pi)
    ctx.curve_to(-0.32 * s, -0.04 * s, -0.14 * s, -0.24 * s, 0, -0.44 * s)
    ctx.close_path()
    fill(ctx, color)
    ctx.new_sub_path()
    ctx.arc(0, 0.14 * s, 0.19 * s, math.pi * 0.55, math.pi * 0.95)
    stroke(ctx, hl, 0.06 * s)


def icon_calendar(ctx, s, color, bg=WHITE, accent=MID):
    rrect(ctx, -0.38 * s, -0.32 * s, 0.76 * s, 0.72 * s, 0.10 * s)
    fill(ctx, color)
    rrect(ctx, -0.30 * s, -0.10 * s, 0.60 * s, 0.42 * s, 0.05 * s)
    fill(ctx, bg)
    for x in (-0.18, 0.18):
        rrect(ctx, (x - 0.045) * s, -0.44 * s, 0.09 * s, 0.22 * s, 0.045 * s)
        fill(ctx, color)
    for j, yy in enumerate((0.02, 0.18)):
        for i, xx in enumerate((-0.17, 0.0, 0.17)):
            rrect(ctx, (xx - 0.055) * s, (yy - 0.05) * s, 0.11 * s, 0.10 * s, 0.025 * s)
            fill(ctx, accent if (i == 2 and j == 1) else color)


def draw_scissors(ctx, x, y, size, rot, open_a, blade, handle, pivot):
    k = size / 200.0
    with saved(ctx):
        ctx.translate(x, y)
        ctx.rotate(rot)
        ctx.scale(k, k)
        for sgn in (1, -1):
            with saved(ctx):
                ctx.rotate(sgn * open_a)
                ctx.move_to(0, 0)
                ctx.line_to(-sgn * 24, 52)
                stroke(ctx, handle, 15)
                circle(ctx, -sgn * 34, 80, 27)
                stroke(ctx, handle, 13)
                ctx.move_to(-sgn * 11, 10)
                ctx.curve_to(-sgn * 16, -50, -sgn * 6, -110, sgn * 2, -150)
                ctx.curve_to(sgn * 9, -100, sgn * 13, -40, sgn * 10, 10)
                ctx.close_path()
                fill(ctx, blade)
        circle(ctx, 0, 0, 9)
        fill(ctx, pivot)


def icon_scissors(ctx, s, color, open_a=0.32):
    draw_scissors(ctx, 0.02 * s, 0.02 * s, 0.82 * s, 0.0, open_a, color, color, WHITE)


def icon_sparkle(ctx, s, color, color2=None):
    star4(ctx, -0.06 * s, 0.06 * s, 0.36 * s)
    fill(ctx, color)
    star4(ctx, 0.28 * s, -0.28 * s, 0.15 * s)
    fill(ctx, color2 or color)


def icon_paw(ctx, s, color, ox=0.0, oy=0.0):
    with saved(ctx):
        ctx.translate(ox, oy)
        ctx.move_to(0, 0.02 * s)
        ctx.curve_to(0.20 * s, 0.02 * s, 0.36 * s, 0.24 * s, 0.26 * s, 0.36 * s)
        ctx.curve_to(0.17 * s, 0.45 * s, 0.07 * s, 0.38 * s, 0, 0.38 * s)
        ctx.curve_to(-0.07 * s, 0.38 * s, -0.17 * s, 0.45 * s, -0.26 * s, 0.36 * s)
        ctx.curve_to(-0.36 * s, 0.24 * s, -0.20 * s, 0.02 * s, 0, 0.02 * s)
        ctx.close_path()
        for (tx, ty, rot) in ((-0.33, -0.10, -0.35), (-0.12, -0.30, -0.1), (0.12, -0.30, 0.1), (0.33, -0.10, 0.35)):
            with saved(ctx):
                ctx.translate(tx * s, ty * s)
                ctx.rotate(rot)
                ellipse(ctx, 0, 0, 0.10 * s, 0.135 * s)
        fill(ctx, color)


def icon_van(ctx, s, color, win=WHITE, t=0.0):
    rrect(ctx, -0.48 * s, -0.28 * s, 0.62 * s, 0.46 * s, 0.09 * s)
    ctx.move_to(0.08 * s, -0.18 * s)
    ctx.line_to(0.28 * s, -0.18 * s)
    ctx.curve_to(0.36 * s, -0.18 * s, 0.47 * s, -0.04 * s, 0.48 * s, 0.04 * s)
    ctx.line_to(0.48 * s, 0.18 * s)
    ctx.line_to(0.08 * s, 0.18 * s)
    ctx.close_path()
    fill(ctx, color)
    rrect(ctx, 0.17 * s, -0.11 * s, 0.17 * s, 0.12 * s, 0.03 * s)
    fill(ctx, win)
    icon_paw(ctx, 0.26 * s, win, ox=-0.17 * s, oy=-0.07 * s)
    for wx in (-0.28, 0.27):
        circle(ctx, wx * s, 0.19 * s, 0.12 * s)
        fill(ctx, color)
        circle(ctx, wx * s, 0.19 * s, 0.075 * s)
        fill(ctx, win)
        with saved(ctx):
            ctx.translate(wx * s, 0.19 * s)
            ctx.rotate(t * 0.5)
            ctx.move_to(-0.05 * s, 0)
            ctx.line_to(0.05 * s, 0)
            stroke(ctx, color, 0.025 * s)


def icon_chat(ctx, s, color, tick):
    rrect(ctx, -0.42 * s, -0.34 * s, 0.84 * s, 0.58 * s, 0.20 * s)
    ctx.move_to(-0.24 * s, 0.16 * s)
    ctx.line_to(-0.36 * s, 0.42 * s)
    ctx.line_to(-0.02 * s, 0.20 * s)
    ctx.close_path()
    fill(ctx, color)
    for dx in (-0.08, 0.08):
        with saved(ctx):
            ctx.translate(dx * s, -0.05 * s)
            icon_check(ctx, 0.48 * s, tick, w=0.16)


def icon_globe(ctx, s, color):
    circle(ctx, 0, 0, 0.40 * s)
    stroke(ctx, color, 0.07 * s)
    ellipse(ctx, 0, 0, 0.17 * s, 0.40 * s)
    stroke(ctx, color, 0.06 * s)
    ctx.move_to(-0.40 * s, 0)
    ctx.line_to(0.40 * s, 0)
    for yy in (-0.2, 0.2):
        hw = math.sqrt(0.40 ** 2 - yy ** 2) - 0.03
        ctx.move_to(-hw * s, yy * s)
        ctx.line_to(hw * s, yy * s)
    stroke(ctx, color, 0.06 * s)


def icon_phone(ctx, s, color):
    rrect(ctx, -0.25 * s, -0.43 * s, 0.50 * s, 0.86 * s, 0.11 * s)
    stroke(ctx, color, 0.08 * s)
    ctx.move_to(-0.07 * s, -0.30 * s)
    ctx.line_to(0.07 * s, -0.30 * s)
    stroke(ctx, color, 0.055 * s)
    circle(ctx, 0, 0.29 * s, 0.045 * s)
    fill(ctx, color)


def app_badge(ctx, x, y, size, draw_icon, scale=1.0, rot=0.0, bg=WHITE, shadow=DEEP, shadow_a=0.28):
    if scale <= 0.01:
        return
    with saved(ctx):
        ctx.translate(x, y)
        ctx.rotate(rot)
        ctx.scale(scale, scale)
        rrect(ctx, -size / 2, -size / 2 + 10, size, size, size * 0.28)
        fill(ctx, shadow, shadow_a)
        rrect(ctx, -size / 2, -size / 2, size, size, size * 0.28)
        fill(ctx, bg)
        draw_icon(ctx, size * 0.62)


def logo_mark(ctx, x, y, size, rot=0.0, t=0.0):
    with saved(ctx):
        ctx.translate(x, y)
        ctx.rotate(rot)
        rrect(ctx, -size / 2, -size / 2 + 16, size, size, size * 0.28)
        fill(ctx, DEEP, 0.5)
        rrect(ctx, -size / 2, -size / 2, size, size, size * 0.28)
        fill(ctx, WHITE)
        icon_paw(ctx, size * 0.66, MID, oy=-size * 0.06)
        circle(ctx, size * 0.40, -size * 0.40, size * 0.15)
        fill(ctx, LIGHT)
        star4(ctx, size * 0.40, -size * 0.40, size * 0.10 * (0.85 + 0.15 * math.sin(t * 0.3)))
        fill(ctx, DARK)


# ---------------------------------------------------------------- mascotas
PET = dict(body=WHITE, shade=MINT, accent=LIGHT, detail=DARK, muzzle=MINT, nose_cat=MID, collar=MID, tag=LIGHT)


def _eye(ctx, x, y, rx, ry, blink, happy, th):
    if happy:
        ctx.new_sub_path()
        ctx.arc(x, y + 5, rx * 1.05, math.pi * 1.1, math.pi * 1.9)
        stroke(ctx, th["detail"], 6.5)
        return
    k = max(0.10, 1 - blink)
    ellipse(ctx, x, y, rx, ry * k)
    fill(ctx, th["detail"])
    if k > 0.55:
        circle(ctx, x + rx * 0.36, y - ry * 0.36 * k, rx * 0.38)
        fill(ctx, WHITE)


def dog_head(ctx, th, blink=0.0, ear=0.0, happy=False):
    ellipse(ctx, 0, 0, 100, 90)
    fill(ctx, th["body"])
    ellipse(ctx, -38, -14, 31, 31)
    fill(ctx, th["accent"])
    ellipse(ctx, 0, 40, 50, 35)
    fill(ctx, th["muzzle"])
    _eye(ctx, -37, -12, 12.5, 14, blink, happy, th)
    _eye(ctx, 37, -12, 12.5, 14, blink, happy, th)
    ctx.move_to(-20, 20)
    ctx.curve_to(-20, 8, 20, 8, 20, 20)
    ctx.curve_to(20, 30, 6, 37, 0, 37)
    ctx.curve_to(-6, 37, -20, 30, -20, 20)
    ctx.close_path()
    fill(ctx, th["detail"])
    ellipse(ctx, -6, 16, 6, 3.5)
    fill(ctx, WHITE, 0.7)
    ctx.move_to(0, 37)
    ctx.line_to(0, 45)
    ctx.move_to(0, 45)
    ctx.curve_to(-2, 54, -14, 56, -18, 47)
    ctx.move_to(0, 45)
    ctx.curve_to(2, 54, 14, 56, 18, 47)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    stroke(ctx, th["detail"], 4.5)
    for sgn in (-1, 1):            # orejas caidas
        with saved(ctx):
            ctx.translate(sgn * 74, -56)
            ctx.scale(sgn, 1)
            ctx.rotate(-(0.06 + ear))
            ctx.move_to(-8, -6)
            ctx.curve_to(30, -26, 70, 10, 60, 80)
            ctx.curve_to(56, 118, 20, 124, 10, 92)
            ctx.curve_to(2, 60, -18, 24, -8, -6)
            ctx.close_path()
            fill(ctx, th["accent"])


def draw_dog(ctx, x, y, s, th=PET, full=True, blink=0.0, ear=0.0, tail=0.0, happy=False, tilt=0.0, collar=True):
    """Perrito plano. (x, y) = centro de la cabeza; s = escala."""
    with saved(ctx):
        ctx.translate(x, y)
        ctx.scale(s, s)
        if full:
            with saved(ctx):                         # cola
                ctx.translate(80, 226)
                ctx.rotate(-0.15 + tail)
                ctx.move_to(0, 0)
                ctx.curve_to(40, -10, 72, -50, 66, -104)
                stroke(ctx, th["body"], 30)
            ctx.move_to(-62, 30)                     # cuerpo
            ctx.curve_to(-112, 100, -128, 215, -108, 262)
            ctx.line_to(108, 262)
            ctx.curve_to(128, 215, 112, 100, 62, 30)
            ctx.close_path()
            fill(ctx, th["body"])
            ellipse(ctx, 0, 122, 44, 50)
            fill(ctx, th["muzzle"])
            for sgn in (-1, 1):
                ctx.move_to(sgn * 64, 262)
                ctx.curve_to(sgn * 62, 205, sgn * 82, 176, sgn * 104, 180)
                stroke(ctx, th["shade"], 5)
                ellipse(ctx, sgn * 100, 256, 36, 15)
                fill(ctx, th["body"])
                ellipse(ctx, sgn * 100, 256, 36, 15)
                stroke(ctx, th["shade"], 4)
                rrect(ctx, sgn * 36 - 21, 150, 42, 117, 21)
                src(ctx, th["body"])
                ctx.fill_preserve()
                stroke(ctx, th["shade"], 4)
                for dx in (-7, 7):
                    ctx.move_to(sgn * 36 + dx, 252)
                    ctx.line_to(sgn * 36 + dx, 264)
                stroke(ctx, th["shade"], 3.5)
            if collar:
                rrect(ctx, -68, 84, 136, 22, 11)
                fill(ctx, th["collar"])
                circle(ctx, 0, 114, 12)
                src(ctx, th["tag"])
                ctx.fill_preserve()
                stroke(ctx, th["collar"], 3)
        with saved(ctx):
            about(ctx, 0, 50, 1, 1, tilt)
            dog_head(ctx, th, blink, ear, happy)


def cat_head(ctx, th, blink=0.0, ear=0.0, happy=False):
    for sgn in (-1, 1):                      # orejas (detras de la cabeza)
        with saved(ctx):
            ctx.translate(sgn * 58, -52)
            ctx.scale(sgn, 1)
            if sgn == 1:
                ctx.rotate(0.35 * ear)
            ctx.move_to(-38, 8)
            ctx.line_to(6, -80)
            ctx.curve_to(12, -93, 24, -93, 28, -80)
            ctx.line_to(44, 14)
            ctx.close_path()
            fill(ctx, th["body"])
            ctx.move_to(-18, -2)
            ctx.line_to(9, -58)
            ctx.curve_to(13, -67, 20, -67, 22, -58)
            ctx.line_to(30, 0)
            ctx.close_path()
            fill(ctx, th["accent"])
    ellipse(ctx, 0, 0, 104, 86)
    fill(ctx, th["body"])
    for sgn in (-1, 1):                      # cachetes peludos
        ctx.move_to(sgn * 92, -6)
        ctx.line_to(sgn * 118, 8)
        ctx.line_to(sgn * 100, 16)
        ctx.line_to(sgn * 114, 28)
        ctx.line_to(sgn * 88, 34)
        ctx.close_path()
        fill(ctx, th["body"])
    for (x0, y0, x1, y1) in ((-20, -80, -15, -58), (0, -84, 0, -60), (20, -80, 15, -58)):
        ctx.move_to(x0, y0)
        ctx.line_to(x1, y1)
    stroke(ctx, th["accent"], 8)
    _eye(ctx, -40, -4, 13, 17, blink, happy, th)
    _eye(ctx, 40, -4, 13, 17, blink, happy, th)
    ctx.move_to(-11, 16)
    ctx.line_to(11, 16)
    ctx.line_to(0, 27)
    ctx.close_path()
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    src(ctx, th["nose_cat"])
    ctx.fill_preserve()
    stroke(ctx, th["nose_cat"], 5)
    ctx.move_to(0, 27)
    ctx.curve_to(0, 37, -10, 41, -19, 34)
    ctx.move_to(0, 27)
    ctx.curve_to(0, 37, 10, 41, 19, 34)
    stroke(ctx, th["detail"], 4)
    for sgn in (-1, 1):
        for (y0, y1) in ((16, 6), (24, 26), (32, 44)):
            ctx.move_to(sgn * 48, y0)
            ctx.line_to(sgn * 122, y1)
    stroke(ctx, th["detail"], 3.5, 0.55)


def draw_cat(ctx, x, y, s, th=PET, full=True, blink=0.0, ear=0.0, tail=0.0, happy=False, tilt=0.0):
    """Gatito plano. (x, y) = centro de la cabeza; s = escala. tail en -1..1"""
    with saved(ctx):
        ctx.translate(x, y)
        ctx.scale(s, s)
        if full:
            sw = tail
            ctx.move_to(56, 250)                      # cola
            ctx.curve_to(150, 262, 200, 200, 178 + 30 * sw, 132)
            ctx.curve_to(162 + 40 * sw, 84, 188 + 56 * sw, 52, 214 + 60 * sw, 66)
            stroke(ctx, th["body"], 26)
            ctx.move_to(-52, 40)                      # cuerpo
            ctx.curve_to(-96, 110, -110, 215, -92, 262)
            ctx.line_to(92, 262)
            ctx.curve_to(110, 215, 96, 110, 52, 40)
            ctx.close_path()
            fill(ctx, th["body"])
            ellipse(ctx, 0, 128, 38, 56)
            fill(ctx, th["muzzle"])
            for sgn in (-1, 1):
                ctx.move_to(sgn * 54, 262)
                ctx.curve_to(sgn * 52, 210, sgn * 70, 182, sgn * 90, 186)
                stroke(ctx, th["shade"], 5)
                ellipse(ctx, sgn * 86, 256, 32, 14)
                fill(ctx, th["body"])
                ellipse(ctx, sgn * 86, 256, 32, 14)
                stroke(ctx, th["shade"], 4)
                rrect(ctx, sgn * 30 - 17, 156, 34, 111, 17)
                src(ctx, th["body"])
                ctx.fill_preserve()
                stroke(ctx, th["shade"], 4)
                for dx in (-6, 6):
                    ctx.move_to(sgn * 30 + dx, 253)
                    ctx.line_to(sgn * 30 + dx, 264)
                stroke(ctx, th["shade"], 3.5)
        with saved(ctx):
            about(ctx, 0, 50, 1, 1, tilt)
            cat_head(ctx, th, blink, ear, happy)


def mittens(ctx, x, y, s, gap, th=PET, scale=1.0):
    """Dos patitas apoyadas sobre un borde."""
    if scale <= 0.01:
        return
    for sgn in (-1, 1):
        px = x + sgn * gap * s
        with saved(ctx):
            about(ctx, px, y, scale)
            ellipse(ctx, px, y + 6 * s, 31 * s, 22 * s)
            fill(ctx, DEEP, 0.22)
            ellipse(ctx, px, y, 31 * s, 22 * s)
            fill(ctx, th["body"])
            for dx in (-9, 9):
                ctx.move_to(px + dx * s, y - 19 * s)
                ctx.line_to(px + dx * s, y - 8 * s)
            stroke(ctx, th["detail"], 3.5 * s, 0.35)


# =====================================================================
#  ESCENA 1 (0-3 s): marca + sello NUEVO + perrito y gatito asomandose
# =====================================================================
def scene_intro(ctx, t):
    src(ctx, DARK)
    ctx.paint()
    glow(ctx, 540, 700, 950, MID, 0.50)
    dot_grid(ctx, t, MINT, 0.06)
    floaters(ctx, t, LIGHT, 0.22, seed=3)

    # lineas geometricas que se dibujan
    dashed_ring(ctx, 540, 680, 440, LIGHT, 0.16, 3, t * 0.008)
    arc_draw(ctx, 540, 680, 490, -math.pi * 0.65, ease_out_cubic(prog(t, 2, 22)) * 1.5 * math.pi, LIGHT, 0.45, 7)
    arc_draw(ctx, 540, 680, 515, math.pi * 0.35, ease_out_cubic(prog(t, 6, 22)) * 0.5 * math.pi, MID, 0.9, 7)

    # onda expansiva inicial ("entra con fuerza")
    p = prog(t, 0, 16)
    if p < 1:
        circle(ctx, 540, 640, 60 + 1000 * ease_out_cubic(p))
        stroke(ctx, LIGHT, 70 * (1 - p) + 2, 0.9 * (1 - p))
    for k, (d0, col) in enumerate(((0, LIGHT), (3, MID))):
        q = prog(t, d0, 12)
        if 0 < q < 1:
            x = lerp(-600, 1700, ease_in_out_cubic(q))
            with saved(ctx):
                ctx.translate(x, 960)
                ctx.rotate(-0.5)
                rrect(ctx, -60 - k * 30, -1400, 80 + k * 50, 2800, 40)
                fill(ctx, col, 0.55)

    # ---- nombre
    S = fit(TEXTOS["marca_1"], "black", 220, 860)
    tP = T(TEXTOS["marca_1"], "black", S)
    by = 690
    fxP = letter_drop(t, 2, 1.5)
    tP.draw(ctx, 548, by + 10, DEEP, alpha=0.55, fx=fxP, pivot="glyph")
    tP.draw(ctx, 540, by, WHITE, fx=fxP, pivot="glyph", label="marca")

    tY = T(TEXTOS["marca_2"], "black", S)
    right = 540 + tP.width / 2
    yb = by + 0.84 * S
    p = prog(t, 10, 13)
    xo = (1 - ease_out_back(p)) * 520
    ya_left = right + xo - tY.width
    # lineas de velocidad
    pl = ease_out_cubic(prog(t, 13, 10))
    for k, (dy, ln) in enumerate(((0.60, 170), (0.39, 250), (0.18, 130))):
        if pl <= 0:
            break
        x1 = ya_left - 34 + 10 * math.sin(t * 0.35 + k * 1.7)
        ctx.move_to(x1, yb - dy * S)
        ctx.line_to(x1 - ln * pl, yb - dy * S)
        stroke(ctx, LIGHT, 15, 0.95)
    tY.draw(ctx, right + xo + 8, yb + 10, DEEP, align="right", alpha=0.55 * clamp(p * 3))
    tY.draw(ctx, right + xo, yb, LIGHT, align="right", alpha=clamp(p * 3), label="marca")

    # ---- sello NUEVO
    bx, byy, br = 846, 398, 98
    p = prog(t, 15, 11)
    if p > 0:
        sc = lerp(2.6, 1.0, ease_out_back(p)) * (1 + 0.035 * math.sin(t * 0.22))
        rot = lerp(-0.9, -0.22, ease_out_cubic(p)) + 0.04 * math.sin(t * 0.13)
        with group(ctx, clamp(p * 4)):
            with saved(ctx):
                ctx.translate(bx, byy)
                ctx.rotate(rot)
                ctx.scale(sc, sc)
                pts = [((br if i % 2 == 0 else br * 0.88) * math.cos(i * TAU / 32),
                        (br if i % 2 == 0 else br * 0.88) * math.sin(i * TAU / 32)) for i in range(32)]
                with saved(ctx):
                    ctx.translate(0, 9)
                    rounded_poly(ctx, pts)
                    fill(ctx, DEEP, 0.55)
                rounded_poly(ctx, pts)
                fill(ctx, LIGHT)
                ctx.set_dash([10, 9])
                circle(ctx, 0, 0, br * 0.70)
                stroke(ctx, DARK, 3.5, 0.6, cap=cairo.LINE_CAP_BUTT)
                ctx.set_dash([])
                tn = T(TEXTOS["sello"], "black", fit(TEXTOS["sello"], "black", 44, br * 1.45, 1), 1)
                tn.draw(ctx, 0, 0.36 * tn.size, DARK, label=None)
    # impacto del sello: rayitas
    q = prog(t, 22, 10)
    if 0 < q < 1:
        for i in range(8):
            a = i * TAU / 8 + 0.2
            r0, r1 = br + 10 + 40 * q, br + 30 + 70 * ease_out_cubic(q)
            ctx.move_to(bx + r0 * math.cos(a), byy + r0 * math.sin(a))
            ctx.line_to(bx + r1 * math.cos(a), byy + r1 * math.sin(a))
        stroke(ctx, LIGHT, 8, 1 - q)

    # ---- tarjeta con la frase + mascotas asomandose
    lines, fs = wrap_fit(TEXTOS["frase_intro"], "bold", 66, 770, 3)
    lh = fs * 1.24
    card_top = 1140
    card_h = 0.72 * fs + lh * (len(lines) - 1) + 150
    cy_card = card_top + (1 - ease_out_back(prog(t, 18, 14))) * 760

    pets = [  # (x, inicio, dibujante)
        (392, 26, "dog"),
        (688, 31, "cat"),
    ]
    with saved(ctx):
        ctx.rectangle(0, 0, W, cy_card + 2)
        ctx.clip()
        for (px, st, kind) in pets:
            rise = spring(prog(t, st, 18))
            if rise <= 0:
                continue
            hy = cy_card - 78 + (1 - rise) * 260
            if kind == "dog":
                ear = 0.05 * math.sin(t * 0.2) + 0.32 * math.sin((t - 52) * 0.8) * math.exp(-max(t - 52, 0) * 0.1) * (t > 52)
                draw_dog(ctx, px, hy, 0.95, full=False, blink=blinks(t, [60]), ear=ear,
                         tilt=0.07 * math.sin(t * 0.12))
            else:
                draw_cat(ctx, px, hy, 0.95, full=False, blink=blinks(t, [70]), ear=bump(t, 50, 7) + bump(t, 58, 7),
                         tilt=-0.06 * math.sin(t * 0.11 + 1))

    with saved(ctx):
        rrect(ctx, 110, cy_card + 16, 860, card_h, 50)
        fill(ctx, DEEP, 0.5)
        rrect(ctx, 110, cy_card, 860, card_h, 50)
        fill(ctx, MINT)
    for (px, st, kind) in pets:
        mittens(ctx, px, cy_card + 2, 0.95, 46, scale=pop(t, st + 12, 9))

    # frase palabra por palabra + resaltador en "nueva"
    target = TEXTOS["palabra_resaltada"].strip().lower()
    first_base = cy_card + 75 + 0.72 * fs
    wbase = 0
    for li, line in enumerate(lines):
        tl = T(line, "bold", fs)
        base = first_base + li * lh
        for wi, word in enumerate(line.split()):
            if target and word.strip(".,;:!¡¿?").lower() == target:
                a, b = tl.wspan[wi]
                left = tl.left(540, "center")
                m = ease_out_cubic(prog(t, 40, 9))
                if m > 0:
                    rrect(ctx, left + a - 12, base - 0.42 * fs, (b - a + 24) * m, 0.54 * fs, 10)
                    fill(ctx, LIGHT)
        tl.draw(ctx, 540, base, DARK, fx=(lambda tt, off: (lambda i, wi: word_pop(tt, 24, 1.7)(i, wi + off)))(t, wbase),
                label="frase")
        wbase += tl.nwords

    sparkles(ctx, t, [(170, 470, 26, 0), (950, 640, 20, 1), (205, 905, 18, 2), (905, 925, 24, 1.5),
                      (660, 300, 16, 2.5), (110, 1520, 18, 3)], WHITE, start=20)


# =====================================================================
#  ESCENA 2 (3-9 s): los tres servicios
# =====================================================================
STAGE = (540, 760, 290)


def illus_vet(ctx, t, cfg):
    cx, cy, r = STAGE
    yl = cy + 70
    pts = [(-252, 0), (-210, 0), (-196, -16), (-184, 0), (-172, 0), (-160, 34), (-146, -72), (-131, 24), (-120, 0),
           (120, 0), (131, -18), (143, 0), (154, 0), (166, 36), (180, -74), (195, 24), (206, 0), (252, 0)]
    pts = [(cx + x, yl + y) for x, y in pts]
    ctx.move_to(*pts[0])
    for pnt in pts[1:]:
        ctx.line_to(*pnt)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    stroke(ctx, LIGHT, 7, 0.28)
    # pulso que recorre la linea
    ph = (t % 26) / 26
    with saved(ctx):
        ctx.rectangle(cx - 260 + ph * 520 - 120, 0, 120, H)
        ctx.clip()
        ctx.move_to(*pts[0])
        for pnt in pts[1:]:
            ctx.line_to(*pnt)
        stroke(ctx, LIGHT, 8, 1.0)
    ellipse(ctx, cx, cy + 172, 135, 16)
    fill(ctx, DEEP, 0.6)
    draw_dog(ctx, cx, cy - 66, 0.9, blink=blinks(t, [34]), tail=0.38 * math.sin(t * 0.55),
             ear=0.04 * math.sin(t * 0.3), tilt=0.06 * math.sin(t * 0.14))
    hp = pop(t, 22, 10)
    if hp > 0:
        hy = cy - 190 + 8 * math.sin(t * 0.18)
        heart(ctx, cx - 160, hy, 74 * hp)
        fill(ctx, LIGHT)
        star4(ctx, cx - 112, hy - 36, 14 * hp)
        fill(ctx, WHITE)


def illus_bath(ctx, t, cfg):
    cx, cy, r = STAGE
    with saved(ctx):
        circle(ctx, cx, cy, r)
        ctx.clip()
        # ducha y gotas
        sx, sy = cx - 175, cy - 200
        ctx.move_to(cx - 330, cy - 235)
        ctx.line_to(sx - 10, sy - 18)
        stroke(ctx, MINT, 18)
        with saved(ctx):
            ctx.translate(sx, sy)
            ctx.rotate(0.75)
            rrect(ctx, -46, -14, 92, 34, 14)
            fill(ctx, MINT)
            rrect(ctx, -40, 14, 80, 10, 5)
            fill(ctx, WHITE)
        d = (0.62, 0.78)
        for k in range(15):
            s = ((t * 0.045) + k / 15) % 1.0
            off = ((k * 7) % 5 - 2) * 16
            x = sx + 10 + d[0] * s * 240 - d[1] * off
            y = sy + 22 + d[1] * s * 240 + d[0] * off
            with saved(ctx):
                ctx.translate(x, y)
                ctx.rotate(-0.68)
                icon_drop(ctx, 30, WHITE, hl=WHITE)
    # cola asomando de la banadera
    with saved(ctx):
        ctx.translate(cx + 150, cy + 110)
        ctx.rotate(0.15 + 0.35 * math.sin(t * 0.6))
        ctx.move_to(0, 0)
        ctx.curve_to(30, -50, 60, -90, 54, -150)
        stroke(ctx, WHITE, 28)
    tilt = 0.08 * math.sin(t * 0.16)
    draw_dog(ctx, cx, cy - 6, 0.92, full=False, happy=True, ear=0.1 * math.sin(t * 0.25), tilt=tilt)
    # espuma en la cabeza
    with saved(ctx):
        about(ctx, cx, cy + 40, 1, 1, tilt)
        for (fx_, fy, fr) in ((-46, -82, 26), (-10, -96, 32), (30, -88, 27), (60, -70, 20), (-74, -64, 18)):
            circle(ctx, cx + fx_ * 0.8, cy + fy - 14 + 2 * math.sin(t * 0.3 + fx_), fr * 0.9)
            src(ctx, WHITE)
            ctx.fill_preserve()
            stroke(ctx, MINT, 5)
    # banadera
    top = cy + 56
    ctx.move_to(cx - 214, top + 26)
    ctx.line_to(cx + 214, top + 26)
    ctx.line_to(cx + 214, top + 70)
    ctx.arc(cx + 144, top + 70, 70, 0, math.pi / 2)
    ctx.line_to(cx - 144, top + 140)
    ctx.arc(cx - 144, top + 70, 70, math.pi / 2, math.pi)
    ctx.close_path()
    fill(ctx, WHITE)
    with saved(ctx):
        ctx.move_to(cx - 214, top + 26)
        ctx.line_to(cx + 214, top + 26)
        ctx.line_to(cx + 214, top + 70)
        ctx.arc(cx + 144, top + 70, 70, 0, math.pi / 2)
        ctx.line_to(cx - 144, top + 140)
        ctx.arc(cx - 144, top + 70, 70, math.pi / 2, math.pi)
        ctx.close_path()
        ctx.clip()
        rrect(ctx, cx - 230, top + 78, 460, 24, 0)
        fill(ctx, LIGHT)
    for fxx in (-150, 150):
        rrect(ctx, cx + fxx - 16, top + 128, 32, 34, 12)
        fill(ctx, DARK)
    rrect(ctx, cx - 236, top, 472, 36, 18)
    fill(ctx, MINT)
    # espuma en el borde
    rnd = random.Random(7)
    for i in range(12):
        bx = cx - 205 + i * 37 + rnd.uniform(-6, 6)
        br = rnd.uniform(15, 27)
        circle(ctx, bx, top + 4 + 2.5 * math.sin(t * 0.3 + i), br)
        src(ctx, WHITE)
        ctx.fill_preserve()
        stroke(ctx, MINT, 4)
    mittens(ctx, cx, top + 10, 0.92, 76)
    # burbujas que suben
    with saved(ctx):
        circle(ctx, cx, cy, r + 30)
        ctx.clip()
        rnd = random.Random(11)
        for i in range(11):
            bx0 = cx + rnd.uniform(-230, 230)
            sp = rnd.uniform(2.6, 4.4)
            ph = rnd.uniform(0, 300)
            br = rnd.uniform(10, 26)
            y = top + 10 - ((t * sp + ph) % 330)
            x = bx0 + 12 * math.sin(t * 0.15 + ph)
            circle(ctx, x, y, br)
            stroke(ctx, WHITE, 4, 0.9)
            circle(ctx, x - br * 0.35, y - br * 0.35, br * 0.22)
            fill(ctx, WHITE, 0.9)


def illus_groom(ctx, t, cfg):
    cx, cy, r = STAGE
    ellipse(ctx, cx - 16, cy + 158, 130, 16)
    fill(ctx, DEEP, 0.6)
    snip = 0.5 + 0.5 * math.cos(t * 0.75)
    draw_cat(ctx, cx - 16, cy - 76, 0.88, blink=blinks(t, [40]), tail=math.sin(t * 0.12),
             ear=0.6 * (1 - snip) * (t > 8), tilt=0.05 * math.sin(t * 0.13))
    # pelitos que vuelan
    for k in range(6):
        s = ((t * 0.035) + k / 6) % 1.0
        x = cx + 70 + s * 150 + 14 * math.sin(k * 2.1 + t * 0.2)
        y = cy - 196 + s * 210 + 160 * s * s
        with saved(ctx):
            ctx.translate(x, y)
            ctx.rotate(t * 0.12 + k)
            for (ox, oy, rr) in ((0, 0, 7), (8, -5, 5.5), (-7, -6, 5)):
                circle(ctx, ox, oy, rr)
            fill(ctx, WHITE, 0.9 * (1 - s))
    draw_scissors(ctx, cx + 170, cy - 148, 175, -0.72, 0.06 + 0.30 * snip, WHITE, LIGHT, DARK)
    if t > 30:
        sparkles(ctx, t, [(cx - 190, cy - 40, 22, 0), (cx + 190, cy + 70, 18, 0.6), (cx - 150, cy + 140, 14, 1.2)],
                 LIGHT, start=30)


SERVICES = [
    dict(lines=TEXTOS["servicio_1"], bg=MINT, ink=DARK, stage=DARK, arc=MID, ring=DARK, tshadow=LIGHT,
         pill_bg=DARK, pill_ink=LIGHT, deco=MID, bar=DARK, illus=illus_vet,
         main=lambda c, s: icon_cross(c, s, MID),
         second=lambda c, s: icon_house_pin(c, s, DARK, MID)),
    dict(lines=TEXTOS["servicio_2"], bg=DARK, ink=WHITE, stage=MID, arc=LIGHT, ring=LIGHT, tshadow=DEEP,
         pill_bg=LIGHT, pill_ink=DARK, deco=LIGHT, bar=LIGHT, illus=illus_bath,
         main=lambda c, s: icon_drop(c, s, MID),
         second=lambda c, s: icon_calendar(c, s, DARK, WHITE, MID)),
    dict(lines=TEXTOS["servicio_3"], bg=LIGHT, ink=DARK, stage=DARK, arc=WHITE, ring=DARK, tshadow=WHITE,
         pill_bg=DARK, pill_ink=LIGHT, deco=DARK, bar=DARK, illus=illus_groom,
         main=lambda c, s: icon_scissors(c, s, MID),
         second=lambda c, s: icon_sparkle(c, s, MID, LIGHT)),
]


def scene_service(ctx, t, idx):
    cfg = SERVICES[idx]
    cx, cy, r = STAGE
    src(ctx, cfg["bg"])
    ctx.paint()
    glow(ctx, cx, cy, 760, WHITE, 0.20 if cfg["bg"] != DARK else 0.0)
    if cfg["bg"] == DARK:
        glow(ctx, cx, cy, 800, MID, 0.45)
    dot_grid(ctx, t + idx * 40, cfg["deco"], 0.08)
    floaters(ctx, t, cfg["deco"], 0.25, seed=10 + idx)

    # encabezado: titulo chico + barra de progreso (3 segmentos, tipo historias)
    ha = clamp(prog(t, 2, 8) * 1.0) if idx == 0 else 1.0
    tl = T(TEXTOS["titulo_servicios"], "bold", fit(TEXTOS["titulo_servicios"], "bold", 34, 760, 5), 5)
    tl.draw(ctx, 540, 286, cfg["ink"], alpha=0.85 * ha, label="encabezado")
    seg_w, gap = 236, 22
    x0 = 540 - (3 * seg_w + 2 * gap) / 2
    for i in range(3):
        rrect(ctx, x0 + i * (seg_w + gap), 318, seg_w, 12, 6)
        fill(ctx, cfg["bar"], 0.2 * ha)
        f = 1.0 if i < idx else (clamp(t / 58) if i == idx else 0.0)
        if f > 0:
            rrect(ctx, x0 + i * (seg_w + gap), 318, max(12, seg_w * f), 12, 6)
            fill(ctx, cfg["bar"], ha)

    # escenario circular + ilustracion (bajado un poco para centrar)
    ctx.translate(0, 45)
    sp = ease_out_back(prog(t, 1, 13))
    if sp > 0:
        with saved(ctx):
            about(ctx, cx, cy, lerp(0.4, 1.0, sp))
            with group(ctx, clamp(prog(t, 1, 5))):
                dashed_ring(ctx, cx, cy, r + 58, cfg["ring"], 0.28, 4, t * 0.01)
                arc_draw(ctx, cx, cy, r + 30, -math.pi / 2, ease_out_cubic(prog(t, 4, 22)) * 1.7 * math.pi,
                         cfg["arc"], 1.0, 9)
                circle(ctx, cx, cy, r)
                fill(ctx, cfg["stage"])
                cfg["illus"](ctx, t, cfg)

    # iconos tipo app alrededor
    bob = lambda k: 6 * math.sin(t * 0.15 + k)
    app_badge(ctx, 806, 520 + bob(0), 150, cfg["main"], scale=pop(t, 8, 11), rot=0.12)
    app_badge(ctx, 258, 650 + bob(2), 112, cfg["second"], scale=pop(t, 12, 11), rot=-0.12)
    chk = prog(t, 25, 8)
    app_badge(ctx, 818, 1004 + bob(4), 112,
              lambda c, s: icon_check(c, s, WHITE, p=ease_out_cubic(chk), w=0.18),
              scale=pop(t, 21, 10), rot=0.08, bg=MID)

    # titulo del servicio
    l1, l2 = cfg["lines"]
    if l2:
        S1 = fit(l1, "black", 132, 860)
        b1 = 1238
    else:
        S1 = fit(l1, "black", 190, 860)
        b1 = 1300
    t1 = T(l1, "black", S1)
    fx1 = letter_drop(t, 6, 1.1, drop=70)
    t1.draw(ctx, 547, b1 + 9, cfg["tshadow"], fx=fx1, pivot="glyph")
    t1.draw(ctx, 540, b1, cfg["ink"], fx=fx1, pivot="glyph", label="servicio")
    if l2:
        S2 = fit(l2, "extrabold", 80, 760)
        t2 = T(l2, "extrabold", S2)
        ph = 1.32 * S2
        pw = t2.width + 0.9 * S2
        pcy = b1 + 40 + ph / 2 + 6
        sc = pop(t, 14, 11)
        if sc > 0:
            with saved(ctx):
                about(ctx, 540, pcy, sc, sc, -0.03 * (1 - sc) - 0.02)
                rrect(ctx, 540 - pw / 2, pcy - ph / 2, pw, ph, ph / 2)
                fill(ctx, cfg["pill_bg"])
                t2.draw(ctx, 540, pcy + 0.355 * S2, cfg["pill_ink"], label="servicio2" if sc > 0.99 else None)


# =====================================================================
#  ESCENA 3 (9-12 s): un solo contacto + las dos opciones
# =====================================================================
def scene_contact(ctx, t):
    src(ctx, MINT)
    ctx.paint()
    glow(ctx, 540, 900, 900, WHITE, 0.6)
    dot_grid(ctx, t, MID, 0.08)
    floaters(ctx, t, MID, 0.28, seed=21)

    # icono de chat
    sc = pop(t, 5, 10)
    q = ((t - 10) % 30) / 30 if t > 10 else 0
    if q > 0:
        circle(ctx, 540, 322, 66 + 70 * q)
        stroke(ctx, MID, 6, 0.6 * (1 - q))
    if sc > 0:
        with saved(ctx):
            about(ctx, 540, 322, sc)
            circle(ctx, 540, 330, 66)
            fill(ctx, MID, 0.35)
            circle(ctx, 540, 322, 66)
            fill(ctx, DARK)
            with saved(ctx):
                ctx.translate(540, 324)
                icon_chat(ctx, 82, WHITE, MID)

    # titulo en dos lineas
    S = min(fit(TEXTOS["contacto_1"], "black", 88, 860), fit(TEXTOS["contacto_2"], "black", 88, 860))
    L1, L2 = T(TEXTOS["contacto_1"], "black", S), T(TEXTOS["contacto_2"], "black", S)
    b1, b2 = 498, 498 + 1.06 * S
    m = ease_out_cubic(prog(t, 18, 8))
    if m > 0:
        lft = L2.left(540, "center")
        rrect(ctx, lft - 16, b2 - 0.44 * S, (L2.width + 32) * m, 0.56 * S, 12)
        fill(ctx, LIGHT)
    L1.draw(ctx, 540, b1, DARK, fx=word_pop(t, 7, 2.2), label="contacto")
    L2.draw(ctx, 540, b2, DARK, fx=word_pop(t, 12, 2.2), label="contacto")

    # tarjetas de opciones
    cards = [(660, 14, -1, TEXTOS["opcion_1"], "van", 28), (950, 19, 1, TEXTOS["opcion_2"], "pin", 33)]
    for (y0, st, side, (o1, o2), icon, tick_t) in cards:
        p = ease_out_back(prog(t, st, 12))
        if p <= 0:
            continue
        dx = side * (1 - p) * 1100
        hgt = 240
        ccy = y0 + hgt / 2
        with saved(ctx):
            ctx.translate(dx, 0)
            rrect(ctx, 110, y0 + 14, 860, hgt, 46)
            fill(ctx, MID, 0.35)
            rrect(ctx, 110, y0, 860, hgt, 46)
            fill(ctx, DARK)
            circle(ctx, 224, ccy, 78)
            fill(ctx, LIGHT)
            with saved(ctx):
                if icon == "van":
                    ctx.translate(226 + 3 * math.sin(t * 0.5), ccy + 2 + 2.5 * abs(math.sin(t * 0.45)))
                    for k, yy in enumerate((-16, 6, 26)):
                        ctx.move_to(-96 - 10 * k, yy)
                        ctx.line_to(-74 - 4 * math.sin(t * 0.5 + k), yy)
                    stroke(ctx, DARK, 6, 0.5)
                    icon_van(ctx, 112, DARK, LIGHT, t)
                else:
                    ctx.translate(224, ccy - 4 - 10 * abs(math.sin(t * 0.18)))
                    icon_pin(ctx, 116, DARK, hole=LIGHT, paw=True)
            fs = min(fit(o1, "bold", 60, 520), fit(o2, "bold", 60, 520))
            ta, tb = T(o1, "bold", fs), T(o2, "bold", fs)
            ta.draw(ctx, 330, ccy - 10, WHITE, align="left", label="opcion" if p > 0.99 else None)
            tb.draw(ctx, 330, ccy - 10 + 1.12 * fs, LIGHT, align="left", label="opcion" if p > 0.99 else None)
            # tilde de "listo"
            kx = 902
            circle(ctx, kx, ccy, 34)
            stroke(ctx, LIGHT, 5)
            k = pop(t, tick_t, 8)
            if k > 0:
                circle(ctx, kx, ccy, 34 * k)
                fill(ctx, LIGHT)
                with saved(ctx):
                    ctx.translate(kx, ccy)
                    icon_check(ctx, 52, DARK, p=ease_out_cubic(prog(t, tick_t + 2, 6)), w=0.2)

    # separador "o"
    so = pop(t, 25, 9)
    if so > 0:
        with saved(ctx):
            about(ctx, 540, 925, so)
            circle(ctx, 540, 925, 46)
            fill(ctx, MID)
            circle(ctx, 540, 925, 46)
            stroke(ctx, MINT, 8)
            to = T(TEXTOS["separador"], "black", 50)
            to.draw(ctx, 540, 925 + 0.30 * 50, WHITE)

    # "Muy pronto: ..."
    txt = TEXTOS["pronto"]
    head, tail = (txt.split(":", 1)[0] + ":", txt.split(":", 1)[1]) if ":" in txt else ("", txt)
    fs = 44
    while True:
        tw = (T(head, "extrabold", fs).width if head else 0) + T(tail, "semibold", fs).width
        if tw + 2 * 44 + 64 <= 860 or fs < 20:
            break
        fs -= 1
    pw = tw + 2 * 44 + 64
    pcy = 1306
    ph = 96
    sp = pop(t, 32, 11)
    if sp > 0:
        with saved(ctx):
            about(ctx, 540, pcy, sp)
            rrect(ctx, 540 - pw / 2, pcy - ph / 2, pw, ph, ph / 2)
            fill(ctx, WHITE)
            ctx.set_dash([12, 10])
            rrect(ctx, 540 - pw / 2 + 4, pcy - ph / 2 + 4, pw - 8, ph - 8, ph / 2 - 4)
            stroke(ctx, MID, 4, 1.0, cap=cairo.LINE_CAP_BUTT)
            ctx.set_dash([])
            x = 540 - pw / 2 + 44
            star4(ctx, x + 22, pcy, 22 * (0.85 + 0.15 * math.sin(t * 0.35)))
            fill(ctx, MID)
            x += 64
            base = pcy + 0.355 * fs
            lab = "pronto" if sp > 0.99 else None
            if head:
                th_ = T(head, "extrabold", fs)
                th_.draw(ctx, x, base, DARK, align="left", label=lab)
                x += th_.width
            T(tail, "semibold", fs).draw(ctx, x, base, DARK, align="left", label=lab)
            # brillo que recorre la etiqueta
            sh = prog(t, 50, 16)
            if 0 < sh < 1:
                rrect(ctx, 540 - pw / 2, pcy - ph / 2, pw, ph, ph / 2)
                ctx.clip()
                gx = lerp(540 - pw / 2 - 150, 540 + pw / 2 + 150, sh)
                ctx.move_to(gx - 40, pcy + 80)
                ctx.line_to(gx + 20, pcy - 80)
                ctx.line_to(gx + 70, pcy - 80)
                ctx.line_to(gx + 10, pcy + 80)
                ctx.close_path()
                fill(ctx, LIGHT, 0.55)


# =====================================================================
#  ESCENA 4 (12-15 s): cierre con logo y contacto
# =====================================================================
def scene_end(ctx, t):
    src(ctx, DARK)
    ctx.paint()
    rays(ctx, 540, 470, 14, t * 0.006, LIGHT, 0.045)
    glow(ctx, 540, 520, 820, MID, 0.55)
    dot_grid(ctx, t, MINT, 0.05)
    floaters(ctx, t, LIGHT, 0.2, seed=31)

    # logo
    p = prog(t, 3, 14)
    if p > 0:
        sc = ease_out_back(p) * (1 + 0.05 * bump(t, 68, 12))
        dashed_ring(ctx, 540, 470, 205, LIGHT, 0.3 * clamp(p * 2), 4, -t * 0.012)
        arc_draw(ctx, 540, 470, 178, -math.pi / 2, ease_out_cubic(prog(t, 6, 18)) * TAU * 0.999, LIGHT, 0.85, 6)
        with saved(ctx):
            about(ctx, 540, 470, sc)
            logo_mark(ctx, 540, 470, 250, rot=(1 - ease_out_cubic(p)) * -0.6, t=t)
    sparkles(ctx, t, [(330, 330, 24, 0), (770, 300, 18, 0.7), (790, 600, 22, 1.4), (300, 610, 16, 2)],
             WHITE, start=12)

    # marca "Patitas Ya"
    brand = TEXTOS["marca_1"] + " " + TEXTOS["marca_2"]
    n1 = len(TEXTOS["marca_1"].split())
    S = fit(brand, "black", 150, 860)
    tb = T(brand, "black", S)
    fxw = word_pop(t, 9, 4, dur=10, rise=40)
    by = 805
    tb.draw(ctx, 547, by + 9, DEEP, fx=fxw, alpha=0.6)
    tb.draw(ctx, 540, by, WHITE, fx=lambda i, wi: fxw(i, wi) if wi < n1 else (0, 0, 0, 0, 0), label="cierre")
    tb.draw(ctx, 540, by, LIGHT, fx=lambda i, wi: fxw(i, wi) if wi >= n1 else (0, 0, 0, 0, 0), label="cierre")

    # etiquetas web + WhatsApp
    pills = [(918, 16, MINT, TEXTOS["web"], "globe"), (1048, 21, LIGHT, TEXTOS["whatsapp"], "phone")]
    for (pcy, st, bgc, text, icon) in pills:
        fs = fit(text, "bold", 50, 860 - 2 * 40 - 66)
        tt = T(text, "bold", fs)
        ph = 104
        pw = tt.width + 2 * 40 + 66
        p = prog(t, st, 11)
        if p <= 0:
            continue
        e = ease_out_back(p)
        with saved(ctx):
            ctx.translate(0, (1 - e) * 120)
            about(ctx, 540, pcy, lerp(0.6, 1, e))
            with group(ctx, clamp(p * 3)):
                rrect(ctx, 540 - pw / 2, pcy - ph / 2 + 10, pw, ph, ph / 2)
                fill(ctx, DEEP, 0.55)
                rrect(ctx, 540 - pw / 2, pcy - ph / 2, pw, ph, ph / 2)
                fill(ctx, bgc)
                ix = 540 - pw / 2 + 40 + 24
                with saved(ctx):
                    ctx.translate(ix, pcy)
                    (icon_globe if icon == "globe" else icon_phone)(ctx, 58, DARK)
                tt.draw(ctx, 540 - pw / 2 + 40 + 66, pcy + 0.355 * fs, DARK, align="left",
                        label="contacto_final" if p >= 1 else None)
                sh = prog(t, 44 + (st - 16) * 1.2, 16)
                if 0 < sh < 1:
                    rrect(ctx, 540 - pw / 2, pcy - ph / 2, pw, ph, ph / 2)
                    ctx.clip()
                    gx = lerp(540 - pw / 2 - 150, 540 + pw / 2 + 150, sh)
                    ctx.move_to(gx - 40, pcy + 80)
                    ctx.line_to(gx + 20, pcy - 80)
                    ctx.line_to(gx + 70, pcy - 80)
                    ctx.line_to(gx + 10, pcy + 80)
                    ctx.close_path()
                    fill(ctx, WHITE, 0.6)

    # mascotas saludando
    ground = 1418
    ctx.move_to(200, ground + 4)
    ctx.line_to(880, ground + 4)
    stroke(ctx, LIGHT, 6, 0.25 * clamp(prog(t, 20, 8)))
    for (px, st, kind) in ((372, 24, "dog"), (712, 28, "cat")):
        p = prog(t, st, 16)
        if p <= 0:
            continue
        sy = spring(p, 5, 1.8)
        sxk = 1 + 0.12 * (1 - sy) if p < 1 else 1
        with saved(ctx):
            about(ctx, px, ground, sxk, max(sy, 0.01))
            sc = 0.76
            hy = ground - 262 * sc
            if kind == "dog":
                draw_dog(ctx, px, hy, sc, blink=blinks(t, [58, 82]), tail=0.4 * math.sin(t * 0.6),
                         ear=0.05 * math.sin(t * 0.3), tilt=0.07 * math.sin(t * 0.12))
            else:
                draw_cat(ctx, px, hy, sc, blink=blinks(t, [66]), tail=math.sin(t * 0.13),
                         ear=bump(t, 48, 7), tilt=-0.06 * math.sin(t * 0.12 + 1))


# =====================================================================
#  Linea de tiempo y transiciones
# =====================================================================
SCENES = [  # (fotograma inicial, fotograma final, funcion, color de fondo)
    (0, 90, scene_intro),
    (90, 150, lambda c, t: scene_service(c, t, 0)),
    (150, 210, lambda c, t: scene_service(c, t, 1)),
    (210, 270, lambda c, t: scene_service(c, t, 2)),
    (270, 360, scene_contact),
    (360, 450, scene_end),
]
TRANSITIONS = {1: ("circle", 10), 2: ("push", 9), 3: ("push", 9), 4: ("stripes", 13), 5: ("circle", 10)}
HOLD = {0: (52, 90), 1: (40, 60), 2: (40, 60), 3: (40, 60), 4: (58, 90), 5: (46, 90)}  # tramos quietos (control)


def scene_at(f):
    for k, (a, b, fn) in enumerate(SCENES):
        if a <= f < b:
            return k, f - a
    return len(SCENES) - 1, f - SCENES[-1][0]


def _wipe_region(ctx, q):
    xl = lambda y: -420 + (W + 840) * q + (y - H / 2) * 0.36
    ctx.move_to(-60, -60)
    ctx.line_to(xl(-60), -60)
    ctx.line_to(xl(H + 60), H + 60)
    ctx.line_to(-60, H + 60)
    ctx.close_path()


def render(ctx, f):
    k, t = scene_at(f)
    tr = TRANSITIONS.get(k)
    if not tr or t >= tr[1]:
        SCENES[k][2](ctx, t)
        return k, t, False
    kind, dur = tr
    p = (t + 1) / dur
    prev = lambda: SCENES[k - 1][2](ctx, f - SCENES[k - 1][0])
    nxt = lambda: SCENES[k][2](ctx, t)
    if kind == "circle":
        e = ease_in_out_cubic(p)
        R = 1180 * e
        with saved(ctx):
            prev()
        with saved(ctx):
            circle(ctx, 540, 960, R)
            ctx.clip()
            nxt()
        if p < 1:
            circle(ctx, 540, 960, R)
            stroke(ctx, LIGHT, 10 + 50 * (1 - e), 1.0)
    elif kind == "push":
        e = ease_in_out_cubic(p)
        with saved(ctx):
            ctx.translate(-W * e, 0)
            prev()
        with saved(ctx):
            ctx.translate(W * (1 - e), 0)
            ctx.rectangle(0, 0, W, H)
            ctx.clip()
            nxt()
        if p < 1:
            ctx.rectangle(W * (1 - e) - 16, 0, 32, H)
            fill(ctx, MID)
    else:  # stripes
        q = [ease_in_out_cubic(clamp(p * 1.4 - d)) for d in (0.0, 0.2, 0.4)]
        with saved(ctx):
            prev()
        _wipe_region(ctx, q[0])
        fill(ctx, LIGHT)
        _wipe_region(ctx, q[1])
        fill(ctx, DARK)
        with saved(ctx):
            _wipe_region(ctx, q[2])
            ctx.clip()
            nxt()
    return k, t, True


def make_surface():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    return surf, cairo.Context(surf)


def draw_frame(ctx, f):
    with saved(ctx):
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        src(ctx, DARK)
        ctx.paint()
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    with saved(ctx):
        return render(ctx, f)


# ---------------------------------------------------------------- control de calidad
def qa_check(frames=None):
    """Revisa que ningun texto quede fuera de la zona segura ni se pise con otro."""
    surf, ctx = make_surface()
    problems = []
    frames = frames if frames is not None else range(TOTAL)
    for f in frames:
        k, t = scene_at(f)
        a, b = HOLD[k]
        if not (a <= t < b):
            continue
        QA["on"], QA["boxes"] = True, []
        draw_frame(ctx, f)
        QA["on"] = False
        boxes = QA["boxes"]
        for (lab, (x0, y0, x1, y1)) in boxes:
            if x0 < SAFE[0] or y0 < SAFE[1] or x1 > SAFE[2] or y1 > SAFE[3]:
                problems.append(f"f{f} '{lab}' fuera de zona segura: ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f})")
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                (la, A), (lb, B) = boxes[i], boxes[j]
                ox = min(A[2], B[2]) - max(A[0], B[0])
                oy = min(A[3], B[3]) - max(A[1], B[1])
                if ox > 2 and oy > 2:
                    problems.append(f"f{f} textos encimados: '{la}' y '{lb}'")
    return sorted(set(problems))


def preview(out_dir, times):
    os.makedirs(out_dir, exist_ok=True)
    surf, ctx = make_surface()
    paths = []
    for sec in times:
        f = min(TOTAL - 1, int(round(sec * FPS)))
        draw_frame(ctx, f)
        surf.flush()
        p = os.path.join(out_dir, f"f{f:03d}_{sec:05.2f}s.png")
        surf.write_to_png(p)
        paths.append(p)
    return paths


def export(out_path):
    surf, ctx = make_surface()
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-tune", "animation",
           "-profile:v", "high", "-level", "4.1",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-r", str(FPS), "-frames:v", str(TOTAL), "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(TOTAL):
        draw_frame(ctx, f)
        surf.flush()
        proc.stdin.write(surf.get_data())
        if f % 45 == 0:
            print(f"  fotograma {f + 1}/{TOTAL}  ({time.time() - t0:.0f} s)", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("FFmpeg fallo al crear el video.")
    print(f"Listo: {out_path}  ({time.time() - t0:.0f} s)")


def main():
    ap = argparse.ArgumentParser(description="Genera el video de Patitas Ya")
    ap.add_argument("--preview", action="store_true", help="solo guarda fotogramas de control en previews/")
    ap.add_argument("--at", type=str, default="", help="segundos a previsualizar, ej: 1.5,4,10")
    ap.add_argument("--out", default=os.path.join(HERE, ARCHIVO_SALIDA))
    args = ap.parse_args()

    print("Control de textos (zona segura y superposiciones)...")
    probs = qa_check()
    for pr in probs[:40]:
        print("  ! " + pr)
    print("  OK, sin problemas." if not probs else f"  {len(probs)} avisos.")

    if args.preview:
        times = [float(x) for x in args.at.split(",")] if args.at else [1.0, 2.6, 4.6, 6.6, 8.6, 11.5, 14.5]
        for p in preview(os.path.join(HERE, "previews"), times):
            print("  " + p)
        return
    export(args.out)


if __name__ == "__main__":
    main()
