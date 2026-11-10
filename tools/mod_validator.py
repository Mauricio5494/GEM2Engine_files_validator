#!/usr/bin/env python3
"""
Iron Nest Mod Validator - Herramienta CLI para uso interno del agente.

Valida y auto-repara archivos críticos del mod Iron Nest (GEM2 / Call to Arms)
antes de instalarlos en el juego. Diseñada para evitar ciclos lentos de
CTD → revisar game.log → fix → reinstalar.

Uso (orientado al agente):
    python3 mod_validator.py <ruta>                 # Validar solo (reporte)
    python3 mod_validator.py <ruta> --fix           # Validar + auto-reparar
    python3 mod_validator.py <ruta> --sync          # Sincronizar salida_mod -> mod instalado
    python3 mod_validator.py <ruta> --fix --sync    # Fixear y sincronizar

Códigos de salida: 0 = OK, 1 = errores (sin --fix), 2 = errores no reparables
"""

import sys
import os
import shutil
import argparse
import re
from pathlib import Path

# Colores para salida en terminal
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def color(text, c):
    return f"{c}{text}{RESET}"


class ValidationResult:
    def __init__(self):
        self.errors = []      # (file, line, message, fixable)
        self.fixes = []       # (file, action, detail)
        self.checked = 0

    def add_error(self, file, line, message, fixable=False):
        self.errors.append((file, line, message, fixable))

    def add_fix(self, file, action, detail):
        self.fixes.append((file, action, detail))

    def summary(self):
        return {
            "checked": self.checked,
            "errors": len(self.errors),
            "fixes": len(self.fixes),
            "fixable_errors": sum(1 for _, _, _, f in self.errors if f),
            "unfixable_errors": sum(1 for _, _, _, f in self.errors if not f),
        }


class Validator:
    def __init__(self, auto_fix=False, sync=False, verbose=False):
        self.auto_fix = auto_fix
        self.sync = sync
        self.verbose = verbose
        self.result = ValidationResult()

    def log(self, msg):
        if self.verbose:
            print(color(f"  [check] {msg}", BLUE))

    def fix(self, file, action, detail, apply_fn):
        if self.auto_fix:
            self.log(f"  [fix] {action}: {detail}")
            apply_fn()
            self.result.add_fix(file, action, detail)
        else:
            self.result.add_error(file, 0, detail, fixable=True)

    # ------------------------------------------------------------------
    # Validador de .ext
    # ------------------------------------------------------------------
    def validate_ext(self, path):
        self.log(f"Validando .ext: {path}")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines = content.split("\n")

        # Paréntesis balanceados
        open_p = content.count("(")
        close_p = content.count(")")
        if open_p != close_p:
            self.result.add_error(path, 0, f"Paréntesis desbalanceados: {open_p} abiertos, {close_p} cerrados", fixable=False)

        # Llaves balanceadas
        open_b = content.count("{")
        close_b = content.count("}")
        if open_b != close_b:
            self.result.add_error(path, 0, f"Llaves desbalanceadas: {open_b} abiertas, {close_b} cerradas", fixable=False)

        # Includes con barra inicial
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("(include"):
                if '"' in stripped:
                    start = stripped.find('"') + 1
                    end = stripped.find('"', start)
                    inc_path = stripped[start:end]
                    if not inc_path.startswith("/"):
                        def _fix_ext_include(path=path, i=i, line=line, inc_path=inc_path):
                            new_line = line.replace(f'"{inc_path}"', f'"/{inc_path}"')
                            lines[i-1] = new_line
                            with open(path, 'w') as f:
                                f.write("\n".join(lines))
                        self.fix(path, "include_barra", f"Añadir barra inicial a include: {inc_path}", _fix_ext_include)

        # No debe tener {icon}, {icon_small}, {hud_icon} sueltos
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("{icon") or stripped.startswith("{icon_small") or stripped.startswith("{hud_icon"):
                block = stripped.split()[0]
                def _fix_ext_icon(path=path, i=i, block=block):
                    # Eliminar la línea completa
                    del lines[i-1]
                    with open(path, 'w') as f:
                        f.write("\n".join(lines))
                self.fix(path, "eliminar_icon", f"Eliminar '{block}' de nivel raíz en .ext", _fix_ext_icon)

        # Argumentos de brain_vehicle deben llevar paréntesis
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if "brain_vehicle" in stripped:
                fixes_needed = []
                if re.search(r'engage_range\s+\d', stripped) and not re.search(r'engage_range\s*\(', stripped):
                    fixes_needed.append(('engage_range', r'engage_range\s+(\d+)', r'engage_range(\1)'))
                if re.search(r'fire_on_move\s+\d', stripped) and not re.search(r'fire_on_move\s*\(', stripped):
                    fixes_needed.append(('fire_on_move', r'fire_on_move\s+(\d+)', r'fire_on_move(\1)'))
                if re.search(r'reverse_allowed\s+\d', stripped) and not re.search(r'reverse_allowed\s*\(', stripped):
                    fixes_needed.append(('reverse_allowed', r'reverse_allowed\s+(\d+)', r'reverse_allowed(\1)'))
                if re.search(r'prefer_front_armor\s+\d', stripped) and not re.search(r'prefer_front_armor\s*\(', stripped):
                    fixes_needed.append(('prefer_front_armor', r'prefer_front_armor\s+(\d+)', r'prefer_front_armor(\1)'))
                if re.search(r'leg_ik_enabled\s+\d', stripped) and not re.search(r'leg_ik_enabled\s*\(', stripped):
                    fixes_needed.append(('leg_ik_enabled', r'leg_ik_enabled\s+(\d+)', r'leg_ik_enabled(\1)'))
                if re.search(r'slope_limit\s+\d', stripped) and not re.search(r'slope_limit\s*\(', stripped):
                    fixes_needed.append(('slope_limit', r'slope_limit\s+(\d+)', r'slope_limit(\1)'))
                if re.search(r'walker_gait\s+"\w+"', stripped) and not re.search(r'walker_gait\s*\(', stripped):
                    fixes_needed.append(('walker_gait', r'walker_gait\s+("(\w+)")', r'walker_gait(\1)'))

                for arg_name, pattern, replacement in fixes_needed:
                    def _fix_ext_arg(path=path, i=i, line=line, pattern=pattern, replacement=replacement, arg_name=arg_name):
                        new_line = re.sub(pattern, replacement, line)
                        lines[i-1] = new_line
                        with open(path, 'w') as f:
                            f.write("\n".join(lines))
                    self.fix(path, f"parentesis_{arg_name}", f"Añadir paréntesis a {arg_name} en brain_vehicle", _fix_ext_arg)

        self.result.checked += 1

    # ------------------------------------------------------------------
    # Validador de .inc
    # ------------------------------------------------------------------
    def validate_inc(self, path):
        self.log(f"Validando .inc: {path}")
        with open(path, "rb") as f:
            raw = f.read()

        # CRLF
        crlf_count = raw.count(b"\r\n")
        lf_only = raw.count(b"\n") - crlf_count
        if lf_only > 0:
            def _fix_inc_crlf(path=path, raw=raw):
                fixed = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                with open(path, 'wb') as f:
                    f.write(fixed)
            self.fix(path, "crlf", f"Convertir {lf_only} líneas de LF a CRLF", _fix_inc_crlf)

        text = raw.decode("utf-8", errors="replace")
        first_line = text.split("\n")[0].strip() if text else ""
        if first_line != ";SDL":
            self.result.add_error(path, 1, f"Cabecera inválida: '{first_line}'. Debe ser ';SDL'", fixable=True)

        # Contenedor (define ... {brain ... })
        lines = text.split("\n")
        in_define = False
        in_brain = False
        brain_depth = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue

            if stripped.startswith("(define"):
                in_define = True
            if in_define and "{brain" in stripped:
                in_brain = True
                brain_depth = stripped.count("{")

            if "{state" in stripped and not in_brain:
                def _fix_inc_state(path=path, i=i, line=line):
                    # Mover {state} dentro de un contenedor (define...{brain})
                    # Esto es complejo de auto-fixear sin conocer el contexto completo
                    pass
                self.result.add_error(path, i, "Bloque '{state' fuera de contenedor (define...{brain}). Requiere envolver en (define \"nombre\" {brain \"tipo\" ... })", fixable=True)

            if in_brain:
                opens = stripped.count("{")
                closes = stripped.count("}")
                brain_depth += opens - closes
                if brain_depth <= 0:
                    in_brain = False

        if not in_define:
            self.result.add_error(path, 0, "Archivo .inc no tiene contenedor (define ... ). Requiere envolver en (define \"nombre\" {brain \"tipo\" ... })", fixable=True)

        self.result.checked += 1

    # ------------------------------------------------------------------
    # Validador de .mdl
    # ------------------------------------------------------------------
    def validate_mdl(self, path):
        self.log(f"Validando .mdl: {path}")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines = content.split("\n")

        open_b = content.count("{")
        close_b = content.count("}")
        if open_b != close_b:
            self.result.add_error(path, 0, f"Llaves desbalanceadas: {open_b} abiertas, {close_b} cerradas", fixable=False)

        depth = 0
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            opens = stripped.count("{")
            closes = stripped.count("}")
            if opens > closes:
                depth += 1
            if closes > opens:
                depth -= (closes - opens)
        if depth != 0:
            self.result.add_error(path, 0, f"Profundidad final no es 0 (quedan {depth} llaves sin cerrar)", fixable=False)

        # Detectar cualquier bloque {Volume ... } en el .mdl.
        # En el juego base (tiger2h.mdl) el .mdl NO tiene bloques {Volume} sueltos:
        # solo usa {VolumeView} dentro de cada {bone}. Los volúmenes físicos van
        # en el .def ({volume ...}). Cualquier {Volume} en .mdl causa
        # unexpected token (eResource.cpp:102) al cargar.
        import re as _re
        volume_blocks = []  # (start_line, end_line)

        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            # Solo bloques {Volume } (no {VolumeView que es válido dentro de los bones)
            if _re.match(r"\{Volume\b", stripped) or _re.match(r"\{Volume ", stripped):
                start = i
                depth = stripped.count("{") - stripped.count("}")
                j = i + 1
                while j < len(lines) and depth > 0:
                    s2 = lines[j].strip()
                    depth += s2.count("{") - s2.count("}")
                    j += 1
                end = j - 1  # línea donde depth vuelve a 0
                volume_blocks.append((start + 1, end + 1))  # 1-indexed
                i = j
            else:
                i += 1

        for vstart, vend in volume_blocks:
            def _fix_mdl_volume(path=path, vstart=vstart, vend=vend):
                lns = open(path, "r", encoding="utf-8", errors="replace").read().split("\n")
                # eliminar líneas vstart-1 .. vend-1 inclusive
                del lns[vstart-1:vend]
                with open(path, "w") as f:
                    f.write("\n".join(lns))
            self.fix(path, "eliminar_volume_mdl", f"Eliminar bloque {{Volume}} en líneas {vstart}-{vend} (no pertenece al .mdl, va en el .def)", _fix_mdl_volume)

        self.result.checked += 1

    # ------------------------------------------------------------------
    # Validador de .def
    # ------------------------------------------------------------------
    def validate_def(self, path):
        self.log(f"Validando .def: {path}")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("(include"):
                if '"' in stripped:
                    start = stripped.find('"') + 1
                    end = stripped.find('"', start)
                    inc_path = stripped[start:end]
                    if not inc_path.startswith("/"):
                        def _fix_def_include(path=path, i=i, line=line, inc_path=inc_path):
                            new_line = line.replace(f'"{inc_path}"', f'"/{inc_path}"')
                            lines[i-1] = new_line
                            with open(path, 'w') as f:
                                f.write("\n".join(lines))
                        self.fix(path, "include_barra", f"Añadir barra inicial a include en .def: {inc_path}", _fix_def_include)

        self.result.checked += 1

    # ------------------------------------------------------------------
    # Validador de .set (roster)
    # ------------------------------------------------------------------
    def validate_set(self, path):
        self.log(f"Validando .set: {path}")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines = content.split("\n")

        if Path(path).name.upper() == "PATHER.SET":
            first = lines[0].strip() if lines else ""
            if first != "{Pathers":
                self.result.add_error(path, 1, f"PATHER.SET debe empezar con '{{Pathers', no con '{first}'", fixable=False)
            self.result.checked += 1
            return

        for i, line in enumerate(lines, 1):
            if '"iron_nest"' in line:
                context = "\n".join(lines[i:i+10])
                if "min_stage" in context and "{cost" in context:
                    if "period(conquest)" in context:
                        self.result.add_error(path, i, "period(conquest) es inválido en conquest. Usar period(mid) o period(late)", fixable=True)
                elif "cd(" in context and "ci(" in context and "cost(" in context:
                    pass
                else:
                    self.result.add_error(path, i, "Formato de entrada iron_nest no reconocido", fixable=True)

        self.result.checked += 1

    # ------------------------------------------------------------------
    # Sincronización salida_mod -> mod instalado
    # ------------------------------------------------------------------
    def sync_to_mod(self, source_dir, mod_dir):
        """Copia archivos de salida_mod al mod instalado."""
        source = Path(source_dir)
        mod = Path(mod_dir)

        if not source.exists():
            self.result.add_error(str(source), 0, "Directorio salida_mod no encontrado", fixable=False)
            return

        if not mod.exists():
            self.result.add_error(str(mod), 0, "Directorio del mod instalado no encontrado", fixable=False)
            return

        copied = 0
        for item in source.rglob("*"):
            if item.is_file():
                rel = item.relative_to(source)
                dest = mod / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
                copied += 1
                self.log(f"  [sync] Copiado: {rel}")

        self.result.add_fix("sync", "copiar_archivos", f"{copied} archivos copiados de salida_mod a mods/iron_nest/")

    # ------------------------------------------------------------------
    # Ejecutar
    # ------------------------------------------------------------------
    def validate_file(self, path):
        path = Path(path)
        if not path.exists():
            self.result.add_error(str(path), 0, "Archivo no encontrado", fixable=False)
            return

        ext = path.suffix.lower()
        name = path.name.upper()

        if ext == ".ext":
            self.validate_ext(path)
        elif ext == ".inc":
            self.validate_inc(path)
        elif ext == ".mdl":
            self.validate_mdl(path)
        elif ext == ".def":
            self.validate_def(path)
        elif ext == ".set":
            self.validate_set(path)
        elif name == "PATHER.SET":
            self.validate_set(path)

    def validate_directory(self, dir_path):
        dir_path = Path(dir_path)
        if not dir_path.exists():
            self.result.add_error(str(dir_path), 0, "Directorio no encontrado", fixable=False)
            return

        patterns = ["*.ext", "*.inc", "*.mdl", "*.def", "*.set", "PATHER.SET"]
        for pattern in patterns:
            for f in dir_path.rglob(pattern):
                self.validate_file(f)

    def report(self):
        s = self.result.summary()
        print("\n" + "=" * 60)
        print(color("IRON NEST MOD VALIDATOR - REPORTE (agente)", BOLD + BLUE))
        print("=" * 60)
        print(f"Archivos revisados: {s['checked']}")
        print(f"Errores: {s['errors']} (reparables: {s['fixable_errors']}, no reparables: {s['unfixable_errors']})")
        print(f"Auto-fixes aplicados: {s['fixes']}")
        print("-" * 60)

        for file, line, msg, fixable in self.result.errors:
            sev = "FIXABLE" if fixable else "FATAL"
            sev_color = YELLOW if fixable else RED
            print(f"{color(sev, sev_color)} [{file}:{line}] {msg}")

        if self.result.fixes:
            print("-" * 60)
            for file, action, detail in self.result.fixes:
                print(f"{color('FIX', GREEN)} [{file}] {action}: {detail}")

        print("-" * 60)

        fatal = s['unfixable_errors']
        if fatal > 0:
            print(color(f"✗ {fatal} error(es) fatal(es) no reparable(s). Revisar manualmente.", RED))
            return False
        elif s['errors'] > 0 and not self.auto_fix:
            print(color(f"⚠ {s['errors']} error(es) reparable(s). Ejecutar con --fix para auto-reparar.", YELLOW))
            return False
        elif s['errors'] > 0 and self.auto_fix:
            print(color(f"✓ Todos los errores reparables han sido auto-fixeados.", GREEN))
            return True
        else:
            print(color("✓ Todos los archivos pasaron la validación", GREEN))
            return True


def main():
    parser = argparse.ArgumentParser(
        description="Validador CLI para el mod Iron Nest (uso interno del agente)"
    )
    parser.add_argument("path", help="Ruta al archivo o directorio a validar")
    parser.add_argument("--fix", action="store_true", help="Auto-reparar errores reparables")
    parser.add_argument("--sync", action="store_true", help="Sincronizar salida_mod -> mod instalado")
    parser.add_argument("-v", "--verbose", action="store_true", help="Mostrar detalles")
    args = parser.parse_args()

    # Ruta del mod instalado (Steam Flatpak)
    MOD_INSTALLED = Path("/home/sparky/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Call to Arms - Gates of Hell/mods/iron_nest")

    validator = Validator(auto_fix=args.fix, sync=args.sync, verbose=args.verbose)

    path = Path(args.path)
    if path.is_dir():
        validator.validate_directory(path)
        if args.sync:
            validator.sync_to_mod(path, MOD_INSTALLED)
    else:
        validator.validate_file(path)

    success = validator.report()
    sys.exit(0 if success else 2)


if __name__ == "__main__":
    main()
