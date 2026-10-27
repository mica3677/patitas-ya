#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Renderiza una ilusion de giro ambiguo (puntos girando) a MP4 vertical, cuadro a cuadro.
No depende de ningun navegador: la calidad no cambia con el equipo.

Ejemplos:
    python3 ilusion_video.py                                  # esfera, 15 s, 1080x1920, 60 fps
    python3 ilusion_video.py --forma cilindro --puntos 9000
    python3 ilusion_video.py --arriba "¿Lo ves girar?" --abajo "SÍGUEME." --seg 20 --fps 30
    python3 ilusion_video.py --preview                        # solo un PNG de control
"""
import argparse, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
SS = 3                      # supersampling de la figura (bordes suaves)
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"]
FONTS_B = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"]
FONTS_I = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Oblique.ttf"]


PALETAS = {
    "clasico":  ("#000000", "#ffffff", "#ffffff", "#ffffff"),   # fondo, texto, puntos arriba (o grupo 1), puntos abajo (o grupo 0)
    "azul":     ("#000000", "#dbe7ff", "#8fb4ff", "#2f5bff"),
    "rojo_azul": ("#000000", "#ffffff", "#ff2d3d", "#2d6bff"),
    "oro_violeta": ("#000000", "#ffe9b0", "#ffc83d", "#6a4cff"),
    "fuego":    ("#060200", "#ffe2b8", "#ffd24a", "#ff4a1c"),
    "hielo":    ("#000308", "#eaf6ff", "#ffffff", "#6fc3ff"),
    "rosa":     ("#05020a", "#ffe3f4", "#ff8fd0", "#7c5cff"),
    "esmeralda": ("#000805", "#dcffee", "#9dffd0", "#12b886"),
    "cian":     ("#00080b", "#e0ffff", "#7cf8ff", "#2a7bff"),
    "plata":    ("#000000", "#ffffff", "#ffffff", "#8fa0b8"),
    "halloween": ("#0a0500", "#ffd9a0", "#ffb347", "#ff5e00"),
    "navidad":  ("#04100a", "#ffffff", "#ff5a5a", "#3ddc84"),
    "usa":      ("#040818", "#ffffff", "#ff4155", "#2f6bff"),
    "multicolor": ("#000000", "#ffffff", "#f4c542", "#2ec4f0", ["#f4c542", "#58e04a", "#8f4cf0", "#ff3b3b", "#ff7a1a", "#2ec4f0"]),   # seis colores: uno por pieza
    "arcoiris": ("#000000", "#ffffff", "#ff3b3b", "#9b5cff", ["#ff3b3b", "#ff9a1f", "#ffe14a", "#4cdc6a", "#3aa8ff", "#9b5cff"]),
}


def rgb(h):
    h = h.lstrip("#")
    if len(h) != 6:
        sys.exit(f"color invalido: #{h} (usa 6 digitos, ej. #ff8800)")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _aristas(v, e, n, rng):
    v = np.asarray(v, dtype=float); k = rng.integers(len(e), size=n); u = rng.random(n)[:, None]
    a = v[[e[i][0] for i in k]]; b = v[[e[i][1] for i in k]]
    return a + (b - a) * u


def _tri(u, v, A, B, C):
    d = lambda p, q, r: (p[0] - r[0]) * (q[1] - r[1]) - (q[0] - r[0]) * (p[1] - r[1])
    P = (u, v); d1, d2, d3 = d(P, A, B), d(P, B, C), d(P, C, A)
    return ~(((d1 < 0) | (d2 < 0) | (d3 < 0)) & ((d1 > 0) | (d2 > 0) | (d3 > 0)))


def _cara(u, v):
    """Cara tallada de la calabaza en (u = angulo desde el frente, v = altura -1..1): True = agujero."""
    ojos = (_tri(u, v, (-.62, .12), (-.22, .12), (-.42, .44)) | _tri(u, v, (.22, .12), (.62, .12), (.42, .44))
            | _tri(u, v, (-.1, -.04), (.1, -.04), (0, .12)))
    yc = -.38 + .35 * (u / .8) ** 2; k = np.floor((u + .8) / .16)
    diente = np.where(k % 2 == 1, v > yc, v < yc)
    boca = (np.abs(u) < .8) & (np.abs(v - yc) < .12) & ~diente
    return ojos | boca


def _cuerpo_calabaza(c, a):
    s = np.sqrt(1 - c * c); rr = 1 - .13 * (1 - np.abs(np.cos(4 * a)))     # 8 gajos
    return np.c_[s * np.cos(a) * rr, c * .78, s * np.sin(a) * rr]


def _n3(v):
    v = np.asarray(v, dtype=float); l = np.linalg.norm(v)
    return v / (l if l else 1.)


def _futbol_americano(n, rng):
    R, G = rng.random, rng.normal; out = []
    def P(s, u, rr=1.):
        rho = .54 * max(0., 1 - s * s) ** .75 * rr
        return [s * .98, rho * math.sin(u), rho * math.cos(u)]
    for _ in range(n):
        q = R()
        if q < .52: out.append(P(R() * 2 - 1, R() * 2 * math.pi))
        elif q < .72: out.append(P((-1 if R() < .5 else 1) * (.5 if R() < .5 else .58) + G() * .004, R() * 2 * math.pi))
        elif q < .82: out.append(P((R() * 2 - 1) * .3, G() * .012, 1.01))
        else: out.append(P(-.25 + int(R() * 6) * .1 + G() * .006, (R() * 2 - 1) * .14, 1.01))
    return np.array(out)


def _baloncesto(n, rng):
    R, G = rng.random, rng.normal; out = []; Rb = .95
    for _ in range(n):
        q = R(); t = R() * 2 * math.pi; c = math.cos(t) * Rb; s_ = math.sin(t) * Rb
        if q < .3: out.append(_n3(rng.normal(size=3)) * Rb)
        elif q < .5: out.append([c, G() * .006, s_])
        elif q < .7: out.append([c, s_, G() * .006])
        else:
            sg = 1 if q < .85 else -1; rho = 1.15
            out.append([Rb * math.sin(rho) * math.cos(t), Rb * math.sin(rho) * math.sin(t), sg * Rb * math.cos(rho)])
    return np.array(out)


def _futbol(n, rng):
    R = rng.random; f = (1 + 5 ** .5) / 2; Rb = .95; V = []
    for a in (-1, 1):
        for b in (-f, f):
            V += [[0, a, b], [a, b, 0], [b, 0, a]]
    V = np.array(V, dtype=float)
    E = [(i, j) for i in range(12) for j in range(i + 1, 12) if abs(((V[i] - V[j]) ** 2).sum() - 4) < .01]
    T = np.array([V[i] + (V[j] - V[i]) * t for i, j in E for t in (1 / 3, 2 / 3)])
    D = np.linalg.norm(T[:, None] - T[None], axis=2); dm = D[D > 1e-9].min()
    SE = [(i, j) for i in range(60) for j in range(i + 1, 60) if D[i, j] < dm * 1.02]
    caps = np.array([_n3(v) for v in V]); out = []
    for _ in range(n):
        q = R()
        if q < .74:
            a, b = SE[int(R() * len(SE))]; out.append(_n3(T[a] + (T[b] - T[a]) * R()) * Rb)
        elif q < .9:
            c = caps[int(R() * 12)]
            while True:
                v = c + (rng.random(3) * 2 - 1) * .27
                if np.linalg.norm(v - c) <= .27: break
            out.append(_n3(v) * Rb)
        else: out.append(_n3(rng.normal(size=3)) * Rb)
    return np.array(out)


def _ovni(n, rng):
    R, G = rng.random, rng.normal; out = []
    for _ in range(n):
        q = R(); a = R() * 2 * math.pi
        if q < .34:
            r = math.sqrt(R()); out.append([r * math.cos(a), .17 * max(0., 1 - r * r) ** .6 * (1 if R() < .5 else -1), r * math.sin(a)])
        elif q < .48:
            v = _n3([G(), abs(G()), G()]); out.append([v[0] * .36, .1 + v[1] * .36, v[2] * .36])
        elif q < .6:
            k = int(R() * 12) * math.pi / 6; out.append([.9 * math.cos(k) + G() * .03, G() * .025, .9 * math.sin(k) + G() * .03])
        elif q < .66: out.append([.97 * math.cos(a), G() * .01, .97 * math.sin(a)])
        elif q < .7: out.append([.45 * math.cos(a), -.14, .45 * math.sin(a)])
        else:
            y = -.18 - R() * .82; r = .06 + .64 * (-.18 - y) / .82; out.append([r * math.cos(a), y, r * math.sin(a)])
    return np.array(out)


def _cohete(n, rng):
    R, G = rng.random, rng.normal; out = []
    for _ in range(n):
        q = R(); a = R() * 2 * math.pi
        if q < .3: out.append([.22 * math.cos(a), -.5 + R() * 1.05, .22 * math.sin(a)])
        elif q < .42:
            t = R(); out.append([.22 * (1 - t) * math.cos(a), .55 + t * .45, .22 * (1 - t) * math.sin(a)])
        elif q < .58:
            az = int(R() * 3) * 2 * math.pi / 3 + math.pi / 2; u, v = R(), R()
            if u + v > 1: u, v = 1 - u, 1 - v
            r = .22 + v * .4; y = -.05 - u * .45 - v * .63
            out.append([r * math.cos(az) + G() * .004, y, r * math.sin(az) + G() * .004])
        elif q < .63:
            r = math.sqrt(R()); t = R() * 2 * math.pi; x = .1 * r * math.cos(t)
            out.append([x, .22 + .1 * r * math.sin(t), math.sqrt(max(0., .0484 - x * x)) + .005])
        elif q < .7: out.append([.225 * math.cos(a), .05 if R() < .5 else -.25, .225 * math.sin(a)])
        else:
            t = R(); r = .19 * (1 - t) * math.sqrt(R()); out.append([r * math.cos(a) + G() * .01, -.5 - t * .62, r * math.sin(a) + G() * .01])
    return np.array(out)


def _estrella(n, rng):
    R = rng.random; out = []
    V = [[(.4 if k % 2 else 1) * math.cos(math.pi / 2 + k * math.pi / 5), (.4 if k % 2 else 1) * math.sin(math.pi / 2 + k * math.pi / 5) - .095] for k in range(10)]
    for _ in range(n):
        q = R(); k = int(R() * 10); A = V[k]; B = V[(k + 1) % 10]
        if q < .55:
            u, v = R(), R()
            if u + v > 1: u, v = 1 - u, 1 - v
            out.append([A[0] * u + B[0] * v, (A[1] + .095) * u + (B[1] + .095) * v - .095, (1 if R() < .5 else -1) * (.04 + .13 * (1 - u - v))])
        elif q < .8:
            u = R(); out.append([A[0] + (B[0] - A[0]) * u, A[1] + (B[1] - A[1]) * u, (R() * 2 - 1) * .045])
        else:
            P = V[2 * int(R() * 5)]; u = R()
            out.append([P[0] * (1 - u), (P[1] + .095) * (1 - u) - .095, (1 if R() < .5 else -1) * (.17 * (1 - u) + .04)])
    return np.array(out)


def _copo(n, rng):
    V = [[0, 0, 0]]; E = []
    def add(p, q, w):
        V.append(p); V.append(q); E.extend([(len(V) - 2, len(V) - 1)] * w)
    for k in range(6):
        a = math.pi / 2 + k * math.pi / 3; d = [math.cos(a), math.sin(a)]
        add([0, 0, 0], [d[0], d[1], 0], 4)
        for t, L, w in ((.3, .42, 2), (.55, .3, 2), (.78, .18, 1)):
            for sg in (-1, 1):
                b = a + sg * math.pi / 3; p = [d[0] * t, d[1] * t, 0]
                add(p, [p[0] + math.cos(b) * L, p[1] + math.sin(b) * L, 0], w)
    pts = _aristas(np.array(V) * .95, E, n, rng)
    return pts + rng.normal(size=(n, 3)) * [.006, .006, .012]


def _arbol(n, rng):
    R, G = rng.random, rng.normal; out = []
    TI = [(-.6 + .36 * j, .6, .86 - .18 * j) for j in range(4)]
    gar = lambda s: [(.86 * (1 - s) + .04) * math.cos(s * 12 * math.pi), -.6 + 1.68 * s, (.86 * (1 - s) + .04) * math.sin(s * 12 * math.pi)]
    fin = lambda p: [p[0] * .88, (p[1] - .175) * .88, p[2] * .88]
    SV = [[(.4 if k % 2 else 1) * .13 * math.cos(math.pi / 2 + k * math.pi / 5), (.4 if k % 2 else 1) * .13 * math.sin(math.pi / 2 + k * math.pi / 5)] for k in range(10)]
    for _ in range(n):
        q = R(); a = R() * 2 * math.pi
        if q < .5:
            u = R(); yb, h, Rr = TI[0 if u < .4 else 1 if u < .7 else 2 if u < .9 else 3]
            t = R() ** .7; r = Rr * (1 - t) * (1 + .05 * math.cos(12 * a)); out.append(fin([r * math.cos(a), yb + h * t, r * math.sin(a)]))
        elif q < .54: out.append(fin([.1 * math.cos(a), -.85 + R() * .25, .1 * math.sin(a)]))
        elif q < .74:
            p = gar(R()); out.append(fin([p[0] + G() * .01, p[1], p[2] + G() * .01]))
        elif q < .92:
            p = gar(.06 + int(R() * 14) * .065); v = _n3(rng.normal(size=3))
            out.append(fin([p[0] * 1.1 + v[0] * .05, p[1] + v[1] * .05, p[2] * 1.1 + v[2] * .05]))
        else:
            k = int(R() * 10); A = SV[k]; B = SV[(k + 1) % 10]; u = R()
            out.append(fin([A[0] + (B[0] - A[0]) * u, 1.2 + A[1] + (B[1] - A[1]) * u, G() * .01]))
    return np.array(out)


def _fantasma(n, rng):
    R, G = rng.random, rng.normal; out = []; Rg = .55; hem = lambda a: -.72 + .13 * math.cos(4 * a)
    for _ in range(n):
        q = R(); a = R() * 2 * math.pi
        if q < .22:
            v = _n3([G(), abs(G()), G()]); out.append([v[0] * Rg, .3 + v[1] * Rg, v[2] * Rg])
        elif q < .7:
            h = hem(a); out.append([Rg * math.cos(a), h + R() * (.3 - h), Rg * math.sin(a)])
        elif q < .78: out.append([Rg * math.cos(a), hem(a) + G() * .006, Rg * math.sin(a)])
        elif q < .9:
            sx = -1 if R() < .5 else 1; r = math.sqrt(R()); t = R() * 2 * math.pi; ex = sx * .2 + .07 * r * math.cos(t)
            out.append([ex, .2 + .11 * r * math.sin(t), math.sqrt(max(0., Rg * Rg - ex * ex)) * .98])
        else:
            r = math.sqrt(R()); t = R() * 2 * math.pi; ex = .09 * r * math.cos(t)
            out.append([ex, -.12 + .13 * r * math.sin(t), math.sqrt(max(0., Rg * Rg - ex * ex)) * .98])
    return np.array(out)


def _calavera(n, rng):
    R, G = rng.random, rng.normal; out = []
    rx = lambda y: .62 * math.sqrt(max(0., 1 - ((y - .2) / .62) ** 2)) if y >= .2 else .62 - .26 * min(1., (.2 - y) / .7)
    zf = lambda x, y: rx(y) * 1.08 * math.sqrt(max(.02, 1 - (x / max(.05, rx(y))) ** 2)) + .006
    for _ in range(n):
        q = R(); a = R() * 2 * math.pi
        if q < .56 or q >= .92:
            y = -.5 + R() * 1.32; r = rx(y); out.append([r * math.cos(a), y, r * 1.08 * math.sin(a)])
        elif q < .62:
            sx = -1 if R() < .5 else 1; x = sx * .27 + .17 * math.cos(a); y = .1 + .2 * math.sin(a); out.append([x, y, zf(x, y)])
        elif q < .72:
            sx = -1 if R() < .5 else 1; r = math.sqrt(R()); x = sx * .27 + .17 * r * math.cos(a); y = .1 + .2 * r * math.sin(a); out.append([x, y, zf(x, y)])
        elif q < .76:
            u, v = R(), R()
            if u + v > 1: u, v = 1 - u, 1 - v
            x = -.08 * u + .08 * v; y = -.06 - .2 * u - .2 * v; out.append([x, y, zf(x, y)])
        elif q < .86:
            k = int(R() * 8); x = -.21 + k * .06 + G() * .003; y = -.5 + R() * .2; out.append([x, y, zf(x, y)])
        else:
            y = -.3 if R() < .5 else -.4; x = (R() * 2 - 1) * .23; out.append([x, y, zf(x, y)])
    return np.array(out)


def _telarana(n, rng):
    R, G = rng.random, rng.normal; out = []; M = 12; D = 2 * math.pi / M
    off = [m * D + G() * .04 for m in range(M)]
    def ring_pt():
        k = 1 + int(R() * 9); r0 = k * .105; m = int(R() * M); a0 = off[m]
        a1 = off[(m + 1) % M] + (2 * math.pi if m + 1 == M else 0); f = R(); a = a0 + (a1 - a0) * f; r = r0 * (1 - .1 * math.sin(math.pi * f))
        return [r * math.cos(a), r * math.sin(a)]
    dew = [ring_pt() for _ in range(18)]
    for _ in range(n):
        q = R()
        if q < .3:
            m = int(R() * M); r = math.sqrt(R()); out.append([r * math.cos(off[m]), r * math.sin(off[m]), G() * .008])
        elif q < .9:
            p = ring_pt(); out.append([p[0], p[1], G() * .008])
        else:
            p = dew[int(R() * len(dew))]; out.append([p[0] + G() * .012, p[1] + G() * .012, G() * .012])
    return np.array(out)



def _glifos(txt, mw, mh):
    """Letras a puntos: devuelve (x, y, esBorde) centrado y escalado a mw x mh."""
    CW, CH = 1200, 400
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts", "Poppins-ExtraBold.ttf")
    def fuente(sz):
        try: return ImageFont.truetype(ruta, int(sz))
        except OSError: return font(FONTS_B, int(sz))
    fs = 300; img = Image.new("L", (CW, CH), 0); d = ImageDraw.Draw(img)
    tw = d.textlength(txt, font=fuente(fs))
    if tw > 1100: fs = fs * 1100 / tw
    d.text((CW / 2, CH / 2 + 15), txt, font=fuente(fs), fill=255, anchor="mm")
    on = np.asarray(img) > 128
    def sh(dx, dy): return np.roll(np.roll(on, dy, 0), dx, 1)
    borde = on & ~(sh(3, 0) & sh(-3, 0) & sh(0, 3) & sh(0, -3))
    ys, xs = np.mgrid[0:CH:2, 0:CW:2]; sel = on[::2, ::2]
    px, py, pb = xs[sel], ys[sel], borde[::2, ::2][sel]
    if not len(px): return np.zeros((0, 3))
    sc = min(mw / max(1, px.max() - px.min()), mh / max(1, py.max() - py.min())); cx, cy = (px.min() + px.max()) / 2, (py.min() + py.max()) / 2
    return np.c_[(px - cx) * sc, -(py - cy) * sc, pb.astype(float)]


def _texto3d(n, rng, palabra):
    G = _glifos((palabra or "USA")[:14], 1.9, 1.2)
    if not len(G): return np.zeros((n, 3))
    T = .11; q = rng.random(n); i = rng.integers(len(G), size=n); bi = np.flatnonzero(G[:, 2] > .5)
    ib = bi[rng.integers(len(bi), size=n)] if len(bi) else i
    usar_borde = (q >= .68) & (len(bi) > 0); idx = np.where(usar_borde, ib, i)
    z = np.where(usar_borde, (rng.random(n) * 2 - 1) * T, np.where(q < .34, T, -T))
    return np.c_[G[idx, 0], G[idx, 1], z]


def _joya(n, rng):
    A = math.pi / 4; v = [[.5 * math.cos(k * A), .32 + .24, .5 * math.sin(k * A)] for k in range(8)]
    v += [[.95 * math.cos(k * A + A / 2), .24, .95 * math.sin(k * A + A / 2)] for k in range(8)] + [[0, -.8 + .24, 0]]
    e = []
    for k in range(8):
        k1 = (k + 1) % 8; e += [(k, k1), (k, k1), (8 + k, 8 + k1), (k, 8 + k), (k, 8 + (k + 7) % 8), (8 + k, 16), (8 + k, 16)]
    return _aristas(np.array(v), e, n, rng)



def _bandera(n, rng):
    R, G = rng.random, rng.normal; out = []; W0, H0 = .95, .5; cy0 = H0 - .538
    def P(x, y): return [x, y + .035 * ((x + W0) / (2 * W0)) * math.sin(4.5 * x + 1) + .23, .14 * ((x + W0) / (2 * W0)) * math.sin(4.5 * x)]
    stars = [[-W0 + (.1267 if r % 2 else .0633) + c * .1267, H0 - .0538 * (r + 1)] for r in range(9) for c in range(5 if r % 2 else 6)]
    for _ in range(n):
        q = R()
        if q < .06: out.append([-W0 - .02 + G() * .004, -.98 + R() * 1.5 + .23, G() * .006]); continue
        if q < .26: out.append(P(-W0 + R() * .76, cy0 + R() * .538)); continue
        if q < .42:
            st = stars[int(R() * len(stars))]; a = R() * 2 * math.pi; r = math.sqrt(R()) * .016; out.append(P(st[0] + r * math.cos(a), st[1] + r * math.sin(a))); continue
        for _g in range(80):
            x = -W0 + R() * 2 * W0; y = -H0 + R() * 2 * H0
            if x < -W0 + .76 and y > cy0: continue
            if int((H0 - y) * 13) % 2 == 0 or R() < .12: out.append(P(x, y)); break
    return np.array(out)


def _muneco(n, rng):
    R, G = rng.random, rng.normal; out = []; S = [(-.62, .5), (.05, .36), (.56, .25)]
    def pt(c, r): v = _n3(rng.normal(size=3)); return [v[0] * r, c + v[1] * r, v[2] * r]
    for _ in range(n):
        q = R(); a = R() * 2 * math.pi
        if q < .64:
            u = R(); c, r = S[0 if u < .5 else 1 if u < .8 else 2]; out.append(pt(c, r))
        elif q < .68:
            t = R(); r = .05 * (1 - t); out.append([r * math.cos(a), .56 + r * math.sin(a), .24 + t * .38])
        elif q < .72:
            sx = -1 if R() < .5 else 1; out.append([sx * .09 + G() * .012, .64 + G() * .012, .235 + G() * .006])
        elif q < .75:
            t = -.9 + int(R() * 5) * .45; out.append([.11 * t + G() * .006, .46 + .035 * t * t + G() * .006, .235 + G() * .005])
        elif q < .79: out.append([G() * .012, .14 - int(R() * 3) * .15 + G() * .012, .34 + G() * .006])
        elif q < .87:
            if R() < .6: out.append([.2 * math.cos(a), .8 + R() * .22, .2 * math.sin(a)])
            else:
                r = math.sqrt(R()) * .34; out.append([r * math.cos(a), .78, r * math.sin(a)])
        elif q < .92: out.append([.275 * math.cos(a), .38 + G() * .015, .275 * math.sin(a)])
        else:
            sx = -1 if R() < .5 else 1; t = R(); out.append([sx * (.33 + t * .55), .1 + t * .32 + G() * .006, G() * .006])
    out = np.array(out); out[:, 1] += .05
    return out


def _baston(n, rng):
    R = rng.random; L1, L2, L3 = 1.3, math.pi * .25, .2; L = L1 + L2 + L3; out = []
    def C(s):
        if s < L1: return (0., -.9 + s), (0., 1.)
        if s < L1 + L2:
            t = math.pi - (s - L1) / .25; return (.25 + .25 * math.cos(t), .4 + .25 * math.sin(t)), (math.sin(t), -math.cos(t))
        return (.5, .4 - (s - L1 - L2)), (0., -1.)
    for _ in range(n * 60):
        if len(out) >= n: break
        s = R() * L; psi = R() * 2 * math.pi; c, T = C(s); P = (-T[1], T[0]); ph = (s * 3.4 + psi / (2 * math.pi)) % 1
        if ph > .5 and R() > .12: continue
        out.append([c[0] + .09 * math.cos(psi) * P[0] - .25, c[1] + .09 * math.cos(psi) * P[1] + .13, .09 * math.sin(psi)])
    return np.array(out)



def _dado(n, rng):
    R = rng.random; H = .7; out = []; ed = []
    F = [(2, 1, 1), (2, -1, 6), (0, 1, 3), (0, -1, 4), (1, 1, 2), (1, -1, 5)]
    LY = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)], 4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
          5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)], 6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)]}
    pips = [(k, s_, u * .4, v * .4) for k, s_, c in F for u, v in LY[c]]
    for x in (-1, 1):
        for y in (-1, 1):
            for z in (-1, 1):
                p = [x, y, z]
                for k in range(3):
                    if p[k] < 0: q_ = list(p); q_[k] = 1; ed.append((np.array(p, float), np.array(q_, float)))
    for _ in range(n):
        q = R()
        if q < .22:
            p, r = ed[int(R() * 12)]; out.append((p + (r - p) * R()) * H)
        elif q < .5:
            k = int(R() * 3); p = [0., 0., 0.]; p[k] = -1 if R() < .5 else 1; p[(k + 1) % 3] = R() * 2 - 1; p[(k + 2) % 3] = R() * 2 - 1; out.append(np.array(p) * H)
        else:
            k, s_, u, v = pips[int(R() * len(pips))]; r = math.sqrt(R()) * .11; a = R() * 2 * math.pi; p = [0., 0., 0.]
            p[k] = s_ * H * 1.004; p[(k + 1) % 3] = u + r * math.cos(a); p[(k + 2) % 3] = v + r * math.sin(a); out.append(p)
    return np.array(out, dtype=float)


def _moneda(n, rng):
    R, G = rng.random, rng.normal; out = []; Gl = _glifos("$", .8, 1.15); GE = Gl[Gl[:, 2] > .5] if len(Gl) else Gl
    for _ in range(n):
        q = R(); a = R() * 2 * math.pi; f = 1 if R() < .5 else -1
        if q < .22:
            while True:
                b = R() * 2 * math.pi
                if math.sin(60 * b) >= -.2: break
            out.append([.95 * math.cos(b), .95 * math.sin(b), (R() * 2 - 1) * .045])
        elif q < .34: out.append([.88 * math.cos(a) + G() * .003, .88 * math.sin(a) + G() * .003, f * .055])
        elif q < .42: out.append([.78 * math.cos(a), .78 * math.sin(a), f * .05])
        elif q < .72 and len(Gl):
            pnt = GE[int(R() * len(GE))] if (R() < .35 and len(GE)) else Gl[int(R() * len(Gl))]; out.append([pnt[0], pnt[1], f * .07])
        else:
            r = math.sqrt(R()) * .88; out.append([r * math.cos(a), r * math.sin(a), f * .045])
    return np.array(out)



def _cubo_cortado(n, rng):
    """Cubo con una esquina abierta: por fuera un color (grupo 1) y por dentro otro (grupo 0)."""
    R = rng.random; H = .72; out = []; ed = []
    cut = lambda p: p[0] > 0 and p[1] > 0 and p[2] > 0
    for x in (-1, 1):
        for y in (-1, 1):
            for z in (-1, 1):
                p = [x, y, z]
                for k in range(3):
                    if p[k] < 0: q_ = list(p); q_[k] = 1; ed.append((np.array(p, float), np.array(q_, float)))
    for _ in range(n):
        q = R()
        if q < .5:
            while True:
                k = int(R() * 3); p = [0., 0., 0.]; p[k] = -H if R() < .5 else H; p[(k + 1) % 3] = (R() * 2 - 1) * H; p[(k + 2) % 3] = (R() * 2 - 1) * H
                if not cut(p): break
            out.append(p + [0, 1])
        elif q < .68:
            while True:
                a, b = ed[int(R() * 12)]; p = list((a + (b - a) * R()) * H)
                if not cut(p): break
            out.append(p + [0, 1])
        else:
            k = int(R() * 3); p = [0., 0., 0.]; p[(k + 1) % 3] = R() * H; p[(k + 2) % 3] = R() * H; out.append(p + [0, 0])
    return np.array(out)


def _medusa(n, rng):
    R, G = rng.random, rng.normal; out = []
    for _ in range(n):
        q = R(); a = R() * 2 * math.pi
        if q < .3:
            v = _n3([G(), abs(G()), G()]); rr = 1 + .06 * math.sin(10 * math.atan2(v[2], v[0])) * (1 - v[1])
            out.append([v[0] * .62 * rr, .35 + v[1] * .5, v[2] * .62 * rr, 0, 1])
        elif q < .38:
            m = int(R() * 12) * math.pi / 6; t = R() * math.pi / 2
            out.append([.62 * math.sin(t) * math.cos(m), .35 + .5 * math.cos(t), .62 * math.sin(t) * math.sin(m), 0, 1])
        elif q < .43:
            rr = 1 + .06 * math.sin(10 * a); out.append([.62 * rr * math.cos(a), .35, .62 * rr * math.sin(a), 0, 1])
        elif q < .58:
            t = R(); k = int(R() * 4) * math.pi / 2 + .4; ph = k + 5 * t
            out.append([.13 * math.cos(ph) + G() * .012, .3 - t * .95, .13 * math.sin(ph) + G() * .012, 0, 0])
        else:
            t = R(); tk = int(R() * 18) * 2 * math.pi / 18; r = .6 * (1 - .3 * t)
            out.append([r * math.cos(tk) + .05 * math.sin(8 * t + tk * 3), .35 - t * 1.1, r * math.sin(tk) + .05 * math.cos(8 * t + tk * 3), 0, 0])
    return np.array(out)


def _mariposa(n, rng):
    R, G = rng.random, rng.normal; out = []
    f = lambda th: math.exp(math.cos(th)) - 2 * math.cos(4 * th) - math.sin(th / 12) ** 5
    for _ in range(n):
        q = R()
        if q < .1: out.append([G() * .015, -.5 + R() * 1, G() * .015, 0, 1]); continue
        if q < .14:
            sg = -1 if R() < .5 else 1; t = R(); out.append([sg * (.03 + .25 * t), .4 + .32 * math.sqrt(t), G() * .004, 0, 1]); continue
        th = R() * 24 * math.pi; r = f(th) / 3.8; sc = 1. if q < .45 else .15 + .85 * R(); x = math.sin(th) * r * sc; y = math.cos(th) * r * sc
        out.append([x, y + .05, .22 * abs(x) + G() * .004, 0, 1 if sc > .72 else 0])
    return np.array(out)


def _planeta(n, rng):
    out = []
    def tierra(p):
        return (math.sin(2.1 * p[0] + 1.3 * p[1]) + math.sin(2.9 * p[1] - 1.7 * p[2] + 2) + math.sin(3.4 * p[2] + 2.2 * p[0] - 1)
                + .7 * math.sin(4.6 * p[0] - 3.1 * p[1] + .7 * p[2]) + .5 * math.sin(6.3 * p[1] + 5.2 * p[2] - p[0])) > 1.0
    for _ in range(n):
        for _g in range(300):
            v = _n3(rng.normal(size=3)); l = tierra(v)
            if l or rng.random() < .2: out.append([v[0] * .92, v[1] * .92, v[2] * .92, 0, 1 if l else 0]); break
    return np.array(out)


def _arbol_fractal(n, rng):
    R, G = rng.random, rng.normal; segs = []; tips = []; out = []
    def rot(v, ax, ang):
        c, s_ = math.cos(ang), math.sin(ang); d = float(np.dot(ax, v)); cr = np.cross(ax, v)
        return v * c + cr * s_ + ax * d * (1 - c)
    def grow(p, d, L, depth):
        q = p + d * L
        for _ in range(6 - depth): segs.append((p, q))
        if depth >= 6: tips.append(q); return
        kids = 3 if depth < 2 else 2 + (1 if R() < .4 else 0)
        for _c in range(kids):
            ax = _n3(rng.normal(size=3)); ax = _n3(ax - d * float(np.dot(ax, d)))
            grow(q, rot(d, ax, .4 + R() * .35), L * .74, depth + 1)
    grow(np.array([0., -.95, 0.]), np.array([0., 1., 0.]), .55, 0)
    for _ in range(n):
        if R() < .5:
            a, b = segs[int(R() * len(segs))]; out.append(list(a + (b - a) * R() + rng.normal(size=3) * .004) + [0, 0])
        else:
            t = tips[int(R() * len(tips))]; out.append(list(t + rng.normal(size=3) * .07) + [0, 1])
    out = np.array(out); y0, y1 = out[:, 1].min(), out[:, 1].max(); rm = np.hypot(out[:, 0], out[:, 2]).max()
    sc = min(1.9 / (y1 - y0), .95 / (rm or 1)); cy = (y0 + y1) / 2
    out[:, 0] *= sc; out[:, 2] *= sc; out[:, 1] = (out[:, 1] - cy) * sc
    return out


def _cometa(n, rng):
    R, G = rng.random, rng.normal; out = []; H = (.62, .25)
    for _ in range(n):
        q = R()
        if q < .22:
            v = _n3(rng.normal(size=3)); r = .13 * math.sqrt(R()); out.append([H[0] + v[0] * r, H[1] + v[1] * r, v[2] * r, 0, 1])
        elif q < .3:
            v = _n3(rng.normal(size=3)); out.append([H[0] + v[0] * .19, H[1] + v[1] * .19, v[2] * .19, 0, 1])
        else:
            t = R() ** .8; w = .03 + .3 * t
            if q < .6: ph = R() * 2 * math.pi; rr = w * math.sqrt(R())
            else: ph = t * 6 + int(R() * 5) * 2 * math.pi / 5; rr = w * .85
            out.append([H[0] - t * 1.6, H[1] - .5 * t * t + rr * math.cos(ph), rr * math.sin(ph), 0, 0])
    return np.array(out)


def _nebulosa(n, rng):
    R, G = rng.random, rng.normal; out = []
    B = [(rng.normal(size=3) * .3, np.array([.14 + R() * .16, .12 + R() * .14, .14 + R() * .16]), k % 2) for k in range(6)]
    for _ in range(n):
        if R() < .12: out.append([G() * .5, G() * .3, G() * .5, 0, 1])
        else:
            c, sz, g = B[int(R() * 6)]; out.append(list(c + rng.normal(size=3) * sz) + [0, g])
    return np.array(out)


def _plasma(n, rng):
    R, G = rng.random, rng.normal; out = []
    paths = []
    for _ in range(16):
        d = _n3(rng.normal(size=3)); P = [np.zeros(3)]; off = np.zeros(3)
        for k in range(1, 23): off = off + rng.normal(size=3) * .035; P.append(d * (k / 22 * .95) + off)
        paths.append(P)
    for _ in range(n):
        q = R()
        if q < .08: out.append(list(rng.normal(size=3) * .06) + [0, 1])
        elif q < .66:
            P = paths[int(R() * 16)]; k = int(R() * 22); out.append(list(P[k] + (P[k + 1] - P[k]) * R() + rng.normal(size=3) * .006) + [0, 1])
        else: out.append(list(_n3(rng.normal(size=3)) * .98) + [0, 0])
    return np.array(out)


def _explosion(n, rng):
    R = rng.random; D = [_n3(rng.normal(size=3)) for _ in range(90)]; out = []
    for _ in range(n):
        d = D[int(R() * 90)]; r = .1 + .88 * R() ** .8; out.append(list(d * r + rng.normal(size=3) * .004) + [0, 0 if r > .6 else 1])
    return np.array(out)


def _esfera_fib(n, rng):
    i = np.arange(n); y = 1 - 2 * (i + .5) / n; r = np.sqrt(1 - y * y); g = math.pi * (3 - 5 ** .5)
    return np.c_[np.cos(i * g) * r, y, np.sin(i * g) * r]


def _mitades(n, rng):
    R, G = rng.random, rng.normal; out = []; Rr = .85; Gp = .12
    for _ in range(n):
        q = R(); sg = -1 if R() < .5 else 1; a = R() * 2 * math.pi
        if q < .6:
            v = _n3(rng.normal(size=3)); l = v[0] < 0; out.append([v[0] * Rr + (-Gp if l else Gp), v[1] * Rr, v[2] * Rr, 0, 1 if l else 0])
        elif q < .82:
            r = math.sqrt(R()) * Rr; out.append([sg * Gp, r * math.cos(a), r * math.sin(a), 0, 1 if sg < 0 else 0])
        else: out.append([sg * Gp, Rr * math.cos(a), Rr * math.sin(a), 0, 1 if sg < 0 else 0])
    return np.array(out)


def _cuencos(n, rng):
    R = rng.random; out = []; Rr = .8; C = .28
    for _ in range(n):
        q = R(); sg = 1 if R() < .5 else -1; a = R() * 2 * math.pi
        if q < .84:
            v = _n3(rng.normal(size=3)); out.append([abs(v[0]) * sg * Rr - sg * C, v[1] * Rr, v[2] * Rr, 0, 1 if sg == 1 else 0])
        else: out.append([-sg * C, Rr * math.cos(a), Rr * math.sin(a), 0, 1 if sg == 1 else 0])
    return np.array(out)


def _planeta_cortado(n, rng):
    R = rng.random; out = []; SH = [(.95, 1), (.72, 0), (.5, 1)]
    cut = lambda p: p[0] > 0 and p[1] > 0 and p[2] > 0
    while len(out) < n:
        q = R()
        if q < .6:
            v = _n3(rng.normal(size=3)); r, g = SH[int(R() * 3)]; p = v * r
            if not cut(p): out.append(list(p) + [0, g])
        elif q < .9:
            k = int(R() * 3); r = math.sqrt(R()) * .95; t = R() * math.pi / 2; p = [0., 0., 0.]; p[(k + 1) % 3] = r * math.cos(t); p[(k + 2) % 3] = r * math.sin(t)
            out.append(p + [0, 1 if r > .72 else 0 if r > .5 else 1 if r > .25 else 0])
        else:
            v = _n3(rng.normal(size=3)); r = .25 * R() ** (1 / 3); p = v * r
            if not cut(p): out.append(list(p) + [0, 0])
    return np.array(out)


def _toro_cortado(n, rng):
    R = rng.random; out = []; R0, r0 = .65, .3
    def P(u, rr, v): return [(R0 + rr * math.cos(v)) * math.cos(u), rr * math.sin(v), (R0 + rr * math.cos(v)) * math.sin(u)]
    for _ in range(n):
        if R() < .62: out.append(P(math.pi / 2 + R() * 1.5 * math.pi, r0, R() * 2 * math.pi) + [0, 1])
        else: out.append(P(0 if R() < .5 else math.pi / 2, math.sqrt(R()) * r0, R() * 2 * math.pi) + [0, 0])
    return np.array(out)


def _esfera_en_cubo(n, rng):
    R = rng.random; out = []; H = .66; ed = []
    for x in (-1, 1):
        for y in (-1, 1):
            for z in (-1, 1):
                p = [x, y, z]
                for k in range(3):
                    if p[k] < 0: q_ = list(p); q_[k] = 1; ed.append((np.array(p, float), np.array(q_, float)))
    for _ in range(n):
        q = R()
        if q < .26:
            a, b = ed[int(R() * 12)]; out.append(list((a + (b - a) * R()) * H) + [0, 1])
        elif q < .34:
            k = int(R() * 3); p = [0., 0., 0.]; p[k] = -H if R() < .5 else H; p[(k + 1) % 3] = (R() * 2 - 1) * H; p[(k + 2) % 3] = (R() * 2 - 1) * H; out.append(p + [0, 1])
        else: out.append(list(_n3(rng.normal(size=3)) * .42) + [0, 0])
    return np.array(out)


def _cubitos(n, rng):
    R = rng.random; out = []; S_, h = .56, .2
    for _ in range(n):
        c = [int(R() * 3) - 1 for _ in range(3)]; g = (c[0] + c[1] + c[2]) % 2; k = int(R() * 3); p = [0., 0., 0.]
        if R() < .2:
            p[k] = (-1 if R() < .5 else 1) * h; p[(k + 1) % 3] = (R() * 2 - 1) * h; p[(k + 2) % 3] = (R() * 2 - 1) * h
        else:
            p = [(-1 if R() < .5 else 1) * h for _ in range(3)]; p[k] = (R() * 2 - 1) * h
        out.append([c[0] * S_ + p[0], c[1] * S_ + p[1], c[2] * S_ + p[2], 0, g])
    return np.array(out)



def _conos_anidados(n, rng):
    R = rng.random; out = []
    for _ in range(n):
        q = R(); t = math.sqrt(R())
        if q < .5 or q >= .9:
            while True:
                a = R() * 2 * math.pi
                if not (.5 < a < 2.2): break
            out.append([.85 * t * math.cos(a), -.9 + t * 1.7, .85 * t * math.sin(a), 0, 1] if q < .5 else [.85 * math.cos(a), .8, .85 * math.sin(a), 0, 1])
        else:
            a = R() * 2 * math.pi; out.append([.5 * t * math.cos(a), -.6 + t * 1.1, .5 * t * math.sin(a), 0, 0])
    return np.array(out)


def _cubo_puntos(n, rng):
    R = rng.random; H = .7; out = []; ed = []
    for x in (-1, 1):
        for y in (-1, 1):
            for z in (-1, 1):
                p = [x, y, z]
                for k in range(3):
                    if p[k] < 0: q_ = list(p); q_[k] = 1; ed.append((np.array(p, float), np.array(q_, float)))
    for _ in range(n):
        if R() < .76:
            a, b = ed[int(R() * 12)]; out.append(list((a + (b - a) * R()) * H))
        else:
            k = int(R() * 3); p = [0., 0., 0.]; p[k] = -H if R() < .5 else H; p[(k + 1) % 3] = (R() * 2 - 1) * H; p[(k + 2) % 3] = (R() * 2 - 1) * H; out.append(p)
    return np.array(out)


def _cubo_partido(n, rng):
    R = rng.random; out = []; H, G = .7, .1; ext = [(0., H), (-H, H), (-H, H)]
    for _ in range(n):
        sg = -1 if R() < .5 else 1; k = int(R() * 3); p = [0., 0., 0.]
        if R() < .45:
            for m in range(3): p[m] = ext[m][0] + R() * (ext[m][1] - ext[m][0]) if m == k else ext[m][0 if R() < .5 else 1]
        else:
            for m in range(3): p[m] = ext[m][0] + R() * (ext[m][1] - ext[m][0])
            p[k] = ext[k][0 if R() < .5 else 1]
        out.append([sg * (p[0] + G), p[1], p[2], 0, 1 if sg < 0 else 0])
    return np.array(out)


def _esfera_diagonal(n, rng):
    R = rng.random; out = []; Rr, G, a = .85, .12, .6; nx = (math.cos(a), math.sin(a)); e1 = (-math.sin(a), math.cos(a))
    for _ in range(n):
        q = R(); sg = -1 if R() < .5 else 1; t = R() * 2 * math.pi
        if q < .6:
            v = _n3(rng.normal(size=3)); s2 = -1 if v[0] * nx[0] + v[1] * nx[1] < 0 else 1
            out.append([v[0] * Rr + s2 * G * nx[0], v[1] * Rr + s2 * G * nx[1], v[2] * Rr, 0, 1 if s2 < 0 else 0])
        else:
            r = math.sqrt(R()) * Rr if q < .85 else Rr
            out.append([sg * G * nx[0] + r * math.cos(t) * e1[0], sg * G * nx[1] + r * math.cos(t) * e1[1], r * math.sin(t), 0, 1 if sg < 0 else 0])
    return np.array(out)


def _toro_partido(n, rng):
    R = rng.random; out = []; R0, r0, G = .65, .3, .1
    def P(u, rr, v): return [(R0 + rr * math.cos(v)) * math.cos(u), rr * math.sin(v), (R0 + rr * math.cos(v)) * math.sin(u)]
    for _ in range(n):
        sg = 1 if R() < .5 else -1; v = R() * 2 * math.pi
        p = P((0 if sg > 0 else math.pi) + (R() - .5) * math.pi, r0, v) if R() < .66 else P(math.pi / 2 if R() < .5 else -math.pi / 2, math.sqrt(R()) * r0, v)
        out.append([p[0] + sg * G, p[1], p[2], 0, 0 if sg > 0 else 1])
    return np.array(out)


def _cono_partido(n, rng):
    R = rng.random; out = []; G = .1
    for _ in range(n):
        q = R(); sg = -1 if R() < .5 else 1; t = math.sqrt(R()); g = 1 if sg < 0 else 0
        if q < .58:
            a = (R() - .5) * math.pi; r = .85 * t; out.append([sg * (r * math.cos(a) + G), -.9 + t * 1.7, r * math.sin(a), 0, g])
        elif q < .9: out.append([sg * G, -.9 + t * 1.7, (R() * 2 - 1) * .85 * t, 0, g])
        else:
            a = (R() - .5) * math.pi; out.append([sg * (.85 * math.cos(a) + G), .8, .85 * math.sin(a), 0, g])
    return np.array(out)


def _cilindro_partido(n, rng):
    R = rng.random; out = []; Rc, Hh, G = .55, .95, .1
    for _ in range(n):
        q = R(); sg = -1 if R() < .5 else 1; a = (R() - .5) * math.pi; g = 1 if sg < 0 else 0
        if q < .55: out.append([sg * (Rc * math.cos(a) + G), (R() * 2 - 1) * Hh, Rc * math.sin(a), 0, g])
        elif q < .85: out.append([sg * G, (R() * 2 - 1) * Hh, (R() * 2 - 1) * Rc, 0, g])
        else: out.append([sg * (Rc * math.cos(a) + G), -Hh if R() < .5 else Hh, Rc * math.sin(a), 0, g])
    return np.array(out)


def _flechas_ciclo(n, rng):
    """Dos cintas de 152 grados (dorada y violeta) con punta de flecha, medidas cuadro por cuadro sobre el video de referencia.
    Sin tapas: bordes gruesos y brillantes, puntos tenues en las cintas y en las puntas, y un hueco de 28 grados entre una flecha y la otra."""
    Hh, Hb, L, SPAN = .49, .93, .65, math.radians(152); TE = math.radians(62); m = round(n / 2); r = rng.random; g = []
    tg = np.array([math.cos(TE), 0, -math.sin(TE)]); P = lambda t, y: np.array([math.sin(t), y, math.cos(t)])
    A, B, tip = P(TE, -Hb), P(TE, Hb), P(TE + math.radians(40), 0)      # la punta queda sobre el cilindro, 40 grados mas adelante
    for _ in range(m):
        q = r(); br = 1.0; sg = .0045
        if q < .60: p = P(TE - SPAN * r(), (r() * 2 - 1) * Hh); br = .8                        # cinta: puntos tenues
        elif q < .68: p = P(TE - SPAN * r(), Hh)                                                  # borde grueso de arriba
        elif q < .76: p = P(TE - SPAN * r(), -Hh)                                                 # borde grueso de abajo
        elif q < .79: p = P(TE - SPAN, (r() * 2 - 1) * Hh)                                        # arranque de la cinta
        elif q < .84: u = r(); p = A + (B - A) * u                                                # base de la punta
        elif q < .88: u = r(); s_ = (A, B)[r() < .5]; p = s_ + (tip - s_) * u; sg = .0025       # lados de la punta, mas finos
        else:
            u, v = r(), r()
            if u + v > 1: u, v = 1 - u, 1 - v
            p = A + (B - A) * u + (tip - A) * v; br = .8                                          # relleno de la punta (misma densidad que la cinta)
        g.append(np.append(p + rng.normal(size=3) * sg, br))
    g = np.array(g); o = np.zeros((len(g), 7)); o[:, :3] = g[:, :3]; o[:, 4] = 1; o[:, 5] = 1; o[:, 6] = g[:, 3]
    p2 = np.zeros((len(g), 7)); p2[:, :3] = -g[:, :3]; p2[:, 5] = 1; p2[:, 6] = g[:, 3]
    return np.vstack([o, p2])


def _mitades_contrarias(n, rng):
    R = rng.random; out = []; Rr, G = .85, .12
    for _ in range(n):
        q = R()
        if q < .3:
            m = int(R() * 8) * math.pi / 4; t = R() * math.pi; v = [math.sin(t) * math.cos(m), math.cos(t), math.sin(t) * math.sin(m)]
        else: v = _n3(rng.normal(size=3))
        if q < .75:
            l = v[0] < 0; out.append([v[0] * Rr + (-G if l else G), v[1] * Rr, v[2] * Rr, 0, 1 if l else 0, 1 if l else -1])
        else:
            sg = -1 if R() < .5 else 1; a = R() * 2 * math.pi; r = math.sqrt(R()) * Rr
            out.append([sg * G, r * math.cos(a), r * math.sin(a), 0, 1 if sg < 0 else 0, 1 if sg < 0 else -1])
    return np.array(out)


def _esferas_contrarias(n, rng):
    R = rng.random; out = []; SH = [(.92, 1, 1), (.66, 0, -1), (.4, 1, 2)]
    for _ in range(n):
        u = R(); r, g, sp = SH[0 if u < .5 else 1 if u < .82 else 2]
        if R() < .5:
            m = int(R() * 12) * math.pi / 6; t = R() * math.pi; v = [math.sin(t) * math.cos(m), math.cos(t), math.sin(t) * math.sin(m)]
        else: v = _n3(rng.normal(size=3))
        out.append([v[0] * r, v[1] * r, v[2] * r, 0, g, sp])
    return np.array(out)


def _cubos_contrarios(n, rng):
    R = rng.random; out = []; ed = []; CB = [(.8, 1, 1), (.46, 0, -1)]
    for x in (-1, 1):
        for y in (-1, 1):
            for z in (-1, 1):
                p = [x, y, z]
                for k in range(3):
                    if p[k] < 0: q_ = list(p); q_[k] = 1; ed.append((np.array(p, float), np.array(q_, float)))
    for _ in range(n):
        H, g, sp = CB[0 if R() < .6 else 1]
        if R() < .72:
            a, b = ed[int(R() * 12)]; out.append(list((a + (b - a) * R()) * H) + [0, g, sp])
        else:
            k = int(R() * 3); p = [0., 0., 0.]; p[k] = -H if R() < .5 else H; p[(k + 1) % 3] = (R() * 2 - 1) * H; p[(k + 2) % 3] = (R() * 2 - 1) * H; out.append(p + [0, g, sp])
    return np.array(out)


def _rodajas(n, rng):
    R = rng.random; out = []; Rr = .88
    for _ in range(n):
        k = int(R() * 7); y = -.78 + k * .26; r = math.sqrt(max(.02, Rr * Rr - y * y)); a = R() * 2 * math.pi; q = R()
        if q < .35:
            m = int(R() * 12) * math.pi / 6; rr = math.sqrt(R()) * r; p = [rr * math.cos(m), y, rr * math.sin(m)]
        elif q < .55: p = [r * math.cos(a), y, r * math.sin(a)]
        else:
            rr = math.sqrt(R()) * r; p = [rr * math.cos(a), y, rr * math.sin(a)]
        out.append(p + [0, k % 2, -1 if k % 2 else 1])
    return np.array(out)


def _en_poli(p, poly):
    c = False; j = len(poly) - 1
    for i in range(len(poly)):
        a, b = poly[i], poly[j]
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]: c = not c
        j = i
    return c


def _prisma(n, polys, L, sc, rng):
    """Prisma: contorno en x,y (con huecos opcionales) extruido +-L en z; bordes marcados y caras de puntos."""
    R = rng.random; segs = []; cum = []; av = []; tot = 0.
    for P in polys:
        for i in range(len(P)):
            a, b = P[i], P[(i + 1) % len(P)]; segs.append((a, b)); tot += math.hypot(b[0] - a[0], b[1] - a[1]); cum.append(tot); av.append(a)
    xs = [p[0] for p in polys[0]]; ys = [p[1] for p in polys[0]]; x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cum = np.array(cum); out = []
    pick = lambda: int(np.searchsorted(cum, R() * tot))
    for _ in range(n):
        q = R()
        if q < .45:
            a, b = segs[pick()]; u = R(); p = [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, L if R() < .5 else -L]
        elif q < .7:
            v = av[int(R() * len(av))]; p = [v[0], v[1], (R() * 2 - 1) * L]
        elif q < .86:
            a, b = segs[pick()]; u = R(); p = [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, (R() * 2 - 1) * L]
        else:
            while True:
                t = (x0 + R() * (x1 - x0), y0 + R() * (y1 - y0))
                if _en_poli(t, polys[0]) and not any(_en_poli(t, h) for h in polys[1:]): break
            p = [t[0], t[1], L if R() < .5 else -L]
        out.append([(p[0] - cx) * sc, (p[1] - cy) * sc, p[2] * sc])
    return np.array(out)


def _cajas(n, boxes, rng):
    """Varias cajas [cx,cy,cz,hx,hy,hz]: aristas marcadas y caras de puntos."""
    R = rng.random; A = np.array([b[3] * b[4] + b[4] * b[5] + b[3] * b[5] for b in boxes]); cum = np.cumsum(A); out = []
    for _ in range(n):
        k = min(int(np.searchsorted(cum, R() * cum[-1])), len(boxes) - 1); cx, cy, cz, hx, hy, hz = boxes[k]; h = [hx, hy, hz]; p = [0., 0., 0.]; a = int(R() * 3)
        if R() < .7:
            for m in range(3): p[m] = (R() * 2 - 1) * h[m] if m == a else (-1 if R() < .5 else 1) * h[m]
        else:
            for m in range(3): p[m] = (R() * 2 - 1) * h[m]
            p[a] = (-1 if R() < .5 else 1) * h[a]
        out.append([cx + p[0], cy + p[1], cz + p[2]])
    return np.array(out)


def _piramide_video(n, rng):
    """La piramide de base cuadrada del video 'triangulo negro': eje de giro a media altura, proporcion 4:3, fase inicial 10 grados."""
    R, G = rng.random, rng.normal; s_, hh = .643, .859; ph = math.radians(10)
    V0 = np.array([[0, 0, hh], [-s_, -s_, -hh], [s_, -s_, -hh], [s_, s_, -hh], [-s_, s_, -hh]])
    V = np.c_[V0[:, 0] * math.cos(ph) + V0[:, 2] * math.sin(ph), V0[:, 1], -V0[:, 0] * math.sin(ph) + V0[:, 2] * math.cos(ph)]
    E = [(0, 1), (0, 2), (0, 3), (0, 4), (1, 2), (2, 3), (3, 4), (4, 1)]; F = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (1, 2, 3), (1, 3, 4)]
    LN = np.array([np.linalg.norm(V[a] - V[b]) for a, b in E]); AR = np.array([np.linalg.norm(np.cross(V[b] - V[a], V[c] - V[a])) / 2 for a, b, c in F])
    cl, ca_ = np.cumsum(LN), np.cumsum(AR); out = []
    for _ in range(n):
        if R() < .8:
            a, b = E[min(int(np.searchsorted(cl, R() * cl[-1])), len(E) - 1)]; out.append(list(V[a] + (V[b] - V[a]) * R() + rng.normal(size=3) * .0022))
        else:
            a, b, c = F[min(int(np.searchsorted(ca_, R() * ca_[-1])), len(F) - 1)]; u, v = R(), R()
            if u + v > 1: u, v = 1 - u, 1 - v
            out.append(list(V[a] + (V[b] - V[a]) * u + (V[c] - V[a]) * v))
    return np.array(out)


def _casita(n, rng):
    """Casita con puerta, ventanas, chimenea y humo: la casa de un color (grupo 1) y los detalles de otro (grupo 0)."""
    R, G = rng.random, rng.normal; Wd, Lh, E, Rg, K, SH = .6, .6, .09, .69, .9, .23; out = []
    poly = [(-Wd, -.69), (Wd, -.69), (Wd, E), (0, Rg), (-Wd, E)]
    for p in _prisma(round(n * .54), [poly], Lh, 1., rng): out.append([p[0] * K, (p[1] - SH) * K, p[2] * K, 0, 1])
    WS = [(0, .28, .2, 'z', 1), (-.36, -.38, .22, 'z', 1), (.36, -.38, .22, 'z', 1), (0, .28, .2, 'z', -1), (-.36, -.38, .22, 'z', -1), (.36, -.38, .22, 'z', -1),
          (.25, -.36, .24, 'x', 1), (-.25, -.36, .24, 'x', 1), (.25, -.36, .24, 'x', -1), (-.25, -.36, .24, 'x', -1)]
    SM = [(.37, .78, -.25, .05), (.43, .95, -.25, .075), (.5, 1.14, -.25, .1)]
    def win(cx, cy, s_, pl, sg):
        h = s_ / 2
        if R() < .3: u, v = (R() * 2 - 1) * h, (R() * 2 - 1) * h
        else:
            k = int(R() * 6); t = (R() * 2 - 1) * h; u, v = [(t, -h), (t, h), (-h, t), (h, t), (t, 0), (0, t)][k]
        u += G() * .003; v += G() * .003
        return [cx + u, cy + v, sg * (Lh + .004)] if pl == 'z' else [sg * (Wd + .004), cy + v, cx + u]
    while len(out) < n:
        q = R()
        if q < .5:
            w = WS[int(R() * len(WS))]; p = win(*w)
        elif q < .72:
            r = R()
            if r < .45:
                k = int(R() * 3); t = R(); d = [(-.12, -.69 + t * .42), (.12, -.69 + t * .42), (-.12 + t * .24, -.27)][k]
            elif r < .85:
                R2 = (-.33, -.45) if R() < .5 else (-.5, -.64); k = int(R() * 4); t = R()
                d = [(-.075 + t * .15, R2[0]), (-.075 + t * .15, R2[1]), (-.075, R2[0] + t * (R2[1] - R2[0])), (.075, R2[0] + t * (R2[1] - R2[0]))][k]
            else: d = (.085 + G() * .007, -.52 + G() * .007)
            p = [d[0] + G() * .003, d[1] + G() * .003, Lh + .004]
        elif q < .88:
            lo = [.28, .2, -.34]; hi = [.46, .62, -.16]; a = int(R() * 3); p = [0., 0., 0.]
            if R() < .6:
                for m in range(3): p[m] = lo[m] + R() * (hi[m] - lo[m]) if m == a else (lo[m] if R() < .5 else hi[m])
            else:
                for m in range(3): p[m] = lo[m] + R() * (hi[m] - lo[m])
                p[a] = lo[a] if R() < .5 else hi[a]
        else:
            s2 = SM[int(R() * 3)]; p = [s2[0] + G() * s2[3], s2[1] + G() * s2[3] * .8, s2[2] + G() * s2[3]]
        out.append([p[0] * K, (p[1] - SH) * K, p[2] * K, 0, 0])
    return np.array(out)


def _buho(n, rng):
    R, G = rng.random, rng.normal; out = []; rx, ry, rz = .62, .78, .58
    zb = lambda x, y: rz * math.sqrt(max(.01, 1 - (x / rx) ** 2 - (y / ry) ** 2))
    def tri(A, B, C):
        u, v = R(), R()
        if u + v > 1: u, v = 1 - u, 1 - v
        return [A[0] + (B[0] - A[0]) * u + (C[0] - A[0]) * v, A[1] + (B[1] - A[1]) * u + (C[1] - A[1]) * v]
    while len(out) < n:
        q = R(); a = R() * 2 * math.pi; sx = -1 if R() < .5 else 1
        if q < .38:
            v = _n3(rng.normal(size=3)); out.append([v[0] * rx, v[1] * ry, v[2] * rz, 0, 1])
        elif q < .47:
            x = sx * .25 + .25 * math.cos(a); y = .25 + .25 * math.sin(a); out.append([x, y, zb(x, y) + .012, 0, 0])
        elif q < .6:
            r = .14 * math.sqrt(R()); x = sx * .25 + r * math.cos(a); y = .25 + r * math.sin(a); out.append([x, y, zb(x, y) + .016, 0, 0])
        elif q < .66:
            p = tri((-.06, .06), (.06, .06), (0, -.1)); out.append([p[0], p[1], zb(p[0], p[1]) + .05, 0, 0])
        elif q < .74:
            t = R(); seg = int(R() * 3); P = [(sx * .5, .55), (sx * .42, .9), (sx * .2, .7)]; A, B = P[seg], P[(seg + 1) % 3]
            out.append([A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, .3, 0, 1])
        elif q < .9:
            row = int(R() * 4); y0 = -.08 - row * .19; k = int(R() * 5); cx = -.36 + k * .18 + (.09 if row % 2 else 0); t = R() * math.pi
            x = cx + .09 * math.cos(t); y = y0 - .09 * math.sin(t)
            if (x / rx) ** 2 + (y / ry) ** 2 < .8: out.append([x, y, zb(x, y) + .012, 0, 0])
        elif q < .97:
            ph = sx * (1.05 if R() < .5 else 1.25); th = .35 + R() * 2.0
            out.append([math.sin(th) * math.sin(ph) * rx * 1.01, math.cos(th) * ry, math.sin(th) * math.cos(ph) * rz * 1.01, 0, 1])
        else: out.append([sx * .18 + G() * .03, -.78 + G() * .015, .25 + G() * .03, 0, 0])
    return np.array(out[:n])


def _gato(n, rng):
    R, G = rng.random, rng.normal; out = []; rx, ry, rz = .78, .62, .6
    zh = lambda x, y: rz * math.sqrt(max(.05, 1 - (x / rx) ** 2 - (y / ry) ** 2))
    while len(out) < n:
        q = R(); a = R() * 2 * math.pi; sx = -1 if R() < .5 else 1
        if q < .4:
            v = _n3(rng.normal(size=3)); out.append([v[0] * rx, v[1] * ry, v[2] * rz, 0, 1])
        elif q < .52:
            P = [(sx * .72, .3), (sx * .62, .98), (sx * .28, .58)]; seg = int(R() * 3); A, B = P[seg], P[(seg + 1) % 3]; t = R()
            out.append([A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, .22, 0, 1])
        elif q < .58:
            u, v = R(), R()
            if u + v > 1: u, v = 1 - u, 1 - v
            A, B, C = (sx * .62, .4), (sx * .55, .82), (sx * .35, .56)
            out.append([A[0] + (B[0] - A[0]) * u + (C[0] - A[0]) * v, A[1] + (B[1] - A[1]) * u + (C[1] - A[1]) * v, .24, 0, 0])
        elif q < .7:
            x = sx * .3 + .12 * math.cos(a); y = .08 + .15 * math.sin(a); out.append([x, y, zh(x, y) + .012, 0, 0])
        elif q < .82:
            r = math.sqrt(R()); u = .12 * r * math.cos(a); y = .08 + .15 * r * math.sin(a)
            if abs(u) >= .028: x = sx * .3 + u; out.append([x, y, zh(x, y) + .016, 0, 0])
        elif q < .85:
            u, v = R(), R()
            if u + v > 1: u, v = 1 - u, 1 - v
            x = (v - u) * .07; y = -.12 + u * .08 + v * .08; out.append([x, y, zh(x, y) + .02, 0, 0])
        elif q < .9:
            t = R(); x = sx * .16 * t; y = -.2 - .07 * math.sin(math.pi * t * .9); out.append([x, y, zh(x, y) + .012, 0, 0])
        else:
            k = int(R() * 3) - 1; t = R(); x = sx * (.42 + t * .55); y = -.1 + k * .05 + k * t * .12; out.append([x, y, max(.1, zh(sx * .42, -.1) * (1 - t * .5)), 0, 0])
    return np.array(out[:n])


def _hongo(n, rng):
    R, G = rng.random, rng.normal; out = []
    SP = [_n3([G() * 1.1, abs(G()) + .35, G() * 1.1]) for _ in range(9)]
    for _ in range(n):
        q = R(); a = R() * 2 * math.pi
        if q < .46:
            v = _n3([G(), abs(G()), G()]); out.append([v[0] * .9, .05 + v[1] * .62, v[2] * .9, 0, 1])
        elif q < .66:
            c = SP[int(R() * 9)]
            while True:
                v = _n3([c[0] + G() * .12, c[1] + G() * .12, c[2] + G() * .12])
                if np.linalg.norm(v - c) <= .13: break
            out.append([v[0] * .905, .05 + v[1] * .625, v[2] * .905, 0, 0])
        elif q < .76:
            r = .3 + R() * .55; k = int(R() * 18) * math.pi / 9; out.append([r * math.cos(k), .05, r * math.sin(k), 0, 0])
        elif q < .96:
            y = -.85 + R() * .9; r = .18 + .1 * ((.05 - y) / .9) ** 1.5; out.append([r * math.cos(a), y, r * math.sin(a), 0, 0])
        else: out.append([.27 * math.cos(a), -.35 + G() * .01, .27 * math.sin(a), 0, 0])
    return np.array(out)


def _rot_y(P, a):
    P = np.asarray(P, dtype=float); c, s_ = math.cos(a), math.sin(a)
    return np.c_[P[:, 0] * c + P[:, 2] * s_, P[:, 1], -P[:, 0] * s_ + P[:, 2] * c]


def _flechas(n, rng):
    ARW = [(-.07, -.3), (.07, -.3), (.07, .06), (.2, .06), (0, .4), (-.2, .06), (-.07, .06)]; H = [1, .82, 1.12, .9, 1.06, .86]; K, R = 6, .62; out = []
    for k in range(K):
        h = H[k]; th = k * math.pi / 3 + .3; half = .35 * 1.9 * h
        w = _rot_y(_prisma(round(n / K), [ARW], .03, 1.9 * h, rng), th)
        out.append(np.c_[w[:, 0] + R * math.sin(th), w[:, 1] - .7 + half, w[:, 2] + R * math.cos(th), np.zeros(len(w)), np.full(len(w), k)])
    return np.vstack(out)


def _cadena(n, rng):
    R = rng.random; out = []; K, Rr, sp = 6, .22, .27
    for i in range(n):
        k = i % K; t = R() * 2 * math.pi; tt = R() * 2 * math.pi; r = Rr + math.cos(tt) * .018; y = (k - 2.5) * sp; c = r * math.cos(t); s_ = r * math.sin(t); q = math.sin(tt) * .018
        out.append([q, y + s_, c, 0, k] if k % 2 else [c, y + s_, q, 0, k])
    return np.array(out)


def _torre_aros(n, rng):
    R, G = rng.random, rng.normal; out = []; tilt = [.12, -.1, .15, -.14, .1, -.12]; rad = [.8, .68, .56, .45, .35, .26]
    for _ in range(n):
        if R() < .08: out.append([G() * .018, -.95 + R() * 1.9, G() * .018, 0, 2]); continue
        k = int(R() * 6); u = R() * 2 * math.pi; v = R() * 2 * math.pi; rr = rad[k] + .085 * math.cos(v); x = rr * math.cos(u); y = .085 * math.sin(v); z = rr * math.sin(u); a = tilt[k]
        out.append([x, y * math.cos(a) - z * math.sin(a) - .72 + k * .27, y * math.sin(a) + z * math.cos(a), 0, k])
    return np.array(out)


def _lapices(n, rng):
    R, G = rng.random, rng.normal; out = []; K, r, TIP, LEN, RB = 6, .085, .2, 1.3, .19; TOP = [.6, .42, .7, .5, .66, .38]
    for i in range(n):
        k = i % K; a0 = k * math.pi / 3; cx, cz = RB * math.cos(a0), RB * math.sin(a0); top = TOP[k] - .15; bot = top - LEN; q = R(); j = int(R() * 6); aj = j * math.pi / 3; a2 = (j + 1) * math.pi / 3
        lerp = lambda u: (cx + r * (math.cos(aj) + (math.cos(a2) - math.cos(aj)) * u), cz + r * (math.sin(aj) + (math.sin(a2) - math.sin(aj)) * u))
        if q < .42: p = [cx + r * math.cos(aj), bot + R() * LEN, cz + r * math.sin(aj)]
        elif q < .56:
            x, z = lerp(R()); p = [x, bot if R() < .5 else top, z]
        elif q < .72:
            u = R(); p = [cx + r * math.cos(aj) * (1 - u), top + TIP * u, cz + r * math.sin(aj) * (1 - u)]
        elif q < .9:
            x, z = lerp(R()); p = [x, bot + R() * LEN, z]
        else:
            u = .7 + R() * .3; p = [cx + G() * .004 + r * math.cos(aj) * (1 - u) * .4, top + TIP * u, cz + G() * .004 + r * math.sin(aj) * (1 - u) * .4]
        out.append(p + [0, k])
    return np.array(out)


def _escalera_cubos(n, rng):
    R = rng.random; out = []; S_, h = 12, .13
    for _ in range(n):
        s_ = int(R() * S_); a = s_ * .62; c = (.52 * math.sin(a), -.78 + s_ * .14, .52 * math.cos(a)); k = int(R() * 3)
        if R() < .6:
            p = [(-1 if R() < .5 else 1) * h for _ in range(3)]; p[k] = (R() * 2 - 1) * h
        else:
            p = [(R() * 2 - 1) * h for _ in range(3)]; p[k] = (-1 if R() < .5 else 1) * h
        w = _rot_y([p], a)[0]; out.append([c[0] + w[0], c[1] + w[1], c[2] + w[2], 0, s_ % 6])
    return np.array(out)


def _aspas(n, rng):
    R, G = rng.random, rng.normal; out = []; K, Rr = 6, .9
    for i in range(n):
        k = i % K; a0 = k * 2 * math.pi / K; A = (0, 0); B = (Rr * math.cos(a0), Rr * math.sin(a0)); C = (.55 * Rr * math.cos(a0 + .75), .55 * Rr * math.sin(a0 + .75)); z = (k - 2.5) * .035
        if R() < .6:
            P = [A, B, C]; e = int(R() * 3); X, Y = P[e], P[(e + 1) % 3]; t = R(); p = [X[0] + (Y[0] - X[0]) * t, X[1] + (Y[1] - X[1]) * t]
        else:
            u, v = R(), R()
            if u + v > 1: u, v = 1 - u, 1 - v
            p = [B[0] * u + C[0] * v, B[1] * u + C[1] * v]
        out.append([p[0] + G() * .003, p[1] + G() * .003, z, 0, k])
    return np.array(out)


def formas(nombre, n, rng, palabra="USA"):
    if nombre == "esfera":
        M, P = 12, 9
        pts = np.empty((n, 3))
        for i in range(n):
            if i % 2:
                a = rng.integers(M) / M * 2 * math.pi; th = rng.random() * math.pi
            else:
                a = rng.random() * 2 * math.pi; th = (1 + rng.integers(P)) / (P + 1) * math.pi
            pts[i] = [math.sin(th) * math.cos(a), math.cos(th), math.sin(th) * math.sin(a)]
        return pts
    if nombre == "cilindro":
        a = rng.random(n) * 2 * math.pi; y = rng.random(n) * 2 - 1
        return np.c_[np.cos(a) * .55, y * .95, np.sin(a) * .55]
    if nombre == "toro":
        u = rng.random(n) * 2 * math.pi; v = rng.random(n) * 2 * math.pi; R, r = .7, .28
        return np.c_[(R + r * np.cos(v)) * np.cos(u), r * np.sin(v), (R + r * np.cos(v)) * np.sin(u)]
    if nombre == "helice":
        out = []
        for i in range(n):
            s_ = i % 3; y = rng.random() * 2 - 1; a = y * 3 * math.pi
            if s_ < 2: out.append([math.cos(a + s_ * math.pi) * .5, y, math.sin(a + s_ * math.pi) * .5, 0, s_])
            else:
                b = round(y * 8) / 8; ab = b * 3 * math.pi; u = rng.random() * 2 - 1
                out.append([math.cos(ab) * .5 * u, b, math.sin(ab) * .5 * u, 0, 1 if u > 0 else 0])
        return np.array(out)
    if nombre == "cono":
        t = np.sqrt(rng.random(n)); a = rng.random(n) * 2 * math.pi
        return np.c_[np.cos(a) * .75 * t, 1 - 2 * t, np.sin(a) * .75 * t]
    if nombre == "piramide":
        return _aristas([[-.7, -.8, -.7], [.7, -.8, -.7], [.7, -.8, .7], [-.7, -.8, .7], [0, .95, 0]],
                       [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (1, 4), (2, 4), (3, 4)], n, rng)
    if nombre == "cono_invertido":
        q = formas("cono", n, rng); q[:, 1] *= -1
        return q
    if nombre == "galaxia":
        b = 2.4; th = lambda r: b * np.log(r / .08) + .5; P = lambda m: rng.normal(size=m)
        cr = .15 + .8 * np.sqrt(rng.random(40)); ca = th(cr) + rng.integers(2, size=40) * math.pi + P(40) * .08
        q = rng.random(n); cnt = lambda lo, hi: int(((q >= lo) & (q < hi)).sum())
        m = cnt(0, .15); bulbo = np.c_[P(m) * .13, P(m) * .07, P(m) * .13]
        m = cnt(.15, .20); nucleo = P(m * 3).reshape(m, 3) * [.04, .03, .04]
        m = cnt(.20, .26); al = P(m) * .2; ac = P(m) * .04
        barra = np.c_[al * math.cos(.5) - ac * math.sin(.5), P(m) * .025, al * math.sin(.5) + ac * math.cos(.5)]
        m = cnt(.26, .78); r = .08 + .92 * rng.random(m) ** .85
        arm = np.where(rng.random(m) < .72, rng.integers(2, size=m) * math.pi, math.pi / 2 + rng.integers(2, size=m) * math.pi)
        a = th(r) + arm + P(m) * (.1 + .1 * r)       # 2 brazos principales y 2 menores
        brazos = np.c_[r * np.cos(a), P(m) * .02 * (1.2 - r) + .05 * r * r * np.sin(a), r * np.sin(a)]
        m = cnt(.78, .88); j = rng.integers(40, size=m)                      # cumulos de estrellas jovenes
        cumulos = np.c_[cr[j] * np.cos(ca[j]) + P(m) * .02, P(m) * .012, cr[j] * np.sin(ca[j]) + P(m) * .02]
        m = cnt(.88, .96); r = rng.random(m) ** .7; a = rng.random(m) * 2 * math.pi        # disco entre brazos
        disco = np.c_[r * np.cos(a), P(m) * .03 * (1.2 - r), r * np.sin(a)]
        m = cnt(.96, 1.01); halo = P(m * 3).reshape(m, 3) * [.5, .18, .5]
        return np.r_[bulbo, nucleo, barra, brazos, cumulos, disco, halo]
    if nombre == "tornado":
        y = rng.random(n) * 2 - 1; h = (y + 1) / 2
        rad = (.1 + .72 * h ** 1.6) * (1 + rng.normal(size=n) * .04)
        ang = y * 5 + rng.integers(4, size=n) * math.pi / 2 + rng.normal(size=n) * .07
        return np.c_[np.cos(ang) * rad, y * .95, np.sin(ang) * rad]
    if nombre == "saturno":
        nb = int(n * .42); v = rng.normal(size=(nb, 3)); v = v / np.linalg.norm(v, axis=1, keepdims=True) * .5
        m = n - nb; r = .72 + .36 * rng.random(m); r[(r > .92) & (r < .96)] += .04   # hueco entre anillos
        a = rng.random(m) * 2 * math.pi; px = r * np.cos(a); t = .4
        return np.r_[v, np.c_[px * math.cos(t), px * math.sin(t) + rng.normal(size=m) * .004, r * np.sin(a)]]
    if nombre == "agujero_negro":
        # disco de accrecion fino (gira) + luz curvada y anillo de fotones fijos en pantalla (4ta columna = 1)
        R, G = rng.random, rng.normal; out = []
        for _ in range(n):
            q = R(); a = R() * 2 * math.pi
            if q < .6:
                for _t in range(60):
                    r = .52 + .62 * R() ** 1.9; aa = R() * 2 * math.pi
                    w = .5 + .5 * math.cos(3 * (aa - 4 * math.log(r / .52))); w = w * w * .8 + .2
                    if R() <= w: break
                out.append([r * math.cos(aa), G() * .006 * (1 + 3 * r * r), r * math.sin(aa), 0])
            elif q < .67:
                r = .5 + abs(G()) * .012; out.append([r * math.cos(a), G() * .004, r * math.sin(a), 0])
            elif q < .77:
                r = .4 + G() * .0035; out.append([r * math.cos(a), r * math.sin(a), 0, 1])
            elif q < .95:
                ph = (1 if R() < .5 else -1) * math.pi / 2 + G() * .5; r = .41 + R() ** 1.6 * .2
                out.append([r * math.cos(ph), r * math.sin(ph), 0, 1])
            else:
                r = .9 + R() * .35; out.append([r * math.cos(a), G() * .03 * (r - .5), r * math.sin(a), 0])
        return np.array(out)
    if nombre == "calabaza":
        ns, ng, ne, nf = int(n * .05), int(n * .04), int(n * .06), int(n * .30); nb = n - ns - ng - ne - nf
        t = rng.random(ns); a2 = rng.random(ns) * 2 * math.pi
        tallo = np.c_[.07 * np.cos(a2) + .12 * t * t, .72 + .3 * t, .07 * np.sin(a2)]
        vela = np.c_[rng.normal(size=ng) * .18, -.05 + rng.normal(size=ng) * .15, rng.normal(size=ng) * .18]
        u = (rng.random(ne * 30) * 2 - 1) * .85; v = (rng.random(ne * 30) * 2 - 1) * .62; D = .04     # borde marcado de la cara
        borde = ~_cara(u, v) & (_cara(u + D, v) | _cara(u - D, v) | _cara(u, v + D) | _cara(u, v - D))
        borde_pts = _cuerpo_calabaza(v[borde][:ne], np.pi / 2 + u[borde][:ne])
        uf = (rng.random(nf * 20) * 2 - 1) * .85; vf = (rng.random(nf * 20) * 2 - 1) * .62          # ojos, nariz y boca encendidos por la vela
        kf = _cara(uf, vf); relleno = _cuerpo_calabaza(vf[kf][:nf], np.pi / 2 + uf[kf][:nf]) * .97
        c = rng.random(nb * 2) * 2 - 1; a = rng.random(nb * 2) * 2 * math.pi
        uu = np.arctan2(np.sin(a - math.pi / 2), np.cos(a - math.pi / 2))
        ok = ~((np.abs(uu) < .85) & (np.abs(c) < .62) & _cara(uu, c))
        cuerpo = _cuerpo_calabaza(c[ok][:nb], a[ok][:nb])
        return np.r_[cuerpo, borde_pts, relleno, vela, tallo]
    if nombre == "reloj_arena":
        u = rng.random(n); a = rng.random(n) * 2 * math.pi; t = np.sqrt(rng.random(n)); yy = rng.random(n) * 2 - 1
        vidrio = np.c_[(.12 + .6 * yy ** 2) * np.cos(a), yy, (.12 + .6 * yy ** 2) * np.sin(a)]
        ya = np.where(rng.random(n) < .5, 1., -1.); rb = .72 + rng.normal(size=n) * .006
        borde = np.c_[rb * np.cos(a), ya, rb * np.sin(a)]
        pila = np.c_[.6 * t * np.cos(a), -.95 + .45 * (1 - t), .6 * t * np.sin(a)]
        hilo = np.c_[rng.normal(size=n) * .008, -.5 + rng.random(n) * .5, rng.normal(size=n) * .008]
        ys = .5 + .3 * t; rs = (.12 + .6 * ys ** 2) * .92 * t
        arriba = np.c_[rs * np.cos(a), ys, rs * np.sin(a)]
        piezas = [vidrio, borde, pila, hilo, arriba]; cortes = [.5, .62, .84, .9]
        idx = np.digitize(u, cortes)
        return np.array([piezas[idx[i]][i] for i in range(n)])
    if nombre == "luna":
        nz = lambda v: v / np.linalg.norm(v, axis=-1, keepdims=True)
        cr = nz(rng.normal(size=(18, 3))); rh = .07 + rng.random(18) * .2
        ns = int(n * .4); sup = nz(rng.normal(size=(ns, 3))) * .95
        m = n - ns; j = rng.integers(18, size=m); c = cr[j]
        h = np.where((np.abs(c[:, 1]) < .9)[:, None], [0, 1, 0], [1, 0, 0]).astype(float)
        e1 = nz(np.cross(c, h)); e2 = np.cross(c, e1)
        rr = np.where(rng.random(m) < .75, rh[j], rh[j] * np.sqrt(rng.random(m))); t = rng.random(m) * 2 * math.pi
        cra = .95 * (np.cos(rr)[:, None] * c + np.sin(rr)[:, None] * (np.cos(t)[:, None] * e1 + np.sin(t)[:, None] * e2))
        return np.r_[sup, cra]
    if nombre == "teseracto":
        V = np.array([[(m >> b & 1) * 2 - 1 for b in range(4)] for m in range(16)], dtype=float)
        f = 1 / (3.2 - V[:, 3]); pr = V[:, :3] * f[:, None]; pr = pr / np.abs(pr).max() * .7
        e = [(i, i | (1 << b)) for i in range(16) for b in range(4) if not (i >> b) & 1]
        return _aristas(pr, e, n, rng)
    if nombre == "bobina":
        u = rng.random(n) * 2 * math.pi; v = 14 * u + np.where(rng.random(n) < .5, 0, math.pi); R, r = .7, .28
        j = lambda: rng.normal(size=n) * .006
        return np.c_[(R + r * np.cos(v)) * np.cos(u) + j(), r * np.sin(v) + j(), (R + r * np.cos(v)) * np.sin(u) + j()]
    if nombre == "sierpinski":
        V = np.array([[0, 1.04, 0]] + [[.98 * math.cos(math.radians(a)), -.35, .98 * math.sin(math.radians(a))] for a in (90, 210, 330)]) * .88
        pick = rng.integers(4, size=n + 30); p = np.zeros(3); out = np.empty((n + 30, 3))
        for i in range(n + 30):
            p = (p + V[pick[i]]) / 2; out[i] = p
        return out[30:]
    if nombre == "futbol_americano": return _futbol_americano(n, rng)
    if nombre == "baloncesto": return _baloncesto(n, rng)
    if nombre == "futbol": return _futbol(n, rng)
    if nombre == "ovni": return _ovni(n, rng)
    if nombre == "cohete": return _cohete(n, rng)
    if nombre == "estrella": return _estrella(n, rng)
    if nombre == "copo": return _copo(n, rng)
    if nombre == "arbol_navidad": return _arbol(n, rng)
    if nombre == "fantasma": return _fantasma(n, rng)
    if nombre == "calavera": return _calavera(n, rng)
    if nombre == "telarana": return _telarana(n, rng)
    if nombre == "texto3d": return _texto3d(n, rng, palabra)
    if nombre == "joya": return _joya(n, rng)
    if nombre == "bandera": return _bandera(n, rng)
    if nombre == "muneco_nieve": return _muneco(n, rng)
    if nombre == "baston_caramelo": return _baston(n, rng)
    if nombre == "dado": return _dado(n, rng)
    if nombre == "moneda": return _moneda(n, rng)
    if nombre == "cubo": return _cubo_cortado(n, rng)
    if nombre == "medusa": return _medusa(n, rng)
    if nombre == "mariposa": return _mariposa(n, rng)
    if nombre == "planeta": return _planeta(n, rng)
    if nombre == "arbol_fractal": return _arbol_fractal(n, rng)
    if nombre == "cometa": return _cometa(n, rng)
    if nombre == "nebulosa": return _nebulosa(n, rng)
    if nombre == "plasma": return _plasma(n, rng)
    if nombre == "explosion": return _explosion(n, rng)
    if nombre == "esfera_fibonacci": return _esfera_fib(n, rng)
    if nombre == "mitades": return _mitades(n, rng)
    if nombre == "cuencos": return _cuencos(n, rng)
    if nombre == "planeta_cortado": return _planeta_cortado(n, rng)
    if nombre == "toro_cortado": return _toro_cortado(n, rng)
    if nombre == "esfera_en_cubo": return _esfera_en_cubo(n, rng)
    if nombre == "cubitos": return _cubitos(n, rng)
    if nombre == "conos_anidados": return _conos_anidados(n, rng)
    if nombre == "cubo_puntos": return _cubo_puntos(n, rng)
    if nombre == "cubo_partido": return _cubo_partido(n, rng)
    if nombre == "esfera_diagonal": return _esfera_diagonal(n, rng)
    if nombre == "toro_partido": return _toro_partido(n, rng)
    if nombre == "cono_partido": return _cono_partido(n, rng)
    if nombre == "cilindro_partido": return _cilindro_partido(n, rng)
    if nombre == "flechas_ciclo": return _flechas_ciclo(n, rng)
    if nombre == "mitades_contrarias": return _mitades_contrarias(n, rng)
    if nombre == "esferas_contrarias": return _esferas_contrarias(n, rng)
    if nombre == "cubos_contrarios": return _cubos_contrarios(n, rng)
    if nombre == "rodajas": return _rodajas(n, rng)
    if nombre == "prisma_triangular": return _prisma(n, [[(-.5, .45), (-.5, -.45), (.55, 0)]], .45, 1.3, rng)
    if nombre == "prisma_hexagonal": return _prisma(n, [[(.6 * math.cos(k * math.pi / 3), .6 * math.sin(k * math.pi / 3)) for k in range(6)]], .45, 1.25, rng)
    if nombre == "casita": return _casita(n, rng)
    if nombre == "buho": return _buho(n, rng)
    if nombre == "gato": return _gato(n, rng)
    if nombre == "hongo": return _hongo(n, rng)
    if nombre == "rampa": return _prisma(n, [[(-.6, -.4), (.6, -.4), (.6, .4)]], .5, 1.2, rng)
    if nombre == "escalera": return _prisma(n, [[(-.6, -.6), (.6, -.6), (.6, .6), (.3, .6), (.3, .3), (0, .3), (0, 0), (-.3, 0), (-.3, -.3), (-.6, -.3)]], .35, 1.15, rng)
    if nombre == "cruz": return _cajas(n, [(0, 0, 0, .75, .14, .14), (0, 0, 0, .14, .75, .14), (0, 0, 0, .14, .14, .75)], rng)
    if nombre == "marco": return _prisma(n, [[(-.8, -.8), (.8, -.8), (.8, .8), (-.8, .8)], [(-.5, -.5), (-.5, .5), (.5, .5), (.5, -.5)]], .3, 1., rng)
    if nombre == "torre_escalonada": return _cajas(n, [(0, -.7, 0, .75, .18, .75), (0, -.34, 0, .55, .18, .55), (0, .02, 0, .38, .18, .38), (0, .38, 0, .2, .18, .2), (0, .7, 0, .09, .14, .09)], rng)
    if nombre == "piramide_video": return _piramide_video(n, rng)
    if nombre == "flechas": return _flechas(n, rng)
    if nombre == "cadena": return _cadena(n, rng)
    if nombre == "torre_aros": return _torre_aros(n, rng)
    if nombre == "lapices": return _lapices(n, rng)
    if nombre == "escalera_cubos": return _escalera_cubos(n, rng)
    if nombre == "aspas": return _aspas(n, rng)
    sys.exit("forma desconocida: " + nombre)


def envolver(draw, texto, f, ancho):
    lineas, cur = [], ""
    for p in texto.split():
        t = (cur + " " + p).strip()
        if draw.textlength(t, font=f) > ancho and cur:
            lineas.append(cur); cur = p
        else:
            cur = t
    return lineas + ([cur] if cur else [])


def capa_texto(arriba, abajo, diseno="clasico"):
    img = Image.new("L", (W, H), 0); d = ImageDraw.Draw(img)
    if diseno == "triangulo":     # medido sobre el video: Space Mono 48,8 px (titulo) y 38,5 px cursiva (abajo)
        carpeta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")
        f1 = ImageFont.truetype(os.path.join(carpeta, "SpaceMono-Regular.ttf"), 48.8)
        for i, l in enumerate(envolver(d, arriba, f1, W * .7)):
            d.text((W / 2, 375 + i * 74), l, font=f1, fill=255, anchor="ms")
        f2 = ImageFont.truetype(os.path.join(carpeta, "SpaceMono-Italic.ttf"), 38.5)
        d.text((W / 2 + 1.5, 1500), abajo, font=f2, fill=255, anchor="ms")
        return np.asarray(img, dtype=np.float32) / 255
    f1 = font(FONTS_B, 52)
    for i, l in enumerate(envolver(d, arriba, f1, W * .8)):
        d.text((W / 2, 200 + i * 72), l, font=f1, fill=255, anchor="mt")
    f2 = font(FONTS_I, 40)
    d.text((W / 2, H - 330), abajo, font=f2, fill=255, anchor="mt")
    return np.asarray(img, dtype=np.float32) / 255


# ---------------------------------------------------------------------------------------------------------------
# Figura escondida: un campo de puntos donde una mitad sube y la otra baja. La figura solo existe en el MOVIMIENTO
# (principio gestaltico del destino comun): dentro de la silueta se ven solo los puntos que suben, afuera solo los que
# bajan. En una captura quieta la densidad es pareja y no se ve nada.
# ---------------------------------------------------------------------------------------------------------------
CAMPOS = ["campo_estrella", "campo_corazon", "campo_rayo", "campo_circulo", "campo_flecha", "campo_palabra"]


def _silueta(nombre, palabra, tam, t, seg):
    """Mascara booleana (tam x tam, centro = centro del campo) de la figura en el instante t. Gira, respira y se desplaza despacio."""
    m = Image.new("L", (tam, tam), 0); d = ImageDraw.Draw(m); c = tam / 2
    resp = 1 + .06 * math.sin(2 * math.pi * t / 7); R = tam * .30 * resp
    ox, oy = tam * .03 * math.sin(2 * math.pi * t / 11), tam * .03 * math.cos(2 * math.pi * t / 13)
    rot = 2 * math.pi * t / 26
    def poligono(pp, girar=True):
        q = [((x * math.cos(rot) - y * math.sin(rot)) if girar else x, (x * math.sin(rot) + y * math.cos(rot)) if girar else y) for x, y in pp]
        d.polygon([(c + ox + x * R, c + oy + y * R) for x, y in q], fill=255)
    if nombre == "campo_estrella":
        poligono([((1 if k % 2 == 0 else .46) * math.sin(k * math.pi / 5), -(1 if k % 2 == 0 else .46) * math.cos(k * math.pi / 5)) for k in range(10)])
    elif nombre == "campo_corazon":
        pp = [(16 * math.sin(a) ** 3 / 17, -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) / 17 + .05) for a in np.linspace(0, 2 * math.pi, 120)]
        poligono(pp, girar=False)
    elif nombre == "campo_rayo":
        poligono([(.25, -1), (-.55, .12), (-.05, .12), (-.3, 1), (.6, -.2), (.08, -.2), (.5, -1)], girar=False)
    elif nombre == "campo_circulo":
        d.ellipse((c + ox - R, c + oy - R, c + ox + R, c + oy + R), fill=255)
    elif nombre == "campo_flecha":
        poligono([(-1, -.28), (.15, -.28), (.15, -.7), (1, 0), (.15, .7), (.15, .28), (-1, .28)])
    elif nombre == "campo_palabra":
        ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts", "Poppins-ExtraBold.ttf")
        txt = (palabra or "HOLA").upper(); fs = 400
        try: f = ImageFont.truetype(ruta, fs)
        except OSError: f = font(FONTS_B, fs)
        tw = d.textlength(txt, font=f); fs = fs * min(1, tam * .86 / tw) * resp; f = ImageFont.truetype(ruta, int(fs))
        d.text((c + ox, c + oy), txt, font=f, fill=255, anchor="mm")
    return np.asarray(m) > 127


def render_campo(a):
    rng = np.random.default_rng(a.semilla)
    FR = int(W * .435); FS = 2 * FR                                  # radio y lado del campo (circular, casi todo el ancho)
    n = a.puntos; v = a.vueltas_min * 14.0                           # px/s de deriva
    x0 = rng.random(n) * FS; y0 = rng.random(n) * FS
    capa = np.where(rng.random(n) < .5, -1, 1); ruido = rng.random(n) < .12      # -1 sube, 1 baja; 12% van a su aire
    ang = rng.random(n) * 2 * math.pi; r_i = rng.random(n); s_i = rng.random(n)
    pal = PALETAS[a.paleta]; pbg, ptx, pa, pb = pal[:4]
    c_bg, c_tx = rgb(a.fondo or pbg), rgb(a.texto or ptx); c_a = rgb(a.color or pa); c_b = rgb(a.color2) if a.color2 else (rgb(pb) if not a.color else c_a)
    texto = capa_texto(a.arriba, a.abajo, a.diseno); base = c_bg + (c_tx - c_bg) * texto[..., None]
    if a.estrellas:
        sr = np.random.default_rng(a.semilla + 101); N = a.estrellas
        sx, sy = sr.integers(0, W - 3, N), sr.integers(0, H - 3, N); sb = .15 + .6 * sr.random(N) * sr.random(N); sz = np.where(sr.random(N) < .15, 3, 2)
        for k in range(N): base[sy[k]:sy[k] + sz[k], sx[k]:sx[k] + sz[k]] += c_tx * sb[k]
    cy = H * (.5 if a.diseno == "triangulo" else .47)
    box = (int(W / 2 - FR - 6), int(cy - FR - 6), int(W / 2 + FR + 6), int(cy + FR + 6)); bw, bh = box[2] - box[0], box[3] - box[1]
    total = int(round(a.seg * a.fps)); r_px = a.tam * .6 * SS
    pausa = a.pausa or 0.0; t_p = a.seg * .62      # pausa didactica: todo se congela y la figura desaparece
    rev = a.revela or 0.0; t_rev0, t_rev1 = (0.0, rev) if rev > 0 else (-1.0, 0.0)                    # por defecto la figura esta desde el primer segundo; --revela S la ordena de a poco
    DS = 2

    def fotograma(i):
        t = i / a.fps
        te = t if t < t_p else (t_p if t < t_p + pausa else t - pausa)                          # tiempo "congelable"
        u = min(1, max(0, (te - t_rev0) / (t_rev1 - t_rev0))); c = u * u * (3 - 2 * u)
        mk = _silueta(a.forma, a.palabra, FS // DS, te, a.seg)
        sgn = -1 if a.reves else 1
        x = x0.copy(); y = (y0 + capa * v * te * sgn) % FS
        x = np.where(ruido, (x0 + np.cos(ang) * v * te) % FS, x); y = np.where(ruido, (y0 + np.sin(ang) * v * te) % FS, y)
        dentro = mk[np.clip((y / DS).astype(int), 0, mk.shape[0] - 1), np.clip((x / DS).astype(int), 0, mk.shape[1] - 1)]
        consistente = np.where(capa < 0, dentro, ~dentro)
        p_vis = .5 / (1 - .5 * c)                         # adelgaza el campo al principio para que el brillo no cambie mientras se ordena
        vis = np.where(ruido, s_i < .5, (consistente | (r_i >= c)) & (s_i < p_vis)) & (np.hypot(x - FR, y - FR) < FR)
        px = (x[vis] + 6) * SS; py = (y[vis] + 6) * SS
        tt = (y[vis] / FS)[:, None]; col = (c_b + (c_a - c_b) * (1 - tt)).astype(np.uint8)
        if os.environ.get('CAMPO_DEBUG'): col = np.where((capa[vis] < 0)[:, None], np.array([255, 60, 60]), np.array([60, 140, 255])).astype(np.uint8)
        ca_ = np.zeros((bh * SS, bw * SS, 3), np.uint8); ma_ = np.zeros((bh * SS, bw * SS), np.uint8); rr = int(math.ceil(r_px))
        ix0, iy0 = np.rint(px).astype(int), np.rint(py).astype(int)
        for dy in range(-rr, rr + 1):
            for dx in range(-rr, rr + 1):
                if dx * dx + dy * dy > r_px * r_px: continue
                xx, yy = ix0 + dx, iy0 + dy; ok = (xx >= 0) & (xx < bw * SS) & (yy >= 0) & (yy < bh * SS)
                ca_[yy[ok], xx[ok]] = col[ok]; ma_[yy[ok], xx[ok]] = 255
        cimg = Image.fromarray(ca_).resize((bw, bh), Image.LANCZOS)
        colr = np.asarray(cimg, dtype=np.float32) / 255
        cov = np.asarray(Image.fromarray(ma_).resize((bw, bh), Image.LANCZOS), dtype=np.float32)[..., None] / 255
        out = base.copy(); sub = out[box[1]:box[3], box[0]:box[2]]; sub[:] = sub * (1 - cov) + colr * 255
        if a.brillo > 0:
            g1 = np.asarray(cimg.filter(ImageFilter.GaussianBlur(4)), dtype=np.float32); g2 = np.asarray(cimg.filter(ImageFilter.GaussianBlur(14)), dtype=np.float32)
            sub += (g1 * 3 + g2 * 8) * (a.brillo / 100)
        return (np.clip(out, 0, 255) + .5).astype(np.uint8)

    if a.preview:
        Image.fromarray(fotograma(int(total * a.preview_t))).save("preview.png"); print("preview.png"); return
    salida = a.salida or f"ilusion-{a.forma}-{a.fps}fps.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
           "-vf", "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p", "-c:v", "libx264", "-preset", "veryslow", "-crf", str(a.crf), "-tune", "grain",
           "-profile:v", "high", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", salida]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(total):
        p.stdin.write(fotograma(i).tobytes())
        if i % a.fps == 0: print(f"\r{i // a.fps}/{int(a.seg)} s", end="", flush=True)
    p.stdin.close(); p.wait(); print(f"\nlisto: {salida} ({W}x{H}, {a.fps} fps, {a.seg:g} s)")


# ---------------------------------------------------------------------------------------------------------------
# Formato 3: imagen residual. Se mira un punto sobre colores "al reves" y despues sobre blanco: aparecen los colores reales.
# Formato 4: pared de cafe. Lineas paralelas que parecen torcidas; al final se marcan para mostrar que son rectas.
# ---------------------------------------------------------------------------------------------------------------
RESIDUALES = ["residual_usa", "residual_corazon", "residual_circulos", "residual_arcoiris"]
PAREDES = ["pared_cafe"]
_SM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts", "SpaceMono-Regular.ttf")
_SMI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts", "SpaceMono-Italic.ttf")


def _estimulo(nombre, S=2):
    """(imagen RGB, mascara de la figura): colores complementarios sobre negro."""
    im = Image.new("RGB", (W * S, H * S), (0, 0, 0)); mk = Image.new("L", (W * S, H * S), 0); d = ImageDraw.Draw(im); dm = ImageDraw.Draw(mk); cx, cy = W * S / 2, H * S * .5
    if nombre == "residual_usa":           # bandera de EE.UU. con los colores invertidos: cian = rojo, negro = blanco, amarillo = azul
        fw = 1000 * S; fh = fw / 1.9; x0, y0 = cx - fw / 2, cy - fh / 2
        for k in range(13): d.rectangle((x0, y0 + k * fh / 13, x0 + fw, y0 + (k + 1) * fh / 13 + 1), fill=(0, 255, 255) if k % 2 == 0 else (0, 0, 0))
        cw, ch = fw * .4, fh * 7 / 13; d.rectangle((x0, y0, x0 + cw, y0 + ch), fill=(255, 255, 0)); dm.rectangle((x0, y0, x0 + fw, y0 + fh), fill=255)
        for r in range(9):
            n = 6 if r % 2 == 0 else 5
            for c in range(n):
                sx = x0 + cw * ((c + .5) / 6 if n == 6 else (c + 1) / 6); sy = y0 + ch * (r + .6) / 9.2; rr = fh * .032
                d.polygon([(sx + (rr if k % 2 == 0 else rr * .4) * math.sin(k * math.pi / 5), sy - (rr if k % 2 == 0 else rr * .4) * math.cos(k * math.pi / 5)) for k in range(10)], fill=(0, 0, 0))
    elif nombre == "residual_corazon":     # corazon cian: se ve rojo
        pp = [(cx + 16 * math.sin(a) ** 3 * 26 * S, cy - 40 * S - (13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) * 26 * S + 10 * S) for a in np.linspace(0, 2 * math.pi, 240)]
        d.polygon(pp, fill=(0, 255, 255)); dm.polygon(pp, fill=255)
    elif nombre == "residual_arcoiris":    # anillos en los complementarios del arcoiris: se ve un arcoiris real
        cols = [(0, 255, 255), (0, 128, 255), (0, 0, 255), (255, 0, 255), (255, 128, 0), (105, 255, 0)]
        for k, c in enumerate(cols):
            r = (400 - k * 58) * S; d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c); dm.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
        r = 52 * S; d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0))
    else:                                  # tres discos: cian, magenta y amarillo se ven rojo, verde y azul
        R = 143 * S; off = 215 * S
        for k, col in enumerate([(0, 255, 255), (255, 0, 255), (255, 255, 0)]):
            a = -math.pi / 2 + k * 2 * math.pi / 3; x, y = cx + off * math.cos(a), cy + off * math.sin(a) + 20 * S
            d.ellipse((x - R, y - R, x + R, y + R), fill=col); dm.ellipse((x - R, y - R, x + R, y + R), fill=255)
    if S > 1: im = im.resize((W, H), Image.LANCZOS); mk = mk.resize((W, H), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32), np.asarray(mk, dtype=np.float32)[..., None] / 255


def render_residual(a):
    """Test de imagen residual en tres tiempos: mirar el punto (con animacion y cuenta), blanco, y revelacion de los colores reales."""
    T2, T3 = 5.0, 2.5; T1 = max(6.0, a.seg - T2 - T3); total = int(round((T1 + T2 + T3) * a.fps)); fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")
    P = lambda n, sz: ImageFont.truetype(os.path.join(fp, n), sz)
    fT, fS, fN, fL = P("Poppins-ExtraBold.ttf", 66), P("SpaceMono-Regular.ttf", 38), P("Poppins-ExtraBold.ttf", 170), P("Poppins-SemiBold.ttf", 44)
    est, mk = _estimulo(a.forma); cx, cy = W / 2, H * .5
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); rad = np.hypot((xx - cx) / W, (yy - cy) / H * .75)
    fondo = (np.array([16, 26, 46], np.float32) * np.clip(1 - rad * 1.7, 0, 1)[..., None] ** 1.5 + np.array([2, 3, 8], np.float32)).astype(np.float32)
    halo = np.asarray(Image.fromarray(est.astype(np.uint8)).filter(ImageFilter.GaussianBlur(46)), dtype=np.float32)
    ys, xs = np.where(mk[..., 0] > .5); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()               # recuadro de la figura, para la revelacion
    rng = np.random.default_rng(a.semilla); NP = 46
    bx, by, br_, bv, bb, bp = rng.random(NP) * W, rng.random(NP) * H, 8 + rng.random(NP) * 26, 10 + rng.random(NP) * 22, .05 + rng.random(NP) * .10, rng.random(NP) * 6
    def sprite(r):
        g = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32); d = np.hypot(g[0], g[1]) / r; return np.clip(1 - d, 0, 1) ** 1.6
    sp = [sprite(int(r)) for r in br_]
    def mezcla(c, extra=0): return c
    def texto(im, y, t, f, col, ancho=.84, interl=84, alpha=255):
        d = ImageDraw.Draw(im, "RGBA")
        for j, l in enumerate(envolver(d, t, f, W * ancho)): d.text((W / 2, y + j * interl), l, font=f, fill=col + (alpha,), anchor="ms")
    def ease(u): u = min(1, max(0, u)); return u * u * (3 - 2 * u)
    SUBS = [(.3, 2.5, "Mira el punto blanco del centro."), (2.9, 3.9, "No parpadees."), (4.2, 5.6, "Sigue mirando el punto."), (5.8, 8.35, "Tus ojos se están cansando de estos colores."), (8.35, 9.0, "Ya casi."),
            (9.3, 10.6, "Ahora mira el blanco."), (11.0, 11.8, "¿Ves la bandera?"), (12.5, 14.4, "Tu cerebro la está inventando."), (14.6, 16.3, "Los colores no estaban ahí.")]
    def _subtitulo(t):
        for t0, t1, tx in SUBS:
            if t0 <= t <= t1: return tx, ease((t - t0) / .25) * ease((t1 - t) / .25)
        return None
    def cuadro(i):
        t = i / a.fps
        if t < T1:                                                                                              # --- 1) mirar el punto
            img = fondo + halo * .30 * ease(t / 1.0)
            for k in range(NP):                                                                                 # luces de fondo que flotan (bokeh)
                y = int((by[k] - bv[k] * t) % H); x = int(bx[k] + 14 * math.sin(t * .6 + bp[k])); r = sp[k].shape[0] // 2
                ya, yb, xa, xb = max(0, y - r), min(H, y + r + 1), max(0, x - r), min(W, x + r + 1)
                if yb > ya and xb > xa: img[ya:yb, xa:xb] += (sp[k][ya - (y - r):yb - (y - r), xa - (x - r):xb - (x - r)] * 255 * bb[k])[..., None] * np.array([.7, .85, 1], np.float32)
            u = ease(t / 1.0); br = 1 + .03 * math.sin(2 * math.pi * t / 4)                                      # la figura aparece suave y respira apenas
            img = img * (1 - mk * u) + np.clip(est * br, 0, 255) * mk * u
            im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(im, "RGBA")
            prog = t / T1; rr = 46
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(255, 255, 255, 60), width=4)               # anillo de progreso alrededor del punto
            d.arc((cx - rr, cy - rr, cx + rr, cy + rr), -90, -90 + 360 * prog, fill=(255, 255, 255, 235), width=5)
            pul = 1 + .18 * math.sin(2 * math.pi * t / 1.2); d.ellipse((cx - 15 * pul, cy - 15 * pul, cx + 15 * pul, cy + 15 * pul), fill=(0, 0, 0, 255)); d.ellipse((cx - 10 * pul, cy - 10 * pul, cx + 10 * pul, cy + 10 * pul), fill=(255, 255, 255, 255))
            texto(im, 330, a.arriba, fT, (255, 255, 255), interl=82)
            fr = (t % 1.0)                                                                                   # onda que sale del punto en cada segundo (acompana al tic del audio)
            if t >= 1.0: rp = 46 + 150 * fr; d.ellipse((cx - rp, cy - rp, cx + rp, cy + rp), outline=(255, 255, 255, int(150 * (1 - fr) ** 2)), width=3)
            sub = _subtitulo(t)
            if sub: d.text((W / 2, 330 + 82 * (len(envolver(d, a.arriba, fT, W * .84)) - 1) + 78), sub[0], font=fS, fill=(170, 200, 255, int(235 * sub[1])), anchor="ms")
            n = str(int(math.ceil(T1 - t))); d.text((W / 2, 1500), n, font=fN, fill=(255, 255, 255, 255), anchor="ms")
            return im.tobytes()
        if t < T1 + T2:                                                                                         # --- 2) blanco
            u = t - T1; im = Image.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(im, "RGBA")
            rr = 34 + 5 * math.sin(2 * math.pi * u / 1.6); d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(0, 0, 0, 55), width=3)
            d.ellipse((cx - 15, cy - 15, cx + 15, cy + 15), fill=(0, 0, 0, 255)); d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=(255, 255, 255, 255))
            texto(im, 330, a.abajo, fT, (20, 20, 30), interl=82, alpha=int(255 * ease(u / .5)))
            sub = _subtitulo(t)
            if sub: d.text((W / 2, 330 + 82 * (len(envolver(d, a.abajo, fT, W * .84)) - 1) + 78), sub[0], font=fS, fill=(90, 90, 110, int(255 * sub[1])), anchor="ms")
            if u > 3.4: d.text((W / 2, 1560), "parpadea una vez", font=fS, fill=(90, 90, 110, int(255 * ease((u - 3.4) / .6))), anchor="ms")
            return im.tobytes()
        u = t - T1 - T2                                                                                         # --- 3) revelacion: lo que mirabas vs lo que aparecio
        img = fondo.copy(); im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(im, "RGBA"); k_ = ease(u / .6)
        texto(im, 330, (a.palabra if a.palabra and a.palabra != "USA" else "Tu cerebro puso los colores"), fT, (255, 255, 255), interl=82, alpha=int(255 * k_))
        rec = est[y0:y1 + 1, x0:x1 + 1]; esc = min(620 / rec.shape[1], 430 / rec.shape[0])
        for j, (arr, etq, yc) in enumerate(((rec, "lo que mirabas", 800), (255 - rec, "lo que viste", 1330))):
            pim = Image.fromarray(arr.astype(np.uint8)).resize((int(arr.shape[1] * esc), int(arr.shape[0] * esc)), Image.LANCZOS)
            if j == 1: ex = (255 - est) * mk; g_ = Image.fromarray(np.clip(ex, 0, 255).astype(np.uint8)).crop((x0, y0, x1 + 1, y1 + 1)).resize(pim.size).filter(ImageFilter.GaussianBlur(24)); im.paste(Image.blend(Image.new("RGB", pim.size), g_, .0), (0, 0)) if False else None
            pos = (int(W / 2 - pim.width / 2), int(yc - pim.height / 2 + 14 * (1 - k_)))
            lay = Image.new("RGBA", im.size, (0, 0, 0, 0)); lay.paste(pim.convert("RGBA"), pos); lay.putalpha(lay.getchannel("A").point(lambda v: int(v * k_))); im = Image.alpha_composite(im.convert("RGBA"), lay).convert("RGB")
            d = ImageDraw.Draw(im, "RGBA"); d.text((W / 2, yc + pim.height / 2 + 62), etq, font=fL, fill=(170, 200, 255, int(255 * k_)), anchor="ms")
        d.polygon([(W / 2 - 34, 1040), (W / 2 + 34, 1040), (W / 2, 1090)], fill=(255, 255, 255, int(255 * k_)))
        sub = _subtitulo(t)
        if sub: d.text((W / 2, 1640), sub[0], font=fS, fill=(170, 200, 255, int(235 * sub[1])), anchor="ms")
        return im.tobytes()
    if a.preview: Image.frombytes("RGB", (W, H), cuadro(int(a.preview_t * total))).save("preview.png"); print("preview.png"); return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
           "-vf", "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-maxrate", "12M", "-bufsize", "24M", "-profile:v", "high",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", a.salida or f"ilusion-{a.forma}-{a.fps}fps.mp4"]
    if a.audio:       # audio: se normaliza el volumen (-14 LUFS, como piden las redes) y se mezcla en AAC
        cmd[cmd.index("-vf"):cmd.index("-vf")] = ["-i", a.audio]
        cmd[-1:-1] = ["-af", "loudnorm=I=-14:TP=-1.5:LRA=7", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(total):
        p.stdin.write(cuadro(i))
        if i % a.fps == 0: print(f"\r{i // a.fps}/{int(total / a.fps)} s", end="", flush=True)
    p.stdin.close(); p.wait(); print(f"\nlisto: {T1:g} s mirando + {T2:g} s blanco + {T3:g} s revelacion")


def render_pared(a):
    """Pared de cafe: filas de cuadrados blancos y negros desplazadas, separadas por una linea gris. Las lineas parecen inclinadas; al final se marcan."""
    rng = np.random.default_rng(a.semilla)
    c1, c2 = np.array(rgb(a.color or "#ffffff"), np.float32), np.array(rgb(a.fondo or "#000000"), np.float32); gris = (c1 + c2) / 2
    c_bg = np.array([10, 12, 18], np.float32); c_tx = np.array(rgb(a.texto or "#ffffff"), np.float32)
    h = 100; sq = h; filas = 8; ancho = 1040; alto = filas * (h + 6) + 6; x0, y0 = (W - ancho) // 2, (H - alto) // 2 + 20
    total = int(round(a.seg * a.fps)); t_rev = a.seg * .62; vel = a.vueltas_min * 5.0           # px/s
    f1, f3 = ImageFont.truetype(_SM, 48.8), ImageFont.truetype(_SMI, 40)
    tiles = np.zeros((alto, ancho, 3), np.float32); tiles[:] = gris
    xs = np.arange(ancho)
    def cuadro(i):
        t = i / a.fps; img = np.zeros((H, W, 3), np.float32) + c_bg
        t2 = tiles.copy()
        for r in range(filas):
            ya = 6 + r * (h + 6); off = ((r % 2) * sq / 2 + vel * t) % (2 * sq)
            par = (((xs + off) // sq).astype(int) % 2) == 0
            t2[ya:ya + h] = np.where(par[None, :, None], c1, c2)
        img[y0:y0 + alto, x0:x0 + ancho] = t2
        im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)); d_ = ImageDraw.Draw(im, "RGBA")
        for j, l in enumerate(envolver(d_, a.arriba, f1, W * .7)): d_.text((W / 2, 375 + j * 74), l, font=f1, fill=tuple(int(v) for v in c_tx) + (255,), anchor="ms")
        if t > t_rev:                                                                                     # revelacion: las lineas rojas se dibujan de izquierda a derecha y muestran que son paralelas
            u = min(1, (t - t_rev) / 1.2)
            for r in range(filas + 1):
                yy = y0 + 3 + r * (h + 6); d_.line((x0 - 20, yy, x0 - 20 + (ancho + 40) * u, yy), fill=(255, 60, 60, 255), width=4)
            d_.text((W / 2, 1560), a.abajo, font=f3, fill=tuple(int(v) for v in c_tx) + (int(255 * min(1, (t - t_rev) / 1.2)),), anchor="ms")
        return im.tobytes()
    if a.preview: Image.frombytes("RGB", (W, H), cuadro(int(a.preview_t * total))).save("preview.png"); print("preview.png"); return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
           "-vf", "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-maxrate", "10M", "-bufsize", "20M", "-profile:v", "high",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", a.salida or f"ilusion-{a.forma}-{a.fps}fps.mp4"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(total):
        p.stdin.write(cuadro(i))
        if i % a.fps == 0: print(f"\r{i // a.fps}/{int(a.seg)} s", end="", flush=True)
    p.stdin.close(); p.wait(); print(f"\nlisto: {a.salida}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--forma", default="esfera", choices=["esfera", "cilindro", "cubo", "toro", "helice", "cono", "piramide", "cono_invertido", "galaxia", "tornado", "saturno", "agujero_negro",
                                                  "calabaza", "reloj_arena", "luna", "teseracto", "bobina", "sierpinski", "futbol_americano", "baloncesto", "futbol", "ovni",
                                                  "cohete", "estrella", "copo", "arbol_navidad", "fantasma", "calavera", "telarana", "texto3d", "joya", "bandera", "muneco_nieve",
                                                  "baston_caramelo", "dado", "moneda", "esfera_fibonacci", "medusa", "mariposa", "planeta", "arbol_fractal", "cometa", "nebulosa",
                                                  "plasma", "explosion", "mitades", "cuencos", "planeta_cortado", "toro_cortado", "esfera_en_cubo", "cubo_puntos", "cubitos", "conos_anidados",
                                                  "cubo_partido", "esfera_diagonal", "toro_partido", "cono_partido", "cilindro_partido", "mitades_contrarias", "esferas_contrarias",
                                                  "cubos_contrarios", "rodajas",
                                                  "flechas", "cadena", "torre_aros", "lapices", "escalera_cubos", "aspas", "flechas_ciclo", "piramide_video", "prisma_triangular", "prisma_hexagonal", "casita", "buho", "gato", "hongo", "rampa", "escalera", "cruz", "marco", "torre_escalonada"] + CAMPOS + RESIDUALES + PAREDES)
    ap.add_argument("--puntos", type=int, default=2500)
    ap.add_argument("--tam", type=float, default=3.0, help="tamaño del punto en px")
    ap.add_argument("--vueltas-min", type=float, default=12, help="vueltas por minuto")
    ap.add_argument("--inclinacion", type=float, default=15, help="grados de camara")
    ap.add_argument("--profundidad", type=float, default=0, help="0-100; 0 = ambiguo")
    ap.add_argument("--figura", type=float, default=42, help="tamaño de la figura, %% del ancho")
    ap.add_argument("--arriba", default="¿Puedes invertir el giro solo con tu mente?")
    ap.add_argument("--abajo", default="SÍGUEME SI LO LOGRASTE.")
    ap.add_argument("--seg", type=float, default=15)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--paleta", default="clasico", choices=list(PALETAS), help="colores predefinidos")
    ap.add_argument("--fondo", help="color de fondo, ej. #000000")
    ap.add_argument("--texto", help="color del texto")
    ap.add_argument("--color", help="color de los puntos (arriba si hay degradado)")
    ap.add_argument("--color2", help="color de los puntos abajo (activa el degradado)")
    ap.add_argument("--brillo", type=float, default=0, help="0-100, halo de luz alrededor de los puntos")
    ap.add_argument("--estrellas", type=int, default=0, help="cantidad de estrellitas de fondo")
    ap.add_argument("--palabra", default="USA", help="texto para la forma texto3d")
    ap.add_argument("--diseno", default="clasico", choices=["clasico", "triangulo"], help="triangulo = texto y posicion como el video del triangulo")
    ap.add_argument("--exacta", action="store_true", help="respeta las vueltas por minuto aunque el bucle no cierre")
    ap.add_argument("--semilla", type=int, default=7)
    ap.add_argument("--reves", action="store_true")
    ap.add_argument("--crf", type=int, default=10, help="calidad x264: menor = mejor (0 = sin perdida)")
    ap.add_argument("--pausa", type=float, default=None, help="campo_*: segundos de pausa a los 62%% del video donde todo se congela y la figura desaparece (nada = sin pausa)")
    ap.add_argument("--revela", type=float, default=None, help="campo_*: segundos que tarda el ruido en ordenarse (0 o nada = la figura esta desde el principio)")
    ap.add_argument("--audio", default=None, help="imagen residual: archivo de audio (wav/mp3) que se mezcla al video")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--preview", action="store_true", help="solo guarda un PNG de control")
    ap.add_argument("--preview-t", type=float, default=1 / 7, help="momento del preview, 0 a 1")
    a = ap.parse_args()

    if a.forma in CAMPOS: return render_campo(a)
    if a.forma in RESIDUALES: return render_residual(a)
    if a.forma in PAREDES: return render_pared(a)
    rng = np.random.default_rng(a.semilla)
    pts = formas(a.forma, a.puntos, rng, a.palabra)
    fijo = pts[:, 3] > .5 if pts.shape[1] >= 4 else np.zeros(len(pts), dtype=bool)   # puntos fijos en pantalla (no giran)
    grupo = pts[:, 4] if pts.shape[1] >= 5 else None
    giro = pts[:, 5] if pts.shape[1] >= 6 else np.ones(len(pts))                       # cada grupo puede girar a su propio ritmo (1, -1, 2...)                                   # objetos de dos colores: grupo 1 = color de arriba, 0 = color de abajo
    brillo_pt = pts[:, 6] if pts.shape[1] >= 7 else None                               # brillo propio de cada punto (cintas tenues, bordes vivos)
    pts = pts[:, :3]
    texto = capa_texto(a.arriba, a.abajo, a.diseno)
    pal = PALETAS[a.paleta]; pbg, ptx, pa, pb = pal[:4]
    multi = [rgb(c) for c in pal[4]] if len(pal) > 4 and not (a.color or a.color2) else None      # paleta de seis colores
    c_bg, c_tx = rgb(a.fondo or pbg), rgb(a.texto or ptx)
    c_a = rgb(a.color or pa)
    c_b = rgb(a.color2) if a.color2 else (rgb(pb) if not a.color else c_a)
    base = c_bg + (c_tx - c_bg) * texto[..., None]          # fondo + texto, listo para pegar los puntos
    if a.estrellas:
        sr = np.random.default_rng(a.semilla + 101); N = a.estrellas
        sx, sy = sr.integers(0, W - 3, N), sr.integers(0, H - 3, N); sb = .15 + .6 * sr.random(N) * sr.random(N); sz = np.where(sr.random(N) < .15, 3, 2)
        for k in range(N):
            base[sy[k]:sy[k] + sz[k], sx[k]:sx[k] + sz[k]] += c_tx * sb[k]
    # el color va pegado al objeto: por altura, o del centro al borde si la figura es plana
    if grupo is not None:
        eje = grupo.astype(float)
    elif a.forma in ("agujero_negro", "galaxia"):
        eje = 1 - np.minimum(1, np.linalg.norm(pts, axis=1))      # del centro (color de arriba) al borde (color de abajo)
    else:
        eje = pts[:, 1] if np.ptp(pts[:, 1]) >= .5 else 1 - np.hypot(pts[:, 0], pts[:, 2])
    ty = (eje - eje.min()) / max(1e-9, np.ptp(eje))   # 0 = color de abajo, 1 = color de arriba
    cols = np.array(multi)[np.clip(np.rint(ty * 5).astype(int), 0, 5)] if multi is not None else c_b + (c_a - c_b) * ty[:, None]
    R = W * a.figura / 100; cy = H * (.5 if a.diseno == "triangulo" else .47)
    tilt = math.radians(a.inclinacion); ct, st = math.cos(tilt), math.sin(tilt)
    dep = a.profundidad / 100
    total = int(round(a.seg * a.fps))
    # para que el video sea un bucle perfecto, el giro total se ajusta a vueltas enteras
    vueltas = a.vueltas_min / 60 * a.seg if a.exacta else max(1, round(a.vueltas_min / 60 * a.seg))   # exacta = respeta la velocidad, el bucle puede no cerrar
    sgn = -1 if a.reves else 1

    # recuadro de la figura, para no procesar toda la pantalla en cada cuadro
    m = int(R * 1.25)
    box = (max(0, int(W / 2 - m)), max(0, int(cy - m)), min(W, int(W / 2 + m)), min(H, int(cy + m)))
    bw, bh = box[2] - box[0], box[3] - box[1]

    def fotograma(i):
        ang = sgn * 2 * math.pi * vueltas * i / total
        ca, sa = np.cos(ang * giro), np.sin(ang * giro)
        x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
        x1 = np.where(fijo, x, x * ca + z * sa); z1 = -x * sa + z * ca
        y2 = np.where(fijo, y, y * ct - z1 * st); z2 = np.where(fijo, 0., y * st + z1 * ct)
        img = Image.new("RGB", (bw * SS, bh * SS), (0, 0, 0)); d = ImageDraw.Draw(img)
        mk = Image.new("L", (bw * SS, bh * SS), 0); dm = ImageDraw.Draw(mk)
        px = (W / 2 + x1 * R - box[0]) * SS; py = (cy - y2 * R - box[1]) * SS
        r = a.tam * (1 + dep * .6 * z2) * .6 * SS
        al = np.clip(1 - dep * .7 * (1 - z2) / 2, .08, 1)
        if brillo_pt is not None: al = al * brillo_pt
        pre = (cols * al[:, None]).astype(np.uint8)
        if a.profundidad == 0 and len(px) > 12000:      # muchos puntos del mismo tamano: se pegan todos juntos con numpy (mucho mas rapido)
            ca_ = np.asarray(img).copy(); ma_ = np.asarray(mk).copy(); rr = int(math.ceil(r[0]))
            ix0, iy0 = np.rint(px).astype(int), np.rint(py).astype(int); v8 = (al * 255).astype(np.uint8)
            for dy in range(-rr, rr + 1):
                for dx in range(-rr, rr + 1):
                    if dx * dx + dy * dy > r[0] * r[0]: continue
                    xx, yy = ix0 + dx, iy0 + dy; ok = (xx >= 0) & (xx < bw * SS) & (yy >= 0) & (yy < bh * SS)
                    ca_[yy[ok], xx[ok]] = pre[ok]; ma_[yy[ok], xx[ok]] = v8[ok]
            img = Image.fromarray(ca_); mk = Image.fromarray(ma_)
        else:
            for k in range(len(px)):
                e = (px[k] - r[k], py[k] - r[k], px[k] + r[k], py[k] + r[k])
                d.ellipse(e, fill=tuple(int(v) for v in pre[k])); dm.ellipse(e, fill=int(al[k] * 255))
        cimg = img.resize((bw, bh), Image.LANCZOS)
        col = np.asarray(cimg, dtype=np.float32) / 255
        cov = np.asarray(mk.resize((bw, bh), Image.LANCZOS), dtype=np.float32)[..., None] / 255
        out = base.copy()
        sub = out[box[1]:box[3], box[0]:box[2]]
        sub[:] = sub * (1 - cov) + col * 255
        if a.brillo > 0:     # halo: dos desenfoques (cerca y lejos) sumados a la imagen
            g1 = np.asarray(cimg.filter(ImageFilter.GaussianBlur(4)), dtype=np.float32)
            g2 = np.asarray(cimg.filter(ImageFilter.GaussianBlur(14)), dtype=np.float32)
            sub += (g1 * 3 + g2 * 8) * (a.brillo / 100)
        return (np.clip(out, 0, 255) + .5).astype(np.uint8)

    if a.preview:
        Image.fromarray(fotograma(int(total * a.preview_t))).save("preview.png"); print("preview.png"); return

    salida = a.salida or f"ilusion-{a.forma}-{a.fps}fps.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(a.fps), "-i", "-", "-vf", "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p", "-c:v", "libx264", "-preset", "veryslow",
           "-crf", str(a.crf), "-tune", "grain", "-profile:v", "high", "-color_primaries", "bt709",
           "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", salida]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(total):
        p.stdin.write(fotograma(i).tobytes())
        if i % a.fps == 0:
            print(f"\r{i // a.fps}/{int(a.seg)} s", end="", flush=True)
    p.stdin.close(); p.wait()
    print(f"\nlisto: {salida} ({W}x{H}, {a.fps} fps, {a.seg:g} s, {vueltas} vueltas)")


if __name__ == "__main__":
    main()
