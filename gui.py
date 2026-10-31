#!/usr/bin/env python3
"""Interfaz gráfica de weewxDdbbEditor.

Una ventana sencilla, pensada para quien no quiere tocar una terminal: elegir
la base de datos, marcar el periodo, escribir el nuevo total y pulsar un botón.

Solo usa la biblioteca estándar (Tkinter), así que funciona igual en Windows,
Linux y macOS.
"""

from __future__ import annotations

import datetime as dt
import queue
import sys
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from rainfix import __version__, core

TITULO = "Corrector de lluvia WeeWX"
UNIDADES = {
    "Pulgadas (US)": "in",
    "Milímetros (METRIC)": "mm",
}
UNIDADES_INVERSO = {v: k for k, v in UNIDADES.items()}
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"
ANCHO_ETIQUETA = 18


def _numero(valor: float, decimales: int = 2) -> str:
    """Número con coma decimal, más natural en español."""
    return f"{valor:,.{decimales}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _texto_fecha(fecha: dt.datetime) -> str:
    return fecha.strftime(FORMATO_FECHA)


class Ventana(ttk.Frame):
    def __init__(self, raiz: tk.Tk) -> None:
        super().__init__(raiz, padding=16)
        self.raiz = raiz
        self.grid(row=0, column=0, sticky="nsew")
        raiz.columnconfigure(0, weight=1)
        raiz.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.db_var = tk.StringVar()
        self.desde_var = tk.StringVar()
        self.hasta_var = tk.StringVar()
        self.total_var = tk.StringVar()
        self.unidades_var = tk.StringVar(value=UNIDADES_INVERSO["in"])
        self.utc_var = tk.BooleanVar(value=False)
        self.backup_var = tk.BooleanVar(value=True)

        self._registros: list[core.Fila] | None = None
        self._filas: list[core.Cambio] = []
        self._resumen: dict[str, object] = {}
        self._trabajando = False
        self._cola: queue.Queue[tuple] = queue.Queue()
        self._unidades_tocadas = False

        self._crear_estilos()
        self._crear_widgets()
        self._trazas()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _crear_estilos(self) -> None:
        estilo = ttk.Style(self.raiz)
        for tema in ("clam", "vista", "default"):
            if tema in estilo.theme_names():
                estilo.theme_use(tema)
                break

        base = tkfont.nametofont("TkDefaultFont")
        self.fuente_titulo = base.copy()
        self.fuente_titulo.configure(size=max(base.cget("size") + 6, 16), weight="bold")
        self.fuente_subtitulo = base.copy()
        self.fuente_subtitulo.configure(size=max(base.cget("size") + 1, 11))
        self.fuente_boton = base.copy()
        self.fuente_boton.configure(size=max(base.cget("size") + 2, 11), weight="bold")
        self.fuente_pequena = base.copy()
        self.fuente_pequena.configure(size=max(base.cget("size") - 1, 8))

        estilo.configure("Titulo.TLabel", font=self.fuente_titulo)
        estilo.configure("Subtitulo.TLabel", font=self.fuente_subtitulo, foreground="#555555")
        estilo.configure("Pista.TLabel", font=self.fuente_pequena, foreground="#666666")
        estilo.configure("Aviso.TLabel", font=self.fuente_pequena, foreground="#9a6700")
        estilo.configure("Error.TLabel", font=self.fuente_pequena, foreground="#b42318")
        estilo.configure("Ok.TLabel", font=self.fuente_pequena, foreground="#1a7f37")
        estilo.configure("Paso.TLabelframe.Label", font=self.fuente_subtitulo)
        estilo.configure("TButton", padding=(10, 6))
        estilo.configure(
            "Principal.TButton",
            font=self.fuente_boton,
            padding=(16, 10),
            background="#1f6feb",
            foreground="white",
            bordercolor="#1f6feb",
            lightcolor="#1f6feb",
            darkcolor="#1f6feb",
        )
        estilo.map(
            "Principal.TButton",
            background=[("disabled", "#d5d8dc"), ("active", "#1858c4")],
            foreground=[("disabled", "#8a8f98")],
            bordercolor=[("disabled", "#d5d8dc")],
            lightcolor=[("disabled", "#d5d8dc")],
            darkcolor=[("disabled", "#d5d8dc")],
        )
        estilo.configure(
            "Aplicar.TButton",
            font=self.fuente_boton,
            padding=(16, 10),
            background="#1a7f37",
            foreground="white",
            bordercolor="#1a7f37",
            lightcolor="#1a7f37",
            darkcolor="#1a7f37",
        )
        estilo.map(
            "Aplicar.TButton",
            background=[("disabled", "#d5d8dc"), ("active", "#146c2e")],
            foreground=[("disabled", "#8a8f98")],
            bordercolor=[("disabled", "#d5d8dc")],
            lightcolor=[("disabled", "#d5d8dc")],
            darkcolor=[("disabled", "#d5d8dc")],
        )
        estilo.configure("Progreso.Horizontal.TProgressbar", thickness=18)

    def _crear_widgets(self) -> None:
        fila = 0

        cabecera = ttk.Frame(self)
        cabecera.grid(row=fila, column=0, sticky="ew", pady=(0, 12))
        cabecera.columnconfigure(0, weight=1)
        ttk.Label(cabecera, text=TITULO, style="Titulo.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            cabecera,
            text="Corrige el total de lluvia de un periodo sin reescribir la forma del temporal.",
            style="Subtitulo.TLabel",
            wraplength=760,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(cabecera, text=f"versión {__version__}", style="Pista.TLabel").grid(
            row=0, column=1, sticky="e"
        )

        # --- Paso 1: base de datos -------------------------------------
        fila += 1
        paso1 = ttk.LabelFrame(self, text=" 1 · Elige la base de datos de WeeWX ", style="Paso.TLabelframe")
        paso1.grid(row=fila, column=0, sticky="ew", pady=(0, 10))
        paso1.columnconfigure(1, weight=1)

        ttk.Label(paso1, text="Archivo:").grid(row=0, column=0, sticky="w", padx=(12, 6), pady=(10, 4))
        self.entrada_db = ttk.Entry(paso1, textvariable=self.db_var)
        self.entrada_db.grid(row=0, column=1, sticky="ew", pady=(10, 4))
        self.entrada_db.bind("<FocusOut>", self._al_salir_de_db)
        ttk.Button(paso1, text="Elegir archivo…", command=self.elegir_db).grid(
            row=0, column=2, padx=(8, 12), pady=(10, 4)
        )

        ttk.Label(paso1, text="Unidades de los datos:").grid(
            row=1, column=0, sticky="w", padx=(12, 6), pady=(0, 4)
        )
        self.combo_unidades = ttk.Combobox(
            paso1,
            textvariable=self.unidades_var,
            values=list(UNIDADES),
            state="readonly",
            width=22,
        )
        self.combo_unidades.grid(row=1, column=1, sticky="w", pady=(0, 4))
        self.combo_unidades.bind("<<ComboboxSelected>>", self._unidades_cambiadas)

        self.aviso_unidades = ttk.Label(paso1, text="", style="Pista.TLabel", wraplength=700)
        self.aviso_unidades.grid(row=2, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 10))

        # --- Paso 2: periodo -------------------------------------------
        fila += 1
        paso2 = ttk.LabelFrame(self, text=" 2 · Indica el periodo que quieres corregir ", style="Paso.TLabelframe")
        paso2.grid(row=fila, column=0, sticky="ew", pady=(0, 10))
        paso2.columnconfigure(1, weight=1)
        paso2.columnconfigure(3, weight=1)

        ttk.Label(paso2, text="Desde:").grid(row=0, column=0, sticky="w", padx=(12, 6), pady=(10, 4))
        ttk.Entry(paso2, textvariable=self.desde_var).grid(
            row=0, column=1, sticky="ew", pady=(10, 4)
        )
        ttk.Label(paso2, text="Hasta:").grid(row=0, column=2, sticky="w", padx=(12, 6), pady=(10, 4))
        ttk.Entry(paso2, textvariable=self.hasta_var).grid(
            row=0, column=3, sticky="ew", padx=(0, 12), pady=(10, 4)
        )

        atajos = ttk.Frame(paso2)
        atajos.grid(row=1, column=0, columnspan=4, sticky="w", padx=12, pady=(2, 4))
        ttk.Label(atajos, text="Rellenar rápido:", style="Pista.TLabel").pack(side="left", padx=(0, 8))
        for texto, dias, mes in (
            ("Últimas 24 horas", 1, False),
            ("Últimos 7 días", 7, False),
            ("Últimos 30 días", 30, False),
            ("Último mes natural", 0, True),
        ):
            ttk.Button(
                atajos,
                text=texto,
                command=lambda d=dias, m=mes: self.atajo_fechas(d, m),
            ).pack(side="left", padx=(0, 6))

        pie2 = ttk.Frame(paso2)
        pie2.grid(row=2, column=0, columnspan=4, sticky="ew", padx=12, pady=(0, 10))
        pie2.columnconfigure(0, weight=1)
        ttk.Label(
            pie2,
            text="Formato: AAAA-MM-DD HH:MM:SS · también vale solo la fecha (AAAA-MM-DD)",
            style="Pista.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(
            pie2, text="Las fechas están en UTC", variable=self.utc_var
        ).grid(row=0, column=1, sticky="e")

        # --- Paso 3: nuevo total ---------------------------------------
        fila += 1
        paso3 = ttk.LabelFrame(self, text=" 3 · Escribe el nuevo total de lluvia ", style="Paso.TLabelframe")
        paso3.grid(row=fila, column=0, sticky="ew", pady=(0, 10))
        paso3.columnconfigure(2, weight=1)

        ttk.Label(paso3, text="Nuevo total:").grid(row=0, column=0, sticky="w", padx=(12, 6), pady=(10, 4))
        entrada_total = ttk.Entry(paso3, textvariable=self.total_var, width=14)
        entrada_total.grid(row=0, column=1, sticky="w", pady=(10, 4))
        ttk.Label(paso3, text="milímetros", style="Subtitulo.TLabel").grid(
            row=0, column=2, sticky="w", padx=(6, 12), pady=(10, 4)
        )

        self.etiqueta_actual = ttk.Label(
            paso3,
            text="Pulsa «Comprobar» para ver cuánta lluvia hay ahora en ese periodo.",
            style="Pista.TLabel",
            wraplength=760,
        )
        self.etiqueta_actual.grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 10))

        # --- Acciones ---------------------------------------------------
        fila += 1
        acciones = ttk.Frame(self)
        acciones.grid(row=fila, column=0, sticky="ew", pady=(0, 8))
        acciones.columnconfigure(2, weight=1)

        self.boton_comprobar = ttk.Button(
            acciones, text="Comprobar", style="Principal.TButton", command=self.comprobar
        )
        self.boton_comprobar.grid(row=0, column=0, padx=(0, 8))

        self.boton_corregir = ttk.Button(
            acciones,
            text="Corregir la base de datos",
            style="Aplicar.TButton",
            command=self.corregir,
            state="disabled",
        )
        self.boton_corregir.grid(row=0, column=1, padx=(0, 8))

        self.check_backup = ttk.Checkbutton(
            acciones,
            text="Hacer copia de seguridad antes de cambiar",
            variable=self.backup_var,
        )
        self.check_backup.grid(row=0, column=2, sticky="w", padx=8)

        ttk.Button(acciones, text="Ayuda", command=self.mostrar_ayuda).grid(row=0, column=3, sticky="e")

        # --- Progreso ---------------------------------------------------
        fila += 1
        self.progreso = ttk.Progressbar(
            self, style="Progreso.Horizontal.TProgressbar", mode="determinate"
        )
        self.progreso.grid(row=fila, column=0, sticky="ew", pady=(0, 8))
        self.progreso.grid_remove()

        # --- Resultados -------------------------------------------------
        fila += 1
        resultados = ttk.LabelFrame(self, text=" Resultado ", style="Paso.TLabelframe")
        resultados.grid(row=fila, column=0, sticky="nsew", pady=(0, 6))
        resultados.columnconfigure(0, weight=1)
        resultados.rowconfigure(0, weight=1)
        self.rowconfigure(fila, weight=1)

        self.salida = tk.Text(
            resultados,
            height=12,
            wrap="word",
            relief="flat",
            background="#fbfbfb",
            padx=10,
            pady=8,
            font=tkfont.nametofont("TkFixedFont"),
        )
        self.salida.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(8, 10))
        barra = ttk.Scrollbar(resultados, orient="vertical", command=self.salida.yview)
        barra.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=(8, 10))
        self.salida.configure(yscrollcommand=barra.set, state="disabled")

        # --- Estado -----------------------------------------------------
        fila += 1
        self.estado = ttk.Label(self, text="Empieza eligiendo el archivo de la base de datos.", style="Pista.TLabel")
        self.estado.grid(row=fila, column=0, sticky="w")

    def _trazas(self) -> None:
        for variable in (self.db_var, self.desde_var, self.hasta_var, self.total_var, self.unidades_var, self.utc_var):
            variable.trace_add("write", self._invalidar)

    def _invalidar(self, *_args: object) -> None:
        if self._trabajando:
            return
        if self._registros is not None:
            self._registros = None
            self._filas = []
        self.boton_corregir.configure(state="disabled")

    # ------------------------------------------------------------------
    # Utilidades de interfaz
    # ------------------------------------------------------------------
    def _escribir(self, texto: str, limpiar: bool = False) -> None:
        self.salida.configure(state="normal")
        if limpiar:
            self.salida.delete("1.0", "end")
        self.salida.insert("end", texto + "\n")
        self.salida.see("end")
        self.salida.configure(state="disabled")

    def _estado(self, texto: str, estilo: str = "Pista.TLabel") -> None:
        self.estado.configure(text=texto, style=estilo)

    def _unidad(self) -> str:
        return UNIDADES.get(self.unidades_var.get(), "in")

    def _db(self) -> Path | None:
        texto = self.db_var.get().strip().strip('"')
        if not texto:
            return None
        return Path(texto).expanduser()

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _unidades_cambiadas(self, _evento: object = None) -> None:
        self._unidades_tocadas = True

    def elegir_db(self) -> None:
        inicial = self._db()
        ruta = filedialog.askopenfilename(
            parent=self.raiz,
            title="Elige la base de datos de WeeWX",
            initialdir=str(inicial.parent) if inicial and inicial.parent.is_dir() else None,
            filetypes=[
                ("Bases de datos de WeeWX", "*.sdb *.db *.sqlite *.sqlite3"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not ruta:
            return
        self.db_var.set(ruta)
        self._al_elegir_db()

    def _al_salir_de_db(self, _evento: object = None) -> None:
        if self._trabajando:
            return
        db = self._db()
        if db is not None and db.is_file():
            self._al_elegir_db()

    def _al_elegir_db(self) -> None:
        db = self._db()
        if db is None or not db.is_file():
            self.aviso_unidades.configure(text="", style="Pista.TLabel")
            return

        deteccion = core.detectar_unidades(db)
        if deteccion is None:
            self.unidades_var.set(UNIDADES_INVERSO["in"])
            self.aviso_unidades.configure(
                text=(
                    "No se ha encontrado weewx.conf para saber las unidades. Se asume "
                    "pulgadas (instalación típica en EE. UU.). Si tu WeeWX usa el sistema "
                    "métrico, elige «Milímetros (METRIC)»."
                ),
                style="Aviso.TLabel",
            )
        else:
            unidad, config = deteccion
            if not self._unidades_tocadas:
                self.unidades_var.set(UNIDADES_INVERSO[unidad])
            self.aviso_unidades.configure(
                text=(
                    f"Detectado en {config}: los datos están en "
                    f"{core.NOMBRES_UNIDAD[unidad]}. Puedes cambiarlo si lo sabes seguro."
                ),
                style="Ok.TLabel",
            )

        try:
            ultimo = core.ultimo_registro(db, "archive")
        except core.ErrorApp as exc:
            self._estado(str(exc), "Error.TLabel")
            return
        if ultimo is not None and not self.desde_var.get().strip() and not self.hasta_var.get().strip():
            self.hasta_var.set(_texto_fecha(ultimo))
            self.desde_var.set(_texto_fecha(ultimo - dt.timedelta(days=7)))
            self._estado(
                "Fechas rellenadas con los últimos 7 días de datos. Ajústalas si lo necesitas.",
                "Pista.TLabel",
            )
        else:
            self._estado("Base de datos lista. Revisa el periodo y pulsa «Comprobar».", "Ok.TLabel")

    def atajo_fechas(self, dias: int, mes_natural: bool) -> None:
        db = self._db()
        if db is None or not db.is_file():
            messagebox.showwarning(
                "Falta la base de datos",
                "Primero elige el archivo de la base de datos de WeeWX.",
                parent=self.raiz,
            )
            return
        try:
            ultimo = core.ultimo_registro(db, "archive")
        except core.ErrorApp as exc:
            messagebox.showerror("No se pudo leer la base de datos", str(exc), parent=self.raiz)
            return
        if ultimo is None:
            messagebox.showwarning(
                "Base de datos vacía",
                "La tabla archive no tiene ningún registro.",
                parent=self.raiz,
            )
            return

        if mes_natural:
            inicio = ultimo.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            inicio = ultimo - dt.timedelta(days=dias)
        self.desde_var.set(_texto_fecha(inicio))
        self.hasta_var.set(_texto_fecha(ultimo))

    def _leer_formulario(self) -> tuple[Path, dt.datetime, dt.datetime, float]:
        db = self._db()
        if db is None:
            raise core.ErrorApp("elige primero el archivo de la base de datos.")
        db = core.comprobar_db(db)

        if not self.desde_var.get().strip() or not self.hasta_var.get().strip():
            raise core.ErrorApp("escribe la fecha de inicio y la de fin del periodo.")

        desde = core.parsear_fecha_flexible(self.desde_var.get(), fin=False)
        hasta = core.parsear_fecha_flexible(self.hasta_var.get(), fin=True)
        if hasta < desde:
            raise core.ErrorApp("la fecha de inicio no puede ser posterior a la de fin.")

        texto_total = self.total_var.get().strip()
        if not texto_total:
            raise core.ErrorApp("escribe el nuevo total de lluvia, en milímetros.")
        nuevo_mm = core.parsear_numero(texto_total)

        return db, desde, hasta, nuevo_mm

    def comprobar(self) -> None:
        if self._trabajando:
            return
        try:
            db, desde, hasta, nuevo_mm = self._leer_formulario()
            registros = core.leer_registros(
                db,
                "archive",
                core.a_epoch(desde, self.utc_var.get()),
                core.a_epoch(hasta, self.utc_var.get()),
            )
            if not registros:
                raise core.ErrorApp(
                    "no hay ningún registro con lluvia en ese periodo.\n\n"
                    "Este programa no puede inventar lluvia donde no la había: elige un "
                    "periodo en el que ya existan datos de precipitación."
                )
            _, total_mm, factor, filas = core.calcular_cambio(
                registros, nuevo_mm, self._unidad()
            )
        except core.ErrorApp as exc:
            self._registros = None
            self.boton_corregir.configure(state="disabled")
            self._estado(str(exc).splitlines()[0], "Error.TLabel")
            messagebox.showerror("Revisa los datos", str(exc), parent=self.raiz)
            return

        self._registros = registros
        self._filas = filas
        self._resumen = {
            "db": db,
            "desde": desde,
            "hasta": hasta,
            "nuevo_mm": nuevo_mm,
            "total_mm": total_mm,
            "factor": factor,
        }

        zona = "UTC" if self.utc_var.get() else "hora local"
        self._escribir("", limpiar=True)
        self._escribir(f"Base de datos : {db}")
        self._escribir(f"Unidades      : {core.NOMBRES_UNIDAD[self._unidad()]}")
        self._escribir(
            f"Periodo       : {desde:{FORMATO_FECHA}} → {hasta:{FORMATO_FECHA}} ({zona})"
        )
        self._escribir(f"Registros     : {_numero(len(registros), 0)}")
        self._escribir(f"Acumulado     : {_numero(total_mm)} mm")
        self._escribir(
            f"Nuevo total   : {_numero(nuevo_mm)} mm  ({_numero(factor * 100)} % del original)"
        )
        self._escribir(f"Factor        : {_numero(factor, 6)}")
        self._escribir("")
        self._escribir("Todo listo para corregir. Pulsa «Corregir la base de datos».")
        self.etiqueta_actual.configure(
            text=(
                f"Ahora mismo hay {_numero(total_mm)} mm en ese periodo. "
                f"Se multiplicará todo por {_numero(factor, 6)}."
            ),
            style="Ok.TLabel",
        )
        self._estado("Comprobación hecha sin modificar nada. Puedes aplicar el cambio.", "Ok.TLabel")
        self.boton_corregir.configure(state="normal")

    def corregir(self) -> None:
        if self._trabajando or self._registros is None:
            return
        resumen = self._resumen
        db = resumen["db"]
        desde = resumen["desde"]
        hasta = resumen["hasta"]
        total_mm = resumen["total_mm"]
        nuevo_mm = resumen["nuevo_mm"]
        factor = resumen["factor"]
        assert isinstance(db, Path)

        detalle = (
            f"Se van a modificar {_numero(len(self._registros), 0)} registros.\n\n"
            f"Periodo: {desde:{FORMATO_FECHA}} → {hasta:{FORMATO_FECHA}}\n"
            f"Acumulado actual: {_numero(total_mm)} mm\n"
            f"Nuevo acumulado:  {_numero(nuevo_mm)} mm\n"
            f"Factor: ×{_numero(factor, 6)}\n\n"
            "Esta operación cambia la base de datos. ¿Quieres continuar?"
        )
        if not messagebox.askyesno("Confirmar la corrección", detalle, parent=self.raiz, default="no"):
            return

        if not self.backup_var.get():
            if not messagebox.askyesno(
                "Sin copia de seguridad",
                "Has desactivado la copia de seguridad. Si algo sale mal no habrá "
                "marcha atrás.\n\n¿Seguro que quieres continuar?",
                parent=self.raiz,
                default="no",
            ):
                return

        self._trabajando = True
        self._bloquear(True)
        self.progreso.configure(maximum=len(self._filas), value=0)
        self.progreso.grid()
        self._estado("Guardando copia de seguridad y aplicando cambios…", "Pista.TLabel")

        hilo = threading.Thread(
            target=self._trabajo_corregir,
            args=(db, list(self._filas), self.backup_var.get()),
            daemon=True,
        )
        hilo.start()
        self.after(60, self._procesar_cola)

    def _trabajo_corregir(self, db: Path, filas: list[core.Cambio], backup: bool) -> None:
        try:
            destino = None
            if backup:
                destino = core.copia_seguridad(db)
            cambios = core.aplicar(
                db,
                "archive",
                filas,
                lambda hecho, total: self._cola.put(("progreso", hecho, total)),
            )
            self._cola.put(("fin", cambios, destino, len(filas)))
        except core.ErrorApp as exc:
            self._cola.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001 - se muestra al usuario
            self._cola.put(("error", f"Error inesperado: {exc}\n\n{traceback.format_exc()}"))

    def _procesar_cola(self) -> None:
        try:
            while True:
                mensaje = self._cola.get_nowait()
                tipo = mensaje[0]
                if tipo == "progreso":
                    _, hecho, total = mensaje
                    self.progreso.configure(maximum=total, value=hecho)
                elif tipo == "fin":
                    _, cambios, destino, esperados = mensaje
                    self._fin_correcto(cambios, destino, esperados)
                elif tipo == "error":
                    self._fin_error(mensaje[1])
        except queue.Empty:
            pass

        if self._trabajando:
            self.after(60, self._procesar_cola)

    def _fin_correcto(self, cambios: int, destino: Path | None, esperados: int) -> None:
        self._trabajando = False
        self._registros = None
        self._filas = []
        self._bloquear(False)
        self.progreso.grid_remove()
        self.boton_corregir.configure(state="disabled")

        self._escribir("")
        if destino is not None:
            self._escribir(f"Copia de seguridad: {destino}")
        self._escribir(f"Registros actualizados: {_numero(cambios, 0)}")
        if cambios != esperados:
            self._escribir(
                "Aviso: se esperaban "
                f"{_numero(esperados, 0)} registros. ¿Estaba WeeWX escribiendo en la base de datos?"
            )
        self._escribir("")
        self._escribir("Falta un último paso para que las gráficas cuadren:")
        self._escribir("  weectl database rebuild-daily      (WeeWX 5.0 o superior)")
        self._escribir("  wee_database --rebuild-daily       (WeeWX anterior a 5.0)")
        self._escribir("")
        self._escribir("Comprueba las gráficas antes de dar el cambio por definitivo.")

        self._estado("Cambios aplicados. Reconstruye los resúmenes diarios de WeeWX.", "Ok.TLabel")
        messagebox.showinfo(
            "Corrección terminada",
            f"Se han actualizado {_numero(cambios, 0)} registros.\n\n"
            + (f"Copia de seguridad:\n{destino}\n\n" if destino else "")
            + "Último paso, en una terminal de WeeWX:\n"
            "   weectl database rebuild-daily\n\n"
            "Así los resúmenes diarios y las gráficas mostrarán el nuevo total.",
            parent=self.raiz,
        )

    def _fin_error(self, texto: str) -> None:
        self._trabajando = False
        self._bloquear(False)
        self.progreso.grid_remove()
        self._estado("No se pudo completar la corrección.", "Error.TLabel")
        self._escribir("")
        self._escribir("ERROR: " + texto)
        messagebox.showerror("No se pudo completar", texto, parent=self.raiz)

    def _bloquear(self, bloquear: bool) -> None:
        for widget in self._descendientes(self):
            if widget is self.boton_corregir:
                continue
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="disabled" if bloquear else "readonly")
            elif isinstance(widget, (ttk.Entry, ttk.Button, ttk.Checkbutton)):
                widget.configure(state="disabled" if bloquear else "normal")
        if bloquear:
            self.boton_corregir.configure(state="disabled")
        else:
            self.boton_corregir.configure(
                state="normal" if self._registros is not None else "disabled"
            )
        self.raiz.configure(cursor="watch" if bloquear else "")

    def _descendientes(self, contenedor: tk.Misc) -> list[tk.Widget]:
        hijos: list[tk.Widget] = []
        for hijo in contenedor.winfo_children():
            hijos.append(hijo)
            hijos.extend(self._descendientes(hijo))
        return hijos

    def cerrar(self) -> None:
        if self._trabajando:
            if not messagebox.askyesno(
                "Hay una corrección en marcha",
                "Se están escribiendo cambios en la base de datos. Si cierras ahora "
                "puede quedar a medias.\n\n¿Quieres cerrar de todas formas?",
                parent=self.raiz,
                default="no",
            ):
                return
        self.raiz.destroy()

    def mostrar_ayuda(self) -> None:
        ayuda = tk.Toplevel(self.raiz)
        ayuda.title("Cómo usar el corrector")
        ayuda.transient(self.raiz)
        ayuda.geometry(
            f"740x780+{max(self.raiz.winfo_rootx() + 80, 0)}+{max(self.raiz.winfo_rooty() + 20, 0)}"
        )
        ayuda.minsize(600, 500)

        marco = ttk.Frame(ayuda)
        marco.pack(fill="both", expand=True)
        marco.columnconfigure(0, weight=1)
        marco.rowconfigure(0, weight=1)

        texto = tk.Text(
            marco,
            wrap="word",
            padx=16,
            pady=14,
            relief="flat",
            background="#fbfbfb",
            font=tkfont.nametofont("TkDefaultFont"),
        )
        texto.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(marco, orient="vertical", command=texto.yview)
        barra.grid(row=0, column=1, sticky="ns")
        texto.configure(yscrollcommand=barra.set)
        guia = f"""Cómo usar el corrector de lluvia

1. Elige el archivo de la base de datos de WeeWX (normalmente weewx.sdb).
   El programa intenta averiguar solo si los datos están en pulgadas o en
   milímetros leyendo weewx.conf.

2. Elige el periodo. Puedes escribir las fechas o usar los botones
   «Últimos 7 días», «Últimos 30 días»…

3. Escribe el nuevo total de lluvia del periodo, en milímetros.

4. Pulsa «Comprobar». No cambia nada: solo enseña cuánta lluvia hay ahora,
   el porcentaje y el factor que se aplicaría.

5. Si todo cuadra, pulsa «Corregir la base de datos» y confirma.

Qué hace: multiplica por el mismo factor todos los valores de lluvia del
periodo. Así se conserva la forma del temporal (y los rainRate) y solo
cambia la cantidad total.

Importante:
· Antes de corregir, para WeeWX o evita que escriba en la base de datos.
· El programa guarda una copia .bak junto a la base de datos. Aun así,
  haz también tu propia copia.
· Después hay que reconstruir los resúmenes diarios, o las gráficas
  seguirán mostrando los totales antiguos:
      weectl database rebuild-daily
      wee_database --rebuild-daily   (WeeWX anterior a 5.0)

Limitaciones:
· No puede añadir lluvia en un periodo en el que no llovió.
· No se puede poner el total a 0. Usa 0,0001 mm si quieres anular un
  registro falso: no afecta al acumulado y se puede recuperar después.

Esta herramienta modifica tu base de datos. Úsala con una copia a mano.
"""
        texto.insert("1.0", guia)
        texto.configure(state="disabled")
        ttk.Button(ayuda, text="Cerrar", command=ayuda.destroy).pack(pady=(0, 12))


def _activar_dpi_windows() -> None:
    """Evita que la ventana se vea borrosa en pantallas de Windows con escala."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _ruta_icono() -> Path | None:
    """Localiza el icono tanto en el código fuente como empaquetado."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidatos = [
        base / "rainfix" / "assets" / "icono.png",
        base / "assets" / "icono.png",
        Path(__file__).resolve().parent / "rainfix" / "assets" / "icono.png",
    ]
    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    return None


def main() -> int:
    _activar_dpi_windows()
    raiz = tk.Tk()
    raiz.title(TITULO)
    raiz.minsize(840, 700)

    ancho, alto = 940, 860
    pantalla_ancho = raiz.winfo_screenwidth()
    pantalla_alto = raiz.winfo_screenheight()
    ancho = min(ancho, pantalla_ancho - 40)
    alto = min(alto, pantalla_alto - 80)
    x = max((pantalla_ancho - ancho) // 2, 0)
    y = max((pantalla_alto - alto) // 3, 0)
    raiz.geometry(f"{ancho}x{alto}+{x}+{y}")

    icono = _ruta_icono()
    if icono is not None:
        try:
            imagen = tk.PhotoImage(file=str(icono))
            raiz.iconphoto(True, imagen)
            raiz._icono = imagen  # type: ignore[attr-defined]
        except tk.TclError:
            pass

    ventana = Ventana(raiz)
    raiz.protocol("WM_DELETE_WINDOW", ventana.cerrar)
    raiz.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
