# GEM2 Engine Files Validator

Offline validator and auto-repair tool for mods of **Call to Arms - Gates of Hell** (GEM2 engine). Validates SDL-based files (`.mdl`, `.def`, `.ext`, `.inc`, `.set`) to prevent CTDs and syncs corrected files to your game mod directory.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Linux-lightgrey)](https://linux.org)

---

## Table of Contents

- [About](#about)
- [Features](#features)
- [Installation](#installation)
- [Running without a terminal (double-click)](#running-without-a-terminal-double-click)
- [Usage](#usage)
- [Graphical User Interface (GUI)](#graphical-user-interface-gui)
- [Repository Structure](#repository-structure)
- [What It Validates](#what-it-validates)
- [Reverse Engineering Methodology](#reverse-engineering-methodology)
- [Legal Disclaimer](#legal-disclaimer)
- [License](#license)

---

## About

The **GEM2 Engine Files Validator** is a Python-based offline tool created for modders of *Call to Arms - Gates of Hell* (GEM2 engine). It parses, validates, and auto-repairs the SDL-formatted data files that define vehicles, weapons, armor, rosters, and other gameplay entities — catching syntax errors, malformed includes, and structural issues before they cause **CTDs (Crash To Desktop)** in-game.

It was developed using insights from reverse-engineering the game binaries and comparing against base-game reference files.

## Features

- **Validate** `.mdl`, `.def`, `.ext`, `.inc`, and `.set` files without launching the game
- **Auto-repair** common issues: missing leading slashes in includes, unbalanced braces/parentheses, LF→CRLF conversion, invalid SDL block names
- **Detect** blocks that don't belong in a file type (e.g. `{Obstacle}` inside `.mdl`)
- **Sync** validated files from your working directory to your mod's installed folder in the game (`mods/<your_mod>/`)
- **Exit codes**: `0` = OK, `1` = repairable errors, `2` = fatal errors

## Installation

```bash
git clone https://github.com/Mauricio5494/GEM2Engine_files_validator.git
cd GEM2Engine_files_validator
```

No external Python dependencies are required — it runs on Python 3.8+ with the standard library only (**tkinter** is included with Python 3.8+ on most installations).

### System Dependencies

| Platform | Requirement |
|----------|-------------|
| **Windows** | Python 3.8+ installed from [python.org](https://python.org). During installation, check the box **"tcl/tk and IDLE"**. |
| **Linux** | Python 3.8+ and the `python3-tk` package (on Debian/Ubuntu: `sudo apt install python3-tk`). |
| **macOS** | **Not supported** (by author's decision). |

## Running without a terminal (double-click)

You do **not** need to open a terminal to use the GUI.

### Windows

Double-click **`run_gui.bat`**. It launches the app with `pythonw.exe` (no console window).

### Linux

1. Make the launcher executable:

   ```bash
   chmod +x run_gui.sh
   ```

2. Double-click **`run_gui.sh`** in your file manager, or run:

   ```bash
   ./run_gui.sh
   ```

3. Optionally, copy **`GEM2Validator.desktop`** to `~/.local/share/applications/` to add it to your desktop environment's application menu.

## Usage

Validate only (report, no modifications):

```bash
python3 gui/main.py
```

Or directly run the console scripts:

```bash
python3 tools/gem2_validator.py salida_mod/ -v
python3 tools/gem2_validator.py salida_mod/ --fix -v
python3 tools/gem2_validator.py salida_mod/ --fix --sync -v
python3 tools/gem2_validator.py salida_mod/ --sync -v
```

> **Note:** After editing files in your working directory, always run the validator with `--sync` before testing in-game. The game reads from the installed mod directory, not your source folder.

## Graphical User Interface (GUI)

A Tkinter-based desktop application is included under `gui/`. It requires no external dependencies — just Python 3.8+ with tkinter.

### Launching the GUI (no terminal needed)

| Platform | File | How to run |
|----------|------|------------|
| **Windows** | `run_gui.bat` | Double-click (uses `pythonw.exe`, no console window) |
| **Linux** | `run_gui.sh` | Double-click or `./run_gui.sh` (make executable with `chmod +x`) |
| **Any** | `gui/main.py` | `python3 gui/main.py` (fallback) |

### What the GUI does

| Tab | Purpose |
|-----|---------|
| **Validate and Repair** | Run `gem2_validator.py` with `--fix`, `--sync`, and `-v` options via buttons. See real-time output with color-coded severity. |
| **Sync with Game** | Copy validated files from your working directory to your mod's installed folder in the game (`mods/<your_mod>/`). |
| **game.log Viewer** | Open and read the Proton `game.log` with highlighted error lines (`«`, `EXCEPTION_ACCESS_VIOLATION`, `File not found`, etc.). |
| **Pre-RE Scan** | Run the static pre-scan scanner (`pre_re_scan.py`) for early issue detection before the main validator. |
| **Rebuild MDL** | Run `rebuild_mdl.py` to redistribute `{VolumeView}` blocks per bone and fix `Matrix34` transforms after Blender export. |

Before using any tab, click **Browse** to select your output directory and, for sync, your installed mods folder in the game.

### Creating standalone executables (for releases)

To distribute the app as a single `.exe` (Windows) or binary (Linux) without requiring users to install Python, use **PyInstaller**:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name GEM2Validator gui/main.py
```

This produces a standalone executable in `dist/`. Releases can be built for Windows and Linux. **macOS is not supported.**

---

## Repository Structure

```
GEM2Engine_files_validator/
├── LICENSE
├── README.md
├── .gitignore
├── run_gui.bat          # Launcher for Windows (double-click, no terminal)
├── run_gui.sh           # Launcher for Linux (double-click, no terminal)
├── GEM2Validator.desktop # Desktop menu entry for Linux desktop environments
├── gui/
│   ├── __init__.py
│   └── main.py          # Tkinter desktop application (no external deps)
└── tools/                # General-purpose Python scripts (not model-specific)
    ├── gem2_validator.py   # Main offline GEM2 validator (auto-repair + sync)
    ├── mod_validator.py    # First-generation validator
    ├── pre_re_scan.py      # Static pre-scan scanner (early detection)
    └── rebuild_mdl.py      # MDL reorganizer for post-Blender export
└── reverse_engineering/ref/  # Base-game reference files for format comparison
```

## What It Validates

| File Type | What It Checks | Auto-Repairs |
|-----------|---------------|--------------|
| `.mdl` | Balanced braces, `{Volume}` blocks outside `{Skeleton}`, invalid block names, final brace depth | Removes loose `{Volume}` blocks |
| `.def` | Balanced braces, leading slash in includes, `{game_entity}`, `{Extension "model.mdl"}` | Adds slash to includes |
| `.ext` | Balanced braces/parens, include paths, `{icon}` removal, `brain_vehicle` args | Adds slashes, removes stray `{icon}`, adds parens |
| `.inc` | `;SDL` header, CRLF line endings, container syntax | Converts LF→CRLF, adds `;SDL` header |
| `.set` (roster) | Unit entry format, invalid `period(conquest)` | — |
| `PATHER.SET` | Starts with `{Pathers` | — |

## Reverse Engineering Methodology

This tool was built by applying general reverse-engineering concepts to the GEM2 engine and the *Call to Arms - Gates of Hell* executable:

- **Static analysis** of file signatures and SDL structure by comparing mod files against base-game reference files (`tiger2h.mdl`, `tiger2h.def`, `tiger2h.ext`, `abm.inc`)
- **Binary analysis** using disassemblers and debuggers (Ghidra, IDA Free, radare2, x64dbg) to identify engine classes that load `.ext`, `.inc`, `.ply`, `.mdl` files
- **Error pattern mapping** from `game.log` (e.g. `eSDLReader.cpp`, `eResource.cpp`, `eIORepository.cpp`, `eSceneApi.cpp`) back to specific SDL syntax issues
- **Runtime observation** of how the engine reads mod data in memory

> For niche games there is no exact public documentation on reversing a specific binary. This project applies general reversing techniques rather than relying on game-specific guides.

## Legal Disclaimer

- This repository contains **only original code, scripts, and documentation** created by the author. It does **not** include copyrighted game assets from *Call to Arms - Gates of Hell* (textures, sounds, original models, etc.).
- Reverse engineering may be restricted by the game's EULA or Terms of Service. Please review those before using this tool.
- This software is provided "AS IS", without warranty of any kind. The author is not liable for any damage caused by modding your game installation.

## License

MIT License. See [LICENSE](LICENSE) for details.

---

*Built for the Call to Arms / Gates of Hell modding community.*