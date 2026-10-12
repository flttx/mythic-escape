import json
import math
import os
import sys
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
def value(flag): return args[args.index(flag) + 1]
source = value("--source")
blend_out, fbx_out, audit_out = value("--blend"), value("--fbx"), value("--audit")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=source, import_pack_images=True)
meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
if len(meshes) != 1:
    raise RuntimeError("expected exactly one imported mesh, found %d" % len(meshes))
boat = meshes[0]
original_materials = [m.name if m else None for m in boat.data.materials]
coords = [boat.matrix_world @ vertex.co for vertex in boat.data.vertices]
mins = [min(v[i] for v in coords) for i in range(3)]
maxs = [max(v[i] for v in coords) for i in range(3)]
raw = [maxs[i] - mins[i] for i in range(3)]
long_axis = max(range(3), key=lambda i: raw[i])
vertical_axis = 2
if long_axis == vertical_axis:
    raise RuntimeError("GLB longest axis is Blender Z; expected Z-up boat with horizontal long axis")
wide_axis = 1 if long_axis == 0 else 0
targets = {long_axis: 7.0, wide_axis: 2.4, vertical_axis: 1.605}
scale = {axis: targets[axis] / raw[axis] for axis in range(3)}

# Rebuild the one mesh in requested world orientation: X long, Y wide, Z up;
# write coordinates directly, leaving object transforms identity for UE import.
for vertex in boat.data.vertices:
    world = boat.matrix_world @ vertex.co
    remapped = [world[long_axis], world[wide_axis], world[vertical_axis]]
    vertex.co = ((remapped[0] - mins[long_axis]) * scale[long_axis] - 3.5,
                 (remapped[1] - mins[wide_axis]) * scale[wide_axis] - 1.2,
                 (remapped[2] - mins[vertical_axis]) * scale[vertical_axis])
boat.location = (0.0, 0.0, 0.0)
boat.rotation_euler = (0.0, 0.0, 0.0)
boat.scale = (1.0, 1.0, 1.0)
boat.data.update()
boat.name = "SM_Tripo_HeroBoat_Prepared"
boat.data.name = "SM_Tripo_HeroBoat_Prepared_Mesh"
boat.select_set(True)
bpy.context.view_layer.objects.active = boat
bpy.ops.wm.save_as_mainfile(filepath=blend_out, compress=True)
bpy.ops.export_scene.fbx(filepath=fbx_out, use_selection=True, object_types={"MESH"},
                         apply_unit_scale=True, bake_anim=False, add_leaf_bones=False,
                         use_mesh_modifiers=True, axis_forward="-Y", axis_up="Z")
audit = {"source": source, "object": boat.name, "materials": original_materials,
         "original_bounds": {"min": mins, "max": maxs, "dimensions": raw},
         "axis_mapping": {"source_long_to_X": long_axis, "source_wide_to_Y": wide_axis, "source_vertical_to_Z": vertical_axis},
         "scale_ratio": {"x": scale[long_axis], "y": scale[wide_axis], "z": scale[vertical_axis]},
         "target_bounds_m": {"length": 7.0, "beam": 2.4, "height": 1.605, "min_z": 0.0},
         "vertices": len(boat.data.vertices), "polygons": len(boat.data.polygons),
         "uv_layers": len(boat.data.uv_layers), "status": "PREPARED_NOT_UE_VALIDATED"}
with open(audit_out, "w", encoding="utf-8") as f: json.dump(audit, f, indent=2)
print(json.dumps(audit))
