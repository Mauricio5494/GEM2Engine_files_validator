"""
IRON NEST -> GEM2 | PARTE 1: renombrar con prefijos (d_ / p_) y fusionar mallas por grupo funcional
Uso: ejecutar PRIMERO iron_nest_blender.py en la misma sesión (misma escena), luego este archivo (Alt+P).
No es destructivo: los objetos originales se ocultan y los nuevos quedan en la colección 'GEM2_export'.
Se puede re-ejecutar las veces que haga falta (borra y regenera 'GEM2_export').

Qué hace:
  1. Evalúa cada objeto (modificadores Bisel/Solidify, Cloth ya asentada, curvas y texto -> malla) en coordenadas de mundo.
  2. Asigna cada objeto a un grupo funcional (ver reglas abajo).
  3. Fusiona cada grupo en UNA malla con materiales unificados y deja el origen en el pivote de articulación.
Los chunks quedan en ejes de mundo (rotación identidad) y SIN jerarquía (plano). La pose es la que tenga la escena.
"""
import bpy, bmesh, re
import numpy as np
from mathutils import Vector

# ---------------- PARÁMETROS ----------------
OUT_COLLECTION = 'GEM2_export'
OCULTAR_ORIGINALES = True
KD = 3.8                                  # debe coincidir con KD de iron_nest_blender.py (altura del tobillo sobre el suelo)
SKIP = {'Suelo', 'Soporte colision tela'}  # no se exportan (suelo de escena y proxy de colisión de la tela)

# ---------------- REGLAS DE AGRUPACIÓN ----------------
# {c} = esquina de la pata: FL (+X,+Y), FR (+X,-Y), BL (-X,+Y), BR (-X,-Y). +X = frente, +Y = izquierda
# {s} = lado del cañón (L/R) según la posición en el sistema local de la torreta
def R(p): return re.compile(p, re.I)

# 1) Reglas por nombre (objetos sueltos o con padre que no refleja su función). Se evalúan primero.
SPECIAL = [
    (R(r'^Piston cadera'),            'p_piston_hip_{c}'),
    (R(r'^Manguera cadera'),          'p_piston_hip_{c}'),
    (R(r'^Piston tobillo'),           'p_piston_ankle_{c}'),
    (R(r'^Piston (camisa|vastago|anclaje)'), 'p_piston_knee_{c}'),
    (R(r'^(Anillo giro fijo|Repisa giro|Pernos anillo giro|Pernos repisa|Pilar giro|Brida motor giro|Motor giro|Eje motor giro|Pinon giro|Manguera giro)'),
                                      'd_hipmount_{c}'),
    (R(r'^(Ariete elevacion|Manguera ariete)'), 'p_elev_ram_{s}'),
]
# 2) Por ancestro articulado (empty padre)
ANCHOR = {
    'Pivote canon izq': 'd_gun_{s}', 'Pivote canon der': 'd_gun_{s}',
    'Pierna sup': 'd_leg_upper_{c}', 'Pierna inf': 'd_leg_lower_{c}',
    'Pie': 'd_foot_{c}', 'Caja cadera': 'd_hip_{c}',
}
# 3) Resto de la torreta (si nada coincide -> d_turret)
TURRET_RULES = [
    (R(r'mirador'),                                        'd_periscope'),
    (R(r'sirena|bocina|excitador|deposito|manometro|valvula aire'), 'd_horns'),
    (R(r'escotilla|^Vastago valvula$'),                    'd_hatch'),
    (R(r'rejilla|^Lama$'),                                 'd_roof_vent'),
    (R(r'visor'),                                          'd_visor'),
    (R(r'foco|lente'),                                     'd_headlights'),
    (R(r'trasera|\breja\b|colector|^Brida$'),              'd_turret_rear'),
]
# 4) Resto del cuerpo (si nada coincide -> d_hull)
BODY_RULES = [(R(r'puerta'), 'd_door_rear')]
TURRET_GROUPS = {'d_turret', 'd_periscope', 'd_horns', 'd_hatch', 'd_roof_vent', 'd_visor', 'd_headlights', 'd_turret_rear'}

def base(n): return re.sub(r'\.\d{3,}$', '', n)

# ---------------- PREPARACIÓN ----------------
O = bpy.data.objects
BODY, TUR = O.get('Cuerpo'), O.get('Torreta')
if not BODY or not TUR:
    raise RuntimeError("No encuentro 'Cuerpo' / 'Torreta'. Ejecuta primero iron_nest_blender.py en esta escena.")
sc = bpy.context.scene; vl = bpy.context.view_layer

old = bpy.data.collections.get(OUT_COLLECTION)          # limpieza de una ejecución anterior
if old:
    for o in list(old.objects):
        me = o.data; O.remove(o)
        if me and me.users == 0: bpy.data.meshes.remove(me)
    bpy.data.collections.remove(old)
for o in sc.objects:                                     # mostrar originales para poder evaluarlos
    try: o.hide_set(False)
    except RuntimeError: pass

sources = [o for o in sc.objects if o.type in {'MESH', 'CURVE', 'FONT', 'SURFACE'} and base(o.name) not in SKIP]
if any(m.type == 'CLOTH' for o in sources for m in o.modifiers):   # la tela se simula frame a frame: llegar al último
    for f in range(sc.frame_start, sc.frame_end + 1): sc.frame_set(f)
vl.update(); dg = bpy.context.evaluated_depsgraph_get()
W = lambda o: o.evaluated_get(dg).matrix_world
Binv, Tinv = W(BODY).inverted(), W(TUR).inverted()

def corner(p):
    l = Binv @ Vector(p); return ('F' if l.x > 0 else 'B') + ('L' if l.y > 0 else 'R')
def side(p):
    return 'L' if (Tinv @ Vector(p)).y > 0 else 'R'

# Articulaciones por esquina (se leen de los empties del script original)
HIP, UPC, FOOT = {}, {}, {}
PIV = None
for e in sc.objects:
    if e.type != 'EMPTY': continue
    b = base(e.name); M = W(e)
    if b == 'Caja cadera':   HIP[corner(M.translation)] = M.translation.copy()
    elif b == 'Pierna sup':  UPC[corner(M.translation)] = M.translation.copy()
    elif b == 'Pie':         FOOT[corner(M.translation)] = M.copy()
    elif b.startswith('Pivote canon') and PIV is None: PIV = e

def in_turret(ob):
    p = ob.parent
    while p:
        if p == TUR: return True
        p = p.parent
    return False

def classify(ob, c):
    nm = base(ob.name); fmt = dict(c=corner(c), s=side(c))
    for rx, tpl in SPECIAL:
        if rx.search(nm): return tpl.format(**fmt)
    p = ob.parent
    while p:
        if p.type == 'EMPTY' and base(p.name) in ANCHOR:
            t = ANCHOR[base(p.name)]
            return t.format(c=corner(W(p).translation), s=fmt['s'])    # la esquina sale del empty articulado, no del objeto
        p = p.parent
    tur = in_turret(ob)
    for rx, g in (TURRET_RULES if tur else BODY_RULES):
        if rx.search(nm): return g
    return 'd_turret' if tur else 'd_hull'

def pivot(g, bc):
    m = re.match(r'd_(leg_upper|leg_lower|foot|hip|hipmount)_(\w\w)$', g)
    if m:
        k, c = m.groups()
        if k in ('hip', 'hipmount', 'leg_upper'): return HIP[c]                 # eje de la cadera
        if k == 'leg_lower': return 2 * UPC[c] - HIP[c]                          # rodilla = extremo lejano de la pierna superior
        return FOOT[c] @ Vector((0, 0, KD))                                      # tobillo
    if g.startswith('d_gun_'):                                                   # eje de elevación (muñones), centrado en el cañón
        pl = Tinv @ W(PIV).translation; bl = Tinv @ bc
        return W(TUR) @ Vector((pl.x, bl.y, pl.z))
    if g == 'd_hull': return W(BODY).translation.copy()
    if g in TURRET_GROUPS: return W(TUR).translation.copy()                      # eje de giro de la torreta
    return bc                                                                    # p_* y d_door_rear: centro de la pieza

# ---------------- EVALUAR Y CLASIFICAR ----------------
groups = {}   # nombre -> {'meshes': [...], 'lo': ndarray, 'hi': ndarray, 'n': int}
for ob in sources:
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, depsgraph=dg)
    me.transform(ev.matrix_world)
    nv = len(me.vertices)
    if nv == 0: bpy.data.meshes.remove(me); continue
    co = np.empty(nv * 3, dtype=np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    lo, hi = co.min(0), co.max(0)
    g = classify(ob, Vector((lo + hi) / 2))
    G = groups.setdefault(g, {'meshes': [], 'lo': lo.copy(), 'hi': hi.copy(), 'n': 0})
    G['meshes'].append(me); G['lo'] = np.minimum(G['lo'], lo); G['hi'] = np.maximum(G['hi'], hi); G['n'] += 1

# ---------------- FUSIONAR ----------------
coll = bpy.data.collections.new(OUT_COLLECTION); sc.collection.children.link(coll)
report = []
for g in sorted(groups):
    G = groups[g]; mats = []; bm = bmesh.new()
    for me in G['meshes']:
        remap = []
        for m in me.materials:
            if m not in mats: mats.append(m)
            remap.append(mats.index(m))
        if not remap:
            if None not in mats: mats.append(None)
            remap = [mats.index(None)]
        n = len(me.polygons)
        if n:
            arr = np.zeros(n, dtype=np.int32); me.polygons.foreach_get('material_index', arr)
            arr = np.array(remap, dtype=np.int32)[np.clip(arr, 0, len(remap) - 1)]
            me.polygons.foreach_set('material_index', arr)
        bm.from_mesh(me); bpy.data.meshes.remove(me)
    bc = Vector((G['lo'] + G['hi']) / 2); P = Vector(pivot(g, bc))
    bmesh.ops.translate(bm, vec=-P, verts=bm.verts)               # geometría relativa al pivote
    nv, nt = len(bm.verts), sum(len(f.verts) - 2 for f in bm.faces)
    mesh = bpy.data.meshes.new(g); bm.to_mesh(mesh); bm.free()
    for m in mats: mesh.materials.append(m)
    ob = bpy.data.objects.new(g, mesh); ob.location = P; coll.objects.link(ob)
    report.append((g, G['n'], nv, nt))

if OCULTAR_ORIGINALES:
    for o in sources: o.hide_set(True)

# ---------------- INFORME ----------------
# (en Linux/Mac los print() solo salen en la terminal desde la que se lanzó Blender; por eso el informe se guarda también
#  en un bloque de texto: editor de texto > menú de bloques > 'GEM2_informe_parte1')
L = ['=== GEM2 parte 1: %d chunks en la colección %s ===' % (len(report), OUT_COLLECTION),
     '%-22s %8s %9s %9s' % ('chunk', 'objetos', 'vértices', 'tris')]
for g, n, nv, nt in report: L.append('%-22s %8d %9d %9d' % (g, n, nv, nt))
L.append('%-22s %8d %9d %9d' % ('TOTAL', sum(r[1] for r in report), sum(r[2] for r in report), sum(r[3] for r in report)))
for g, n, nv, nt in report:
    if nv > 65000: L.append('AVISO: %s tiene %d vértices (límite del .ply: 65535) -> hay que partirlo' % (g, nv))
if any(abs(e.rotation_euler.y) > 1e-4 for e in sc.objects if e.type == 'EMPTY' and base(e.name).startswith('Pivote canon')):
    L.append('AVISO: los cañones tienen elevación distinta de 0 (pon ELEV_IZQ_DEG y ELEV_DER_DEG = 0 en iron_nest_blender.py)')
if abs(TUR.rotation_euler.z) > 1e-4: L.append('AVISO: la torreta está girada (YAW_DEG distinto de 0)')
if abs(BODY.rotation_euler.y) > 1e-4: L.append('AVISO: hay pendiente (SLOPE_DEG distinto de 0)')
informe = '\n'.join(L); print(informe)
tx = bpy.data.texts.get('GEM2_informe_parte1') or bpy.data.texts.new('GEM2_informe_parte1'); tx.clear(); tx.write(informe)
