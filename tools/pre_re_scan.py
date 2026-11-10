#!/usr/bin/env python3
"""
pre_re_scan.py - Escáner de pre-análisis estático para archivos del mod Iron Nest (GEM2).

Aplica conceptos de ingeniería reversa (inspirados en el análisis de call_to_arms.exe)
para escanear archivos de salida_mod/ en busca de patrones problemáticos ANTES de
ejecutar gem2_validator.py.

Conceptos de RE aplicados:
  - File signatures: detectar tipo de archivo por cabecera/contenido, no solo por extensión
  - Pattern scanning (AOB): buscar secuencias de bytes/texto problemáticas conocidas
  - Static analysis: verificar estructura sin ejecutar el motor del juego
  - Diffing: comparar contra firmas de referencia del juego base

Uso:
    python3 pre_re_scan.py <ruta_a_salida_mod> [--verbose]

Códigos de salida:
    0 = sin problemas detectados
    1 = problemas detectados (revisar reporte)
"""

import sys
import os
import re
from pathlib import Path

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def color(text, c):
    return f"{c}{text}{RESET}"


class Finding:
    """Un hallazgo de patrón problemático, similar a un 'match' en escaneo de memoria."""
    def __init__(self, file, line, pattern, message, severity="WARN", fixable=False):
        self.file = file
        self.line = line
        self.pattern = pattern      # firma/patrón detectado (como un AOB en RE)
        self.message = message
        self.severity = severity    # WARN, ERROR, FATAL
        self.fixable = fixable

    def __str__(self):
        sev_color = RED if self.severity == "FATAL" else (YELLOW if self.severity == "ERROR" else BLUE)
        return f"{color(self.severity, sev_color)} [{self.file}:{self.line}] {self.pattern} -> {self.message}"


class PreReScanner:
    """Escáner estático basado en patrones para archivos de mod GEM2."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.findings = []
        self.checked = 0

    def log(self, msg):
        if self.verbose:
            print(color(f"  [scan] {msg}", BLUE))

    # ------------------------------------------------------------------
    # Detección de tipo de archivo por firma (file signature / magic bytes)
    # ------------------------------------------------------------------
    def detect_type(self, path: Path, raw: bytes, text: str):
        """
        Devuelve el tipo detectado basado en firmas de contenido.
        Análoga a identificar un PE por su cabecera 'MZ' o un ELF por '\x7fELF'.
        """
        first_line = text.split("\n")[0].strip() if text else ""

        # .inc deben empezar con ;SDL (firma de SDL en GEM2)
        if path.suffix.lower() == ".inc" and first_line == ";SDL":
            return "inc_sdl"

        # .ext empiezan con 'actor' o contienen (include
        if path.suffix.lower() == ".ext" and (text.startswith("actor") or "(include" in text):
            return "ext"

        # .def contienen {game_entity} y {Extension
        if path.suffix.lower() == ".def" and ("{game_entity" in text or "{Extension" in text):
            return "def"

        # .mdl contienen {skeleton} o {VolumeView
        if path.suffix.lower() == ".mdl" and ("{skeleton" in text or "{VolumeView" in text):
            return "mdl"

        # .set son rosters o PATHER.SET
        if path.suffix.lower() == ".set" or path.name.upper() == "PATHER.SET":
            return "set"

        return path.suffix.lower().lstrip(".") or "desconocido"

    # ------------------------------------------------------------------
    # Reglas de patrón (firmas de problemas conocidos)
    # Cada regla es una tupla: (tipo_archivo, regex, mensaje, severidad, fixable)
    # ------------------------------------------------------------------
    PATTERN_RULES = [
        # --- .inc: SDL y CRLF ---
        ("inc", r"^[^;].*$", "Línea no comienza con ';' y no es SDL válido", "WARN", False),
        ("inc_sdl", r"\n[^\r]\n", "Posible LF sin CR (debe ser CRLF en .inc de ABM)", "ERROR", True),
        ("inc", r"\(define[^{]*\{brain", "Estructura (define ... {brain detectada", "INFO", False),

        # --- .ext: includes y brain_vehicle ---
        ("ext", r'\(include "[^/]', "Include sin barra inicial: debería ser \"/ruta\"", "ERROR", True),
        ("ext", r'brain_vehicle[^(]*$', "brain_vehicle sin paréntesis en argumentos", "WARN", True),
        ("ext", r'engage_range\s+\d+', "engage_range sin paréntesis", "WARN", True),
        ("ext", r'fire_on_move\s+\d+', "fire_on_move sin paréntesis", "WARN", True),
        ("ext", r'reverse_allowed\s+\d+', "reverse_allowed sin paréntesis", "WARN", True),
        ("ext", r'prefer_front_armor\s+\d+', "prefer_front_armor sin paréntesis", "WARN", True),
        ("ext", r'leg_ik_enabled\s+\d+', "leg_ik_enabled sin paréntesis", "WARN", True),
        ("ext", r'slope_limit\s+\d+', "slope_limit sin paréntesis", "WARN", True),
        ("ext", r'walker_gait\s+"\w+"', "walker_gait sin paréntesis", "WARN", True),
        ("ext", r"^\s*\{icon", "{icon / {icon_small / {hud_icon en nivel raíz de .ext (van en .set)", "WARN", True),

        # --- .mdl: {Volume} no pertenece al .mdl ---
        ("mdl", r"^\s*\{Volume\b", "Bloque {Volume} en .mdl (debe ir en .def como {volume })", "ERROR", True),
        ("mdl", r"^\s*\{skeleton", "Bloque {skeleton} ausente (el juego base lo usa)", "WARN", False),

        # --- .def: includes y estructura ---
        ("def", r'\(include "[^/]', "Include sin barra inicial en .def", "ERROR", True),
        ("def", r"\{game_entity", "Falta {game_entity}", "ERROR", False),
        ("def", r'\{Extension\s+"[^"]+\.mdl"', "Falta {Extension \"modelo.mdl\"}", "ERROR", False),

        # --- .set / PATHER.SET ---
        ("set", r"period\(conquest\)", "period(conquest) inválido en conquest (usar period(mid) o period(late))", "ERROR", True),
        ("set", r'"iron_nest"', "Entrada de iron_nest detectada en roster (verificar periodo y costo)", "INFO", False),
    ]

    # ------------------------------------------------------------------
    # Escaneo de un archivo
    # ------------------------------------------------------------------
    def scan_file(self, path: Path):
        self.checked += 1
        self.log(f"Escaneando: {path}")

        try:
            raw = path.read_bytes()
        except Exception as e:
            self.findings.append(Finding(str(path), 0, "LECTURA", f"No se pudo leer el archivo: {e}", "FATAL", False))
            return

        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = ""

        ftype = self.detect_type(path, raw, text)
        lines = text.split("\n")

        # Aplicar reglas de patrón (pattern scanning / AOB scanning)
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue

            for rtype, pattern, message, severity, fixable in self.PATTERN_RULES:
                if rtype != ftype and rtype != "inc_sdl":
                    continue
                if rtype == "inc_sdl" and ftype != "inc_sdl":
                    continue
                if re.search(pattern, stripped):
                    self.findings.append(Finding(
                        str(path), i, pattern, message, severity, fixable
                    ))

        # Reglas que operan sobre el contenido completo (no línea por línea)
        self._scan_whole_file(path, raw, text, ftype)

    def _scan_whole_file(self, path: Path, raw: bytes, text: str, ftype: str):
        # .inc: verificar CRLF (análogo a verificar alineación de bytes en RE)
        if ftype == "inc_sdl" or path.suffix.lower() == ".inc":
            crlf_count = raw.count(b"\r\n")
            lf_only = raw.count(b"\n") - crlf_count
            if lf_only > 0:
                self.findings.append(Finding(
                    str(path), 1, "CRLF_CHECK",
                    f"{lf_only} línea(s) con LF puro (debe ser CRLF \\r\\n en .inc de ABM)",
                    "ERROR", True
                ))

        # .mdl: verificar llaves balanceadas (análogo a verificar estructura de bloques)
        if ftype == "mdl":
            depth = 0
            for i, line in enumerate(text.split("\n"), 1):
                stripped = line.strip()
                if not stripped or stripped.startswith(";"):
                    continue
                depth += stripped.count("{") - stripped.count("}")
                if depth < 0:
                    self.findings.append(Finding(
                        str(path), i, "BRACE_BALANCE",
                        "Llave de cierre '}' sin apertura correspondiente",
                        "FATAL", False
                    ))
                    depth = 0
            if depth != 0:
                self.findings.append(Finding(
                    str(path), 0, "BRACE_BALANCE",
                    f"Llaves desbalanceadas (profundidad final={depth})",
                    "FATAL", False
                ))

        # .ext: verificar paréntesis balanceados
        if ftype == "ext":
            open_p = text.count("(")
            close_p = text.count(")")
            if open_p != close_p:
                self.findings.append(Finding(
                    str(path), 0, "PAREN_BALANCE",
                    f"Paréntesis desbalanceados: {open_p} abiertos, {close_p} cerrados",
                    "FATAL", False
                ))

    # ------------------------------------------------------------------
    # Ejecutar escaneo sobre un directorio
    # ------------------------------------------------------------------
    def scan_directory(self, dir_path: Path):
        dir_path = Path(dir_path)
        if not dir_path.exists():
            print(color(f"Directorio no encontrado: {dir_path}", RED))
            return False

        patterns = ["*.ext", "*.inc", "*.mdl", "*.def", "*.set", "PATHER.SET"]
        files = []
        for pattern in patterns:
            files.extend(sorted(dir_path.rglob(pattern)))

        if not files:
            print(color("No se encontraron archivos para escanear.", YELLOW))
            return True

        print(color(f"Escaneando {len(files)} archivo(s) en {dir_path}", BOLD + BLUE))
        print("-" * 60)

        for f in files:
            self.scan_file(f)

        return self.report()

    # ------------------------------------------------------------------
    # Reporte de hallazgos
    # ------------------------------------------------------------------
    def report(self):
        fatal = [f for f in self.findings if f.severity == "FATAL"]
        errors = [f for f in self.findings if f.severity == "ERROR"]
        warns = [f for f in self.findings if f.severity == "WARN"]
        infos = [f for f in self.findings if f.severity == "INFO"]
        fixable = [f for f in self.findings if f.fixable]

        print("\n" + "=" * 60)
        print(color("PRE-RE SCAN - REPORTE DE PATRONES (agente)", BOLD + BLUE))
        print("=" * 60)
        print(f"Archivos escaneados: {self.checked}")
        print(f"Hallazgos totales: {len(self.findings)}")
        print(f"  FATAL:   {len(fatal)}")
        print(f"  ERROR:   {len(errors)} (reparables: {sum(1 for f in errors if f.fixable)})")
        print(f"  WARN:    {len(warns)}")
        print(f"  INFO:    {len(infos)}")
        print(f"  Fixables: {len(fixable)}")
        print("-" * 60)

        # Mostrar FATAL y ERROR primero (prioridad alta, como en RE se priorizan crashes)
        for f in sorted(self.findings, key=lambda x: ({"FATAL": 0, "ERROR": 1, "WARN": 2, "INFO": 3}[x.severity], x.file, x.line)):
            fix_tag = " [FIXABLE]" if f.fixable else ""
            print(str(f) + fix_tag)

        print("-" * 60)

        if fatal:
            print(color(f"✗ {len(fatal)} error(es) FATAL. Revisar antes de continuar.", RED))
            return False
        elif errors and not any(f.fixable for f in errors):
            print(color(f"⚠ {len(errors)} error(es) no reparable(s) automáticamente.", YELLOW))
            return False
        elif self.findings:
            print(color(f"⚠ Se detectaron {len(self.findings)} patrón(es). Revisar antes de ejecutar gem2_validator.py.", YELLOW))
            return True
        else:
            print(color("✓ No se detectaron patrones problemáticos.", GREEN))
            return True


def main():
    if len(sys.argv) < 2:
        print(f"Uso: python3 {sys.argv[0]} <ruta_a_salida_mod> [--verbose]")
        sys.exit(1)

    dir_path = sys.argv[1]
    verbose = "--verbose" in sys.argv

    scanner = PreReScanner(verbose=verbose)
    success = scanner.scan_directory(Path(dir_path))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
