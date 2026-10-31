#!/usr/bin/env python3
"""Genera el icono de la aplicación (PNG e ICO) usando Pillow.

Solo hace falta ejecutarlo si se quiere cambiar el diseño. Los archivos ya
generados se guardan en ``rainfix/assets/``.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).resolve().parent.parent / "rainfix" / "assets"
TAMANO = 512


def crear_icono() -> Image.Image:
    imagen = Image.new("RGBA", (TAMANO, TAMANO), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(imagen)

    # Fondo redondeado con un degradado azul.
    fondo = Image.new("RGBA", (TAMANO, TAMANO), (0, 0, 0, 0))
    degradado = ImageDraw.Draw(fondo)
    for y in range(TAMANO):
        proporcion = y / TAMANO
        rojo = int(31 + (11 - 31) * proporcion)
        verde = int(111 + (75 - 111) * proporcion)
        azul = int(235 + (179 - 235) * proporcion)
        degradado.line([(0, y), (TAMANO, y)], fill=(rojo, verde, azul, 255))
    mascara = Image.new("L", (TAMANO, TAMANO), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [0, 0, TAMANO - 1, TAMANO - 1], radius=110, fill=255
    )
    imagen.paste(fondo, (0, 0), mascara)
    dibujo = ImageDraw.Draw(imagen)

    blanco = (255, 255, 255, 255)
    blanco_suave = (219, 234, 254, 255)

    # Nube: tres círculos y una base redondeada.
    dibujo.ellipse([112, 168, 264, 320], fill=blanco)
    dibujo.ellipse([196, 128, 372, 304], fill=blanco)
    dibujo.ellipse([300, 184, 424, 308], fill=blanco)
    dibujo.rounded_rectangle([120, 244, 416, 320], radius=38, fill=blanco)

    # Gotas de lluvia.
    for x, y, alto in ((170, 344, 66), (256, 360, 82), (342, 344, 66)):
        dibujo.polygon(
            [
                (x, y - alto // 2),
                (x - alto // 4, y + alto // 6),
                (x - alto // 5, y + alto // 2),
                (x, y + alto // 2 + 6),
                (x + alto // 5, y + alto // 2),
                (x + alto // 4, y + alto // 6),
            ],
            fill=blanco_suave,
        )

    return imagen


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    imagen = crear_icono()
    png = DESTINO / "icono.png"
    ico = DESTINO / "icono.ico"
    imagen.save(png)
    imagen.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"escrito {png}")
    print(f"escrito {ico}")


if __name__ == "__main__":
    main()
