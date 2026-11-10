@echo off
cd /d "%~dp0"
pythonw.exe gui/main.py
if errorlevel 1 (
    echo.
    echo No se encontro Python o tkinter no esta instalado.
    echo Instala Python desde https://python.org y asegurate de marcar
    echo "tcl/tk and IDLE" durante la instalacion.
    pause