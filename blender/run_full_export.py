#!/usr/bin/env python3
"""
Script maestro para ejecutar todo el pipeline de exportación Iron Nest en una sola sesión de Blender.
Uso: blender --background --python run_full_export.py
"""
import bpy
import sys
import os

# Añadir el directorio del mod al path
mod_dir = "/home/sparky/Descargas/Iron_Nest_CTA_mod"
if mod_dir not in sys.path:
    sys.path.insert(0, mod_dir)

print("=" * 60)
print("INICIANDO PIPELINE COMPLETO IRON NEST")
print("=" * 60)

# ============================================================
# PARTE 0: Ejecutar iron_nest_blender.py (solo geometría base)
# NOTA: El Armature se crea pero los vertex groups NO se asignan
# porque los meshes GEM2_export aún no existen.
# ============================================================
print("\n>>> EJECUTANDO PARTE 0: iron_nest_blender.py (geometría base)")
exec(compile(open(os.path.join(mod_dir, "iron_nest_blender.py"), "rb").read(), "iron_nest_blender.py", 'exec'))
print(">>> PARTE 0 COMPLETADA")

# ============================================================
# PARTE 1: Ejecutar iron_nest_gem2_parte1.py (crea GEM2_export)
# ============================================================
print("\n>>> EJECUTANDO PARTE 1: iron_nest_gem2_parte1.py")
exec(compile(open(os.path.join(mod_dir, "iron_nest_gem2_parte1.py"), "rb").read(), "iron_nest_gem2_parte1.py", 'exec'))
print(">>> PARTE 1 COMPLETADA")

# ============================================================
# PARTE 1.5: Re-asignar vertex groups a los meshes GEM2_export
# Ahora SÍ existen los meshes d_hull, d_turret, d_gun_L, etc.
# ============================================================
print("\n>>> EJECUTANDO PARTE 1.5: Asignando vertex groups a GEM2_export")
arm_obj = bpy.data.objects.get('iron_nest_arm')
if arm_obj:
    # Re-crear el bone_map (copiado de iron_nest_blender.py)
    bone_map = {
        'd_hull':        'body',
        'd_turret':      'turret',
        'd_gun_L':       'gun_rot',
        'd_gun_R':       'gun1_rot',
        'd_periscope':   'turret',
        'd_horns':       'turret',
        'd_hatch':       'turret',
        'd_roof_vent':   'turret',
        'd_visor':       'turret',
        'd_headlights':  'turret',
        'd_turret_rear': 'turret',
        'd_door_rear':   'body',
        'd_hipmount_FL': 'body',
        'd_hipmount_FR': 'body',
        'd_hipmount_BL': 'body',
        'd_hipmount_BR': 'body',
        'p_elev_ram_L':  'elev_ram_l',
        'p_elev_ram_R':  'elev_ram_r',
    }
    for corner in ('FL', 'FR', 'BL', 'BR'):
        k = corner.lower()
        bone_map[f'd_hip_{corner}']         = f'hip_{k}'
        bone_map[f'd_leg_upper_{corner}']   = f'leg_upper_{k}'
        bone_map[f'd_leg_lower_{corner}']   = f'leg_lower_{k}'
        bone_map[f'd_foot_{corner}']        = f'foot_{k}'
        bone_map[f'p_piston_hip_{corner}']  = f'piston_hip_{k}'
        bone_map[f'p_piston_knee_{corner}'] = f'piston_knee_{k}'
        bone_map[f'p_piston_ankle_{corner}'] = f'piston_ankle_{k}'

    # Asignar vertex groups
    for mesh_name, bone_name in bone_map.items():
        obj = bpy.data.objects.get(mesh_name)
        if not obj or obj.type != 'MESH':
            print(f"  AVISO: Mesh '{mesh_name}' no encontrado")
            continue
        vg = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
        vg.add(range(len(obj.data.vertices)), 1.0, 'REPLACE')
        mod = obj.modifiers.get('Armature') or obj.modifiers.new('Armature', 'ARMATURE')
        mod.object = arm_obj
        mod.use_vertex_groups = True
        mod.use_bone_envelopes = False
    print(f"  Vertex groups asignados a {len(bone_map)} meshes")
else:
    print("  ERROR: No se encuentra Armature 'iron_nest_arm'")
print(">>> PARTE 1.5 COMPLETADA")

# ============================================================
# PARTE 2: Ejecutar iron_nest_gem2_parte2.py
# ============================================================
print("\n>>> EJECUTANDO PARTE 2: iron_nest_gem2_parte2.py")
exec(compile(open(os.path.join(mod_dir, "iron_nest_gem2_parte2.py"), "rb").read(), "iron_nest_gem2_parte2.py", 'exec'))
print(">>> PARTE 2 COMPLETADA")

# ============================================================
# PARTE 3: Ejecutar iron_nest_gem2_parte3.py (primera pasada)
# ============================================================
print("\n>>> EJECUTANDO PARTE 3: iron_nest_gem2_parte3.py (primera pasada)")
exec(compile(open(os.path.join(mod_dir, "iron_nest_gem2_parte3.py"), "rb").read(), "iron_nest_gem2_parte3.py", 'exec'))
print(">>> PARTE 3 COMPLETADA (primera pasada)")

# ============================================================
# PARTE 4: Ejecutar iron_nest_gem2_parte4.py (bake texturas)
# ============================================================
parte4_path = os.path.join(mod_dir, "iron_nest_gem2_parte4.py")
if os.path.exists(parte4_path):
    print("\n>>> EJECUTANDO PARTE 4: iron_nest_gem2_parte4.py (BAKE TEXTURAS)")
    exec(compile(open(parte4_path, "rb").read(), "iron_nest_gem2_parte4.py", 'exec'))
    print(">>> PARTE 4 COMPLETADA")
else:
    print("\n>>> PARTE 4: iron_nest_gem2_parte4.py NO ENCONTRADO (saltando bake de texturas)")

# ============================================================
# PARTE 3 BIS: Re-ejecutar iron_nest_gem2_parte3.py para aplicar UV/materiales
# ============================================================
print("\n>>> EJECUTANDO PARTE 3 BIS: iron_nest_gem2_parte3.py (re-export con UV/materiales)")
exec(compile(open(os.path.join(mod_dir, "iron_nest_gem2_parte3.py"), "rb").read(), "iron_nest_gem2_parte3.py", 'exec'))
print(">>> PARTE 3 BIS COMPLETADA")

print("\n" + "=" * 60)
print("PIPELINE COMPLETO FINALIZADO")
print("=" * 60)