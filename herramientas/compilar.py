#!/usr/bin/env python3
"""Crea el ejecutable de la interfaz gráfica con PyInstaller.

Uso:
    python herramientas/compilar.py

El resultado queda en ``dist/``: un único archivo que se puede copiar a
cualquier ordenador, sin instalar Python ni nada más.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOMBRE = "CorrectorLluviaWeeWX"


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Falta PyInstaller. Instálalo con:")
        print("    python -m pip install pyinstaller")
        return 1

    orden = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        NOMBRE,
        "--add-data",
        f"rainfix/assets{os.pathsep}rainfix/assets",
        "--paths",
        str(RAIZ),
    ]

    icono = RAIZ / "rainfix" / "assets" / "icono.ico"
    if sys.platform == "win32" and icono.is_file():
        orden += ["--icon", str(icono)]

    orden.append(str(RAIZ / "gui.py"))

    print("Ejecutando:", " ".join(orden))
    resultado = subprocess.run(orden, cwd=RAIZ)
    if resultado.returncode != 0:
        return resultado.returncode

    ejecutable = RAIZ / "dist" / (NOMBRE + (".exe" if sys.platform == "win32" else ""))
    print()
    print(f"Listo: {ejecutable}")
    if sys.platform != "win32":
        print("Recuerda darle permiso de ejecución: chmod +x", ejecutable.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
