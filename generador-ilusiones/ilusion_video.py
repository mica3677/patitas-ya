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
    "clasico":  ("#000000", "#ffffff", "#ffffff", "#ffffff"),   # fondo, texto, puntos arriba, puntos abajo
    "neon":     ("#05010f", "#ffffff", "#00f0ff", "#ff2bd6"),
    "atardecer": ("#12060a", "#ffe8d6", "#ffd166", "#ff4d6d"),
    "hielo":    ("#020b16", "#e6f7ff", "#e6f7ff", "#4cc9f0"),
    "matrix":   ("#000000", "#b6ffb0", "#b6ffb0", "#00c853"),
    "dorado":   ("#0b0803", "#f5deb3", "#fff1b8", "#d4a017"),
    "violeta":  ("#0a0614", "#f3e8ff", "#f3e8ff", "#9d4edd"),
    "halloween": ("#0a0500", "#ffd9a0", "#ffb347", "#ff5e00"),
    "sangre":   ("#0a0002", "#ffd6d6", "#ff6b6b", "#8b0000"),
    "usa":      ("#040818", "#ffffff", "#ff4155", "#2f6bff"),
    "navidad":  ("#04100a", "#ffffff", "#ff5a5a", "#3ddc84"),
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


def _texto3d(n, rng, palabra):
    CW, CH = 1200, 400; txt = (palabra or "USA")[:14]
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts", "Poppins-ExtraBold.ttf")
    fs = 300
    def fuente(sz):
        try: return ImageFont.truetype(ruta, int(sz))
        except OSError: return font(FONTS_B, int(sz))
    img = Image.new("L", (CW, CH), 0); d = ImageDraw.Draw(img)
    tw = d.textlength(txt, font=fuente(fs))
    if tw > 1100: fs = fs * 1100 / tw
    d.text((CW / 2, CH / 2 + 15), txt, font=fuente(fs), fill=255, anchor="mm")
    on = np.asarray(img) > 128
    def sh(dx, dy): return np.roll(np.roll(on, dy, 0), dx, 1)
    borde = on & ~(sh(3, 0) & sh(-3, 0) & sh(0, 3) & sh(0, -3))
    ys, xs = np.mgrid[0:CH:2, 0:CW:2]; sel = on[::2, ::2]
    px, py, pb = xs[sel], ys[sel], borde[::2, ::2][sel]
    if not len(px): return np.zeros((n, 3))
    sc = min(1.9 / max(1, px.max() - px.min()), 1.2 / max(1, py.max() - py.min())); cx, cy = (px.min() + px.max()) / 2, (py.min() + py.max()) / 2
    T = .11; q = rng.random(n); i = rng.integers(len(px), size=n)
    bi = np.flatnonzero(pb)
    if len(bi): ib = bi[rng.integers(len(bi), size=n)]
    else: ib = i
    usar_borde = (q >= .68) & (len(bi) > 0); idx = np.where(usar_borde, ib, i)
    z = np.where(usar_borde, (rng.random(n) * 2 - 1) * T, np.where(q < .34, T, -T))
    return np.c_[(px[idx] - cx) * sc, -(py[idx] - cy) * sc, z]


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
    if nombre == "cubo":
        c = (-.7, .7); aristas = []
        for x in c:
            for y in c:
                for z in c:
                    p = [x, y, z]
                    for k in range(3):
                        if p[k] < 0:
                            q = list(p); q[k] = .7; aristas.append((p, q))
        out = []
        for _ in range(n):
            p, q = aristas[rng.integers(len(aristas))]; u = rng.random()
            out.append([p[i] + (q[i] - p[i]) * u for i in range(3)])
        return np.array(out)
    if nombre == "toro":
        u = rng.random(n) * 2 * math.pi; v = rng.random(n) * 2 * math.pi; R, r = .7, .28
        return np.c_[(R + r * np.cos(v)) * np.cos(u), r * np.sin(v), (R + r * np.cos(v)) * np.sin(u)]
    if nombre == "helice":
        out = []
        for i in range(n):
            s = i % 3; y = rng.random() * 2 - 1; a = y * 3 * math.pi
            if s < 2:
                out.append([math.cos(a + s * math.pi) * .5, y, math.sin(a + s * math.pi) * .5])
            else:
                b = round(y * 8) / 8; ab = b * 3 * math.pi; u = rng.random() * 2 - 1
                out.append([math.cos(ab) * .5 * u, b, math.sin(ab) * .5 * u])
        return np.array(out)
    if nombre == "cono":
        t = np.sqrt(rng.random(n)); a = rng.random(n) * 2 * math.pi
        return np.c_[np.cos(a) * .75 * t, 1 - 2 * t, np.sin(a) * .75 * t]
    if nombre == "piramide":
        return _aristas([[-.7, -.8, -.7], [.7, -.8, -.7], [.7, -.8, .7], [-.7, -.8, .7], [0, .95, 0]],
                       [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (1, 4), (2, 4), (3, 4)], n, rng)
    if nombre == "diamante":
        v = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]) * .95
        return _aristas(v, [(i, j) for i in range(6) for j in range(i + 1, 6) if j != (i ^ 1)], n, rng)
    if nombre == "resorte":
        u = rng.random(n); a = u * 6 * 2 * math.pi
        return np.c_[np.cos(a) * .6, u * 1.8 - .9, np.sin(a) * .6]
    if nombre == "nudo":
        t = rng.random(n) * 2 * math.pi; r = lambda: (rng.random(n) - .5) * .05
        return np.c_[(np.sin(t) + 2 * np.sin(2 * t)) / 3.2 + r(), (np.cos(t) - 2 * np.cos(2 * t)) / 3.2 + r(),
                     -np.sin(3 * t) / 3.2 + r()]
    if nombre == "mobius":
        u = rng.random(n) * 2 * math.pi; v = (rng.random(n) * 2 - 1) * .35; R = .62
        return np.c_[(R + v * np.cos(u / 2)) * np.cos(u), v * np.sin(u / 2) * 1.2, (R + v * np.cos(u / 2)) * np.sin(u)]
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
    if nombre == "nudo_toroidal":
        t = rng.random(n) * 2 * math.pi; c = 2 + np.cos(3 * t); j = lambda: rng.normal(size=n) * .03
        return np.c_[c * np.cos(2 * t) / 3.1 + j(), np.sin(3 * t) * 1.5 / 3.1 + j(), c * np.sin(2 * t) / 3.1 + j()]
    if nombre == "icosaedro":
        f = (1 + 5 ** .5) / 2; v = []
        for a in (-1, 1):
            for b in (-f, f):
                v += [[0, a, b], [a, b, 0], [b, 0, a]]
        v = np.array(v, dtype=float)
        e = [(i, j) for i in range(12) for j in range(i + 1, 12) if abs(((v[i] - v[j]) ** 2).sum() - 4) < .01]
        return _aristas(v * (.95 / math.sqrt(1 + f * f)), e, n, rng)
    if nombre == "tornado":
        y = rng.random(n) * 2 - 1; h = (y + 1) / 2
        rad = (.1 + .72 * h ** 1.6) * (1 + rng.normal(size=n) * .04)
        ang = y * 5 + rng.integers(4, size=n) * math.pi / 2 + rng.normal(size=n) * .07
        return np.c_[np.cos(ang) * rad, y * .95, np.sin(ang) * rad]
    if nombre == "corazon":
        t = rng.random(n) * 2 * math.pi; c = rng.random(n) * 2 - 1; s = np.sqrt(1 - c * c)
        hx = 16 * np.sin(t) ** 3; hy = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
        return np.c_[hx * s / 17, (hy + 2.5) * s / 15, c * .5]
    if nombre == "ondas":
        r = np.sqrt(rng.random(n)); a = rng.random(n) * 2 * math.pi
        return np.c_[np.cos(a) * r, .2 * np.cos(r * 15) * (1 - r * .55), np.sin(a) * r]
    if nombre == "esfera_fibonacci":
        i = np.arange(n); y = 1 - 2 * (i + .5) / n; r = np.sqrt(1 - y * y); g = math.pi * (3 - 5 ** .5)
        return np.c_[np.cos(i * g) * r, y, np.sin(i * g) * r]
    if nombre == "saturno":
        nb = int(n * .42); v = rng.normal(size=(nb, 3)); v = v / np.linalg.norm(v, axis=1, keepdims=True) * .5
        m = n - nb; r = .72 + .36 * rng.random(m); r[(r > .92) & (r < .96)] += .04   # hueco entre anillos
        a = rng.random(m) * 2 * math.pi; px = r * np.cos(a); t = .4
        return np.r_[v, np.c_[px * math.cos(t), px * math.sin(t) + rng.normal(size=m) * .004, r * np.sin(a)]]
    if nombre == "atomo":
        nn = int(n * .1); m = n - nn; k = rng.integers(3, size=m)
        t = np.where(rng.random(m) < .18, k * 2.1 + rng.normal(size=m) * .1, rng.random(m) * 2 * math.pi)   # electrones: racimos
        x = np.cos(t); z = .42 * np.sin(t); phi = math.pi / 3; y0 = -z * math.sin(phi); z0 = z * math.cos(phi); psi = k * math.pi / 3
        j = lambda: rng.normal(size=m) * .008
        orb = np.c_[x * np.cos(psi) + z0 * np.sin(psi) + j(), y0 + j(), -x * np.sin(psi) + z0 * np.cos(psi) + j()]
        return np.r_[rng.normal(size=(nn, 3)) * .07, orb]
    if nombre == "agujero_negro":
        q = rng.random(n); P = lambda m: rng.normal(size=m)
        nd = int((q < .58).sum()); r = .34 + .66 * rng.random(nd * 4) ** 1.5; aa = rng.random(nd * 4) * 2 * math.pi
        w = (.55 + .45 * np.cos(2 * (aa - 3.2 * np.log(r / .34)))) * (.78 + .22 * np.cos(r * 75))
        k = rng.random(nd * 4) < w; r, aa = r[k][:nd], aa[k][:nd]                 # disco con brazos en espiral y anillos finos
        disco = np.c_[r * np.cos(aa), P(len(r)) * .01 * (1 + 2.5 * r ** 2), r * np.sin(aa)]
        m = int(((q >= .58) & (q < .70)).sum()); a = rng.random(m) * 2 * math.pi; ri = .33 + np.abs(P(m)) * .025
        interior = np.c_[ri * np.cos(a), P(m) * .006, ri * np.sin(a)]                # borde interior ardiente
        m = int(((q >= .70) & (q < .84)).sum()); sf = P(m * 3).reshape(m, 3); sf = sf / np.linalg.norm(sf, axis=1, keepdims=True) * .44
        m = int(((q >= .84) & (q < .94)).sum()); sg = np.where(rng.random(m) < .5, 1, -1); h = .3 + rng.random(m) * .85
        wj = .008 + .03 * h ** 2; chorros = np.c_[P(m) * wj, sg * h, P(m) * wj]         # chorros relativistas
        m = int((q >= .94).sum()); rg = .7 + rng.random(m) * .4; ag = rng.random(m) * 2 * math.pi
        gas = np.c_[rg * np.cos(ag), P(m) * .06 * (rg - .5), rg * np.sin(ag)]
        return np.r_[disco, interior, sf, chorros, gas]
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
    if nombre == "merkaba":
        T = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], dtype=float)
        e3 = np.array([1, 1, 1]) / 3 ** .5; e1 = np.array([1, -1, 0]) / 2 ** .5; e2 = np.array([1, 1, -2]) / 6 ** .5
        v = np.r_[T, -T] @ np.c_[e1, e3, e2] * .55    # punta hacia arriba
        e = [(g + i, g + j) for g in (0, 4) for i in range(4) for j in range(i + 1, 4)]
        return _aristas(v, e, n, rng)
    if nombre == "infinito":
        t = rng.random(n) * 2 * math.pi; d = 1 + np.sin(t) ** 2; j = lambda: rng.normal(size=n) * .018
        return np.c_[np.cos(t) / d + j(), np.sin(t) * np.cos(t) / d * 1.6 + j(), .35 * np.sin(t) + j()]
    if nombre == "girasol":
        i = np.arange(n); r = np.sqrt((i + .5) / n); a = i * 2.39996323
        return np.c_[r * np.cos(a), .4 * r * r - .2, r * np.sin(a)]
    if nombre == "ojo":
        R = .95; P = lambda al, ph: np.c_[R * np.sin(al) * np.cos(ph), R * np.sin(al) * np.sin(ph), R * np.cos(al)]   # +z mira al frente
        q = rng.random(n); cnt = lambda lo, hi: int(((q >= lo) & (q < hi)).sum())
        m = cnt(0, .36); al = np.arccos(1 - 2 * rng.random(m * 3)); al = al[al >= .5][:m]                    # esclerotica
        esc = P(al, rng.random(len(al)) * 2 * math.pi)
        m = cnt(.36, .46); borde = P(.45 + rng.normal(size=m) * .004, rng.random(m) * 2 * math.pi)              # borde del iris
        m = cnt(.46, .84); fibras = P(.17 + rng.random(m) * .27, rng.integers(40, size=m) * 2 * math.pi / 40 + rng.normal(size=m) * .012)
        m = cnt(.84, .92); pupila = P(.165 + rng.normal(size=m) * .004, rng.random(m) * 2 * math.pi)          # borde de la pupila
        m = cnt(.92, 1.01); t = rng.random(m) * 2 * math.pi; venas = P(.5 + rng.random(m) * 1.6 + .15 * np.sin(t * 3), t)
        return np.r_[esc, borde, fibras, pupila, venas]
    if nombre == "loto":
        # 3 coronas de petalos: las de afuera abiertas y caidas, las del medio a 45 grados, las de adentro paradas y curvadas al centro
        K = np.array([13, 8, 5]); AL = np.radians([14, 42, 78]); LL = np.array([1, .9, .65]); B = np.array([.10, .08, .05])
        BEND = np.array([.18, .05, 0]); CURL = np.array([0, 0, .35])
        ne = int(n * .05); m = n - ne; q = rng.random(m); l = np.where(q < .45, 0, np.where(q < .8, 1, 2))
        k = (rng.random(m) * K[l]).astype(int); t = rng.random(m) ** .9; sw = rng.random(m) * 2 - 1; s_ = t * LL[l]
        hw = .24 * LL[l] * np.sin(math.pi * t ** .75) ** .9
        rad = B[l] + s_ * np.cos(AL[l]) - CURL[l] * s_ ** 2; h = s_ * np.sin(AL[l]) - BEND[l] * s_ ** 2 + .9 * (sw * hw) ** 2; across = sw * hw
        az = k * 2 * math.pi / K[l] + l * .35; c, sn = np.cos(az), np.sin(az)
        petalos = np.c_[c * rad - sn * across, -.35 + h, sn * rad + c * across]
        est = np.c_[rng.normal(size=ne) * .05, -.1 + rng.random(ne) * .3, rng.normal(size=ne) * .05]
        return np.r_[petalos, est]
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
    if nombre == "giroscopio":
        nc = int(n * .05); m = n - nc; t = rng.random(m) * 2 * math.pi; g = rng.integers(3, size=m)
        Rr = np.array([1, .82, .64])[g]; c = np.cos(t) * Rr; s_ = np.sin(t) * Rr; z0 = np.zeros(m)
        anillos = np.where((g == 0)[:, None], np.c_[z0, c, s_], np.where((g == 1)[:, None], np.c_[c, z0, s_], np.c_[c, s_, z0]))
        return np.r_[anillos + rng.normal(size=(m, 3)) * .008, rng.normal(size=(nc, 3)) * .1]
    if nombre == "bobina":
        u = rng.random(n) * 2 * math.pi; v = 14 * u + np.where(rng.random(n) < .5, 0, math.pi); R, r = .7, .28
        j = lambda: rng.normal(size=n) * .006
        return np.c_[(R + r * np.cos(v)) * np.cos(u) + j(), r * np.sin(v) + j(), (R + r * np.cos(v)) * np.sin(u) + j()]
    if nombre == "nautilo":
        TM = 5 * math.pi; K = .28; A = math.exp(K * TM) - 1; Rf = lambda t: .12 * np.exp(.14 * t)
        sep = rng.random(n) < .18
        t = np.where(sep, rng.integers(28, size=n) * .56, np.log(1 + rng.random(n) * A) / K); R = Rf(t); rho = .3 * R
        psi = rng.random(n) * 2 * math.pi; d = np.where(sep, np.sqrt(rng.random(n)), 1.); rd = rho * d
        return np.c_[(R * np.cos(t) + rd * np.cos(psi) * np.cos(t)) / 1.5 + .1, (R * np.sin(t) + rd * np.cos(psi) * np.sin(t)) / 1.5, rd * np.sin(psi) / 1.5]
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


def capa_texto(arriba, abajo):
    img = Image.new("L", (W, H), 0); d = ImageDraw.Draw(img)
    f1 = font(FONTS_B, 52)
    for i, l in enumerate(envolver(d, arriba, f1, W * .8)):
        d.text((W / 2, 200 + i * 72), l, font=f1, fill=255, anchor="mt")
    f2 = font(FONTS_I, 40)
    d.text((W / 2, H - 330), abajo, font=f2, fill=255, anchor="mt")
    return np.asarray(img, dtype=np.float32) / 255


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--forma", default="esfera", choices=["esfera", "cilindro", "cubo", "toro", "helice", "cono", "piramide", "diamante", "resorte", "nudo", "mobius",
                                                  "cono_invertido", "galaxia", "nudo_toroidal", "icosaedro", "tornado", "corazon", "ondas", "esfera_fibonacci",
                                                  "saturno", "atomo", "agujero_negro", "calabaza", "reloj_arena", "merkaba", "infinito", "girasol",
                                                  "ojo", "loto", "luna", "teseracto", "giroscopio", "bobina", "nautilo", "sierpinski",
                                                  "futbol_americano", "baloncesto", "futbol", "ovni", "cohete", "estrella", "copo",
                                                  "arbol_navidad", "fantasma", "calavera", "telarana", "texto3d"])
    ap.add_argument("--puntos", type=int, default=2500)
    ap.add_argument("--tam", type=float, default=3.0, help="tamaño del punto en px")
    ap.add_argument("--vueltas-min", type=float, default=12, help="vueltas por minuto")
    ap.add_argument("--inclinacion", type=float, default=15, help="grados de camara")
    ap.add_argument("--profundidad", type=float, default=0, help="0-100; 0 = ambiguo")
    ap.add_argument("--figura", type=float, default=42, help="tamaño de la figura, %% del ancho")
    ap.add_argument("--arriba", default="¿Puedes invertir el giro solo con tu mente?")
    ap.add_argument("--abajo", default="SÍGUEME SI LO LOGRASTE.")
    ap.add_argument("--seg", type=float, default=15)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--paleta", default="clasico", choices=list(PALETAS), help="colores predefinidos")
    ap.add_argument("--fondo", help="color de fondo, ej. #000000")
    ap.add_argument("--texto", help="color del texto")
    ap.add_argument("--color", help="color de los puntos (arriba si hay degradado)")
    ap.add_argument("--color2", help="color de los puntos abajo (activa el degradado)")
    ap.add_argument("--brillo", type=float, default=0, help="0-100, halo de luz alrededor de los puntos")
    ap.add_argument("--estrellas", type=int, default=0, help="cantidad de estrellitas de fondo")
    ap.add_argument("--palabra", default="USA", help="texto para la forma texto3d")
    ap.add_argument("--semilla", type=int, default=7)
    ap.add_argument("--reves", action="store_true")
    ap.add_argument("--crf", type=int, default=10, help="calidad x264: menor = mejor (0 = sin perdida)")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--preview", action="store_true", help="solo guarda un PNG de control")
    ap.add_argument("--preview-t", type=float, default=1 / 7, help="momento del preview, 0 a 1")
    a = ap.parse_args()

    rng = np.random.default_rng(a.semilla)
    pts = formas(a.forma, a.puntos, rng, a.palabra)
    texto = capa_texto(a.arriba, a.abajo)
    pbg, ptx, pa, pb = PALETAS[a.paleta]
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
    if a.forma in ("agujero_negro", "galaxia"):
        eje = 1 - np.minimum(1, np.linalg.norm(pts, axis=1))      # del centro (color de arriba) al borde (color de abajo)
    else:
        eje = pts[:, 1] if np.ptp(pts[:, 1]) >= .5 else 1 - np.hypot(pts[:, 0], pts[:, 2])
    ty = (eje - eje.min()) / max(1e-9, np.ptp(eje))   # 0 = color de abajo, 1 = color de arriba
    cols = c_b + (c_a - c_b) * ty[:, None]
    R = W * a.figura / 100; cy = H * .47
    tilt = math.radians(a.inclinacion); ct, st = math.cos(tilt), math.sin(tilt)
    dep = a.profundidad / 100
    total = int(round(a.seg * a.fps))
    # para que el video sea un bucle perfecto, el giro total se ajusta a vueltas enteras
    vueltas = max(1, round(a.vueltas_min / 60 * a.seg))
    sgn = -1 if a.reves else 1

    # recuadro de la figura, para no procesar toda la pantalla en cada cuadro
    m = int(R * 1.25)
    box = (max(0, int(W / 2 - m)), max(0, int(cy - m)), min(W, int(W / 2 + m)), min(H, int(cy + m)))
    bw, bh = box[2] - box[0], box[3] - box[1]

    def fotograma(i):
        ang = sgn * 2 * math.pi * vueltas * i / total
        ca, sa = math.cos(ang), math.sin(ang)
        x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
        x1 = x * ca + z * sa; z1 = -x * sa + z * ca
        y2 = y * ct - z1 * st; z2 = y * st + z1 * ct
        img = Image.new("RGB", (bw * SS, bh * SS), (0, 0, 0)); d = ImageDraw.Draw(img)
        mk = Image.new("L", (bw * SS, bh * SS), 0); dm = ImageDraw.Draw(mk)
        px = (W / 2 + x1 * R - box[0]) * SS; py = (cy - y2 * R - box[1]) * SS
        r = a.tam * (1 + dep * .6 * z2) * .6 * SS
        al = np.clip(1 - dep * .7 * (1 - z2) / 2, .08, 1)
        pre = (cols * al[:, None]).astype(np.uint8)
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
