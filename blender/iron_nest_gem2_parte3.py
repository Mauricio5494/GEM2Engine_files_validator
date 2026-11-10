"""
IRON NEST -> GEM2 | PARTE 3: exportar .ply (con LODs), .mtl, .mdl y un .anm de prueba
Requisitos: haber ejecutado las partes 1 y 2 en esta misma sesión (colección GEM2_export), y tener en MODULES_DIR los archivos
  gem2_ply.py, gem2_geom.py, gem2_mdl.py, gem2_anm.py
Salida (OUT_DIR, por defecto 'salida_mod' junto a los scripts) con la estructura del mod:
  mod.info
 
  resource/entity/-vehicle/iron_nest/: *.ply, *_lod1/2.ply, iron_nest.mtl, iron_nest.mdl (con {Volume}), iron_nest.def, move_normal.anm, puntos_s.txt
  resource/properties/iron_nest.ext
Mapa chunk -> hueso (ver SPEC): d_hull=body, d_turret=turret, d_gun_L/R=gun_rot_l/r (revolute, elevación), patas = hip/leg_upper/leg_lower/foot
(minúsculas, como en las referencias). Los pistones cuelgan de la pierna que los lleva (pose de reposo, estáticos).
LIMITACIONES CONOCIDAS (provisionales):
  - Un único material (iron_nest.mtl) y UV por proyección de caja: SIN texturas reales hasta hacer el bake.
  - Escala: se fija con TARGET_LENGTH_M (largo total en metros) y UNITS_PER_METER (calibrado con el E-100, ~22). Triángulos en orden inverso a Blender (como los .ply de referencia).
  - El .anm de prueba es un balanceo simple de cadera; su convención de ejes/signos no está comprobada en el juego.
"""
import bpy, bmesh, os, sys, math, importlib
import numpy as np
from mathutils import Vector

# ---------------- PARÁMETROS ----------------
MODULES_DIR = None           # carpeta con gem2_ply.py, gem2_geom.py, gem2_mdl.py, gem2_anm.py. None = se busca sola (ver abajo)
OUT_DIR = None               # None = subcarpeta 'salida_mod' dentro de MODULES_DIR
UNITS_PER_METER = 22.0       # unidades del .mdl por metro. Calibrado con el E-100: sus ruedas de carretera miden 9,0 unidades de radio y el .mdl declara Radius=0.41 m
TARGET_LENGTH_M = 24.0       # largo TOTAL deseado en metros (de la trasera a la boca de los cañones). None = usar UNITS_PER_BU tal cual
UNITS_PER_BU = 6.0           # solo se usa si TARGET_LENGTH_M es None
MAX_VERTS = 60000            # por encima de esto (vértices ya exportados) la malla se parte en varias
LOD_DEFAULT = (0.22, 0.10)   # razón de triángulos de lod1, lod2 (como body/turret del E-100)
LOD_LEG = (0.5, 0.25)        # más conservador para patas, pistones y piezas articuladas
MIN_TRIS_LOD = 300           # por debajo no se generan LODs
MTL_DEFAULT = 'iron_nest'  # material por defecto (nombre sin .mtl); la parte 4 asigna uno por grupo en obj['gem2_mtl']
TURRET_SPEED, GUN_SPEED = 0.004, 0.004   # velocidad de giro de los huesos revolute (valor del trípode, 0.004; el Panther usa 0.005). AJUSTAR si gira muy lento o muy rápido
GUN_LIMITS = (0, 60)         # elevación en grados (0 a 60, como el script original)
SEQUENCES = [('move', 0.2, 0.64)]
WRITE_TEST_ANM, SWING_DEG, ANM_FRAMES = True, 12.0, 40
CORNERS = ('FL', 'FR', 'BL', 'BR')
VOL_RULES = {'body': (120, 'body', 'body'), 'turret': (90, 'turret', 'turret'), 'engine': (400, 'no_target', None)}   # (espesor, tags, componente)
EXTRA_VOLUMES = False        # False: solo body, engine y turret (como lo mínimo del trípode). True: añade además pies, piernas, cañones... (vol_*)
OBSTACLE_BU = (8.3, 10.0)  # semiejes (largo, ancho) de la huella de pathfinding en unidades de Blender (se escala solo); None = sin bloque {Obstacle}
GROUND_CLIP = True           # recorta los volúmenes de tipo caja alineados a los ejes que quedan bajo z=0 (las púas de los pies): el modelo no nace dentro del terreno
LIFT_BU = 0.0                # sube TODO el modelo (unidades de Blender); si sigue 'saltando' al primer movimiento prueba 0.45
MOD_NAME = 'Iron_Nest'       # nombre del mod (carpeta mods/<MOD_NAME> y campo Name de mod.info)
MOD_DESC = 'Iron Nest - self-propelled four-legged artillery'
# GUN_FRAME: frame relativo a turret para la elevación de los cañones.
# Turret frame en .mdl: X=forward, Y=right, Z=up.
# Elevation axis must be horizontal = turret Y (right) or -turret Y (left).
# Frame con local Z = turret Y (right): X=fwd, Y=up, Z=right.
GUN_FRAME = ((1, 0, 0), (0, 0, 1), (0, 1, 0))               # local Z = turret Y = right (horizontal, elevation axis)

def _find_modules_dir():
    # prueba: el valor manual, la carpeta de cada script cargado desde disco en Blender y un par de rutas habituales
    cands = [MODULES_DIR] if MODULES_DIR else []
    for t in bpy.data.texts:
        if t.filepath: cands.append(os.path.dirname(bpy.path.abspath(t.filepath)))
    cands += [os.path.expanduser('~/Descargas/Iron_Nest_CTA_mod'), os.path.expanduser('~/Descargas'), os.path.expanduser('~/Downloads')]
    for d in cands:
        if d and os.path.exists(os.path.join(d, 'gem2_ply.py')): return d
    raise RuntimeError('No encuentro gem2_ply.py. Pon en MODULES_DIR la carpeta donde están gem2_ply.py, gem2_geom.py, gem2_mdl.py y gem2_anm.py. Probé: ' + ', '.join(c for c in cands if c))
MODULES_DIR = _find_modules_dir()
if OUT_DIR is None: OUT_DIR = os.path.join(MODULES_DIR, 'salida_mod')
if MODULES_DIR not in sys.path: sys.path.insert(0, MODULES_DIR)
import gem2_ply as P, gem2_geom as G, gem2_mdl as M, gem2_anm as A
for _m in (P, G, M, A): importlib.reload(_m)
ENT_DIR = os.path.join(OUT_DIR, 'resource', 'entity', '-vehicle', 'iron_nest')      # .ply .mtl .mdl .anm .def
PROP_DIR = os.path.join(OUT_DIR, 'resource', 'properties')                           # iron_nest.ext
os.makedirs(ENT_DIR, exist_ok=True); os.makedirs(PROP_DIR, exist_ok=True)

sc = bpy.context.scene; vl = bpy.context.view_layer
coll = bpy.data.collections.get('GEM2_export')
if not coll: raise RuntimeError("No existe 'GEM2_export': ejecuta antes las partes 1 y 2.")
CH = {o.name: o for o in coll.objects if o.type == 'MESH'}
PT = {o.name: o.matrix_world.translation.copy() for o in coll.objects if o.name.startswith('s_')}

# ---------------- ARMATURE: extraer transforms reales ----------------
arm_obj = bpy.data.objects.get('iron_nest_arm')
if not arm_obj or arm_obj.type != 'ARMATURE':
    raise RuntimeError("No se encuentra Armature 'iron_nest_arm'. Ejecuta iron_nest_blender.py primero (crea Armature + vertex groups).")

def get_armature_transforms(arm_obj):
    """Devuelve {bone_name: (pos_rel, rot_matrix_3x3)} en espacio del padre, desde pose bones.
    El .mdl usa convención row-vector: filas de Matrix34 = ejes locales en espacio del padre.
    Blender usa column-vector: columnas de Matrix = ejes locales en espacio del padre.
    Por tanto, hay que TRANSPONER la matriz de rotación (filas <-> columnas)."""
    bpy.context.view_layer.update()
    out = {}
    for pb in arm_obj.pose.bones:
        # Matriz world del hueso
        mat_w = arm_obj.matrix_world @ pb.matrix
        if pb.parent:
            pmat_w = arm_obj.matrix_world @ pb.parent.matrix
            rel = pmat_w.inverted() @ mat_w
        else:
            rel = mat_w
        pos = rel.translation
        rot = rel.to_3x3()
        # Transponer: frame[i][j] = rot[j][i] para que filas = ejes locales en espacio padre
        out[pb.name] = ([pos.x, pos.y, pos.z], [[rot[j][i] for j in range(3)] for i in range(3)])
    return out

ARM_TR = get_armature_transforms(arm_obj)
# tamaño total del modelo (unidades de Blender) y escala resultante
_lo = np.full(3, 1e9); _hi = np.full(3, -1e9)
for _o in CH.values():
    _bb = np.array([tuple(c) for c in _o.bound_box], np.float64) + np.array(tuple(_o.matrix_world.translation), np.float64)
    _lo = np.minimum(_lo, _bb.min(0)); _hi = np.maximum(_hi, _bb.max(0))
SIZE_BU = _hi - _lo
if TARGET_LENGTH_M: UNITS_PER_BU = TARGET_LENGTH_M * UNITS_PER_METER / float(SIZE_BU[0])

# ---------------- MAPA CHUNK -> HUESO ----------------
# Jerarquía oficial GEM RTS (docs.bestway.com.ua):
# basis (root, Y-mirror) -> body -> turret -> gun_rot/gun1_rot -> gun/gun1
# Helper bones: driver, gunner, commander, charger, gunner2, emit0-2, seat01/02, visor1/02, tps
SPEC = []
def add(bone, parent, chunk=None, kind='fixed', params=None, frame=None, limits=None, pivot=None, speed=None):
    SPEC.append(dict(bone=bone, parent=parent, chunk=chunk, kind=kind, params=params, frame=frame, limits=limits, pivot=pivot, speed=speed))

# Raíz oficial: basis (en origen mundial, Y-mirror handled by exporter)
add('basis', None, None, params='id=basis;')
# Body: hijo de basis
add('body', 'basis', 'd_hull', params='id=body;')
add('door_rear', 'body', 'd_door_rear')
for c in CORNERS: add('hipmount_' + c.lower(), 'body', 'd_hipmount_' + c)
# Engine (invisible helper) - pivote en parte trasera del casco
add('engine', 'body', None, params='id=engine;', pivot=(-4.5, 0.0, 2.0))

# Turret: hijo de body, revolute para giro
add('turret', 'body', 'd_turret', 'revolute', 'id=turret;', speed=TURRET_SPEED)
for ch, bn in (('d_periscope', 'periscope'), ('d_horns', 'horns'), ('d_hatch', 'hatch'), ('d_roof_vent', 'roof_vent'),
               ('d_visor', 'visor'), ('d_headlights', 'headlights'), ('d_turret_rear', 'turret_rear')):
    add(bn, 'turret', ch, params='id=turret;')

# Tripulación: asientos en torreta (según doc: driver, gunner, commander, charger, gunner2)
add('driver', 'turret', None, pivot=(0.5, 0.0, 10.6))
add('gunner', 'turret', None, pivot=(0.5, -1.0, 10.6))
add('commander', 'turret', None, pivot=(0.5, 1.0, 11.0))
add('charger', 'turret', None, pivot=(-1.0, 0.0, 10.0))
add('gunner2', 'turret', None, pivot=(0.0, 0.0, 13.0))  # AA gunner

# Emit bones (crew hatches): emit0 en torreta, emit1/emit2 en suelo
add('emit0', 'turret', None, pivot=(-2.0, 0.0, 2.0))  # hatch de torreta
add('emit1', 'basis', None, pivot=(-9.8, 0.0, 0.0))   # suelo atrás
add('emit2', 'basis', None, pivot=(9.8, 0.0, 0.0))    # suelo adelante

# Seat bones (paired with emit)
add('seat01', 'turret', None, pivot=(0.5, 0.0, 11.1))
add('seat02', 'turret', None, pivot=(0.5, -1.0, 11.1))

# Vision helpers
add('visor1', 'turret', None, pivot=(5.0, 0.0, 3.0))
add('visor2', 'body', None, pivot=(5.0, 0.0, 2.0))

# tps: ancla cámara 3ª persona
add('tps', 'turret', None, pivot=(0.0, 0.0, 15.0))

# Cañones: gun_rot/gun1_rot son revolute para elevación (eje Z local = horizontal right)
GUN_BONES = {'L': ('gun_rot', 'gun', 'id=gun;'), 'R': ('gun1_rot', 'gun1', 'id=gun1;')}
for s in ('L', 'R'):
    k = s.lower(); rot, gun, gid = GUN_BONES[s]
    # Elevation: IKType=revolute, limits 0-60°, eje Z local = turret Y (right)
    add(rot, 'turret', 'd_gun_L' if s == 'L' else 'd_gun_R', 'revolute', gid, GUN_FRAME, GUN_LIMITS, speed=GUN_SPEED)
    add(gun, rot, None, params=gid, pivot='s_gun_muzzle_' + s)
    add('elev_ram_' + k, rot, 'p_elev_ram_' + s)

# Patas cuadrúpedas (custom walker, no estándar GEM RTS)
for c in CORNERS:
    k = c.lower(); lid = 'id=leg_%s;' % k
    add('hip_' + k, 'body', 'd_hip_' + c, params=lid)
    add('leg_upper_' + k, 'hip_' + k, 'd_leg_upper_' + c, params=lid)
    add('leg_lower_' + k, 'leg_upper_' + k, 'd_leg_lower_' + c, params=lid)
    add('foot_' + k, 'leg_lower_' + k, 'd_foot_' + c, params=lid)
    add('piston_hip_' + k, 'leg_upper_' + k, 'p_piston_hip_' + c)
    add('piston_knee_' + k, 'leg_upper_' + k, 'p_piston_knee_' + c)
    add('piston_ankle_' + k, 'leg_lower_' + k, 'p_piston_ankle_' + c)

# ---------------- GEOMETRÍA ----------------
def mesh_corners(me):
    """(pos, nrm) por esquina de triángulo, en coordenadas locales de la malla (relativas al pivote)."""
    me.calc_loop_triangles(); nt = len(me.loop_triangles)
    if nt == 0: return None
    nv = len(me.vertices); co = np.empty(nv * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    lt = np.empty(nt * 3, np.int32); me.loop_triangles.foreach_get('loops', lt)
    vt = np.empty(nt * 3, np.int32); me.loop_triangles.foreach_get('vertices', vt)
    if hasattr(me, 'corner_normals'):
        nl = np.empty(len(me.corner_normals) * 3, np.float32); me.corner_normals.foreach_get('vector', nl)
    else:
        me.calc_normals_split(); nl = np.empty(len(me.loops) * 3, np.float32); me.loops.foreach_get('normal', nl)
    return co[vt], nl.reshape(-1, 3)[lt], lt

def arrays(me, frame):
    got = mesh_corners(me)
    if got is None: return None
    pos, nrm, lt = got
    uvl = G.uv_read(me, 'GEM2UV') if hasattr(me, 'uv_layers') else None
    if uvl is not None:                                       # UV reales hechas por la parte 4 (con el atlas de texturas)
        uv = uvl[lt].copy()
        if float(np.ptp(uv, axis=0).max()) < 1e-9: REPORT.append('AVISO: la capa GEM2UV de %s está vacía (todas las UV iguales): repite la parte 4' % me.name)
        uv[:, 1] = 1.0 - uv[:, 1]                             # v de DirectX: origen arriba (la parte 4 escribe los DDS con la fila 0 arriba)
        tan = G.tangents_from_uv(pos, nrm, uv)
    else: uv, tan = G.box_uv(pos)                              # sin UV: proyección de caja provisional
    if frame: pos, nrm, tan = (G.to_frame(v, frame) for v in (pos, nrm, tan))
    return (pos * UNITS_PER_BU).astype(np.float32), nrm.astype(np.float32), uv, tan.astype(np.float32)

def decimated(me, ratio):
    tmp = bpy.data.objects.new('_tmp_lod', me.copy()); sc.collection.objects.link(tmp)
    m = tmp.modifiers.new('d', 'DECIMATE'); m.ratio = ratio
    vl.update(); dg = bpy.context.evaluated_depsgraph_get()
    out = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    d = tmp.data; bpy.data.objects.remove(tmp); bpy.data.meshes.remove(d)
    return out

def split_mesh(me, k):
    n = len(me.polygons); cen = np.empty(n * 3, np.float32); me.polygons.foreach_get('center', cen); cen = cen.reshape(-1, 3)
    ax = int(np.argmax(cen.max(0) - cen.min(0))); order = np.argsort(cen[:, ax], kind='stable'); grp = np.empty(n, np.int32)
    for gi, part in enumerate(np.array_split(order, k)): grp[part] = gi
    out = []
    for gi in range(k):
        bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if grp[f.index] != gi], context='FACES')
        m2 = bpy.data.meshes.new('%s_p%d' % (me.name, gi + 1)); bm.to_mesh(m2); bm.free(); out.append(m2)
    return out

def write_ply(fname, arrs, mtl):
    p = P.make(*arrs, mtl=mtl); open(os.path.join(ENT_DIR, fname), 'wb').write(P.write(p)); return p.nv, p.ntris

def process_chunk(bone, obj, frame):
    ratios = LOD_LEG if bone.startswith(('hip_', 'leg_', 'foot_', 'piston_', 'hipmount_', 'elev_ram', 'gun_rot', 'gun1_rot')) else LOD_DEFAULT
    mtl_name = obj.get('gem2_mtl', MTL_DEFAULT) + '.mtl'; USED_MTL.add(mtl_name)
    me = obj.data; base = arrays(me, frame)
    if base is None: return []
    nv = P.count_unique(*base); k = max(1, math.ceil(nv / (MAX_VERTS * 0.85)))
    meshes = [me] if k == 1 else split_mesh(me, k); parts = []
    for pi, m in enumerate(meshes):
        pname = bone if pi == 0 else '%s_p%d' % (bone, pi + 1); files, stats = [], []
        a0 = arrays(m, frame)
        if a0 is None: continue
        nlod = len(ratios) if len(a0[0]) // 3 >= MIN_TRIS_LOD else 0
        for li in range(nlod + 1):
            if li == 0: arrs, mm = a0, None
            else:
                mm = decimated(m, ratios[li - 1]); arrs = arrays(mm, frame)
                if arrs is None:
                    bpy.data.meshes.remove(mm); break
            fn = '%s.ply' % pname if li == 0 else '%s_lod%d.ply' % (pname, li)
            try: stats.append(write_ply(fn, arrs, mtl_name)); files.append(fn)
            except ValueError as e: REPORT.append('ERROR %s: %s' % (fn, e))
            if mm is not None: bpy.data.meshes.remove(mm)
        if pi > 0: bpy.data.meshes.remove(m)
        if files: parts.append((pname, files, stats))
    return parts

# ---------------- EXPORTAR ----------------
REPORT = []; USED_MTL = set()
bones, tot_files = [], 0
for sp in SPEC:
    obj = CH.get(sp['chunk']) if sp['chunk'] else None
    bone_name = sp['bone']

    # Obtener transform desde Armature (prioritario) o fallback a pivot manual
    if bone_name in ARM_TR:
        pos_local, rot_matrix_rel = ARM_TR[bone_name]   # relativa al padre (row-vector) -> va al .mdl
        # Aplicar escala y LIFT_BU
        pos = (pos_local[0] * UNITS_PER_BU, pos_local[1] * UNITS_PER_BU, (pos_local[2] + LIFT_BU) * UNITS_PER_BU)
        frame_mdl = rot_matrix_rel                       # orientación del hueso relativa al padre (.mdl)
        # Rotación MUNDIAL del hueso para llevar la geometría (en espacio mundial por Parte 1) al espacio local del hueso
        bpy.context.view_layer.update()
        pb = arm_obj.pose.bones[bone_name]
        mat_bone_w = arm_obj.matrix_world @ pb.matrix
        R_world = mat_bone_w.to_3x3()
        frame_geom = [[R_world[j][i] for j in range(3)] for i in range(3)]   # transpuesta para to_frame()
    else:
        # Fallback: pivote manual (para huesos sin Armature como driver, emit1, emit2, tps)
        if sp['pivot']: pv = sp['pivot'] if isinstance(sp['pivot'], tuple) else PT.get(sp['pivot'])
        elif obj: pv = obj.matrix_world.translation
        else: pv = None
        if pv is None:
            REPORT.append('AVISO: sin pivote para el hueso %s (falta %s)' % (bone_name, sp['pivot'] or sp['chunk'])); continue
        pos = (float(pv[0]) * UNITS_PER_BU, float(pv[1]) * UNITS_PER_BU, (float(pv[2]) + LIFT_BU) * UNITS_PER_BU)
        frame_mdl = sp['frame'] if sp['frame'] else ((1,0,0),(0,1,0),(0,0,1))
        frame_geom = frame_mdl

    if sp['chunk'] and not obj: REPORT.append('AVISO: falta el chunk %s (hueso %s sin malla)' % (sp['chunk'], bone_name))
    parts = process_chunk(bone_name, obj, frame_geom) if obj else []
    first = parts[0] if parts else None
    bones.append(M.Bone(bone_name, sp['parent'], sp['kind'], sp['params'], pos, frame_mdl, sp['limits'], first[1] if first else (), speed=sp['speed']))
    for pname, files, stats in parts[1:]:                 # partes extra: huesos fijos hijos, en el mismo sitio y con el mismo sistema local
        bones.append(M.Bone(pname, bone_name, 'fixed', sp['params'], pos, frame_mdl, None, files))
    for pname, files, stats in parts:
        tot_files += len(files)
        REPORT.append('%-18s %s' % (pname, ' | '.join('%s: %dv %dt' % (f.replace(pname, '').replace('.ply', '') or 'lod0', v, t) for f, (v, t) in zip(files, stats))))

for mn in sorted(USED_MTL):                               # un .mtl por material; texturas junto a él, sin ruta (como e-100c.mtl)
    b0 = mn[:-4]
    open(os.path.join(ENT_DIR, mn), 'w', newline='').write('{material bump\r\n\t{diffuse "%s_am"}\r\n\t{bump "%s_nm"}\r\n\t{specular "%s_gmm"}\r\n\t{color "229 229 229 25"}\r\n\t{blend none}\r\n}' % (b0, b0, b0))
REPORT.append('materiales: ' + ', '.join(sorted(USED_MTL)))
# volúmenes de daño: las primitivas de GEM2_phys (parte 2) -> {Volume ... {Box|Cylinder}} colgando del hueso que lleva ese chunk
vols = []; physc = bpy.data.collections.get('GEM2_phys'); chunk2bone = {sp['chunk']: sp['bone'] for sp in SPEC if sp['chunk']}; bmap = {b.name: b for b in bones}
for o in (physc.objects if physc else []):
    kind = o.get('gem2_kind')
    if not kind: continue
    cname = o.name[:-5] if o.name.endswith('.phys') else o.name; sfx = ''
    for t in ('_sleeve', '_barrel'):
        if cname.endswith(t): cname, sfx = cname[:-len(t)], t
    bn = chunk2bone.get(cname)
    if bn not in bmap: REPORT.append('AVISO: la primitiva %s no tiene hueso' % o.name); continue
    ax = [float(x) for x in o['gem2_ax']]; dim = [float(x) * UNITS_PER_BU for x in o['gem2_dim']]; cen = [float(x) * UNITS_PER_BU for x in o['gem2_c']]
    if kind == 'BOX':                                       # semialtura en Z del volumen (cualquier orientación)
        half = sum(abs(ax[3 * i + 2]) * dim[i] / 2 for i in range(3)); bottom = cen[2] - half
        if bottom < -1e-4:
            axis_aligned = all(abs(ax[3 * i + 2]) > .999 or abs(ax[3 * i + 2]) < 1e-3 for i in range(3))
            k = next((i for i in range(3) if abs(ax[3 * i + 2]) > .999), None)
            if GROUND_CLIP and axis_aligned and k is not None:
                cut = -bottom; dim[k] -= cut; cen[2] += cut / 2; REPORT.append('volumen %s recortado %.2f unidades por debajo del suelo' % (o.name, cut))
            else: REPORT.append('AVISO: el volumen %s queda %.2f unidades bajo el suelo (no se recorta)' % (o.name, -bottom))
    cen[2] += LIFT_BU * UNITS_PER_BU
    vols.append(dict(name=bn if (bn in ('body', 'turret') and not sfx) else 'vol_' + bn + sfx, kind=kind, bone=bn, dim=dim, center=cen, axes=[ax[0:3], ax[3:6], ax[6:9]]))
if not any(v['name'] == 'body' for v in vols) or not any(v['name'] == 'turret' for v in vols):
    raise RuntimeError("Faltan los volúmenes 'body'/'turret': no hay primitivas físicas con metadatos. Abre iron_nest_gem2_parte2.py, pulsa Alt+R (recargar), ejecútalo y vuelve a ejecutar esta parte.")
bv = next(v for v in vols if v['name'] == 'body')
vols.append(dict(name='engine', kind='BOX', bone='body', dim=[x * 0.5 for x in bv['dim']], center=list(bv['center']), axes=[list(a) for a in bv['axes']]))   # 'existe solo formalmente', como en el trípode
if not EXTRA_VOLUMES: vols = [v for v in vols if v['name'] in ('body', 'engine', 'turret')]
open(os.path.join(ENT_DIR, 'iron_nest.mdl'), 'w', encoding='latin-1', newline='').write(M.build(bones, SEQUENCES, note='Iron Nest (Blender) - escala %.1f unidades/BU' % UNITS_PER_BU))
open(os.path.join(OUT_DIR, 'mod.info'), 'w', encoding='utf-8', newline='').write(   # mismo formato que el mod.info de ASV_War_Worlds
    '{Mod\r\n\t{Name "%s"}\r\n\t{Desc "%s"}\r\n\t{minGameVersion "From Dusk"}\r\n\t{maxGameVersion "Till Dawn"}\r\n}\r\n' % (MOD_NAME, MOD_DESC))
open(os.path.join(PROP_DIR, 'iron_nest.ext'), 'w', encoding='utf-8', newline='').write(M.EXT_TEXT.replace('\n', '\r\n'))
open(os.path.join(ENT_DIR, 'iron_nest.def'), 'w', encoding='utf-8', newline='').write(M.build_def(vols, vol_rules=VOL_RULES))
REPORT.append('volúmenes en el .mdl: %d' % len(vols))
with open(os.path.join(ENT_DIR, 'puntos_s.txt'), 'w') as f:
    for n in sorted(PT): f.write('%-18s %.4f %.4f %.4f\n' % ((n,) + tuple(float(x) * UNITS_PER_BU for x in PT[n])))

# ---------------- .anm DE PRUEBA ----------------
if WRITE_TEST_ANM:
    # Usar transforms del Armature para el .anm
    rel = ARM_TR
    names = []
    for c in CORNERS: names += [n + '_' + c.lower() for n in ('hip', 'leg_upper', 'leg_lower', 'foot')]
    if all(n in rel for n in names):
        idx = {n: i for i, n in enumerate(names)}; q0 = A.encode_quat((0, 0, 0, 1))
        frames = [(0, {idx[n]: (0x0b, tuple(rel[n][0]), q0) for n in names})]
        for i in range(1, ANM_FRAMES):
            ups = {}
            for c in CORNERS:
                ph = 0.0 if c in ('FL', 'BR') else math.pi
                a = math.radians(SWING_DEG) * math.sin(2 * math.pi * i / ANM_FRAMES + ph)
                ups[idx['hip_' + c.lower()]] = (2, None, A.encode_quat((0, math.sin(a / 2), 0, math.cos(a / 2))))
            frames.append((i, ups))
        A.write(os.path.join(ENT_DIR, 'move.anm'), names, frames)
        REPORT.append('move.anm: %d frames, %d huesos (balanceo de cadera de prueba)' % (ANM_FRAMES, len(names)))
    else: REPORT.append('AVISO: no se escribió el .anm (faltan huesos de patas en Armature)')

# ---------------- INFORME ----------------
_m = SIZE_BU * UNITS_PER_BU / UNITS_PER_METER
L = ['=== GEM2 parte 3 ===', 'Salida: %s' % OUT_DIR, 'Huesos: %d | .ply escritos: %d | escala: %.2f unidades/BU' % (len(bones), tot_files, UNITS_PER_BU),
     'Tamaño: %.1f x %.1f x %.1f unidades de Blender (largo x ancho x alto) = %.1f x %.1f x %.1f m (a %.1f unidades/m)' % (tuple(SIZE_BU) + tuple(_m) + (UNITS_PER_METER,)),
     'Para PATHER.SET: pon {Radius %.1f} en el perfil "iron_nest" (mitad del ancho en metros)' % (_m[1] / 2)] + REPORT
informe = '\n'.join(L); print(informe)
tx = bpy.data.texts.get('GEM2_informe_parte3') or bpy.data.texts.new('GEM2_informe_parte3'); tx.clear(); tx.write(informe)
