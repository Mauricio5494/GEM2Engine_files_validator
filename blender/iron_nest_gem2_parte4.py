"""
IRON NEST -> GEM2 | PARTE 4: desenvolver UV, hornear texturas (Cycles) y escribir los DDS
Requisitos: partes 1, 2 y 3 ya ejecutadas en esta sesión (colección GEM2_export), y en la carpeta de scripts:
  gem2_dds.py (y los demás gem2_*.py). Hace falta Cycles (viene con Blender).

Por cada grupo de piezas (body, turret, guns, legs):
  1) une sus piezas en una malla temporal (coordenadas de mundo: así los patrones procedurales de óxido salen igual),
  2) UV: Smart UV Project + empaquetado en un atlas,
  3) hornea DIFFUSE (color) y ROUGHNESS (y NORMAL si BAKE_NORMAL=True) con Cycles,
  4) escribe <grupo>_am.dds, <grupo>_gmm.dds, <grupo>_nm.dds en la carpeta de la entidad,
  5) copia las UV a cada pieza (capa 'GEM2UV') y anota en el objeto 'gem2_mtl' = nombre del grupo.
Después hay que VOLVER A EJECUTAR LA PARTE 3: re-exporta los .ply con esas UV, y escribe un .mtl por grupo.
LIMITACIONES: el metal se pierde en el color (se hornea con metallic=0 para que no salga negro); las luces emisivas salen como color normal;
la normal es plana salvo que actives BAKE_NORMAL (la convención de la normal del motor no está comprobada).
"""
import bpy, os, sys, math, importlib
import numpy as np

# ---------------- PARÁMETROS ----------------
MODULES_DIR = None           # None = se busca sola (carpeta de los scripts cargados en Blender)
OUT_DIR = None               # None = 'salida_mod' dentro de MODULES_DIR (igual que la parte 3)
ATLAS_SIZE = {'iron_nest_body': 2048, 'iron_nest_turret': 2048, 'iron_nest_guns': 1024, 'iron_nest_legs': 2048}
BAKE_SAMPLES = 4
MARGIN_PX = 8                # píxeles de sangrado alrededor de cada isla
ISLAND_MARGIN = 0.003        # separación entre islas (fracción del lado del atlas)
ANGLE_LIMIT_DEG = 66.0       # Smart UV Project
SPEC_SCALE = 0.35            # brillo = (1 - rugosidad) * SPEC_SCALE (las texturas _gmm del E-100 tienen media ~0,12)
BAKE_NORMAL = False          # True: hornea la normal del bump procedural (más lento)
NORMAL_FLIP_Y = True         # convención DirectX (verde invertido). Sin comprobar en el motor

CORNERS = ('FL', 'FR', 'BL', 'BR')
GROUPS = {
    'iron_nest_body': ['d_hull', 'd_door_rear'] + ['d_hipmount_' + c for c in CORNERS] + ['d_hip_' + c for c in CORNERS],
    'iron_nest_turret': ['d_turret', 'd_periscope', 'd_horns', 'd_hatch', 'd_roof_vent', 'd_visor', 'd_headlights', 'd_turret_rear'],
    'iron_nest_guns': ['d_gun_L', 'd_gun_R', 'p_elev_ram_L', 'p_elev_ram_R'],
    'iron_nest_legs': [n + c for c in CORNERS for n in ('d_leg_upper_', 'd_leg_lower_', 'd_foot_', 'p_piston_hip_', 'p_piston_knee_', 'p_piston_ankle_')],
}

def _find_modules_dir():
    cands = [MODULES_DIR] if MODULES_DIR else []
    for t in bpy.data.texts:
        if t.filepath: cands.append(os.path.dirname(bpy.path.abspath(t.filepath)))
    cands += [os.path.expanduser('~/Descargas/Iron_Nest_CTA_mod'), os.path.expanduser('~/Descargas'), os.path.expanduser('~/Downloads')]
    for d in cands:
        if d and os.path.exists(os.path.join(d, 'gem2_dds.py')): return d
    raise RuntimeError('No encuentro gem2_dds.py. Pon en MODULES_DIR la carpeta de los scripts gem2_*.py. Probé: ' + ', '.join(c for c in cands if c))
MODULES_DIR = _find_modules_dir()
if OUT_DIR is None: OUT_DIR = os.path.join(MODULES_DIR, 'salida_mod')
if MODULES_DIR not in sys.path: sys.path.insert(0, MODULES_DIR)
import gem2_dds as D, gem2_geom as G
importlib.reload(D); importlib.reload(G)
ENT_DIR = os.path.join(OUT_DIR, 'resource', 'entity', '-vehicle', 'iron_nest'); os.makedirs(ENT_DIR, exist_ok=True)

sc = bpy.context.scene; vl = bpy.context.view_layer
coll = bpy.data.collections.get('GEM2_export')
if not coll: raise RuntimeError("No existe 'GEM2_export': ejecuta antes las partes 1, 2 y 3.")
CH = {o.name: o for o in coll.objects if o.type == 'MESH'}
REPORT = []

if bpy.context.object and bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
PREV_ENGINE = sc.render.engine
try:
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = BAKE_SAMPLES
    try: sc.cycles.use_denoising = False
    except Exception: pass
except Exception as e:
    raise RuntimeError('No se pudo activar Cycles: %s' % e)

# ---------------- AUXILIARES ----------------
def build_scratch(name, chunk_names):
    """Malla temporal con todas las piezas del grupo en coordenadas de mundo. Devuelve (objeto, [(pieza, primer_loop, nº_loops)])."""
    import bmesh
    bm = bmesh.new(); mats = []; spans = []; total = 0
    for cn in chunk_names:
        o = CH.get(cn)
        if o is None: REPORT.append('AVISO: falta el chunk %s (grupo %s)' % (cn, name)); continue
        me = o.data.copy(); me.transform(o.matrix_world)
        remap = []
        for m in me.materials:
            if m not in mats: mats.append(m)
            remap.append(mats.index(m))
        n = len(me.polygons)
        if n and remap:
            arr = np.zeros(n, np.int32); me.polygons.foreach_get('material_index', arr)
            arr = np.array(remap, np.int32)[np.clip(arr, 0, len(remap) - 1)]; me.polygons.foreach_set('material_index', arr)
        spans.append((o, total, len(me.loops))); total += len(me.loops)
        bm.from_mesh(me); bpy.data.meshes.remove(me)
    mesh = bpy.data.meshes.new('_bake_' + name); bm.to_mesh(mesh); bm.free()
    for m in mats: mesh.materials.append(m)
    if len(mesh.loops) != total: raise RuntimeError('desajuste de esquinas en la malla temporal (%d frente a %d): alguna pieza tiene caras inválidas' % (len(mesh.loops), total))
    G.uv_clear(mesh, '')                                      # sin capas UV heredadas: solo la nuestra
    mesh.uv_layers.new(name='GEM2UV')
    ob = bpy.data.objects.new('_bake_' + name, mesh); sc.collection.objects.link(ob)
    return ob, spans

def select_only(ob):
    for o in sc.objects:
        try: o.select_set(False)
        except RuntimeError: pass                      # objetos ocultos (los originales de la parte 1)
    ob.select_set(True); vl.objects.active = ob

def unwrap(ob):
    select_only(ob); bpy.ops.object.mode_set(mode='EDIT')
    try:
        bpy.ops.mesh.select_all(action='SELECT'); sc.tool_settings.use_uv_select_sync = True
        bpy.ops.uv.smart_project(angle_limit=math.radians(ANGLE_LIMIT_DEG), island_margin=ISLAND_MARGIN)
        try: bpy.ops.uv.select_all(action='SELECT')
        except Exception: pass
        try: bpy.ops.uv.pack_islands(margin=ISLAND_MARGIN)
        except TypeError: bpy.ops.uv.pack_islands()
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')

def new_image(name, size):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True); img.colorspace_settings.name = 'Non-Color'; return img

def set_target(mats, img):
    for m in mats:
        nt = m.node_tree; node = nt.nodes.get('GEM2_BAKE') or nt.nodes.new('ShaderNodeTexImage')
        node.name = 'GEM2_BAKE'; node.image = img; node.select = True; nt.nodes.active = node

def clear_target(mats):
    for m in mats:
        node = m.node_tree.nodes.get('GEM2_BAKE')
        if node: m.node_tree.nodes.remove(node)

def bake(ob, kind, img, **kw):
    set_target(ob.data.materials, img); select_only(ob)
    bpy.ops.object.bake(type=kind, margin=MARGIN_PX, margin_type='EXTEND', use_clear=True, **kw)

def pixels(img):
    w, h = img.size; buf = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(buf); return buf.reshape(h, w, 4)

def metallic_off(mats):
    """Cycles hornea el color 'diffuse' multiplicado por (1 - metallic): con metal queda negro. Se apaga y se restaura después."""
    saved = []
    for m in mats:
        for n in m.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                s = n.inputs['Metallic']
                if not s.is_linked: saved.append((s, s.default_value)); s.default_value = 0.0
    return saved

# ---------------- BAKE POR GRUPOS ----------------
for gname, chunks in GROUPS.items():
    size = ATLAS_SIZE.get(gname, 2048)
    for cn in chunks:                                         # limpiar capas GEM2UV de ejecuciones anteriores
        if cn in CH: G.uv_clear(CH[cn].data, 'GEM2UV')
    ob, spans = build_scratch(gname, chunks)
    if not spans: bpy.data.objects.remove(ob); continue
    mats = list(ob.data.materials); ntris = len(ob.data.polygons)
    saved = []
    try:
        unwrap(ob)
        saved = metallic_off(mats)
        img_d, img_r = new_image(gname + '_diff', size), new_image(gname + '_rough', size)
        bake(ob, 'DIFFUSE', img_d, pass_filter={'COLOR'})
        bake(ob, 'ROUGHNESS', img_r)
        normal = None
        if BAKE_NORMAL:
            img_n = new_image(gname + '_norm', size); bake(ob, 'NORMAL', img_n, normal_space='TANGENT'); normal = pixels(img_n)
        paths = D.write_set(ENT_DIR, gname, pixels(img_d), pixels(img_r), normal, NORMAL_FLIP_Y, SPEC_SCALE)
        # UV -> cada pieza
        buf = G.uv_read(ob.data, 'GEM2UV')
        if buf is None or float(np.ptp(buf, axis=0).max()) < 1e-9: raise RuntimeError('el desenvolvido no produjo UV')
        bad = []
        for (o, start, n) in spans:
            ok = G.uv_write(o.data, 'GEM2UV', buf[start:start + n]); o['gem2_mtl'] = gname
            back = G.uv_read(o.data, 'GEM2UV')
            if not ok or back is None or float(np.ptp(back, axis=0).max()) < 1e-9: bad.append(o.name)
        if bad: REPORT.append('ERROR: UV no guardadas o vacías en %s: %s' % (gname, ', '.join(bad)))
        uvmin, uvmax = buf.min(0), buf.max(0)
        REPORT.append('%-18s %6d polígonos, %d piezas, atlas %d | UV en [%.2f..%.2f]x[%.2f..%.2f] | %s' % (gname, ntris, len(spans), size, uvmin[0], uvmax[0], uvmin[1], uvmax[1], ', '.join(paths)))
        for im in (img_d, img_r): bpy.data.images.remove(im)
    except Exception as e:
        REPORT.append('ERROR en %s: %s' % (gname, e))
    finally:
        for s, v in saved: s.default_value = v
        clear_target(mats)
        me = ob.data; bpy.data.objects.remove(ob); bpy.data.meshes.remove(me)

sc.render.engine = PREV_ENGINE                       # se devuelve el motor de render que tenías

# ---------------- INFORME ----------------
L = ['=== GEM2 parte 4 (texturas) ===', 'Salida: %s' % ENT_DIR] + REPORT + ['', 'Ahora vuelve a ejecutar la PARTE 3 para re-exportar los .ply con las UV y los materiales nuevos.']
informe = '\n'.join(L); print(informe)
tx = bpy.data.texts.get('GEM2_informe_parte4') or bpy.data.texts.new('GEM2_informe_parte4'); tx.clear(); tx.write(informe)
