#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Arma la pista de audio del video de imagen residual: voz en off (cortada por frases y puesta en su momento) + musica ambiental
+ sonidos (tic de cada segundo, barrido al pasar al blanco, campanita en la revelacion). Todo generado aca, sin depender de nada externo."""
import subprocess, sys, numpy as np, os
SR = 44100; DUR = 16.5
aqui = os.path.dirname(os.path.abspath(__file__))
voz_mp3 = os.path.join(aqui, "audio", "voz_residual_usa.mp3"); salida = sys.argv[1] if len(sys.argv) > 1 else os.path.join(aqui, "audio", "mezcla_residual.wav")

# frases de la voz (inicio, fin) dentro del mp3, y el segundo del video donde entra cada una
FRASES = [(0.00, 2.20, 0.30), (2.70, 3.78, 2.90), (4.38, 5.82, 4.20), (6.55, 9.19, 5.80), (9.65, 10.42, 8.30),
          (11.08, 12.46, 9.30), (12.95, 13.80, 11.00), (14.50, 18.05, 12.50)]

def cargar(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)

def env(n, a, r):
    e = np.ones(n, np.float32); na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, 1, na) ** 2
    if nr: e[-nr:] *= np.linspace(1, 0, nr) ** 2
    return e

def tono(f, dur, a=.02, r=.3, arm=(1,), amps=(1,)):
    t = np.arange(int(dur * SR)) / SR; x = sum(am * np.sin(2 * np.pi * f * h * t) for h, am in zip(arm, amps)); return x * env(len(t), a, r)

def poner(buf, x, t0, g=1.0):
    i = int(t0 * SR); j = min(len(buf), i + len(x))
    if i < len(buf): buf[i:j] += x[:j - i] * g

def eco(x, retraso=.31, fb=.38, veces=5):
    out = x.copy()
    for k in range(1, veces + 1): d = int(retraso * SR * k); out[d:] += x[:len(x) - d] * fb ** k
    return out

n = int(DUR * SR); musica = np.zeros(n, np.float32); sfx = np.zeros(n, np.float32); voz = np.zeros(n, np.float32)
# --- musica: acordes lentos (Am - F - C - G) + campanitas en escala pentatonica
mid = lambda m: 440 * 2 ** ((m - 69) / 12)
acordes = [[45, 52, 57, 60], [41, 48, 53, 57], [48, 55, 60, 64], [43, 50, 55, 59]]
for k in range(5):
    t0 = k * 4.0
    for m in acordes[k % 4]:
        for det in (-.003, .003):
            x = tono(mid(m) * (1 + det), 4.6, a=1.2, r=1.6, arm=(1, 2, 3), amps=(1, .25, .08)); poner(musica, x, t0, .035)
penta = [69, 72, 74, 76, 79, 81, 84]; rr = np.random.default_rng(4)
for k in range(int(DUR / .5)):
    if rr.random() < .62:
        m = penta[rr.integers(0, len(penta))] - (12 if rr.random() < .3 else 0); x = tono(mid(m), 1.6, a=.004, r=1.4, arm=(1, 2.01, 3.99), amps=(1, .3, .1)) * np.exp(-np.arange(int(1.6 * SR)) / SR * 3.2)
        poner(musica, eco(x), 1.0 + k * .5, .05)
musica *= np.clip(np.minimum(np.arange(n) / (1.5 * SR), (n - np.arange(n)) / (1.5 * SR)), 0, 1)
# --- sonidos
for k in range(1, 9):                                         # tic de cada segundo mientras se mira el punto
    f = 880 if k < 6 else 1320; x = tono(f, .12, a=.002, r=.1, arm=(1, 2), amps=(1, .3)) * np.exp(-np.arange(int(.12 * SR)) / SR * 28); poner(sfx, x, k, .22)
r_ = np.random.default_rng(1).standard_normal(int(1.1 * SR)).astype(np.float32); t_ = np.linspace(0, 1, len(r_))
barrido = np.convolve(r_, np.ones(int(SR / 900 + 4 * np.linspace(1, 20, 1)[0])) / 20, mode="same") * (t_ ** 2) * (1 - t_) ** .6 * 2.2
poner(sfx, barrido.astype(np.float32), 8.45, .35)                # whoosh hacia el blanco
for m, dt in ((72, 0), (76, .09), (79, .18), (84, .27)): poner(sfx, eco(tono(mid(m), 2.0, a=.003, r=1.8, arm=(1, 2.01, 3.99), amps=(1, .3, .1)) * np.exp(-np.arange(int(2.0 * SR)) / SR * 2.6)), 14.0 + dt, .16)   # campanita de la revelacion
# --- voz
v = cargar(voz_mp3)
for i0, i1, t0 in FRASES:
    seg = v[int(i0 * SR):int(i1 * SR)].copy(); seg *= env(len(seg), .03, .05); poner(voz, seg, t0, 1.0)
voz /= max(1e-6, np.abs(voz).max()); voz *= .9
# ducking: la musica baja cuando habla la voz
suav = np.convolve(np.abs(voz), np.ones(int(.25 * SR)) / int(.25 * SR), mode="same"); duck = 1 - .55 * np.clip(suav / .06, 0, 1)
mezcla = voz + musica / max(1e-6, np.abs(musica).max()) * .22 * duck + sfx * .9
mezcla = np.tanh(mezcla * 1.1) / 1.1; mezcla = mezcla / max(1e-6, np.abs(mezcla).max()) * .92
est = np.stack([mezcla, mezcla], 1)
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", salida], input=est.astype(np.float32).tobytes(), check=True)
print("listo", salida)
