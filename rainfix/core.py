"""Lógica compartida por la interfaz de línea de órdenes y la gráfica."""

from __future__ import annotations

import contextlib
import datetime as dt
import re
import sqlite3
from pathlib import Path
from typing import Callable, Sequence

MM_POR_UNIDAD = {"in": 25.4, "mm": 1.0}
NOMBRES_UNIDAD = {"in": "pulgadas", "mm": "milímetros"}
TAMANO_LOTE = 500

Fecha = dt.datetime
Fila = tuple[int, float, float]
Cambio = tuple[float, float, int]

Progreso = Callable[[int, int], None]


class Cancelado(Exception):
    """El usuario ha decidido no continuar."""


class ErrorApp(Exception):
    """Error esperable: se muestra al usuario sin traza."""


# --------------------------------------------------------------------------
# Fechas y números
# --------------------------------------------------------------------------
def parsear_fecha(texto: str) -> Fecha:
    """Convierte 'AAAA/MM/DD-HH/MM/SS' en datetime.

    Acepta cualquier separador (barras, guiones, espacios, dos puntos...) e
    incluso cifras sin rellenar a dos dígitos.
    """
    numeros = re.findall(r"\d+", texto)
    if len(numeros) != 6:
        raise ErrorApp(
            f"fecha no válida: {texto!r}. Se esperaba el formato AAAA/MM/DD-HH/MM/SS"
        )
    try:
        return dt.datetime(*(int(n) for n in numeros))
    except ValueError as exc:
        raise ErrorApp(f"fecha no válida {texto!r}: {exc}") from None


def parsear_fecha_flexible(texto: str, fin: bool = False) -> Fecha:
    """Como :func:`parsear_fecha`, pero admite también solo la fecha.

    Si se escribe únicamente ``AAAA-MM-DD`` se usa la medianoche para el
    inicio del periodo y las 23:59:59 para el fin, que es lo que espera
    cualquiera al elegir "un día completo".
    """
    numeros = re.findall(r"\d+", texto)
    if len(numeros) == 3 and not fin:
        return dt.datetime(*(int(n) for n in numeros))
    if len(numeros) == 3 and fin:
        return dt.datetime(*(int(n) for n in numeros), 23, 59, 59)
    return parsear_fecha(texto)


def a_epoch(fecha: Fecha, utc: bool) -> int:
    if utc:
        return int(fecha.replace(tzinfo=dt.timezone.utc).timestamp())
    return int(fecha.timestamp())


def desde_epoch(epoch: int, utc: bool) -> Fecha:
    """Convierte un epoch de la base de datos en fecha local o UTC (naive)."""
    if utc:
        return dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).replace(tzinfo=None)
    return dt.datetime.fromtimestamp(epoch)


def parsear_numero(texto: str) -> float:
    limpio = texto.strip().replace(" ", "")
    if "," in limpio and "." in limpio:
        limpio = limpio.replace(",", "")
    else:
        limpio = limpio.replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        raise ErrorApp(f"valor numérico no válido: {texto!r}") from None


# --------------------------------------------------------------------------
# Base de datos
# --------------------------------------------------------------------------
def validar_tabla(tabla: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tabla):
        raise ErrorApp(f"nombre de tabla no válido: {tabla!r}")
    return tabla


def comprobar_db(ruta: Path) -> Path:
    ruta = ruta.expanduser()
    if not ruta.is_file():
        raise ErrorApp(f"no se encuentra el archivo {ruta}")
    return ruta


def leer_registros(db: Path, tabla: str, desde: int, hasta: int) -> list[Fila]:
    sql = (
        f"SELECT dateTime, rain, rainRate FROM {tabla} "
        "WHERE dateTime >= ? AND dateTime <= ? AND rain > 0 ORDER BY dateTime"
    )
    try:
        with contextlib.closing(sqlite3.connect(db)) as con:
            return con.execute(sql, (desde, hasta)).fetchall()
    except sqlite3.DatabaseError as exc:
        raise ErrorApp(
            f"no se pudo leer la tabla '{tabla}' de {db}: {exc}\n"
            "  ¿Es realmente una base de datos de WeeWX?"
        ) from None


def ultimo_registro(db: Path, tabla: str) -> Fecha | None:
    """Fecha del último registro de la tabla, útil para los atajos de fechas."""
    sql = f"SELECT MAX(dateTime) FROM {tabla}"
    try:
        with contextlib.closing(sqlite3.connect(db)) as con:
            (valor,) = con.execute(sql).fetchone()
    except sqlite3.DatabaseError as exc:
        raise ErrorApp(f"no se pudo leer la tabla '{tabla}' de {db}: {exc}") from None
    if valor is None:
        return None
    return desde_epoch(int(valor), utc=False)


def copia_seguridad(db: Path) -> Path:
    """Copia consistente de la BD, incluso si WeeWX está escribiendo en ella."""
    destino = db.with_name(f"{db.name}.{dt.datetime.now():%Y%m%d-%H%M%S}.bak")
    try:
        with contextlib.closing(sqlite3.connect(db)) as origen, contextlib.closing(
            sqlite3.connect(destino)
        ) as copia:
            origen.backup(copia)
    except sqlite3.DatabaseError as exc:
        raise ErrorApp(f"no se pudo crear la copia de seguridad: {exc}") from None
    return destino


def calcular_cambio(
    registros: Sequence[Fila], nuevo_mm: float, unidades_db: str
) -> tuple[float, float, float, list[Cambio]]:
    """Devuelve (total_db, total_mm, factor, filas_actualizadas)."""
    factor_unidad = MM_POR_UNIDAD[unidades_db]
    total_db = sum(rain for _, rain, _ in registros)
    if total_db <= 0:
        raise ErrorApp("el periodo no contiene precipitación que corregir.")
    if nuevo_mm < 0:
        raise ErrorApp("el acumulado no puede ser negativo.")
    if nuevo_mm == 0:
        raise ErrorApp(
            "no se puede poner el acumulado a 0: el factor de corrección sería nulo.\n"
            "  Usa un valor muy pequeño (por ejemplo 0.0001 mm): no afecta al acumulado,\n"
            "  deja constancia del cambio y permite recuperar el dato original después."
        )
    total_mm = total_db * factor_unidad
    factor = (nuevo_mm / factor_unidad) / total_db
    filas = [
        (rain * factor, (rate or 0.0) * factor, epoch)
        for epoch, rain, rate in registros
    ]
    return total_db, total_mm, factor, filas


def aplicar(
    db: Path, tabla: str, filas: Sequence[Cambio], progreso: Progreso | None = None
) -> int:
    """Actualiza todos los registros en una única transacción."""
    sql = f"UPDATE {tabla} SET rain = ?, rainRate = ? WHERE dateTime = ?"
    try:
        with contextlib.closing(sqlite3.connect(db)) as con, con:
            for inicio in range(0, len(filas), TAMANO_LOTE):
                con.executemany(sql, filas[inicio : inicio + TAMANO_LOTE])
                if progreso is not None:
                    progreso(min(inicio + TAMANO_LOTE, len(filas)), len(filas))
            return con.total_changes
    except sqlite3.OperationalError as exc:
        raise ErrorApp(
            f"no se pudo escribir en la base de datos ({exc}).\n"
            "  Comprueba que WeeWX esté parado y que el archivo no esté bloqueado."
        ) from None


# --------------------------------------------------------------------------
# Unidades
# --------------------------------------------------------------------------
def detectar_unidades(
    db: Path, config: Path | None = None
) -> tuple[str, Path] | None:
    """Intenta deducir las unidades de ``rain`` a partir de ``weewx.conf``.

    Devuelve ``(unidad, ruta_del_config)`` o ``None`` si no encuentra nada.
    """
    import configparser

    candidatos: list[Path] = []
    if config is not None:
        candidatos.append(config)
    candidatos.extend(
        [
            db.parent / "weewx.conf",
            db.parent.parent / "weewx.conf",
            Path("/etc/weewx/weewx.conf"),
        ]
    )

    vistos: set[Path] = set()
    for candidato in candidatos:
        try:
            candidato = candidato.expanduser().resolve()
        except OSError:
            continue
        if candidato in vistos or not candidato.is_file():
            continue
        vistos.add(candidato)
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(candidato, encoding="utf-8")
            valor = parser.get("StdConvert", "target_unit", fallback=None)
        except (configparser.Error, OSError):
            continue
        if not valor:
            continue
        valor = valor.strip().upper()
        if valor == "US":
            return "in", candidato
        if valor.startswith("METRIC"):
            return "mm", candidato
    return None
