#!/usr/bin/env bash
# Lanzador para Linux (doble clic en gestor de archivos o ./run_gui.sh)
cd "$(dirname "$0")"
exec python3 gui/main.py