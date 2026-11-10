# GEM2 Engine Files Validator

Offline validator and auto-repair tool for **Call to Arms - Gates of Hell** (GEM2 engine) mods. Validates SDL-based files (`.mdl`, `.def`, `.ext`, `.inc`, `.set`) to prevent CTDs and syncs corrected files to your game mod directory.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Linux-lightgrey)](https://linux.org)

---

## Table of Contents

- [About](#about)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Repository Structure](#repository-structure)
- [What It Validates](#what-it-validates)
- [Reverse Engineering Methodology](#reverse-engineering-methodology)
- [Legal Disclaimer](#legal-disclaimer)
- [License](#license)

---

## About

The **GEM2 Engine Files Validator** is a Python-based offline tool created for modders of *Call to Arms - Gates of Hell* (GEM2 engine). It parses, validates, and auto-repairs the SDL-formatted data files that define vehicles, weapons, armor, rosters, and other gameplay entities — catching syntax errors, malformed includes, and structural issues before they cause **CTDs (Crash To Desktop)** in-game.

It was developed alongside the **Iron Nest** mod (a self-propelled four-legged artillery unit) and uses insights from reverse-engineering the game binaries and comparing against base-game reference files.

## Features

- **Validate** `.mdl`, `.def`, `.ext`, `.inc`, and `.set` files without launching the game
- **Auto-repair** common issues: missing leading slashes in includes, unbalanced braces/parentheses, LF→CRLF conversion, invalid SDL block names
- **Detect** blocks that don't belong in a file type (e.g. `{Obstacle}` inside `.mdl`)
- **Sync** validated files from your working directory to the installed Steam/Proton mod folder
- **Exit codes**: `0` = OK, `1` = repairable errors, `2` = fatal errors

## Installation

```bash
git clone https://github.com/Mauricio5494/GEM2Engine_files_validator.git
cd GEM2Engine_files_validator
```

No external Python dependencies are required — it runs on Python 3.8+ with the standard library only.

## Usage

Validate only (report, no modifications):

```bash
python3 salida_mod/tools/gem2_validator.py salida_mod/ -v
```

Validate + auto-repairable fixes:

```bash
python3 salida_mod/tools/gem2_validator.py salida_mod/ --fix -v
```

Validate + auto-repair + sync to installed game mod directory:

```bash
python3 salida_mod/tools/gem2_validator.py salida_mod/ --fix --sync -v
```

Only sync (no validation):

```bash
python3 salida_mod/tools/gem2_validator.py salida_mod/ --sync -v
```

> **Note:** After editing files in your working directory, always run the validator with `--sync` before testing in-game. The game reads from the installed mod directory, not your source folder.

## Repository Structure

```
GEM2Engine_files_validator/
├── LICENSE
├── README.md
├── tools/
│   ├── gem2_validator.py   # Main offline GEM2 validator (auto-repair + sync)
│   ├── mod_validator.py    # First-generation validator
│   └── pre_re_scan.py      # Static pre-scan scanner (early issue detection)
├── blender/                # Blender pipeline scripts (4-part export)
│   ├── run_full_export.py
│   └── ...
├── reverse_engineering/ref/  # Base-game reference files for format comparison
└── salida_mod/             # Example mod output (Iron Nest)
    ├── mod.info
    └── resource/
```

## What It Validates

| File Type | Checks | Auto-Repairs |
|-----------|--------|--------------|
| `.mdl` | Balanced braces, `{Volume}` blocks outside `{Skeleton}`, invalid block names, final brace depth | Removes loose `{Volume}` blocks |
| `.def` | Balanced braces, include leading slash, `{game_entity}`, `{Extension "model.mdl"}` | Adds slash to includes |
| `.ext` | Balanced braces/parens, include paths, `{icon}` removal, `brain_vehicle` args | Adds slashes, removes stray `{icon}`, adds parens |
| `.inc` | `;SDL` header, CRLF line endings, container syntax | Converts LF→CRLF, adds `;SDL` header |
| `.set` (roster) | `iron_nest` entry format, invalid `period(conquest)` | — |
| `PATHER.SET` | Starts with `{Pathers` | — |

## Reverse Engineering Methodology

This tool was built by applying general reverse-engineering concepts to the GEM2 engine and the *Call to Arms - Gates of Hell* executable:

- **Static analysis** of file signatures and SDL structure by comparing mod files against base-game reference files (`tiger2h.mdl`, `tiger2h.def`, `tiger2h.ext`, `abm.inc`)
- **Binary analysis** using disassemblers and debuggers (Ghidra, IDA Free, radare2, x64dbg) to identify engine classes that load `.ext`, `.inc`, `.ply`, `.mdl` files
- **Error pattern mapping** from `game.log` (e.g. `eSDLReader.cpp`, `eResource.cpp`, `eIORepository.cpp`, `eSceneApi.cpp`) back to specific SDL syntax issues
- **Runtime observation** of how the engine reads mod data in memory

> For niche games there is no exact public documentation on reversing a specific binary. This project applies general reversing techniques rather than relying on game-specific guides.

## Legal Disclaimer

- This repository contains **only original code, scripts, and documentation** created by the author. It does **not** include copyrighted game assets from *Call to Arms - Gates of Hell` (textures, sounds, original models, etc.).
- Reverse engineering may be restricted by the game's EULA or Terms of Service. Please review those before using this tool.
- This software is provided "AS IS", without warranty of any kind. The author is not liable for any damage caused by modding your game installation.

## License

MIT License. See [LICENSE](LICENSE) for details.

---

*Built for the Call to Arms / Gates of Hell modding community.*