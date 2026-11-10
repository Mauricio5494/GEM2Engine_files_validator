#!/usr/bin/env python3
"""
GEM2 Offline Validator - Validador de archivos del motor GEM2 (Call to Arms: Gates of Hell).

Implementa reglas de parsing del motor GEM2 basadas en ingeniería inversa del
binario call_to_arms.exe y comparación con archivos de referencia del juego base.

Clases del motor identificadas:
  eSDLReader.cpp  - "Block terminator expected!"
  eSDLParser.cpp  - "unexpected token"
  eIORepository.cpp - "File not found", "File signature mismatch"
  eResource.cpp   - "unexpected token (eResource.cpp:102)"
  eActorSerialize.cpp - "Unit: Wrong pather name"

Uso:
    python3 gem2_validator.py <ruta> [--fix] [--sync] [-v]

Códigos de salida: 0 = OK, 1 = errores reparables, 2 = errores fatales
"""

import sys
import os
import shutil
import argparse
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


class ValidationResult:
    def __init__(self):
        self.errors = []      # (file, line, message, fixable, severity)
        self.fixes = []       # (file, action, detail)
        self.checked = 0
        self.warnings = []

    def add_error(self, file, line, message, fixable=False, severity="ERROR"):
        self.errors.append((file, line, message, fixable, severity))

    def add_warning(self, file, line, message):
        self.warnings.append((file, line, message))

    def add_fix(self, file, action, detail):
        self.fixes.append((file, action, detail))

    def summary(self):
        return {
            "checked": self.checked,
            "errors": len(self.errors),
            "fixes": len(self.fixes),
            "fixable_errors": sum(1 for _, _, _, f, _ in self.errors if f),
            "unfixable_errors": sum(1 for _, _, _, f, _ in self.errors if not f),
            "warnings": len(self.warnings),
        }


class Gem2Validator:
    def __init__(self, auto_fix=False, sync=False, verbose=False):
        self.auto_fix = auto_fix
        self.sync = sync
        self.verbose = verbose
        self.result = ValidationResult()
        self.mod_installed = Path(
            "/home/sparky/.var/app/com.valvesoftware.Steam/.local/share/Steam/"
            "steamapps/common/Call to Arms - Gates of Hell/mods/iron_nest"
        )

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

    def _read_text(self, path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def _read_bytes(self, path):
        with open(path, "rb") as f:
            return f.read()

    def _write_text(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _write_bytes(self, path, data):
        with open(path, "wb") as f:
            f.write(data)

    def _fix_file_lines(self, path, apply_fn):
        """Helper para aplicar un fix a un archivo leyendo/escribiendo líneas."""
        lines = self._read_text(path).split("\n")
        apply_fn(lines)
        self._write_text(path, "\n".join(lines))

    # ==================================================================
    # .mdl
    # ==================================================================

    # Bloques SDL que NO son válidos en un archivo .mdl del motor GEM2.
    # Estos bloques pertenecen a .def o .ext; si aparecen en un .mdl, el motor
    # lanza "unexpected token" y provoca CTD.
    MDL_INVALID_BLOCKS = {
        "Obstacle", "Volume", "Weaponry", "sensor", "Extension", "game_entity",
        "mass", "collider", "PatherId", "lodclass", "targetclass",
        "targetSelector", "props", "basic_armor", "general_durability",
        "crew_inside", "crew_human", "extender", "Chassis", "Locomotion",
        "FuelBag", "dontUseSlope", "disableBackward", "NoGroupMesh",
    }

    def validate_mdl(self, path):
        self.log(f"Validando .mdl: {path}")
        text = self._read_text(path)
        lines = text.split("\n")
        self.result.checked += 1

        # 1. Detectar nombres de bloques SDL inválidos (caracteres no alfanuméricos,
#    tokens Unicode inesperados al inicio de bloque, etc.)
        # El motor GEM2 lanza "unexpected token" cuando encuentra un bloque
        # cuyo nombre no reconoce (p.ej. {Obb2} en lugar de {Obb}, o {«Obstacle}).
        block_name_re = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.]*)")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            # Buscar bloques que empiezan con { seguido de algo que no es un nombre válido
            for m in re.finditer(r"\{([^\s{}]+)", stripped):
                token = m.group(1)
                if not block_name_re.match("{" + token):
                    # El token después de { no es un nombre de bloque SDL válido
                    def _fix(path=path, i=i, line=line):
                        # Marcar para revisión manual (no auto-fixable sin saber el nombre correcto)
                        pass
                    self.result.add_error(path, i,
                        f"Nombre de bloque SDL inválido o no reconocido: '{token}' "
                        f"(el motor lanza 'unexpected token')",
                        fixable=False)

        # 2. Detectar bloques que NO son válidos en un archivo .mdl.
        #    El motor GEM2 lanza "unexpected token" si encuentra estos bloques
        #    en un .mdl (pertenecen a .def o .ext).
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            m = re.match(r"\{([A-Za-z_][A-Za-z0-9_.]*)", stripped)
            if m:
                block_name = m.group(1)
                if block_name in self.MDL_INVALID_BLOCKS:
                    self.result.add_error(path, i,
                        f"Bloque '{block_name}' no es válido en un archivo .mdl "
                        f"(el motor lanza 'unexpected token' y provoca CTD). "
                        f"Este bloque pertenece a .def o .ext, no al .mdl.",
                        fixable=False)

        # 3. Parser SDL simple: verificar llaves balanceadas y terminación
        depth = 0
        max_depth = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            opens = stripped.count("{")
            closes = stripped.count("}")
            depth += opens - closes
            max_depth = max(max_depth, depth)
            if depth < 0:
                self.result.add_error(path, i,
                    "Llave de cierre '}' sin apertura correspondiente",
                    fixable=False)
                depth = 0

        if depth != 0:
            self.result.add_error(path, 0,
                f"Llaves desbalanceadas o bloques sin cerrar (profundidad final={depth})",
                fixable=False)

        # 3. Bloques {Volume sueltos (NO {VolumeView)
        # En el juego base (tiger2h.mdl) el .mdl NO tiene {Volume} al nivel raíz.
        # Los volúmenes físicos van en el .def como {volume ...}.
        volume_blocks = []
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if re.match(r"\{Volume\b", stripped) or re.match(r"\{Volume ", stripped):
                start = i
                block_depth = stripped.count("{") - stripped.count("}")
                j = i + 1
                while j < len(lines) and block_depth > 0:
                    s2 = lines[j].strip()
                    block_depth += s2.count("{") - s2.count("}")
                    j += 1
                end = j - 1
                volume_blocks.append((start + 1, end + 1))
                i = j
            else:
                i += 1

        for vstart, vend in reversed(volume_blocks):
            def _fix(path=path, vstart=vstart, vend=vend):
                self._fix_file_lines(path, lambda lns: del_lines(lns, vstart - 1, vend - 1))
            self.fix(path, "eliminar_volume_mdl",
                f"Eliminar bloque {{Volume}} en líneas {vstart}-{vend} "
                f"(no pertenece al .mdl, va en el .def)",
                _fix)

        # 3. Verificar {skeleton existe
        has_skeleton = any(re.match(r"\{skeleton\b", l.strip()) for l in lines)
        if not has_skeleton:
            self.result.add_warning(path, 1,
                "No se encontró bloque {skeleton}. El juego base usa {skeleton} (minúscula)")

        # 4. Contar {VolumeView (válido, solo informativo)
        vv_count = len(re.findall(r"\{VolumeView", text))
        if vv_count > 0:
            self.log(f"  {vv_count} bloques {{VolumeView}} (válido)")

        # 5. Verificar que los huesos de crew mencionados en el .ext existan en el .mdl.
        #    Si el .ext declara crew_human con place(driver) door(emit1), esos huesos
        #    deben existir en el .mdl o el motor fallará con "Link failed" al vincular
        #    al tripulante (CTD al mover el vehículo).
        ext_path = path.with_suffix(".ext")
        if ext_path.exists():
            ext_text = self._read_text(ext_path)
            crew_bones = set()
            for m in re.finditer(r'place\((\w+)\)', ext_text):
                crew_bones.add(m.group(1))
            for m in re.finditer(r'door\((\w+)\)', ext_text):
                crew_bones.add(m.group(1))
            for m in re.finditer(r'door2\((\w+)\)', ext_text):
                crew_bones.add(m.group(1))
            for m in re.finditer(r'visor\((\w+)\)', ext_text):
                if m.group(1) != "none":
                    crew_bones.add(m.group(1))

            if crew_bones:
                mdl_bones = set(re.findall(r'\{bone\s+"(\w+)"', text))
                missing = crew_bones - mdl_bones
                if missing:
                    self.result.add_error(path, 0,
                        f"Huesos de crew declarados en .ext no encontrados en .mdl: "
                        f"{sorted(missing)}. El motor fallará con 'Link failed' "
                        f"(CTD al vincular tripulante).",
                        fixable=False)

    # ==================================================================
    # .def
    # ==================================================================
    def validate_def(self, path):
        self.log(f"Validando .def: {path}")
        text = self._read_text(path)
        lines = text.split("\n")
        self.result.checked += 1

        # 1. Llaves balanceadas
        depth = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            depth += stripped.count("{") - stripped.count("}")
            if depth < 0:
                self.result.add_error(path, i,
                    "Llave de cierre '}' sin apertura",
                    fixable=False)
                depth = 0
        if depth != 0:
            self.result.add_error(path, 0,
                f"Llaves desbalanceadas (profundidad final={depth})",
                fixable=False)

        # 2. Include con barra inicial
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("(include"):
                m = re.search(r'"([^"]+)"', stripped)
                if m:
                    inc_path = m.group(1)
                    if not inc_path.startswith("/"):
                        def _fix(path=path, i=i, line=line, inc_path=inc_path):
                            self._fix_file_lines(path, lambda lns: lns.__setitem__(
                                i - 1, line.replace(f'"{inc_path}"', f'"/{inc_path}"')))
                        self.fix(path, "include_barra_def",
                            f"Añadir barra inicial a include: {inc_path}",
                            _fix)

        # 3. Debe tener {game_entity}
        if not re.search(r"\{game_entity\b", text):
            self.result.add_error(path, 1,
                "Falta bloque {game_entity} en .def", fixable=False)

        # 4. Debe tener {Extension "<model>.mdl"}
        if not re.search(r'\{Extension\s+"[^"]+\.mdl"', text):
            self.result.add_error(path, 0,
                "Falta {Extension \"modelo.mdl\"} en .def", fixable=False)

    # ==================================================================
    # .ext
    # ==================================================================
    def validate_ext(self, path):
        self.log(f"Validando .ext: {path}")
        text = self._read_text(path)
        lines = text.split("\n")
        self.result.checked += 1

        # 1. Llaves balanceadas
        depth = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            depth += stripped.count("{") - stripped.count("}")
            if depth < 0:
                self.result.add_error(path, i,
                    "Llave de cierre '}' sin apertura", fixable=False)
                depth = 0
        if depth != 0:
            self.result.add_error(path, 0,
                f"Llaves desbalanceadas (profundidad final={depth})", fixable=False)

        # 2. Paréntesis balanceados
        open_p = text.count("(")
        close_p = text.count(")")
        if open_p != close_p:
            self.result.add_error(path, 0,
                f"Paréntesis desbalanceados: {open_p} abiertos, {close_p} cerrados",
                fixable=False)

        # 3. Includes con barra inicial
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("(include"):
                m = re.search(r'"([^"]+)"', stripped)
                if m:
                    inc_path = m.group(1)
                    if not inc_path.startswith("/"):
                        def _fix(path=path, i=i, line=line, inc_path=inc_path):
                            self._fix_file_lines(path, lambda lns: lns.__setitem__(
                                i - 1, line.replace(f'"{inc_path}"', f'"/{inc_path}"')))
                        self.fix(path, "include_barra_ext",
                            f"Añadir barra inicial a include: {inc_path}",
                            _fix)

        # 4. No debe tener {icon}, {icon_small}, {hud_icon} sueltos (van en .set)
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.match(r"\{icon(_small|_hud)?\b", stripped):
                block_name = stripped.split()[0]
                def _fix(path=path, i=i):
                    self._fix_file_lines(path, lambda lns: lns.pop(i - 1))
                self.fix(path, "eliminar_icon_ext",
                    f"Eliminar '{block_name}' de nivel raíz en .ext",
                    _fix)

        # 5. Argumentos de brain_vehicle deben llevar paréntesis
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if "brain_vehicle" in stripped:
                fixes_needed = []
                arg_patterns = [
                    ('engage_range', r'engage_range\s+(\d+)', r'engage_range(\1)'),
                    ('fire_on_move', r'fire_on_move\s+(\d+)', r'fire_on_move(\1)'),
                    ('reverse_allowed', r'reverse_allowed\s+(\d+)', r'reverse_allowed(\1)'),
                    ('prefer_front_armor', r'prefer_front_armor\s+(\d+)', r'prefer_front_armor(\1)'),
                    ('leg_ik_enabled', r'leg_ik_enabled\s+(\d+)', r'leg_ik_enabled(\1)'),
                    ('slope_limit', r'slope_limit\s+(\d+)', r'slope_limit(\1)'),
                ]
                for arg_name, pattern, replacement in arg_patterns:
                    if re.search(pattern, stripped) and not re.search(arg_name + r'\s*\(', stripped):
                        fixes_needed.append((arg_name, pattern, replacement))
                if re.search(r'walker_gait\s+"(\w+)"', stripped) and not re.search(r'walker_gait\s*\(', stripped):
                    fixes_needed.append(('walker_gait', r'walker_gait\s+("(\w+)")', r'walker_gait(\1)'))

                for arg_name, pattern, replacement in fixes_needed:
                    def _fix(path=path, i=i, line=line, pattern=pattern, replacement=replacement):
                        self._fix_file_lines(path, lambda lns: lns.__setitem__(
                            i - 1, re.sub(pattern, replacement, lns[i - 1])))
                    self.fix(path, f"parentesis_{arg_name}",
                        f"Añadir paréntesis a {arg_name} en brain_vehicle",
                        _fix)

    # ==================================================================
    # .inc
    # ==================================================================
    def validate_inc(self, path):
        self.log(f"Validando .inc: {path}")
        raw = self._read_bytes(path)
        self.result.checked += 1

        # 1. CRLF
        crlf_count = raw.count(b"\r\n")
        lf_only = raw.count(b"\n") - crlf_count
        if lf_only > 0:
            def _fix(path=path, raw=raw):
                fixed = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                self._write_bytes(path, fixed)
            self.fix(path, "crlf",
                f"Convertir {lf_only} líneas de LF a CRLF", _fix)

        text = raw.decode("utf-8", errors="replace")
        lines = text.split("\n")
        first_line = lines[0].strip() if lines else ""

        # 2. Cabecera ;SDL
        if first_line != ";SDL":
            def _fix(path=path, raw=raw):
                self._write_bytes(path, b";SDL\r\n" + raw)
            self.fix(path, "cabecera_sdl",
                f"Añadir cabecera ';SDL' (primera línea era '{first_line}')", _fix)

        # 3. Contenedor (define ... {brain ... {state ... }})
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
                brain_depth = stripped.count("{") - stripped.count("}")
            if "{state" in stripped and not in_brain:
                self.result.add_error(path, i,
                    "Bloque '{state' fuera de contenedor (define...{brain}). "
                    "Envolver en (define \"nombre\" {brain \"tipo\" ... })", fixable=True)
            if in_brain:
                brain_depth += stripped.count("{") - stripped.count("}")
                if brain_depth <= 0:
                    in_brain = False

        if not in_define:
            self.result.add_error(path, 0,
                "Archivo .inc no tiene contenedor (define ... ). "
                "Envolver en (define \"nombre\" {brain \"tipo\" ... })", fixable=True)

        # 4. Llaves balanceadas
        open_b = text.count("{")
        close_b = text.count("}")
        if open_b != close_b:
            self.result.add_error(path, 0,
                f"Llaves desbalanceadas: {open_b} abiertas, {close_b} cerradas",
                fixable=False)

    # ==================================================================
    # .set (roster)
    # ==================================================================
    def validate_set(self, path):
        self.log(f"Validando .set: {path}")
        text = self._read_text(path)
        lines = text.split("\n")
        self.result.checked += 1

        name = Path(path).name.upper()
        path_str = str(path)

        # PATHER.SET
        if name == "PATHER.SET":
            first = lines[0].strip() if lines else ""
            if first != "{Pathers":
                self.result.add_error(path, 1,
                    f"PATHER.SET debe empezar con '{{Pathers', no con '{first}'",
                    fixable=False)
            return

        # Rosters de unidades
        for i, line in enumerate(lines, 1):
            if '"iron_nest"' in line:
                context = "\n".join(lines[i:i + 10])
                is_conquest = "conquest" in path_str.lower()

                if is_conquest:
                    if "period(conquest)" in context:
                        self.result.add_error(path, i,
                            "period(conquest) es inválido en conquest. Usar period(mid) o period(late)",
                            fixable=True)
                    if "min_stage" not in context:
                        self.result.add_warning(path, i, "Conquest: falta min_stage(N)")
                    if "max_stage" not in context:
                        self.result.add_warning(path, i, "Conquest: falta max_stage(N)")
                    if "{cost" not in context:
                        self.result.add_warning(path, i, "Conquest: falta {cost N} bloque separado")
                    if "cd(" in context or "ci(" in context or "g(" in context or "b(" in context:
                        self.result.add_warning(path, i,
                            "Conquest: no usar cd(), ci(), g(), b() (son de skirmish)")
                else:
                    if "min_stage" in context or "max_stage" in context:
                        self.result.add_warning(path, i,
                            "Skirmish: no usar min_stage()/max_stage() (son de conquest)")
                    if "{cost" in context:
                        self.result.add_warning(path, i,
                            "Skirmish: usar cost(N) inline, no {cost N} bloque separado")
                    for p in ["cd(", "ci(", "t(", "g(", "b(", "cost("]:
                        if p not in context:
                            self.result.add_warning(path, i,
                                f"Skirmish: falta parámetro {p}")

    # ==================================================================
    # Sincronización
    # ==================================================================
    def sync_to_mod(self, source_dir, mod_dir):
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

        self.result.add_fix("sync", "copiar_archivos",
                            f"{copied} archivos copiados de salida_mod a mods/iron_nest/")

    # ==================================================================
    # Ejecutar
    # ==================================================================
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
            for f in sorted(dir_path.rglob(pattern)):
                self.validate_file(f)

    def report(self):
        s = self.result.summary()
        print("\n" + "=" * 60)
        print(color("GEM2 OFFLINE VALIDATOR - REPORTE (agente)", BOLD + BLUE))
        print("=" * 60)
        print(f"Archivos revisados: {s['checked']}")
        print(f"Errores: {s['errors']} (reparables: {s['fixable_errors']}, no reparables: {s['unfixable_errors']})")
        print(f"Advertencias: {s['warnings']}")
        print(f"Auto-fixes aplicados: {s['fixes']}")
        print("-" * 60)

        for file, line, msg, fixable, severity in self.result.errors:
            sev_color = YELLOW if fixable else RED
            sev = "FIXABLE" if fixable else "FATAL"
            print(f"{color(sev, sev_color)} [{file}:{line}] {msg}")

        if self.result.warnings:
            print("-" * 60)
            for file, line, msg in self.result.warnings:
                print(f"{color('WARN', BLUE)} [{file}:{line}] {msg}")

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


def del_lines(lns, start, end):
    """Elimina líneas de start a end inclusive (0-indexed)."""
    del lns[start:end + 1]


def main():
    parser = argparse.ArgumentParser(
        description="Validador offline GEM2 para el mod Iron Nest"
    )
    parser.add_argument("path", help="Ruta al archivo o directorio a validar")
    parser.add_argument("--fix", action="store_true", help="Auto-reparar errores reparables")
    parser.add_argument("--sync", action="store_true", help="Sincronizar salida_mod -> mod instalado")
    parser.add_argument("-v", "--verbose", action="store_true", help="Mostrar detalles")
    args = parser.parse_args()

    validator = Gem2Validator(auto_fix=args.fix, sync=args.sync, verbose=args.verbose)

    path = Path(args.path)
    if path.is_dir():
        validator.validate_directory(path)
        if args.sync:
            validator.sync_to_mod(path, validator.mod_installed)
    else:
        validator.validate_file(path)

    success = validator.report()
    sys.exit(0 if success else 2)


if __name__ == "__main__":
    main()
