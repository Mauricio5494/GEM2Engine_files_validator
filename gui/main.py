#!/usr/bin/env python3
"""
GEM2 Engine Validator - Graphical User Interface (GUI)
=======================================================

Desktop application to validate, auto-repair, and sync mod files for the
GEM2 engine (Call to Arms - Gates of Hell) without using the terminal.

Depends only on the Python standard library (tkinter).
"""

import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import sys
import os

# UI colors
COLOR_BG = "#f5f5f5"
COLOR_PANEL = "#ffffff"
COLOR_HEADER = "#2c3e50"
COLOR_ACENT = "#3498db"
COLOR_OK = "#2ecc71"
COLOR_ERROR = "#e74c3c"
COLOR_WARN = "#f39c12"
COLOR_TEXT = "#333333"
COLOR_BORDER = "#cccccc"

# Default paths (empty: user selects them with "Browse…")
DEFAULT_MOD_DIR = ""
DEFAULT_INSTALLED_DIR = ""

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tools"


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
        # ── Title ──
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

        # ── Directory selector ──
        dir_frame = ttk.Frame(self.root)
        dir_frame.pack(fill=tk.X, padx=20, pady=(10, 5))

        ttk.Label(dir_frame, text="Mod directory (salida_mod/):").pack(side=tk.LEFT)
        self.mod_entry = ttk.Entry(dir_frame, textvariable=self.mod_dir_var, width=60)
        self.mod_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="Browse…", command=self._browse_mod_dir).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Label(
            dir_frame,
            text="Select your salida_mod/ folder",
            style="Subtitle.TLabel",
        ).pack(side=tk.LEFT, padx=(10, 0))

        # ── Notebook ──
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 0))

        self.tab_validate = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.tab_sync = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.tab_log = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.tab_prere = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.tab_rebuild = ttk.Frame(self.notebook, style="Panel.TFrame")

        self.notebook.add(self.tab_validate, text="Validate and Repair")
        self.notebook.add(self.tab_sync, text="Sync with Game")
        self.notebook.add(self.tab_log, text="game.log Viewer")
        self.notebook.add(self.tab_prere, text="Pre-RE Scan")
        self.notebook.add(self.tab_rebuild, text="Rebuild MDL")

        self._build_validate_tab()
        self._build_sync_tab()
        self._build_log_tab()
        self._build_prere_tab()
        self._build_rebuild_tab()

        # ── Status bar ──
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=20, pady=(5, 15))

        self.status_var = tk.StringVar(value="Ready")
        self.exit_var = tk.StringVar(value="Exit code: —")

        ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel").pack(
            side=tk.LEFT
        )
        ttk.Label(status_frame, textvariable=self.exit_var, style="Status.TLabel").pack(
            side=tk.RIGHT
        )

    # ── Tab: Validate and Repair ──
    def _build_validate_tab(self):
        frame = ttk.Frame(self.tab_validate, style="Panel.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Options
        opts = ttk.LabelFrame(frame, text="Validation options")
        opts.pack(fill=tk.X, pady=(0, 10))

        ttk.Checkbutton(
            opts,
            text="Auto-fix repairable errors (--fix)",
            variable=self.auto_fix_var,
        ).pack(anchor=tk.W, padx=10, pady=3)
        ttk.Checkbutton(
            opts,
            text="Sync to installed game (--sync)",
            variable=self.sync_var,
        ).pack(anchor=tk.W, padx=10, pady=3)
        ttk.Checkbutton(
            opts,
            text="Verbose mode (-v)",
            variable=self.verbose_var,
        ).pack(anchor=tk.W, padx=10, pady=3)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_validate = ttk.Button(
            btn_frame,
            text="Validate",
            style="Accent.TButton",
            command=lambda: self._run_validator(fix=False, sync=False),
        )
        self.btn_validate.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_fix = ttk.Button(
            btn_frame,
            text="Validate + Repair + Sync",
            style="Success.TButton",
            command=lambda: self._run_validator(fix=True, sync=True),
        )
        self.btn_fix.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop = ttk.Button(
            btn_frame,
            text="Stop",
            style="Danger.TButton",
            command=self._stop_process,
            state=tk.DISABLED,
        )
        self.btn_stop.pack(side=tk.LEFT)

        # Progress bar
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(0, 10))

        # Output area
        out_frame = ttk.LabelFrame(frame, text="Validator output")
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

        # Color tags for output
        self.output_validate.tag_configure("ok", foreground="#4caf50")
        self.output_validate.tag_configure("error", foreground="#f44336")
        self.output_validate.tag_configure("warn", foreground="#ff9800")
        self.output_validate.tag_configure("info", foreground="#2196f3")
        self.output_validate.tag_configure("title", foreground="#9cccff", font=("Consolas", 10, "bold"))

    # ── Tab: Sync with Game ──
    def _build_sync_tab(self):
        frame = ttk.Frame(self.tab_sync, style="Panel.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        dir_frame = ttk.Frame(frame)
        dir_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(dir_frame, text="Installed directory (mods/<your_mod>/):").pack(side=tk.LEFT)
        self.installed_entry = ttk.Entry(
            dir_frame, textvariable=self.installed_dir_var, width=60
        )
        self.installed_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="Browse…", command=self._browse_installed_dir).pack(
            side=tk.LEFT, padx=(0, 5)
        )

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_sync = ttk.Button(
            btn_frame,
            text="Sync now",
            style="Accent.TButton",
            command=self._run_sync,
        )
        self.btn_sync.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop_sync = ttk.Button(
            btn_frame,
            text="Stop",
            style="Danger.TButton",
            command=self._stop_process,
            state=tk.DISABLED,
        )
        self.btn_stop_sync.pack(side=tk.LEFT)

        self.progress_sync = ttk.Progressbar(frame, mode="indeterminate")
        self.progress_sync.pack(fill=tk.X, pady=(0, 10))

        out_frame = ttk.LabelFrame(frame, text="Sync output")
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

    # ── Tab: game.log Viewer ──
    def _build_log_tab(self):
        frame = ttk.Frame(self.tab_log, style="Panel.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            btn_frame,
            text="Open game.log",
            style="Accent.TButton",
            command=self._open_game_log,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            btn_frame,
            text="Refresh",
            command=self._refresh_game_log,
        ).pack(side=tk.LEFT)

        self.only_errors_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            btn_frame,
            text="Show errors only",
            variable=self.only_errors_var,
            command=self._refresh_game_log,
        ).pack(side=tk.LEFT, padx=(15, 0))

        out_frame = ttk.LabelFrame(frame, text="game.log content")
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

    # ── Tab: Pre-RE Scan ──
    def _build_prere_tab(self):
        frame = ttk.Frame(self.tab_prere, style="Panel.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        info = ttk.Label(
            frame,
            text="Static pre-analysis scanner (file signatures, pattern scanning). "
                 "Run BEFORE the main validator to detect early issues.",
            style="Subtitle.TLabel",
            wraplength=900,
        )
        info.pack(fill=tk.X, pady=(0, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            btn_frame,
            text="Run Pre-RE Scan",
            style="Accent.TButton",
            command=lambda: self._run_script("pre_re_scan.py", [self.mod_dir_var.get(), "--verbose"]),
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop_prere = ttk.Button(
            btn_frame,
            text="Stop",
            style="Danger.TButton",
            command=self._stop_process,
            state=tk.DISABLED,
        )
        self.btn_stop_prere.pack(side=tk.LEFT)

        self.progress_prere = ttk.Progressbar(frame, mode="indeterminate")
        self.progress_prere.pack(fill=tk.X, pady=(0, 10))

        out_frame = ttk.LabelFrame(frame, text="Scanner output")
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

    # ── Tab: Rebuild MDL ──
    def _build_rebuild_tab(self):
        frame = ttk.Frame(self.tab_rebuild, style="Panel.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        info = ttk.Label(
            frame,
            text="Reorganizes the .mdl exported by the GEM2 plugin (distributes {VolumeView} "
                 "per bone, reads Matrix34 correctly). Run after Blender export.",
            style="Subtitle.TLabel",
            wraplength=900,
        )
        info.pack(fill=tk.X, pady=(0, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            btn_frame,
            text="Run rebuild_mdl.py",
            style="Accent.TButton",
            command=self._run_rebuild_mdl,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop_rebuild = ttk.Button(
            btn_frame,
            text="Stop",
            style="Danger.TButton",
            command=self._stop_process,
            state=tk.DISABLED,
        )
        self.btn_stop_rebuild.pack(side=tk.LEFT)

        self.progress_rebuild = ttk.Progressbar(frame, mode="indeterminate")
        self.progress_rebuild.pack(fill=tk.X, pady=(0, 10))

        out_frame = ttk.LabelFrame(frame, text="Rebuild MDL output")
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

    # ── Actions ──
    def _browse_mod_dir(self):
        d = filedialog.askdirectory(title="Select salida_mod/ folder")
        if d:
            self.mod_dir_var.set(d)

    def _browse_installed_dir(self):
        d = filedialog.askdirectory(title="Select installed mods/<your_mod>/ folder")
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
            self.status_var.set("Running…")
        else:
            self.progress.stop()
            self.status_var.set("Ready")

    def _append_output(self, widget: scrolledtext.ScrolledText, text: str, tag: str = None):
        widget.insert(tk.END, text, tag)
        widget.see(tk.END)
        widget.update_idletasks()

    def _clear_output(self, widget: scrolledtext.ScrolledText):
        widget.delete(1.0, tk.END)

    def _run_validator(self, fix: bool, sync: bool):
        mod_dir = self.mod_dir_var.get()
        if not Path(mod_dir).exists():
            messagebox.showerror("Error", f"Directory does not exist:\n{mod_dir}")
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
            messagebox.showerror("Error", f"Output directory does not exist:\n{mod_dir}")
            return

        self._set_running(True)
        self._clear_output(self.output_sync)

        args = ["python3", str(SCRIPTS_DIR / "gem2_validator.py"), mod_dir, "--sync"]
        threading.Thread(target=self._stream_process, args=(args, self.output_sync), daemon=True).start()

    def _run_script(self, script_name: str, extra_args=None):
        script_path = SCRIPTS_DIR / script_name
        if not script_path.exists():
            messagebox.showerror("Error", f"Script not found:\n{script_path}")
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
        mod_dir = self.mod_dir_var.get()
        raw_mdl = Path(mod_dir) / "resource" / "entity" / "-vehicle" / "iron_nest" / "iron_nest_plugin_raw.mdl"
        if not raw_mdl.exists():
            messagebox.showerror(
                "Error",
                f"Raw MDL file not found:\n{raw_mdl}\n\n"
                "Run the Blender export first.",
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
            self.root.after(0, lambda: self._append_output(output_widget, "Error: Python interpreter not found.\n", "error"))
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
            f"\n--- Process finished with exit code: {exit_code} ---\n",
            "ok" if exit_code == 0 else "error",
        ))
        self.root.after(0, lambda: self.exit_var.set(f"Exit code: {exit_code}"))
        self.root.after(0, lambda: self._set_running(False))

    def _stop_process(self):
        messagebox.showinfo(
            "Stop",
            "To stop a running process, close the application or use Ctrl+C in the terminal.\n"
            "Forced termination from the GUI is not supported in this version.",
        )

    # ── game.log ──
    def _game_log_path(self):
        """No default path: user must select their game.log manually."""
        return None

    def _open_game_log(self):
        log_path = filedialog.askopenfilename(
            title="Select game.log",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
        )
        if not log_path:
            return
        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", log_path])
            else:
                os.startfile(log_path)  # type: ignore[attr-defined]
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file:\n{e}")

    def _refresh_game_log(self):
        log_path = filedialog.askopenfilename(
            title="Select game.log",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
        )
        if not log_path:
            return

        self._clear_output(self.output_log)

        p = Path(log_path)
        if not p.exists():
            self._append_output(
                self.output_log,
                f"File not found:\n{log_path}\n",
                "error",
            )
            return

        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            self._append_output(self.output_log, f"Error reading game.log: {e}\n", "error")
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