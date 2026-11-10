#!/usr/bin/env python3
"""
IRON NEST -> GEM2 | Export maestro usando el plugin gem2_goh_tools (ExportGEM2Multipart).
Uso: flatpak run org.blender.Blender --background --python export_gem2_plugin.py

Pipeline:
  0. Limpia escena
  1. Ejecuta iron_nest_blender.py  (geometría + armature + materiales)
  2. Ejecuta iron_nest_gem2_parte1.py (chunks en colección GEM2_export)
  3. Ejecuta iron_nest_gem2_parte2.py (puntos s_ + GEM2_phys)
  4. Prepara meshes: UV layer + vertex groups (nombres de huesos del armature)
  5. Exporta con el plugin GEM2 (.mdl, .ply, .mtl, .def genérico)
  6. Sobrescribe .def y .ext con los correctos de salida_mod/
  7. Genera .anm, puntos_s.txt, mod.info
"""
import bpy, os, sys, math, struct, datetime
from mathutils import Vector, Matrix

mod_dir = "/home/sparky/Descargas/Iron_Nest_CTA_mod"
if mod_dir not in sys.path:
    sys.path.insert(0, mod_dir)

OUT_DIR = os.path.join(mod_dir, "salida_mod")
ENT_DIR = os.path.join(OUT_DIR, "resource", "entity", "-vehicle", "iron_nest")
PROP_DIR = os.path.join(OUT_DIR, "resource", "properties")
os.makedirs(ENT_DIR, exist_ok=True)
os.makedirs(PROP_DIR, exist_ok=True)

LOG = []
def log(msg):
    LOG.append(msg)
    print(msg)

# ============================================================
# 0. LIMPIAR ESCENA
# ============================================================
log("=== 0. Limpiando escena ===")
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.textures,
             bpy.data.actions, bpy.data.armatures):
    for b in list(coll):
        try:
            coll.remove(b)
        except Exception:
            pass

# ============================================================
# 1. PARTE 0: geometría + armature
# ============================================================
log("=== 1. Ejecutando iron_nest_blender.py ===")
exec(compile(open(os.path.join(mod_dir, "iron_nest_blender.py"), "rb").read(),
             "iron_nest_blender.py", 'exec'))

# ============================================================
# 2. PARTE 1: chunks GEM2_export
# ============================================================
log("=== 2. Ejecutando iron_nest_gem2_parte1.py ===")
exec(compile(open(os.path.join(mod_dir, "iron_nest_gem2_parte1.py"), "rb").read(),
             "iron_nest_gem2_parte1.py", 'exec'))

# ============================================================
# 3. PARTE 2: puntos s_ + GEM2_phys
# ============================================================
log("=== 3. Ejecutando iron_nest_gem2_parte2.py ===")
exec(compile(open(os.path.join(mod_dir, "iron_nest_gem2_parte2.py"), "rb").read(),
             "iron_nest_gem2_parte2.py", 'exec'))

# ============================================================
# 4. PREPARAR MESHES PARA EL EXPORTADOR GEM2
# ============================================================
log("=== 4. Preparando meshes (UVs + vertex groups) ===")
arm_obj = bpy.data.objects.get('iron_nest_arm')
if not arm_obj or arm_obj.type != 'ARMATURE':
    raise RuntimeError("No se encuentra Armature 'iron_nest_arm'")

coll = bpy.data.collections.get('GEM2_export')
if not coll:
    raise RuntimeError("No existe la colección 'GEM2_export'")

meshes = [o for o in coll.objects if o.type == 'MESH']
log(f"  Meshes en GEM2_export: {len(meshes)}")

# Mapeo chunk -> nombre de hueso del armature
bone_map = {
    'd_hull':        'body',
    'd_turret':      'turret',
    'd_gun_L':       'gun_rot',
    'd_gun_R':       'gun1_rot',
    'd_door_rear':   'body',
    'd_periscope':   'turret',
    'd_horns':       'turret',
    'd_hatch':       'turret',
    'd_roof_vent':   'turret',
    'd_visor':       'turret',
    'd_headlights':  'turret',
    'd_turret_rear': 'turret',
    'd_hipmount_fl': 'body',
    'd_hipmount_fr': 'body',
    'd_hipmount_bl': 'body',
    'd_hipmount_br': 'body',
    'p_elev_ram_l':  'elev_ram_l',
    'p_elev_ram_r':  'elev_ram_r',
}
for corner in ('fl', 'fr', 'bl', 'br'):
    bone_map[f'd_hip_{corner}']         = f'hip_{corner}'
    bone_map[f'd_leg_upper_{corner}']   = f'leg_upper_{corner}'
    bone_map[f'd_leg_lower_{corner}']   = f'leg_lower_{corner}'
    bone_map[f'd_foot_{corner}']        = f'foot_{corner}'
    bone_map[f'p_piston_hip_{corner}']  = f'piston_hip_{corner}'
    bone_map[f'p_piston_knee_{corner}'] = f'piston_knee_{corner}'
    bone_map[f'p_piston_ankle_{corner}'] = f'piston_ankle_{corner}'

bone_names = set(b.name for b in arm_obj.data.bones)
log(f"  Huesos en armature: {len(bone_names)}")

for obj in meshes:
    me = obj.data

    # --- Asegurar material (el plugin lo requiere) ---
    if not me.materials:
        m = bpy.data.materials.new(obj.name + "_mat")
        me.materials.append(m)

    # --- Asegurar UV layer activo (el plugin lo requiere) ---
    if not me.uv_layers:
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(me)
        uv_layer = bm.loops.layers.uv.new()
        for face in bm.faces:
            for loop in face.loops:
                loop[uv_layer].uv = (0.5, 0.5)
        bm.to_mesh(me)
        bm.free()
        me.uv_layers.active = me.uv_layers[0]

    # --- Vertex group con nombre del hueso ---
    bone_name = bone_map.get(obj.name, 'body')
    if bone_name not in bone_names:
        log(f"  AVISO: hueso '{bone_name}' no existe en armature, usando 'body'")
        bone_name = 'body'
    vg = obj.vertex_groups.get(bone_name)
    if vg is None:
        vg = obj.vertex_groups.new(name=bone_name)
    vg.add(range(len(me.vertices)), 1.0, 'REPLACE')

    # --- Modificador Armature ---
    mod = obj.modifiers.get('Armature')
    if mod is None:
        mod = obj.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm_obj
    mod.use_vertex_groups = True
    mod.use_bone_envelopes = False

log("  Meshes preparados.")

# ============================================================
# 5. EXPORTAR CON EL PLUGIN GEM2
# ============================================================
log("=== 5. Exportando con plugin gem2_goh_tools ===")
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:
    obj.select_set(True)
if meshes:
    bpy.context.view_layer.objects.active = meshes[0]

bpy.context.view_layer.update()

# Importar la función de exportación del plugin
sys.path.insert(0, "/home/sparky/.var/app/org.blender.Blender/config/blender/5.2/scripts/addons")
from gem2_goh_tools.multipart_export import export_selected_model

output_mdl = os.path.join(ENT_DIR, "iron_nest.mdl")
log(f"  Exportando a: {output_mdl}")
summary = export_selected_model(
    bpy.context,
    output_mdl,
    use_selection=True,
    record_limit=65535,
    material_mode="SIMPLE",
    copy_textures=False,
)
log(f"  Export OK: {summary.get('triangles', '?')} tris, "
    f"{summary.get('parts', '?')} parts, {summary.get('total_records', '?')} records")

# Guardar copia del .mdl del plugin antes de cualquier sobrescritura
import shutil
plugin_mdl_backup = os.path.join(ENT_DIR, 'iron_nest_plugin_raw.mdl')
if os.path.exists(output_mdl):
    shutil.copy2(output_mdl, plugin_mdl_backup)
    log(f"  Copia de seguridad del .mdl del plugin: {plugin_mdl_backup}")

# ============================================================
# 6. SOBRESCRIBIR .def Y .ext CON LOS CORRECTOS
# ============================================================
log("=== 6. Escribiendo .def y .ext correctos ===")

# .def correcto (con {volume}, {Weaponry}, {Extension})
def_text = """{game_entity
\t(include "/properties/iron_nest.ext")

\t{volume "body" {thickness 120} {tags "body"} {component "body"}}
\t{volume "turret" {thickness 90} {tags "turret"} {component "turret"}}
\t{volume "engine" {thickness 400} {tags "no_target"}}

\t{sensor
\t\t{visor "main"
\t\t\t{vision "tank_range_220"}
\t\t}
\t}

\t{Weaponry
\t\t{RestoreIKTime 4}
\t\t{place "gun"
\t\t\t{RestoreIKAfterAim}
\t\t\t{weapon "128mm_pak44" filling "bulletger_128 apcbche" 1}
\t\t\t{gunner "driver"}
\t\t\t{charger "driver"}
\t\t\t("abm_dymamic_stabilised"
\t\t\t\tzeroing(3.0)
\t\t\t\tdispersion(0.20)
\t\t\t)
\t\t}
\t\t{place "gun1"
\t\t\t{RestoreIKAfterAim}
\t\t\t{weapon "128mm_pak44" filling "bulletger_128 apcbche" 1}
\t\t\t{gunner "driver"}
\t\t\t{charger "driver"}
\t\t\t("abm_dymamic_stabilised"
\t\t\t\tzeroing(3.0)
\t\t\t\tdispersion(0.20)
\t\t\t)
\t\t}
\t}

\t{mass 175000}

\t{Extension "iron_nest.mdl"}
}
"""
with open(os.path.join(ENT_DIR, "iron_nest.def"), 'w', encoding='utf-8', newline='') as f:
    f.write(def_text)
log("  iron_nest.def escrito")

# .ext correcto (con include paths con barra inicial y brain_vehicle)
ext_text = """actor
(include "/properties/abm.inc")
(include "/properties/mobility.inc")
(include "/properties/vehicle.ext")
(include "/properties/armor.ext")
(include "/properties/tank_crew.ext")
(include "/scripts/abm/heavyart.inc")

{props "steel" "vehicle" "hatch" "obstacle_ignore_height" "iron_nest_walk"}
("brain_vehicle" args walker)

{collider "tank.heavy"}
{PatherId "iron_nest"}
{lodclass "vehicle"}
{targetclass "tank_heavy"}
{targetSelector "tank_heavy"}

("basic_armor" args 99)
("general_durability" body(250) engine(150) turret(150) mantlet(150) gun(150) track(150) ammo(120))

; Un único tripulante (el Iron Nest original lo maneja todo con un operador): plantilla base de tank_crew.ext.
; Necesita en el .mdl los huesos: driver (asiento), emit1 y emit2 (puertas por las que sube).
("crew_inside")
("crew_human" place(driver) door(emit1) door2(emit2) visor(none))

{extender "inventory"
\t{box
\t\t{Size 9 12}
\t\t{Weight 15000}
\t\t{item "can" 1}
\t\t{item "repair_kit" 5}
\t\t{item "bulletger_128 apcbche" 30}
\t\t{item "bulletger_128 he" 30}
\t}
}

{Chassis "human_carrier"
\t{Locomotion
\t\t{maxspeed   25}
\t\t{maxSpeedAtMaxTurn 25}
\t\t{StartTime  0.1}
\t\t{TurnTime   30}
\t\t{TurnRadius 90}
\t\t{TurnStart  0.01}
\t\t{BrakeTime  0.001}
\t\t{TurnStop   0.5}
\t\t{Gears 1.0}
\t\t{RearGears 1.0}
\t\t{GearSwitchDelay 0.1}
\t\t{StopTime   0.1}
\t\t{Slow   25}
\t\t{Normal 25}
\t\t{Fast   25}
\t}
\t{FuelBag
\t\t{volume 500}
\t\t{rate   1}
\t\t{remain 500}
\t\t{fuel "fuel"}
\t}
\t{dontUseSlope}
\t{disableBackward}
}

{NoGroupMesh 1}
{Volume "inventory" {thickness 10} {tags "no_target"}}
"""
with open(os.path.join(PROP_DIR, "iron_nest.ext"), 'w', encoding='utf-8', newline='') as f:
    f.write(ext_text)
log("  iron_nest.ext escrito")

# ============================================================
# 7. GENERAR .anm, puntos_s.txt, mod.info
# ============================================================
log("=== 7. Generando .anm, puntos_s.txt, mod.info ===")

# --- .anm: animación de balanceo de cadera para las 16 huesos de patas ---
import importlib
spec = importlib.util.spec_from_file_location("gem2_anm", os.path.join(mod_dir, "gem2_anm.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)

CORNERS = ('FL', 'FR', 'BL', 'BR')
SWING_DEG = 12.0
ANM_FRAMES = 40

# Obtener transforms del armature (posición relativa al padre)
bpy.context.view_layer.update()
def get_armature_transforms(arm_obj):
    out = {}
    for pb in arm_obj.pose.bones:
        mat_w = arm_obj.matrix_world @ pb.matrix
        if pb.parent:
            pmat_w = arm_obj.matrix_world @ pb.parent.matrix
            rel = pmat_w.inverted() @ mat_w
        else:
            rel = mat_w
        out[pb.name] = ([rel.translation.x, rel.translation.y, rel.translation.z],
                        [[rel.to_3x3()[j][i] for j in range(3)] for i in range(3)])
    return out

ARM_TR = get_armature_transforms(arm_obj)
names = []
for c in CORNERS:
    names += [n + '_' + c.lower() for n in ('hip', 'leg_upper', 'leg_lower', 'foot')]

if all(n in ARM_TR for n in names):
    idx = {n: i for i, n in enumerate(names)}
    q0 = A.encode_quat((0, 0, 0, 1))
    frames = [(0, {idx[n]: (0x0b, tuple(ARM_TR[n][0]), q0) for n in names})]
    for i in range(1, ANM_FRAMES):
        ups = {}
        for c in CORNERS:
            ph = 0.0 if c in ('FL', 'BR') else math.pi
            a = math.radians(SWING_DEG) * math.sin(2 * math.pi * i / ANM_FRAMES + ph)
            ups[idx['hip_' + c.lower()]] = (2, None, A.encode_quat((0, math.sin(a / 2), 0, math.cos(a / 2))))
        frames.append((i, ups))
    A.write(os.path.join(ENT_DIR, 'move.anm'), names, frames)
    log(f"  move.anm escrito: {ANM_FRAMES} frames, {len(names)} huesos")
else:
    missing = [n for n in names if n not in ARM_TR]
    log(f"  AVISO: no se escribió move.anm (faltan huesos: {missing})")

# --- puntos_s.txt ---
coll_s = bpy.data.collections.get('GEM2_export')
PT = {}
if coll_s:
    for o in coll_s.objects:
        if o.name.startswith('s_'):
            PT[o.name] = o.matrix_world.translation.copy()

# Necesitamos UNITS_PER_BU para escalar los puntos s_
# Recalcular tamaño total como lo hace parte3
CH = {o.name: o for o in coll.objects if o.type == 'MESH'}
_lo = [1e9, 1e9, 1e9]
_hi = [-1e9, -1e9, -1e9]
for o in CH.values():
    bb = np_array = [[c[0], c[1], c[2]] for c in o.bound_box]
    import numpy as np
    bb_arr = np.array(bb, np.float64) + np.array(tuple(o.matrix_world.translation), np.float64)
    _lo = np.minimum(_lo, bb_arr.min(0))
    _hi = np.maximum(_hi, bb_arr.max(0))
SIZE_BU = _hi - _lo
UNITS_PER_METER = 22.0
TARGET_LENGTH_M = 24.0
UNITS_PER_BU = TARGET_LENGTH_M * UNITS_PER_METER / float(SIZE_BU[0])

with open(os.path.join(ENT_DIR, 'puntos_s.txt'), 'w') as f:
    for n in sorted(PT):
        p = PT[n]
        f.write('%-18s %.4f %.4f %.4f\n' % ((n,), float(p[0]) * UNITS_PER_BU, float(p[1]) * UNITS_PER_BU, float(p[2]) * UNITS_PER_BU))
log(f"  puntos_s.txt escrito: {len(PT)} puntos")

# --- mod.info ---
mod_info = '''{Mod
\t{Name "Iron_Nest"}
\t{Desc "Iron Nest - self-propelled four-legged artillery"}
\t{minGameVersion "From Dusk"}
\t{maxGameVersion "Till Dawn"}
}
'''
with open(os.path.join(OUT_DIR, 'mod.info'), 'w', encoding='utf-8', newline='') as f:
    f.write(mod_info)
log("  mod.info escrito")

log("=== EXPORTACIÓN COMPLETADA ===")
