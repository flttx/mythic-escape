import json
import math
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
if any(abs(value) > 1e-6 for value in boat.rotation_euler) or any(abs(value - 1.0) > 1e-6 for value in boat.scale):
    raise RuntimeError("expected GLB mesh with identity rotation and scale for transform-apply normalization")
raw_dimensions = list(boat.dimensions)
scale = (7.0 / raw_dimensions[0], 2.4 / raw_dimensions[1], 1.605 / raw_dimensions[2])
boat.select_set(True)
bpy.context.view_layer.objects.active = boat
boat.scale = scale
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
mins = [min(vertex.co[i] for vertex in boat.data.vertices) for i in range(3)]
maxs = [max(vertex.co[i] for vertex in boat.data.vertices) for i in range(3)]
boat.location = (-(mins[0] + maxs[0]) / 2.0, -(mins[1] + maxs[1]) / 2.0, -mins[2])
bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
boat.name = "SM_Tripo_HeroBoat_Prepared_NormalsV2"
boat.data.name = "SM_Tripo_HeroBoat_Prepared_NormalsV2_Mesh"
bpy.ops.wm.save_as_mainfile(filepath=blend_out, compress=True)
bpy.ops.export_scene.fbx(filepath=fbx_out, use_selection=True, object_types={"MESH"},
                         apply_unit_scale=True, bake_anim=False, add_leaf_bones=False,
                         use_mesh_modifiers=True, axis_forward="-Y", axis_up="Z")
final_mins = [min(vertex.co[i] for vertex in boat.data.vertices) for i in range(3)]
final_maxs = [max(vertex.co[i] for vertex in boat.data.vertices) for i in range(3)]
audit = {
    "source": source, "object": boat.name,
    "method": "Blender object scale transform_apply, then translation-only transform_apply; existing FBX was not overwritten.",
    "original_dimensions": raw_dimensions, "scale_ratio": list(scale),
    "final_bounds": {"min": final_mins, "max": final_maxs, "dimensions": [final_maxs[i] - final_mins[i] for i in range(3)]},
    "vertices": len(boat.data.vertices), "polygons": len(boat.data.polygons),
    "has_custom_normals": bool(boat.data.has_custom_normals), "status": "PREPARED_NORMALSV2_NOT_UE_VALIDATED"
}
with open(audit_out, "w", encoding="utf-8") as handle:
    json.dump(audit, handle, indent=2)
print(json.dumps(audit))
