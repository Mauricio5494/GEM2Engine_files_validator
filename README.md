# GEM2 Engine Files Validator

Validador offline y herramienta de auto-reparación para mods de **Call to Arms - Gates of Hell** (motor GEM2). Valida archivos basados en SDL (`.mdl`, `.def`, `.ext`, `.inc`, `.set`) para prevenir CTDs y sincroniza los archivos corregidos con el directorio de mods del juego.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Linux-lightgrey)](https://linux.org)

---

## Índice

- [Acerca del proyecto](#acerca-del-proyecto)
- [Características](#características)
- [Instalación](#instalación)
- [Uso sin terminal (doble clic](#uso-sin-terminal-doble-clic)
- [Uso](#uso)
- [Interfaz gráfica (GUI)](#interfaz-gráfica-gui)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Qué valida](#qué-valida)
- [Metodología de ingeniería inversa](#metodología-de-ingeniería-inversa)
- [Aviso legal](#aviso-legal)
- [Licencia](#licencia)

---

## Acerca del proyecto

El **GEM2 Engine Files Validator** es una herramienta offline en Python creada para modders de *Call to Arms - Gates of Hell* (motor GEM2). Analiza, valida y auto-repara los archivos con formato SDL que definen vehículos, armas, armaduras, plantillas y otras entidades del juego — detectando errores de sintaxis, includes mal formados y problemas estructurales antes de que provoquen **CTDs (Crash To Desktop)** en el juego.

Fue desarrollado para modders de *Call to Arms - Gates of Hell* y utiliza conocimientos obtenidos de la ingeniería inversa de los binarios del juego y la comparación con archivos de referencia del juego base.

## Características

- **Validar** archivos `.mdl`, `.def`, `.ext`, `.inc` y `.set` sin lanzar el juego
- **Auto-reparar** problemas comunes: barras iniciales faltantes en includes, llaves/paréntesis desbalanceados, conversión LF→CRLF, nombres de bloque SDL inválidos
- **Detectar** bloques que no pertenecen a un tipo de archivo (por ejemplo, `{Obstacle}` dentro de un `.mdl`)
- **Sincronizar** archivos validados desde el directorio de trabajo a la carpeta `mods/iron_nest/` del juego instalado (Steam/Proton)
- **Códigos de salida**: `0` = OK, `1` = errores reparables, `2` = errores fatales

## Instalación

```bash
git clone https://github.com/Mauricio5494/GEM2Engine_files_validator.git
cd GEM2Engine_files_validator
```

No se requieren dependencias externas de Python. La aplicación usa solo la biblioteca estándar (**tkinter**, incluida con Python 3.8+ en la mayoría de instalaciones).

### Dependencias del sistema

| Sistema | Requisito |
|---------|-----------|
| **Windows** | Python 3.8+ instalado desde [python.org](https://python.org). Durante la instalación, marca la casilla **"tcl/tk and IDLE"**. |
| **Linux** | Python 3.8+ y el paquete `python3-tk` (en Debian/Ubuntu: `sudo apt install python3-tk`). |
| **macOS** | **No soportado** (por decisión del autor). |

## Uso sin terminal (doble clic)

No necesitas abrir una terminal para usar la interfaz gráfica.

### Windows

Haz doble clic en **`run_gui.bat`**. Inicia la aplicación con `pythonw.exe` (sin ventana de consola).

### Linux

1. Dale permiso de ejecución:

   ```bash
   chmod +x run_gui.sh
   ```

2. Haz doble clic en **`run_gui.sh`** en tu gestor de archivos, o ejecuta:

   ```bash
   ./run_gui.sh
   ```

3. Opcionalmente, copia **`GEM2Validator.desktop`** a `~/.local/share/applications/` para añadirlo al menú de aplicaciones de tu entorno de escritorio.

## Uso

Validar solo (reporte, sin modificaciones):

```bash
python3 gui/main.py
```

O directamente los scripts de consola:

```bash
python3 tools/gem2_validator.py salida_mod/ -v
python3 tools/gem2_validator.py salida_mod/ --fix -v
python3 tools/gem2_validator.py salida_mod/ --fix --sync -v
python3 tools/gem2_validator.py salida_mod/ --sync -v
```

> **Nota:** Después de editar archivos en tu directorio de trabajo, siempre ejecuta el validador con `--sync` antes de probar en el juego. El juego lee desde el directorio de mods instalado, no desde tu carpeta de origen.

## Interfaz gráfica (GUI)

Una aplicación de escritorio basada en Tkinter está incluida en `gui/`. No requiere dependencias externas — solo Python 3.8+ con tkinter.

### Lanzar la GUI (sin necesidad de terminal)

| Plataforma | Archivo | Cómo ejecutar |
|------------|---------|---------------|
| **Windows** | `run_gui.bat` | Doble clic (usa `pythonw.exe`, sin ventana de consola) |
| **Linux** | `run_gui.sh` | Doble clic o `./run_gui.sh` (da permiso con `chmod +x`) |
| **Cualquiera** | `gui/main.py` | `python3 gui/main.py` (alternativa) |

### Qué hace la GUI

| Pestaña | Propósito |
|---------|-----------|
| **Validar y Reparar** | Ejecuta `gem2_validator.py` con opciones `--fix`, `--sync` y `-v` mediante botones. Muestra salida en tiempo real con colores por severidad. |
| **Sincronizar con Juego** | Copia archivos validados desde tu directorio de trabajo a la carpeta instalada de tu mod en el juego (`mods/<tu_mod>/`). |
| **Visor de game.log** | Abre y lee el `game.log` de Proton con líneas de error resaltadas (`«`, `EXCEPTION_ACCESS_VIOLATION`, `File not found`, etc.). |
| **Pre-RE Scan** | Ejecuta el escáner estático preliminar (`pre_re_scan.py`) para detectar problemas temprano antes del validador principal. |
| **Rebuild MDL** | Ejecuta `rebuild_mdl.py` para redistribuir bloques `{VolumeView}` por hueso y corregir transformaciones `Matrix34` después de exportar desde Blender. |

Antes de usar cualquier pestaña, haz clic en **Examinar…** para seleccionar tu directorio de salida y, para sincronizar, tu carpeta instalada de mods en el juego.

### Crear ejecutables independientes (para releases)

Para distribuir la aplicación como un solo `.exe` (Windows) o binario (Linux) sin que el usuario necesite instalar Python, usa **PyInstaller**:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name GEM2Validator gui/main.py
```

Esto produce un ejecutable independiente en `dist/`. Las releases se pueden compilar para Windows y Linux. **macOS no es compatible.**

---

## Estructura del repositorio

```
GEM2Engine_files_validator/
├── LICENSE
├── README.md
├── .gitignore
├── run_gui.bat          # Lanzador para Windows (doble clic, sin terminal)
├── run_gui.sh           # Lanzador para Linux (doble clic, sin terminal)
├── GEM2Validator.desktop # Entrada de menú para entornos de escritorio Linux
├── gui/
│   ├── __init__.py
│   └── main.py          # Aplicación de escritorio Tkinter (sin dependencias externas)
└── tools/                # Scripts Python de propósito general (no específicos del modelo)
    ├── gem2_validator.py   # Validador principal offline GEM2 (auto-reparar + sincronizar)
    ├── mod_validator.py    # Primera versión del validador
    ├── pre_re_scan.py      # Escáner estático preliminar (detección temprana)
    └── rebuild_mdl.py      # Reorganizador de .mdl para después de exportar de Blender
└── reverse_engineering/ref/  # Archivos de referencia del juego base para comparación de formatos
```

## Qué valida

| Tipo de archivo | Qué revisa | Auto-repara |
|-----------------|------------|-------------|
| `.mdl` | Llaves balanceadas, bloques `{Volume}` fuera de `{Skeleton}`, nombres de bloque inválidos, profundidad final de llaves | Elimina bloques `{Volume}` sueltos |
| `.def` | Llaves balanceadas, barra inicial en includes, `{game_entity}`, `{Extension "modelo.mdl"}` | Añade barra a includes |
| `.ext` | Llaves/paréntesis balanceados, rutas de includes, eliminación de `{icon}`, argumentos de `brain_vehicle` | Añade barras, elimina `{icon}` suelto, añade paréntesis |
| `.inc` | Cabecera `;SDL`, finales de línea CRLF, sintaxis del contenedor | Convierte LF→CRLF, añade cabecera `;SDL` |
| `.set` (plantilla) | Formato de entrada de unidad, `period(conquest)` inválido | — |
| `PATHER.SET` | Empieza con `{Pathers` | — |

## Metodología de ingeniería inversa

Esta herramienta fue construida aplicando conceptos generales de ingeniería inversa al motor GEM2 y al ejecutable de *Call to Arms - Gates of Hell*:

- **Análisis estático** de firmas de archivos y estructura SDL comparando archivos de mod con archivos de referencia del juego base (`tiger2h.mdl`, `tiger2h.def`, `tiger2h.ext`, `abm.inc`)
- **Análisis binario** usando desensambladores y depuradores (Ghidra, IDA Free, radare2, x64dbg) para identificar clases del motor que cargan archivos `.ext`, `.inc`, `.ply`, `.mdl`
- **Mapeo de patrones de error** desde `game.log` (por ejemplo, `eSDLReader.cpp`, `eResource.cpp`, `eIORepository.cpp`, `eSceneApi.cpp`) hasta problemas específicos de sintaxis SDL
- **Observación en tiempo real** de cómo el motor lee los datos del mod en memoria

> Para juegos de nicho no existe documentación pública exacta sobre cómo hacer ingeniería inversa de un binario específico. Este proyecto aplica técnicas generales de ingeniería inversa en lugar de depender de guías específicas del juego.

## Aviso legal

- Este repositorio contiene **únicamente código, scripts y documentación originales** creados por el autor. No incluye assets con copyright del juego *Call to Arms - Gates of Hell* (texturas, sonidos, modelos originales, etc.).
- La ingeniería inversa puede estar restringida por el EULA o Términos de Servicio del juego. Revísalos antes de usar esta herramienta.
- Este software se proporciona "TAL CUAL", sin garantía de ningún tipo. El autor no es responsable de ningún daño causado por modificar tu instalación del juego.

## Licencia

Licencia MIT. Consulta [LICENSE](LICENSE) para más detalles.

---

*Creado para la comunidad de modding de Call to Arms / Gates of Hell.*