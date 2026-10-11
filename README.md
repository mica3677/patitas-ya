# Patitas Ya: video de presentación (15 s)

`patitas-ya-15s.mp4`: vertical 1080x1920, 30 fps, 15 s, sin audio. Para Reels, TikTok e historias.

Todo se dibuja con código (`patitas_video.py`, con Cairo y la tipografía Poppins) y FFmpeg lo une en el MP4.

## Cambiar textos o el número de WhatsApp
1. Abrí `patitas_video.py`.
2. Arriba de todo está `WHATSAPP_NUMERO = "[ACÁ VA EL NÚMERO]"`. Reemplazá lo que está entre comillas.
3. Justo debajo, en `TEXTOS`, están todas las frases. Editalas respetando las comillas.
   Si una frase queda más larga, la letra se achica sola para no cortarse.
4. Volvé a generar el video (ver abajo).

## Generar el video
Necesitás Python 3 y FFmpeg instalados.
```
pip install -r requirements.txt
python3 patitas_video.py            # crea patitas-ya-15s.mp4
python3 patitas_video.py --preview  # solo saca fotos de control en previews/
```
Antes de exportar, el programa revisa automáticamente que ningún texto quede fuera de la zona segura ni encimado con otro.

Tipografía: Poppins (licencia libre SIL OFL, ver `fonts/OFL.txt`).
