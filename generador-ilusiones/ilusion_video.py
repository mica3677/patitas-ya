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
import argparse, math, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

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


def formas(nombre, n, rng):
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
        nb = int(n * .14); r = rng.random(n - nb) ** .65
        ang = rng.integers(3, size=n - nb) * 2 * math.pi / 3 + r * 3.4 + rng.normal(size=n - nb) * .16 * (1.1 - r)
        disco = np.c_[np.cos(ang) * r, rng.normal(size=n - nb) * .025 * (1.2 - r), np.sin(ang) * r]
        return np.r_[disco, rng.normal(size=(nb, 3)) * [.1, .07, .1]]
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
                                                  "cono_invertido", "galaxia", "nudo_toroidal", "icosaedro", "tornado", "corazon", "ondas", "esfera_fibonacci"])
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
    ap.add_argument("--semilla", type=int, default=7)
    ap.add_argument("--reves", action="store_true")
    ap.add_argument("--crf", type=int, default=10, help="calidad x264: menor = mejor (0 = sin perdida)")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--preview", action="store_true", help="solo guarda un PNG de control")
    a = ap.parse_args()

    rng = np.random.default_rng(a.semilla)
    pts = formas(a.forma, a.puntos, rng)
    texto = capa_texto(a.arriba, a.abajo)
    pbg, ptx, pa, pb = PALETAS[a.paleta]
    c_bg, c_tx = rgb(a.fondo or pbg), rgb(a.texto or ptx)
    c_a = rgb(a.color or pa)
    c_b = rgb(a.color2) if a.color2 else (rgb(pb) if not a.color else c_a)
    base = c_bg + (c_tx - c_bg) * texto[..., None]          # fondo + texto, listo para pegar los puntos
    # el color va pegado al objeto: por altura, o del centro al borde si la figura es plana
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
        col = np.asarray(img.resize((bw, bh), Image.LANCZOS), dtype=np.float32) / 255
        cov = np.asarray(mk.resize((bw, bh), Image.LANCZOS), dtype=np.float32)[..., None] / 255
        out = base.copy()
        sub = out[box[1]:box[3], box[0]:box[2]]
        sub[:] = sub * (1 - cov) + col * 255
        return (out + .5).astype(np.uint8)

    if a.preview:
        Image.fromarray(fotograma(total // 7)).save("preview.png"); print("preview.png"); return

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
