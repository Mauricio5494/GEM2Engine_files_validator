#!/usr/bin/env python3
"""
IRON NEST | Reconstruir .mdl con VolumeView distribuidos por hueso.
Recorre el .mdl del plugin usando un stack de huesos abiertos para extraer
pos, matrix y orientation de cada hueso, luego re-emite el .mdl con
{VolumeView} vinculado a cada hueso según su chunk.
"""
import os, re

mod_dir = "/home/sparky/Descargas/Iron_Nest_CTA_mod"
ENT_DIR = os.path.join(mod_dir, "salida_mod", "resource", "entity", "-vehicle", "iron_nest")
mdl_path = os.path.join(ENT_DIR, 'iron_nest.mdl')

with open(mdl_path, 'r', encoding='utf-8') as f:
    content = f.read()

# ============================================================
# Parser secuencial con stack
# ============================================================
bones = {}  # name -> {pos, matrix, orientation}
stack = []  # lista de nombres de huesos abiertos (para jerarquía)

i = 0
n = len(content)
while i < n:
    # Saltar whitespace antes del siguiente token
    while i < n and content[i] in ' \t\r\n':
        i += 1
    if i >= n:
        break
    # Buscar siguiente token relevante
    # {bone "name" ...
    m = re.match(r'\{\s*bone\s+(?:revolute\s+)?("([^"]+)")', content[i:])
    if m:
        bone_name = m.group(2)
        full_match = m.group(0)
        # El hueso empieza en i
        stack.append(bone_name)
        bones[bone_name] = {'pos': (0.0,0.0,0.0), 'matrix': ((1,0,0),(0,1,0),(0,0,1)), 'orientation': None, 'parent': stack[-2] if len(stack) >= 2 else None}
        i += m.end()
        continue

    # {Orientation ... } (solo para basis)
    m = re.match(r'\{\s*Orientation\s*\n?', content[i:])
    if m and stack:
        # Leer 3 líneas de 3 valores cada una
        j = i + m.end()
        rows = []
        for _ in range(3):
            # Saltar whitespace/newlines
            while j < n and content[j] in ' \t\r\n':
                j += 1
            end = j
            while end < n and content[end] not in ' \t\r\n':
                end += 1
            if j < end:
                vals = [float(x) for x in content[j:end].split()]
                if len(vals) == 3:
                    rows.append(tuple(vals))
            j = end
        if len(rows) == 3:
            bones[stack[-1]]['orientation'] = tuple(rows)
        # Saltar hasta el cierre }
        while j < n and content[j] != '}':
            j += 1
        if j < n:
            j += 1
        i = j
        continue

    # {Position x y z}
    m = re.match(r'\{\s*Position\s+([^\}]+)\}', content[i:])
    if m and stack:
        vals = [float(x) for x in m.group(1).split()]
        if len(vals) >= 3:
            bones[stack[-1]]['pos'] = tuple(vals[:3])
        i += m.end()
        continue

    # {Matrix34 ... } - 4 filas de 3 valores cada una (la 4ta fila es la posición)
    m = re.match(r'\{\s*Matrix34\s*\n?', content[i:])
    if m and stack:
        j = i + m.end()
        rows = []
        pos_row = None
        for row_idx in range(4):
            # Saltar whitespace incluyendo newlines hasta el inicio de la fila
            while j < n and content[j] in ' \t\r\n':
                j += 1
            # Leer hasta el fin de línea
            end = j
            while end < n and content[end] != '\n' and content[end] != '\r':
                end += 1
            if j < end:
                line = content[j:end].split()
                vals = [float(x) for x in line]
                if len(vals) == 3:
                    if row_idx < 3:
                        rows.append(tuple(vals))
                    else:
                        pos_row = tuple(vals[:3])
            j = end
        if len(rows) == 3:
            bones[stack[-1]]['matrix'] = tuple(rows)
        if pos_row:
            bones[stack[-1]]['pos'] = pos_row
        # Saltar hasta el cierre }
        while j < n and content[j] != '}':
            j += 1
        if j < n:
            j += 1
        i = j
        continue

    # {animation y {sequence - saltar hasta su cierre (no contienen huesos)
    if content[i:].startswith('{animation') or content[i:].startswith('{sequence'):
        depth = 1
        j = i + 1
        in_str = False
        esc = False
        while j < n and depth > 0:
            ch = content[j]
            if in_str:
                if esc: esc = False
                elif ch == '\\': esc = True
                elif ch == '"': in_str = False
            elif ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            j += 1
        i = j
        continue

    # {Skeleton - no saltar (contiene todo); avanzar solo el '{'
    if content[i:].startswith('{Skeleton'):
        i += 1
        continue

    # { ... } genérico - buscar cierre (solo si no es un bloque conocido)
    if content[i] == '{':
        depth = 1
        j = i + 1
        in_str = False
        esc = False
        while j < n and depth > 0:
            ch = content[j]
            if in_str:
                if esc: esc = False
                elif ch == '\\': esc = True
                elif ch == '"': in_str = False
            elif ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            j += 1
        i = j
        continue

    # Cierre de hueso } - pop del stack
    if content[i] == '}' and stack:
        stack.pop()
        i += 1
        continue

    i += 1

print(f"Transforms parseados: {len(bones)}")
for name in sorted(bones.keys()):
    t = bones[name]
    print(f"  {name}: parent={t['parent']} pos={t['pos']}")

# ============================================================
# Definir jerarquía SPEC (chunk -> hueso)
# ============================================================
SPEC = [
    ("basis", None, 'fixed', None, 'id=basis;', None, None),
    ("body", "basis", 'fixed', 'body.ply', 'id=body;', None, None),
    ("door_rear", "body", 'fixed', 'door_rear.ply', None, None, None),
    ("hipmount_fl", "body", 'fixed', 'hipmount_fl.ply', None, None, None),
    ("hipmount_fr", "body", 'fixed', 'hipmount_fr.ply', None, None, None),
    ("hipmount_bl", "body", 'fixed', 'hipmount_bl.ply', None, None, None),
    ("hipmount_br", "body", 'fixed', 'hipmount_br.ply', None, None, None),
    ("engine", "body", 'fixed', None, 'id=engine;', None, None),
    ("turret", "body", 'revolute', 'turret.ply', 'id=turret;', None, 0.004),
    ("periscope", "turret", 'fixed', 'periscope.ply', 'id=turret;', None, None),
    ("horns", "turret", 'fixed', 'horns.ply', 'id=turret;', None, None),
    ("hatch", "turret", 'fixed', 'hatch.ply', 'id=turret;', None, None),
    ("roof_vent", "turret", 'fixed', 'roof_vent.ply', 'id=turret;', None, None),
    ("visor", "turret", 'fixed', 'visor.ply', 'id=turret;', None, None),
    ("headlights", "turret", 'fixed', 'headlights.ply', 'id=turret;', None, None),
    ("turret_rear", "turret", 'fixed', 'turret_rear.ply', 'id=turret;', None, None),
    ("driver", "turret", 'fixed', None, None, None, None),
    ("gunner", "turret", 'fixed', None, None, None, None),
    ("commander", "turret", 'fixed', None, None, None, None),
    ("charger", "turret", 'fixed', None, None, None, None),
    ("gunner2", "turret", 'fixed', None, None, None, None),
    ("emit0", "turret", 'fixed', None, None, None, None),
    ("seat01", "turret", 'fixed', None, None, None, None),
    ("seat02", "turret", 'fixed', None, None, None, None),
    ("tps", "turret", 'fixed', None, None, None, None),
    ("visor1", "turret", 'fixed', None, None, None, None),
    ("gun_rot", "turret", 'revolute', 'gun_rot.ply', 'id=gun;', (0, 60), 0.004),
    ("gun", "gun_rot", 'fixed', None, 'id=gun;', None, None),
    ("elev_ram_l", "gun_rot", 'fixed', 'elev_ram_l.ply', None, None, None),
    ("gun1_rot", "turret", 'revolute', 'gun1_rot.ply', 'id=gun1;', (0, 60), 0.004),
    ("gun1", "gun1_rot", 'fixed', None, 'id=gun1;', None, None),
    ("elev_ram_r", "gun1_rot", 'fixed', 'elev_ram_r.ply', None, None, None),
]

for c in ('fl', 'fr', 'bl', 'br'):
    SPEC += [
        (f'hip_{c}', 'body', 'fixed', f'hip_{c}.ply', f'id=leg_{c};', None, None),
        (f'leg_upper_{c}', f'hip_{c}', 'fixed', f'leg_upper_{c}.ply', f'id=leg_{c};', None, None),
        (f'leg_lower_{c}', f'leg_upper_{c}', 'fixed', f'leg_lower_{c}.ply', f'id=leg_{c};', None, None),
        (f'foot_{c}', f'leg_lower_{c}', 'fixed', f'foot_{c}.ply', f'id=leg_{c};', None, None),
        (f'piston_hip_{c}', f'leg_upper_{c}', 'fixed', f'piston_hip_{c}.ply', None, None, None),
        (f'piston_knee_{c}', f'leg_upper_{c}', 'fixed', f'piston_knee_{c}.ply', None, None, None),
        (f'piston_ankle_{c}', f'leg_lower_{c}', 'fixed', f'piston_ankle_{c}.ply', None, None, None),
]

# ============================================================
# Generar .mdl
# ============================================================
def n(x):
    s = '%.6g' % x
    return '0' if s in ('-0', '0') else s

def _is_ident(m, eps=1e-6):
    return all(abs(m[i][j] - (1 if i == j else 0)) < eps for i in range(3) for j in range(3))

# Construir lista de huesos con datos
bone_list = []
for spec in SPEC:
    name, parent, kind, ply, params, limits, speed = spec
    t = bones.get(name)
    if t:
        pos = t['pos']
        matrix = t['matrix']
        orientation = t.get('orientation')
    else:
        pos = (0.0, 0.0, 0.0)
        matrix = ((1,0,0),(0,1,0),(0,0,1))
        orientation = None
    bone_list.append({
        'name': name, 'parent': parent, 'kind': kind, 'ply': ply,
        'params': params, 'limits': limits, 'speed': speed,
        'pos': pos, 'matrix': matrix, 'orientation': orientation,
    })

# Calcular hijos
kids = {}
for b in bone_list:
    kids.setdefault(b['parent'], []).append(b)

L = ['{skeleton']
L.append('\t{animation')
L.append('\t\t{sequence "move"\t{smooth 0.2}{speed 0.64}}')
L.append('\t}')

def emit(b, depth):
    t = '\t' * depth
    kind_str = '' if b['kind'] == 'fixed' else b['kind'] + ' '
    L.append('%s{bone %s"%s"' % (t, kind_str, b['name']))

    if b['name'] == 'basis':
        L.append('%s\t{Orientation' % t)
        orient = b['orientation'] if b['orientation'] else ((1,0,0),(0,-1,0),(0,0,1))
        for r in orient:
            L.append('%s\t\t%s' % (t, '\t'.join(n(x) for x in r)))
        L.append('%s\t}' % t)

    if b['params']:
        L.append('%s\t{parameters "%s"}' % (t, b['params']))
    if b['limits']:
        L.append('%s\t{limits %s %s}' % (t, n(b['limits'][0]), n(b['limits'][1])))
    if b['speed']:
        L.append('%s\t{speed %s}' % (t, n(b['speed'])))

    if _is_ident(b['matrix']):
        L.append('%s\t{Position %s}' % (t, '\t'.join(n(x) for x in b['pos'])))
    else:
        L.append('%s\t{Matrix34' % t)
        for r in b['matrix']:
            L.append('%s\t\t%s' % (t, '\t'.join(n(x) for x in r)))
        L.append('%s\t\t%s' % (t, '\t'.join(n(x) for x in b['pos'])))
        L.append('%s\t}' % t)

    # VolumeView si tiene PLY
    if b['ply'] and os.path.exists(os.path.join(ENT_DIR, b['ply'])):
        L.append('%s\t{VolumeView "%s"}' % (t, b['ply']))

    # Hijos
    for c in kids.get(b['name'], []):
        emit(c, depth + 1)

    L.append('%s}' % t)

for b in kids.get(None, []):
    emit(b, 1)

L.append('}')
mdl_text = '\r\n'.join(L) + '\r\n'

with open(mdl_path, 'w', encoding='utf-8', newline='') as f:
    f.write(mdl_text)

print(f"\n.mdl reconstruido: {mdl_path}")
vol_count = sum(1 for b in bone_list if b['ply'])
print(f"Huesos con VolumeView: {vol_count}")
print(f"Total huesos: {len(bone_list)}")
