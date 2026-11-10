"""
IRON NEST -> GEM2 | PARTE 2: puntos de anclaje s_ y modelo físico (<nombre>10.X)
Requiere haber ejecutado la parte 1 (colección GEM2_export con los chunks d_* / p_*). Si re-ejecutas la parte 1, repite esta.

  - Puntos s_: se crean en GEM2_export como EMPTIES (S_MODE='EMPTY') o como mallas de un solo vértice (S_MODE='VERTEX').
  - Modelo físico: colección GEM2_phys, SOLO cajas y cilindros de pocas caras (nada de geometría detallada).
      PHYS_MODE='PARTES'      -> una primitiva por parte (cuerpo, torreta, cañones, cada pata, cada pie)
      PHYS_MODE='ENVOLVENTE'  -> una única malla convexa que envuelve todas las primitivas
Se asume la pose de reposo (elevación 0, torreta a 0°, pendiente 0), igual que en la parte 1.
"""
import bpy, bmesh, math
from mathutils import Vector, Matrix

# ---------------- PARÁMETROS ----------------
S_MODE = 'EMPTY'          # 'EMPTY' | 'VERTEX' (si el exportador .X no admite empties)
PHYS_MODE = 'PARTES'      # 'PARTES' | 'ENVOLVENTE'
OUT_S, OUT_P = 'GEM2_export', 'GEM2_phys'
CYL_SEG = 12
# Constantes tomadas de iron_nest_blender.py (deben coincidir con el original)
KD = 3.8                                   # altura del tobillo sobre el suelo
TS = 1.1                                   # escala de la torreta (afecta a los cañones)
LEG_R, LEG_W, LEG_H = 1.4, 2.4, 3.0        # tambor (radio), ancho (T + .3) y alto de placa de las piernas
DRUM_R, SLEEVE_R, SLEEVE_X1, BARREL_R = 1.62, 1.5, 5.2, 0.85   # tambor, manguito de tela, fin del manguito, collares (sin escalar)
CORNERS = ('FL', 'FR', 'BL', 'BR')
TURRET_GROUPS = ('d_turret', 'd_periscope', 'd_horns', 'd_hatch', 'd_roof_vent', 'd_visor', 'd_headlights', 'd_turret_rear')

# ---------------- PREPARACIÓN ----------------
sc = bpy.context.scene; bpy.context.view_layer.update()
coll_s = bpy.data.collections.get(OUT_S)
if not coll_s: raise RuntimeError("No existe la colección '%s'. Ejecuta primero la parte 1." % OUT_S)
for o in list(coll_s.objects):                           # limpiar s_ de ejecuciones anteriores
    if o.name.startswith('s_'):
        me = o.data; bpy.data.objects.remove(o)
        if me and me.users == 0: bpy.data.meshes.remove(me)
old = bpy.data.collections.get(OUT_P)
if old:
    for o in list(old.objects):
        me = o.data; bpy.data.objects.remove(o)
        if me and me.users == 0: bpy.data.meshes.remove(me)
    bpy.data.collections.remove(old)
coll_p = bpy.data.collections.new(OUT_P); sc.collection.children.link(coll_p)

CH = {o.name: o for o in coll_s.objects}
def need(n):
    if n not in CH: raise RuntimeError("Falta el chunk '%s' (¿parte 1 ejecutada con la geometría completa?)" % n)
    return CH[n]
loc = lambda n: need(n).matrix_world.translation.copy()

def bbox(names):
    pts = [CH[n].matrix_world @ Vector(c) for n in names if n in CH for c in CH[n].bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))

# ---------------- PUNTOS s_ ----------------
S = {'s_turret_pivot': loc('d_turret')}
for s in ('L', 'R'):
    g = need('d_gun_' + s); xmax = max(v.co.x for v in g.data.vertices)
    S['s_gun_pivot_' + s] = g.matrix_world.translation.copy()
    S['s_gun_muzzle_' + s] = g.matrix_world @ Vector((xmax, 0, 0))        # boca: extremo del cañón sobre su eje (+X en reposo)
for c in CORNERS:
    hip, knee, ank = loc('d_leg_upper_' + c), loc('d_leg_lower_' + c), loc('d_foot_' + c)
    S['s_leg_hip_' + c] = hip; S['s_leg_knee_' + c] = knee; S['s_leg_ankle_' + c] = ank
    S['s_leg_foot_' + c] = ank - Vector((0, 0, KD))                       # punto de contacto con el suelo (pendiente 0)
for n, p in S.items():
    if S_MODE == 'EMPTY':
        o = bpy.data.objects.new(n, None); o.empty_display_type = 'PLAIN_AXES'; o.empty_display_size = .6; o.location = p
    else:
        me = bpy.data.meshes.new(n); me.from_pydata([tuple(p)], [], []); o = bpy.data.objects.new(n, me)
    coll_s.objects.link(o)

# ---------------- MODELO FÍSICO ----------------
ALLV = []; report = []
def finish(name, bm):
    ALLV.extend(v.co.copy() for v in bm.verts)
    nt = sum(len(f.verts) - 2 for f in bm.faces)
    me = bpy.data.meshes.new(name + '.phys'); bm.to_mesh(me); bm.free()          # '.phys': Blender no admite dos objetos con el mismo nombre
    ob = bpy.data.objects.new(name + '.phys', me); coll_p.objects.link(ob); report.append((name, nt))   # al exportar se quita el sufijo
    return ob

def box(name, c, ax, ay, az, dims):
    R = Matrix(((ax.x, ay.x, az.x), (ax.y, ay.y, az.y), (ax.z, ay.z, az.z)))
    M = Matrix.Translation(c) @ (R @ Matrix.Diagonal(Vector(dims))).to_4x4()
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0, matrix=M); o = finish(name, bm)
    o['gem2_kind'] = 'BOX'; o['gem2_c'] = tuple(c); o['gem2_ax'] = tuple(ax) + tuple(ay) + tuple(az); o['gem2_dim'] = tuple(dims)   # los lee la parte 3

def aabb(name, lo, hi):
    X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
    box(name, (lo + hi) / 2, X, Y, Z, tuple(hi - lo))

def cyl(name, c, axis, r, h):
    axis = Vector(axis).normalized(); q = axis.to_track_quat('Z', 'X' if abs(axis.y) > .99 else 'Y')
    M = Matrix.Translation(c) @ q.to_matrix().to_4x4()
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=CYL_SEG, radius1=r, radius2=r, depth=h, matrix=M); o = finish(name, bm)
    R3 = q.to_matrix(); o['gem2_kind'] = 'CYL'; o['gem2_c'] = tuple(c); o['gem2_ax'] = tuple(R3.col[0]) + tuple(R3.col[1]) + tuple(R3.col[2]); o['gem2_dim'] = (r, h)

def leg_box(name, a, b):                                   # caja orientada a lo largo de la pierna (articulación a articulación)
    d = b - a; L = d.length; ax = d / L
    ay = Vector((0, 0, 1)).cross(ax).normalized(); az = ax.cross(ay)
    box(name, (a + b) / 2, ax, ay, az, (L + 2 * LEG_R, LEG_W, LEG_H))

# cuerpo y torreta
lo, hi = bbox(['d_hull', 'd_door_rear']); aabb('d_hull', lo, hi)
lo, hi = bbox(TURRET_GROUPS); aabb('d_turret', lo, hi)
# cañones: tambor (eje Y), manguito y cañón (eje X)
for s in ('L', 'R'):
    P = S['s_gun_pivot_' + s]; M_ = S['s_gun_muzzle_' + s]; glo, ghi = bbox(['d_gun_' + s])
    cyl('d_gun_%s' % s, P, (0, 1, 0), DRUM_R * TS, ghi.y - glo.y)
    x1 = P.x + SLEEVE_X1 * TS
    cyl('d_gun_%s_sleeve' % s, Vector(((P.x + x1) / 2, P.y, P.z)), (1, 0, 0), SLEEVE_R * TS, x1 - P.x)
    cyl('d_gun_%s_barrel' % s, Vector(((x1 + M_.x) / 2, P.y, P.z)), (1, 0, 0), BARREL_R * TS, M_.x - x1)
# patas
for c in CORNERS:
    leg_box('d_leg_upper_' + c, S['s_leg_hip_' + c], S['s_leg_knee_' + c])
    leg_box('d_leg_lower_' + c, S['s_leg_knee_' + c], S['s_leg_ankle_' + c])
    lo, hi = bbox(['d_hip_' + c, 'd_hipmount_' + c]); aabb('d_hip_' + c, lo, hi)
    lo, hi = bbox(['d_foot_' + c]); aabb('d_foot_' + c, lo, hi)

if PHYS_MODE == 'ENVOLVENTE':                              # una sola malla convexa que envuelve todo
    for o in list(coll_p.objects):
        me = o.data; bpy.data.objects.remove(o); bpy.data.meshes.remove(me)
    bm = bmesh.new()
    for p in ALLV: bm.verts.new(p)
    r = bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
    bmesh.ops.delete(bm, geom=r['geom_interior'] + r['geom_unused'], context='VERTS')
    report = []; finish('phys_hull', bm)

# ---------------- INFORME ----------------
L = ['=== GEM2 parte 2 ===', 'Puntos s_ (%d, modo %s):' % (len(S), S_MODE)]
for n in sorted(S): L.append('  %-20s (%.2f, %.2f, %.2f)' % ((n,) + tuple(S[n])))
L.append('Modelo físico (%s) en %s (los objetos llevan el sufijo .phys):' % (PHYS_MODE, OUT_P))
for n, nt in report: L.append('  %-22s %3d tris' % (n, nt))
L.append('  TOTAL %d tris' % sum(r[1] for r in report))
informe = '\n'.join(L); print(informe)
tx = bpy.data.texts.get('GEM2_informe_parte2') or bpy.data.texts.new('GEM2_informe_parte2'); tx.clear(); tx.write(informe)
