#!/usr/bin/env python3
"""
GEM2 Engine Validator - Interfaz gráfica (GUI)
===============================================

Aplicación de escritorio para validar, auto-reparar y sincronizar archivos
de mods del motor GEM2 (Call to Arms - Gates of Hell) sin usar la terminal.

Depende solo de la biblioteca estándar de Python (tkinter).
"""

import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import sys
import os

# Colores de la interfaz
COLOR_BG = "#f5f5f5"
COLOR_PANEL = "#ffffff"
COLOR_HEADER = "#2c3e50"
COLOR_ACENT = "#3498db"
COLOR_OK = "#2ecc71"
COLOR_ERROR = "#e74c3c"
COLOR_WARN = "#f39c12"
COLOR_TEXT = "#333333"
COLOR_BORDER = "#cccccc"

# Rutas por defecto (ajustables por el usuario)
DEFAULT_MOD_DIR = str(Path.home() / "Descargas" / "Iron_Nest_CTA_mod" / "salida_mod")
DEFAULT_INSTALLED_DIR = str(
    Path.home()
    / ".var"
    / "app"
    / "com.valvesoftware.Steam"
    / ".local"
    / "Steam"
    / "steamapps"
    / "common"
    / "Call to Arms - Gates of Hell"
    / "mods"
    / "iron_nest"
)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "salida_mod" / "tools"


class Gem2ValidatorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("GEM2 Engine Validator — Call to Arms / Gates of Hell")
        self.root.geometry("1000x750")
        self.root.minsize(850, 650)
        self.root.configure(bg=COLOR_BG)

        # Variables
        self.mod_dir_var = tk.StringVar(value=DEFAULT_MOD_DIR)
        self.installed_dir_var = tk.StringVar(value=DEFAULT_INSTALLED_DIR)
        self.auto_fix_var = tk.BooleanVar(value=False)
        self.sync_var = tk.BooleanVar(value=False)
        self.verbose_var = tk.BooleanVar(value=False)
        self.running = False

        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=COLOR_BG)
        style.configure("Panel.TFrame", background=COLOR_PANEL)
        style.configure(
            "Header.TLabel",
            background=COLOR_HEADER,
            foreground="white",
            font=("Segoe UI", 11, "bold"),
            padding=10,
        )
        style.configure(
            "Title.TLabel",
            background=COLOR_BG,
            foreground=COLOR_HEADER,
            font=("Segoe UI", 16, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=COLOR_BG,
            foreground="#666666",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Accent.TButton",
            background=COLOR_ACENT,
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 6),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#2980b9"), ("disabled", "#95a5a6")],
        )
        style.configure(
            "Success.TButton",
            background=COLOR_OK,
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 6),
        )
        style.map(
            "Success.TButton",
            background=[("active", "#27ae60"), ("disabled", "#95a5a6")],
        )
        style.configure(
            "Danger.TButton",
            background=COLOR_ERROR,
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 6),
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#c0392b"), ("disabled", "#95a5a6")],
        )
        style.configure(
            "Status.TLabel",
            background=COLOR_BG,
            foreground=COLOR_TEXT,
            font=("Segoe UI", 9),
            padding=(5, 2),
        )
        style.configure(
            "Treeview",
            background=COLOR_PANEL,
            fieldbackground=COLOR_PANEL,
            foreground=COLOR_TEXT,
        )

    def _build_ui(self):
        # ── Título ──
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=20, pady=(15, 5))

        ttk.Label(
            title_frame,
            text="GEM2 Engine Validator",
            style="Title.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Label(
            title_frame,
            text="  ·  Call to Arms / Gates of Hell Modding Tool",
            style="Subtitle.TLabel",
        ).pack(side=tk.LEFT, padx=(10, 0))

        # ── Selector de directorio ──
        dir_frame = ttk.Frame(self.root)
        dir_frame.pack(fill=tk.X, padx=20, pady=(10, 5))

        ttk.Label(dir_frame, text="Directorio del mod (salida_mod/):").pack(side=tk.LEFT)
        self.mod_entry = ttk.Entry(dir_frame, textvariable=self.mod_dir_var, width=60)
        self.mod_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="Examinar…", command=self._browse_mod_dir).pack(
            side=tk.LEFT, padx=(0, 5)
        )

        # ── Pestañas ──
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 0))

        self.tab_validate = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.tab_sync = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.tab_log = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.tab_prere = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.tab_rebuild = ttk.Frame(self.notebook, style="Panel.TFrame")

        self.notebook.add(self.tab_validate, text="Validar y Reparar")
        self.notebook.add(self.tab_sync, text="Sincronizar con Juego")
        self.notebook.add(self.tab_log, text="Visor de game.log")
        self.notebook.add(self.tab_prere, text="Pre-RE Scan")
        self.notebook.add(self.tab_rebuild, text="Rebuild MDL")

        self._build_validate_tab()
        self._build_sync_tab()
        self._build_log_tab()
        self._build_prere_tab()
        self._build_rebuild_tab()

        # ── Barra de estado ──
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=20, pady=(5, 15))

        self.status_var = tk.StringVar(value="Listo")
        self.exit_var = tk.StringVar(value="Código de salida: —")

        ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel").pack(
            side=tk.LEFT
        )
        ttk.Label(status_frame, textvariable=self.exit_var, style="Status.TLabel").pack(
            side=tk.RIGHT
        )

    # ── Pestaña: Validar y Reparar ──
    def _build_validate_tab(self):
        frame = ttk.Frame(self.tab_validate, style="Panel.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Opciones
        opts = ttk.LabelFrame(frame, text="Opciones de validación")
        opts.pack(fill=tk.X, pady=(0, 10))

        ttk.Checkbutton(
            opts,
            text="Auto-reparar errores (--fix)",
            variable=self.auto_fix_var,
        ).pack(anchor=tk.W, padx=10, pady=3)
        ttk.Checkbutton(
            opts,
            text="Sincronizar con juego instalado (--sync)",
            variable=self.sync_var,
        ).pack(anchor=tk.W, padx=10, pady=3)
        ttk.Checkbutton(
            opts,
            text="Modo detallado (-v)",
            variable=self.verbose_var,
        ).pack(anchor=tk.W, padx=10, pady=3)

        # Botones
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_validate = ttk.Button(
            btn_frame,
            text="Validar",
            style="Accent.TButton",
            command=lambda: self._run_validator(fix=False, sync=False),
        )
        self.btn_validate.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_fix = ttk.Button(
            btn_frame,
            text="Validar + Reparar + Sincronizar",
            style="Success.TButton",
            command=lambda: self._run_validator(fix=True, sync=True),
        )
        self.btn_fix.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop = ttk.Button(
            btn_frame,
            text="Detener",
            style="Danger.TButton",
            command=self._stop_process,
            state=tk.DISABLED,
        )
        self.btn_stop.pack(side=tk.LEFT)

        # Barra de progreso
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(0, 10))

        # Área de salida
        out_frame = ttk.LabelFrame(frame, text="Salida del validador")
        out_frame.pack(fill=tk.BOTH, expand=True)

        self.output_validate = scrolledtext.ScrolledText(
            out_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            background="#1e1e1e",
            foreground="#d4d4d4",
            insertbackground="white",
            padx=8,
            pady=8,
        )
        self.output_validate.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tags de color para la salida
        self.output_validate.tag_configure("ok", foreground="#4caf50")
        self.output_validate.tag_configure("error", foreground="#f44336")
        self.output_validate.tag_configure("warn", foreground="#ff9800")
        self.output_validate.tag_configure("info", foreground="#2196f3")
        self.output_validate.tag_configure("title", foreground="#9cccff", font=("Consolas", 10, "bold"))

    # ── Pestaña: Sincronizar con Juego ──
    def _build_sync_tab(self):
        frame = ttk.Frame(self.tab_sync, style="Panel.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        dir_frame = ttk.Frame(frame)
        dir_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(dir_frame, text="Directorio instalado (mods/iron_nest/):").pack(side=tk.LEFT)
        self.installed_entry = ttk.Entry(
            dir_frame, textvariable=self.installed_dir_var, width=60
        )
        self.installed_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="Examinar…", command=self._browse_installed_dir).pack(
            side=tk.LEFT, padx=(0, 5)
        )

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_sync = ttk.Button(
            btn_frame,
            text="Sincronizar ahora",
            style="Accent.TButton",
            command=self._run_sync,
        )
        self.btn_sync.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop_sync = ttk.Button(
            btn_frame,
            text="Detener",
            style="Danger.TButton",
            command=self._stop_process,
            state=tk.DISABLED,
        )
        self.btn_stop_sync.pack(side=tk.LEFT)

        self.progress_sync = ttk.Progressbar(frame, mode="indeterminate")
        self.progress_sync.pack(fill=tk.X, pady=(0, 10))

        out_frame = ttk.LabelFrame(frame, text="Salida de sincronización")
        out_frame.pack(fill=tk.BOTH, expand=True)

        self.output_sync = scrolledtext.ScrolledText(
            out_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            background="#1e1e1e",
            foreground="#d4d4d4",
            insertbackground="white",
            padx=8,
            pady=8,
        )
        self.output_sync.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.output_sync.tag_configure("ok", foreground="#4caf50")
        self.output_sync.tag_configure("error", foreground="#f44336")
        self.output_sync.tag_configure("warn", foreground="#ff9800")
        self.output_sync.tag_configure("info", foreground="#2196f3")

    # ── Pestaña: Visor de game.log ──
    def _build_log_tab(self):
        frame = ttk.Frame(self.tab_log, style="Panel.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            btn_frame,
            text="Abrir game.log",
            style="Accent.TButton",
            command=self._open_game_log,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            btn_frame,
            text="Refrescar",
            command=self._refresh_game_log,
        ).pack(side=tk.LEFT)

        self.only_errors_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            btn_frame,
            text="Solo mostrar errores",
            variable=self.only_errors_var,
            command=self._refresh_game_log,
        ).pack(side=tk.LEFT, padx=(15, 0))

        out_frame = ttk.LabelFrame(frame, text="Contenido de game.log")
        out_frame.pack(fill=tk.BOTH, expand=True)

        self.output_log = scrolledtext.ScrolledText(
            out_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            background="#1e1e1e",
            foreground="#d4d4d4",
            insertbackground="white",
            padx=8,
            pady=8,
        )
        self.output_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.output_log.tag_configure("critical", foreground="#f44336", font=("Consolas", 10, "bold"))
        self.output_log.tag_configure("error", foreground="#ff5252")
        self.output_log.tag_configure("warn", foreground="#ff9800")
        self.output_log.tag_configure("info", foreground="#81c784")

        self._refresh_game_log()

    # ── Pestaña: Pre-RE Scan ──
    def _build_prere_tab(self):
        frame = ttk.Frame(self.tab_prere, style="Panel.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        info = ttk.Label(
            frame,
            text="Escáner de pre-análisis estático (file signatures, pattern scanning). "
                 "Ejecutar ANTES del validador principal para detectar problemas temprano.",
            style="Subtitle.TLabel",
            wraplength=900,
        )
        info.pack(fill=tk.X, pady=(0, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            btn_frame,
            text="Ejecutar Pre-RE Scan",
            style="Accent.TButton",
            command=lambda: self._run_script("pre_re_scan.py", [self.mod_dir_var.get(), "--verbose"]),
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop_prere = ttk.Button(
            btn_frame,
            text="Detener",
            style="Danger.TButton",
            command=self._stop_process,
            state=tk.DISABLED,
        )
        self.btn_stop_prere.pack(side=tk.LEFT)

        self.progress_prere = ttk.Progressbar(frame, mode="indeterminate")
        self.progress_prere.pack(fill=tk.X, pady=(0, 10))

        out_frame = ttk.LabelFrame(frame, text="Salida del escáner")
        out_frame.pack(fill=tk.BOTH, expand=True)

        self.output_prere = scrolledtext.ScrolledText(
            out_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            background="#1e1e1e",
            foreground="#d4d4d4",
            insertbackground="white",
            padx=8,
            pady=8,
        )
        self.output_prere.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.output_prere.tag_configure("ok", foreground="#4caf50")
        self.output_prere.tag_configure("error", foreground="#f44336")
        self.output_prere.tag_configure("warn", foreground="#ff9800")
        self.output_prere.tag_configure("info", foreground="#2196f3")

    # ── Pestaña: Rebuild MDL ──
    def _build_rebuild_tab(self):
        frame = ttk.Frame(self.tab_rebuild, style="Panel.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        info = ttk.Label(
            frame,
            text="Reorganiza el .mdl exportado por el plugin GEM2 (distribuye {VolumeView} "
                 "por hueso, lee Matrix34 correctamente). Requiere ejecutar tras la exportación de Blender.",
            style="Subtitle.TLabel",
            wraplength=900,
        )
        info.pack(fill=tk.X, pady=(0, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            btn_frame,
            text="Ejecutar rebuild_mdl.py",
            style="Accent.TButton",
            command=self._run_rebuild_mdl,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop_rebuild = ttk.Button(
            btn_frame,
            text="Detener",
            style="Danger.TButton",
            command=self._stop_process,
            state=tk.DISABLED,
        )
        self.btn_stop_rebuild.pack(side=tk.LEFT)

        self.progress_rebuild = ttk.Progressbar(frame, mode="indeterminate")
        self.progress_rebuild.pack(fill=tk.X, pady=(0, 10))

        out_frame = ttk.LabelFrame(frame, text="Salida de Rebuild MDL")
        out_frame.pack(fill=tk.BOTH, expand=True)

        self.output_rebuild = scrolledtext.ScrolledText(
            out_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            background="#1e1e1e",
            foreground="#d4d4d4",
            insertbackground="white",
            padx=8,
            pady=8,
        )
        self.output_rebuild.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.output_rebuild.tag_configure("ok", foreground="#4caf50")
        self.output_rebuild.tag_configure("error", foreground="#f44336")
        self.output_rebuild.tag_configure("warn", foreground="#ff9800")
        self.output_rebuild.tag_configure("info", foreground="#2196f3")

    # ── Acciones ──
    def _browse_mod_dir(self):
        d = filedialog.askdirectory(title="Seleccionar carpeta salida_mod/")
        if d:
            self.mod_dir_var.set(d)

    def _browse_installed_dir(self):
        d = filedialog.askdirectory(title="Seleccionar carpeta mods/iron_nest/ instalada")
        if d:
            self.installed_dir_var.set(d)

    def _set_running(self, running: bool):
        self.running = running
        state = tk.DISABLED if running else tk.NORMAL
        self.btn_validate.config(state=state)
        self.btn_fix.config(state=state)
        self.btn_sync.config(state=state)
        self.btn_stop.config(state=tk.NORMAL if running else tk.DISABLED)
        self.btn_stop_sync.config(state=tk.NORMAL if running else tk.DISABLED)
        self.btn_stop_prere.config(state=tk.NORMAL if running else tk.DISABLED)
        self.btn_stop_rebuild.config(state=tk.NORMAL if running else tk.DISABLED)

        if running:
            self.progress.start(10)
            self.status_var.set("Ejecutando…")
        else:
            self.progress.stop()
            self.status_var.set("Listo")

    def _append_output(self, widget: scrolledtext.ScrolledText, text: str, tag: str = None):
        widget.insert(tk.END, text, tag)
        widget.see(tk.END)
        widget.update_idletasks()

    def _clear_output(self, widget: scrolledtext.ScrolledText):
        widget.delete(1.0, tk.END)

    def _run_validator(self, fix: bool, sync: bool):
        mod_dir = self.mod_dir_var.get()
        if not Path(mod_dir).exists():
            messagebox.showerror("Error", f"El directorio no existe:\n{mod_dir}")
            return

        self._set_running(True)
        self._clear_output(self.output_validate)

        args = ["python3", str(SCRIPTS_DIR / "gem2_validator.py"), mod_dir]
        if fix:
            args.append("--fix")
        if sync:
            args.append("--sync")
        if self.verbose_var.get():
            args.append("-v")

        threading.Thread(target=self._stream_process, args=(args, self.output_validate), daemon=True).start()

    def _run_sync(self):
        mod_dir = self.mod_dir_var.get()
        installed = self.installed_dir_var.get()
        if not Path(mod_dir).exists():
            messagebox.showerror("Error", f"El directorio de salida no existe:\n{mod_dir}")
            return

        self._set_running(True)
        self._clear_output(self.output_sync)

        # Sincronización simple: copiar archivos validados
        args = ["python3", str(SCRIPTS_DIR / "gem2_validator.py"), mod_dir, "--sync"]
        threading.Thread(target=self._stream_process, args=(args, self.output_sync), daemon=True).start()

    def _run_script(self, script_name: str, extra_args=None):
        script_path = SCRIPTS_DIR / script_name
        if not script_path.exists():
            messagebox.showerror("Error", f"No se encontró el script:\n{script_path}")
            return

        self._set_running(True)

        output_widget = {
            "pre_re_scan.py": self.output_prere,
            "rebuild_mdl.py": self.output_rebuild,
        }.get(script_name)

        if output_widget:
            self._clear_output(output_widget)

        args = ["python3", str(script_path)]
        if extra_args:
            args.extend(extra_args)

        threading.Thread(target=self._stream_process, args=(args, output_widget), daemon=True).start()

    def _run_rebuild_mdl(self):
        # rebuild_mdl.py no acepta argumentos de ruta; asume cwd del proyecto
        mod_dir = self.mod_dir_var.get()
        raw_mdl = Path(mod_dir) / "resource" / "entity" / "-vehicle" / "iron_nest" / "iron_nest_plugin_raw.mdl"
        if not raw_mdl.exists():
            messagebox.showerror(
                "Error",
                f"No se encontró el archivo raw del MDL:\n{raw_mdl}\n\n"
                "Ejecutá primero la exportación de Blender.",
            )
            return

        self._run_script("rebuild_mdl.py")

    def _stream_process(self, args, output_widget: scrolledtext.ScrolledText):
        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            self.root.after(0, lambda: self._append_output(output_widget, "Error: no se encontró el intérprete Python.\n", "error"))
            self.root.after(0, lambda: self._set_running(False))
            return

        for line in proc.stdout:
            tag = None
            lower = line.lower()
            if any(k in lower for k in ["error", "ctd", "exception", "fatal", "unexpected token"]):
                tag = "error"
            elif any(k in lower for k in ["warning", "advertencia", "fixable"]):
                tag = "warn"
            elif any(k in lower for k in ["ok", "validado", "sincronizado", "pasó", "exit code: 0"]):
                tag = "ok"
            elif any(k in lower for k in ["check", "validating", "processing", "reviewing"]):
                tag = "info"

            self.root.after(0, lambda l=line, t=tag: self._append_output(output_widget, l, t))

        proc.wait()
        exit_code = proc.returncode

        self.root.after(0, lambda: self._append_output(
            output_widget,
            f"\n--- Proceso finalizado con código de salida: {exit_code} ---\n",
            "ok" if exit_code == 0 else "error",
        ))
        self.root.after(0, lambda: self.exit_var.set(f"Código de salida: {exit_code}"))
        self.root.after(0, lambda: self._set_running(False))

    def _stop_process(self):
        # Nota: detener procesos subprocess desde tkinter es complejo;
        # aquí solo se detiene la UI y se informa al usuario.
        messagebox.showinfo(
            "Detener",
            "Para detener un proceso en ejecución, cerrá la aplicación o usá Ctrl+C en la terminal.\n"
            "La detención forzada desde la GUI no está soportada en esta versión.",
        )

    # ── game.log ──
    def _game_log_path(self) -> Path:
        return Path(
            str(Path.home())
            / ".var"
            / "app"
            / "com.valvesoftware.Steam"
            / ".local"
            / "Steam"
            / "steamapps"
            / "compatdata"
            / "400750"
            / "pfx"
            / "drive_c"
            / "users"
            / "steamuser"
            / "Documents"
            / "my games"
            / "gates of hell"
            / "log"
            / "game.log"
        )

    def _open_game_log(self):
        log_path = self._game_log_path()
        if log_path.exists():
            try:
                if sys.platform.startswith("linux"):
                    subprocess.Popen(["xdg-open", str(log_path)])
                else:
                    os.startfile(str(log_path))  # type: ignore[attr-defined]
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el archivo:\n{e}")
        else:
            messagebox.showwarning(
                "No encontrado",
                f"No se encontró el game.log en:\n{log_path}\n\n"
                "Verificá que el juego esté instalado vía Steam Flatpak.",
            )

    def _refresh_game_log(self):
        log_path = self._game_log_path()
        self._clear_output(self.output_log)

        if not log_path.exists():
            self._append_output(
                self.output_log,
                f"game.log no encontrado en:\n{log_path}\n",
                "error",
            )
            return

        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            self._append_output(self.output_log, f"Error leyendo game.log: {e}\n", "error")
            return

        only_errors = self.only_errors_var.get()
        for line in lines:
            if only_errors and not any(
                k in line.lower() for k in ["error", "ctd", "exception", "fatal", "«", "unexpected token", "file not found"]
            ):
                continue

            tag = None
            lower = line.lower()
            if "«" in lower or "exception_access_violation" in lower or "fatal" in lower:
                tag = "critical"
            elif "error" in lower or "unexpected token" in lower or "file not found" in lower:
                tag = "error"
            elif "warning" in lower or "advertencia" in lower:
                tag = "warn"
            elif "info" in lower or "log" in lower:
                tag = "info"

            self._append_output(self.output_log, line, tag)


def main():
    root = tk.Tk()
    app = Gem2ValidatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()