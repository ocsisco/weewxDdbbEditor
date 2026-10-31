# weewxDdbbEditor

Corrige el acumulado de precipitación de una base de datos de [WeeWX](https://weewx.com/) (SQLite) dentro de un
rango de fechas.

Es útil para arreglar falsos valores provocados por tareas de mantenimiento y para ajustar desviaciones de
pluviómetros automáticos. En vez de reescribir registro a registro, aplica un factor de corrección proporcional
al periodo elegido, de modo que se conservan los `rainRate` y la forma original de la lluvia.

> ⚠️ **MUY IMPORTANTE**
>
> El autor de esta aplicación **no se hace responsable** de los daños causados sobre las bases de datos
> modificadas ni del mal funcionamiento derivado de su uso.
>
> **Haga siempre una copia de seguridad de la base de datos antes de utilizarla.** El programa crea una
> automáticamente, pero conviene disponer además de una copia propia. Después, pruebe la base de datos modificada
> y verifique que todo se muestra correctamente antes de dar los cambios por definitivos.

---

## Características

- Corrige la precipitación de un periodo completo aplicando un factor proporcional.
- **Interfaz gráfica** con botones, pensada para quien no programa: no hace falta terminal.
- Ejecutables de un solo archivo para Windows (.exe) y Linux, sin instalar Python.
- Copia de seguridad automática antes de escribir en la base de datos.
- Modo simulación para ver el resultado sin modificar nada.
- Modo interactivo y modo no interactivo (apto para scripts).
- Sin dependencias externas: funciona con Python 3.8 o superior en Windows, Linux y macOS.

## Para quien no programa

No hace falta instalar nada ni escribir órdenes en una terminal:

1. Descarga el ejecutable de la pestaña **Releases** del repositorio. Si aún no
   hay ninguna, entra en **Actions → Compilar ejecutables → última ejecución** y
   baja el archivo de *Artifacts*.
   - **Windows:** `CorrectorLluviaWeeWX.exe`. Si Windows muestra un aviso de
     SmartScreen, pulsa «Más información» y luego «Ejecutar de todas formas».
   - **Linux:** `CorrectorLluviaWeeWX-linux.tar.gz`. Descomprímelo, permite la
     ejecución del archivo (clic derecho → Propiedades → permitir ejecutar, o
     `chmod +x CorrectorLluviaWeeWX`) y ábrelo.
2. Abre el programa y sigue los tres pasos de la ventana: elegir la base de
   datos, marcar el periodo y escribir el nuevo total.

La ventana hace todo lo demás: avisa si algo no cuadra, guarda una copia de
seguridad y recuerda el último paso (reconstruir los resúmenes diarios).

## Interfaz gráfica

```bash
python gui.py
```

![Ventana del corrector](docs/ventana.png)

La ventana se usa de arriba abajo, sin escribir órdenes:

1. **Elige la base de datos.** El programa lee `weewx.conf` y deduce solo si los
   datos están en pulgadas o en milímetros. Si no lo encuentra, se puede elegir
   a mano en la lista.
2. **Indica el periodo.** Se puede escribir la fecha o usar los botones
   «Últimas 24 horas», «Últimos 7 días», «Últimos 30 días» y «Último mes
   natural». Las fechas se entienden en hora local salvo que se marque la casilla
   de UTC.
3. **Escribe el nuevo total** del periodo, en milímetros.
4. **Comprobar** enseña cuánta lluvia hay ahora, el porcentaje y el factor. No
   modifica nada.
5. **Corregir la base de datos** pide confirmación, crea la copia `.bak` y aplica
   el cambio.

El botón «Ayuda» de la propia ventana resume estos pasos y las advertencias.

## Instalación desde el código

```bash
git clone https://github.com/ocsisco/weewxDdbbEditor.git
cd weewxDdbbEditor
python main.py --help        # versión de terminal
python gui.py                # versión con ventana
```

Opcionalmente se puede instalar como comando del sistema, de forma que puedan
invocarse `weewx-rain-fix` (terminal) y `weewx-rain-fix-gui` (ventana) desde
cualquier directorio:

```bash
pip install -e .
weewx-rain-fix --version
weewx-rain-fix-gui
```

## Uso rápido

```bash
# 1. Ver qué haría, sin modificar nada
weewx-rain-fix --db /var/lib/weewx/weewx.sdb \
               --desde "2021-01-01 12:00:00" \
               --hasta "2021-01-31 12:00:00" \
               --nuevo-total 12.4 --dry-run

# 2. Aplicar el cambio (crea la copia de seguridad y muestra el resultado)
weewx-rain-fix --db /var/lib/weewx/weewx.sdb \
               --desde "2021-01-01 12:00:00" \
               --hasta "2021-01-31 12:00:00" \
               --nuevo-total 12.4 --yes
```

Salida típica:

```
weewxDdbbEditor 2.0.0
  Base de datos  : /var/lib/weewx/weewx.sdb
  Tabla          : archive  (rain en pulgadas)
  Periodo        : 2021-01-01 12:00:00 → 2021-01-31 12:00:00 (hora local)
  Registros      : 1.234
  Acumulado      : 12.40 mm
  Nuevo total    : 15.00 mm  (120.97 % del original)
  Factor         : 1.209677

  Copia de seguridad: /var/lib/weewx/weewx.sdb.20261031-120000.bak
Aplicando cambios...

1.234 registros actualizados en weewx.sdb.
```

## Uso interactivo en la terminal

Si se ejecuta el programa de terminal sin argumentos, va solicitando los datos paso a paso. Para el público general
es más cómoda la ventana (`python gui.py`), pero este modo sigue disponible:

```bash
python main.py
```

1. Ruta del archivo de la base de datos (relativa o absoluta).
2. Fecha de inicio y fecha de fin.
3. Se muestra el acumulado del periodo; se escribe el nuevo valor en milímetros (Intro para no cambiar nada).
4. Se muestra el porcentaje respecto al original; se confirma con `s` para aplicar el cambio.

Las fechas se escriben como `AAAA/MM/DD-HH/MM/SS`, pero el separador es libre: `2021-01-01 12:00:20`,
`2021 01 01 12 00 20` y `2021-01-01-12-00-20` son equivalentes.

## Opciones

| Opción | Descripción |
| --- | --- |
| `--db RUTA` | Base de datos SQLite de WeeWX. |
| `--desde FECHA` | Inicio del periodo (incluido). |
| `--hasta FECHA` | Fin del periodo (incluido). |
| `--nuevo-total MM` | Nuevo acumulado del periodo, **en milímetros**. |
| `--unidades-db {in,mm}` | Unidades en que la base de datos guarda `rain` y `rainRate`. Por defecto `in`. |
| `--tabla NOMBRE` | Tabla a modificar. Por defecto `archive`. |
| `--utc` | Interpretar las fechas como UTC en vez de hora local. |
| `--dry-run` | Mostrar el resumen y salir sin escribir. |
| `--sin-backup` | No crear la copia de seguridad (no recomendado). |
| `-y`, `--yes` | No pedir confirmación (necesario en scripts). |
| `--version` | Mostrar la versión. |

El programa devuelve el código de salida `0` si todo va bien, `1` si hay un error o se cancela y `130` si se
interrumpe con `Ctrl+C`.

## Cómo funciona

Lee los registros de la tabla `archive` cuya `rain` es mayor que cero dentro del periodo (extremos incluidos),
suma el acumulado y calcula un factor:

```
factor = nuevo_total / total_original
```

Ese factor se aplica a la vez a `rain` y a `rainRate` de cada registro, en una única transacción. Así la
distribución de la lluvia se mantiene intacta y solo cambia su magnitud. Un periodo de un año (unas 50 000
filas) tarda décimas de segundo.

## Copia de seguridad

Antes de escribir, se crea un archivo `<nombre_bd>.<AAAAMMDD-HHMMSS>.bak` junto a la base de datos, usando la
API de backup de SQLite, que es consistente incluso si WeeWX está escribiendo en ella. Para restaurarla:

```bash
cp weewx.sdb.20261031-120000.bak weewx.sdb
```

## Unidades

WeeWX guarda en la base de datos las unidades indicadas en `[StdConvert] target_unit` de `weewx.conf`:

- `target_unit = US` (valor por defecto) → `rain` y `rainRate` están en **pulgadas**: es el valor por defecto
  `--unidades-db in`.
- `target_unit = METRIC` o `METRICWX` → están en **milímetros**: hay que usar `--unidades-db mm`.

El programa siempre muestra el acumulado y solicita el nuevo valor **en milímetros**, independientemente de las
unidades almacenadas en la base de datos.

## Antes y después de usarlo

- Detener WeeWX o, al menos, evitar que escriba en la base de datos durante la modificación.
- Reconstruir los resúmenes diarios, ya que el programa solo corrige la tabla `archive`; los totales de
  `archive_day_rain` y las gráficas que salen de ellos conservarán los valores antiguos:

  ```bash
  weectl database rebuild-daily     # WeeWX 5.0 o superior
  wee_database --rebuild-daily      # WeeWX anterior a 5.0
  ```

## Limitaciones

Al respetar la proporcionalidad se conservan los `rainRate` y los registros originales, lo que implica:

- **No se puede añadir precipitación en un rango donde no la haya**, porque habría que inventar el reparto
  horario de la lluvia y su `rainRate`. El programa avisa y no realiza ningún cambio.
- **No se puede poner el acumulado a `0`** para borrar un registro (por ejemplo, un falso registro por
  movimiento del pluviómetro durante el mantenimiento), ya que el factor sería nulo. En su lugar se usa una cifra
  muy pequeña, como `0.0001`, que no afecta al acumulado y además deja constancia del cambio y permite recuperar
  el dato original volviendo a introducir el valor correcto del periodo.

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
