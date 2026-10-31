#!/usr/bin/env python3
"""weewxDdbbEditor - corrige el acumulado de precipitación de una base de datos WeeWX.

Reescala de forma proporcional los valores de ``rain`` y ``rainRate`` de la tabla
``archive`` dentro de un rango de fechas, conservando la distribución original de
la lluvia y los rain rates.

Solo usa la biblioteca estándar: no hay nada que instalar. Para la versión con
ventana, ejecuta ``gui.py``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from rainfix import __version__, core

MM_POR_UNIDAD = core.MM_POR_UNIDAD
NOMBRES_UNIDAD = core.NOMBRES_UNIDAD

VERDE = "\033[32m"
AMARILLO = "\033[33m"
ROJO = "\033[31m"
CIAN = "\033[36m"
NEGRITA = "\033[1m"
RESET = "\033[0m"

Cancelado = core.Cancelado
ErrorApp = core.ErrorApp
parsear_fecha = core.parsear_fecha


# --------------------------------------------------------------------------
# Consola
# --------------------------------------------------------------------------
def _soportar_color() -> bool:
    """¿Se puede usar color en esta terminal? Habilita ANSI en Windows 10+."""
    if "NO_COLOR" in os.environ or not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        modo = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(modo)):
            return False
        return bool(kernel32.SetConsoleMode(handle, modo.value | 0x0004))
    except Exception:
        return False


_USAR_COLOR = _soportar_color()


def color(texto: str, codigo: str) -> str:
    return f"{codigo}{texto}{RESET}" if _USAR_COLOR else texto


def preguntar(texto: str) -> str:
    try:
        return input(color(texto, VERDE)).strip()
    except EOFError:
        raise Cancelado(
            "no hay una terminal interactiva; usa --yes para confirmar"
        ) from None


def es_si(respuesta: str) -> bool:
    return respuesta.strip().lower() in {"s", "si", "sí", "y", "yes"}


def _fila(etiqueta: str, valor: str) -> None:
    print(f"  {etiqueta:<15}: {valor}")


def _progreso(hecho: int, total: int) -> None:
    if not sys.stdout.isatty() or total == 0:
        return
    print(f"\r  {hecho}/{total} registros ({hecho * 100 // total} %)", end="", flush=True)


def _fin_progreso() -> None:
    if sys.stdout.isatty():
        print()


def resolver_db(ruta: Path | None) -> Path:
    if ruta is None:
        ruta = Path(preguntar("Ruta del archivo de la base de datos: "))
    return core.comprobar_db(ruta)


# --------------------------------------------------------------------------
# Programa
# --------------------------------------------------------------------------
def ejecutar(args: argparse.Namespace) -> int:
    tabla = core.validar_tabla(args.tabla)
    db = resolver_db(args.db)

    desde = parsear_fecha(args.desde or preguntar("Fecha de inicio (AAAA/MM/DD-HH/MM/SS): "))
    hasta = parsear_fecha(args.hasta or preguntar("Fecha de fin    (AAAA/MM/DD-HH/MM/SS): "))
    if hasta < desde:
        raise ErrorApp("la fecha de inicio no puede ser posterior a la fecha de fin.")

    zona = "UTC" if args.utc else "hora local"
    print()
    registros = core.leer_registros(
        db, tabla, core.a_epoch(desde, args.utc), core.a_epoch(hasta, args.utc)
    )
    if not registros:
        raise ErrorApp(
            f"no hay registros con precipitación entre {desde:%Y-%m-%d %H:%M:%S} "
            f"y {hasta:%Y-%m-%d %H:%M:%S} ({zona}).\n"
            "  Este programa no puede añadir lluvia donde no la había."
        )

    factor_unidad = MM_POR_UNIDAD[args.unidades_db]
    total_db = sum(rain for _, rain, _ in registros)
    total_mm = total_db * factor_unidad

    print(color(f"weewxDdbbEditor {__version__}", NEGRITA))
    _fila("Base de datos", str(db))
    _fila("Tabla", f"{tabla}  (rain en {NOMBRES_UNIDAD[args.unidades_db]})")
    _fila("Periodo", f"{desde:%Y-%m-%d %H:%M:%S} → {hasta:%Y-%m-%d %H:%M:%S} ({zona})")
    _fila("Registros", f"{len(registros):,}".replace(",", "."))
    _fila("Acumulado", f"{total_mm:.2f} mm")

    nuevo_mm = args.nuevo_total
    if nuevo_mm is None:
        texto = preguntar("Nuevo acumulado del periodo en milímetros (Intro para no cambiar): ")
        if not texto:
            print(color("\nSin cambios.", CIAN))
            return 0
        nuevo_mm = core.parsear_numero(texto)

    _, _, factor, filas = core.calcular_cambio(registros, nuevo_mm, args.unidades_db)
    _fila("Nuevo total", f"{nuevo_mm:.2f} mm  ({factor * 100:.2f} % del original)")
    _fila("Factor", f"{factor:.6f}")
    print()

    if args.dry_run:
        print(color("Simulación (--dry-run): no se ha modificado nada.", CIAN))
        return 0

    if not args.yes:
        if not es_si(preguntar(f"¿Aplicar el cambio a {len(registros)} registros? [s/N] ")):
            raise Cancelado("no se ha modificado nada")

    if args.sin_backup:
        print(color("Aviso: se omite la copia de seguridad (--sin-backup).", AMARILLO))
    else:
        destino = core.copia_seguridad(db)
        _fila("Copia de seguridad", str(destino))

    print(color("Aplicando cambios...", VERDE))
    try:
        cambios = core.aplicar(db, tabla, filas, _progreso)
    finally:
        _fin_progreso()

    print()
    print(color(f"{cambios:,}".replace(",", ".") + f" registros actualizados en {db.name}.", VERDE))
    if cambios != len(filas):
        print(
            color(
                f"Aviso: se esperaban {len(filas)} registros; puede que WeeWX haya "
                "modificado la base de datos durante el proceso.",
                AMARILLO,
            )
        )
    print()
    print(color("Recuerda:", AMARILLO))
    print("  · Reconstruye los resúmenes diarios para que las gráficas cuadren:")
    print("      weectl database rebuild-daily    (WeeWX 5.0 o superior)")
    print("      wee_database --rebuild-daily     (WeeWX anterior a 5.0)")
    print("  · Comprueba la base de datos antes de dar el cambio por definitivo.")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="weewx-rain-fix",
        description="Corrige el acumulado de precipitación de una base de datos WeeWX "
        "reescalando los valores de forma proporcional en un rango de fechas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  # Ver qué haría, sin tocar nada\n"
            '  weewx-rain-fix --db weewx.sdb --desde "2021-01-01 12:00:00" \\\n'
            '                 --hasta "2021-01-31 12:00:00" --nuevo-total 12.4 --dry-run\n\n'
            "  # Aplicar el cambio sin preguntar (hace copia de seguridad automática)\n"
            '  weewx-rain-fix --db weewx.sdb --desde "2021-01-01 12:00:00" \\\n'
            '                 --hasta "2021-01-31 12:00:00" --nuevo-total 12.4 --yes\n\n'
            "  # Modo interactivo\n"
            "  weewx-rain-fix\n"
        ),
    )
    parser.add_argument("--db", type=Path, metavar="RUTA", help="base de datos SQLite de WeeWX")
    parser.add_argument("--desde", metavar="FECHA", help="inicio del periodo (AAAA/MM/DD-HH/MM/SS)")
    parser.add_argument("--hasta", metavar="FECHA", help="fin del periodo (AAAA/MM/DD-HH/MM/SS)")
    parser.add_argument(
        "--nuevo-total",
        type=float,
        metavar="MM",
        help="nuevo acumulado del periodo, en milímetros",
    )
    parser.add_argument(
        "--unidades-db",
        choices=("in", "mm"),
        default="in",
        help="unidades en que la base de datos guarda rain/rainRate (por defecto: in)",
    )
    parser.add_argument("--tabla", default="archive", help="tabla a modificar (por defecto: archive)")
    parser.add_argument(
        "--utc",
        action="store_true",
        help="interpretar las fechas como UTC en lugar de hora local",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="mostrar el resumen y salir sin modificar nada",
    )
    parser.add_argument(
        "--sin-backup",
        action="store_true",
        help="no crear copia de seguridad antes de escribir (no recomendado)",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="no pedir confirmación (necesario en scripts)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    try:
        return ejecutar(args)
    except Cancelado as exc:
        print(color(f"\nCancelado: {exc}", AMARILLO))
        return 1
    except ErrorApp as exc:
        print(color(f"\nError: {exc}", ROJO), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(color("\nInterrumpido por el usuario.", AMARILLO))
        return 130


if __name__ == "__main__":
    sys.exit(main())
