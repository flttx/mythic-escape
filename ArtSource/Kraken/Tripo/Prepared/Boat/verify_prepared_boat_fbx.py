import json
import sys
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
def value(flag): return args[args.index(flag) + 1]
fbx_path, output = value("--fbx"), value("--output")

baseline = {obj.name for obj in bpy.context.scene.objects}
bpy.ops.import_scene.fbx(filepath=fbx_path)
imported = [obj for obj in bpy.context.scene.objects if obj.name not in baseline]
meshes = [obj for obj in imported if obj.type == "MESH"]
if not meshes:
    raise RuntimeError("FBX imported no mesh objects")
coords = [obj.matrix_world @ vertex.co for obj in meshes for vertex in obj.data.vertices]
mins = [min(v[i] for v in coords) for i in range(3)]
maxs = [max(v[i] for v in coords) for i in range(3)]
dimensions = [maxs[i] - mins[i] for i in range(3)]
report = {
    "fresh_factory_startup": True,
    "fbx": fbx_path,
    "imported_mesh_objects": [{"name": obj.name, "vertices": len(obj.data.vertices), "polygons": len(obj.data.polygons), "uv_layers": len(obj.data.uv_layers), "material_slots": [m.name if m else None for m in obj.data.materials]} for obj in meshes],
    "imported_non_mesh_objects": [{"name": obj.name, "type": obj.type} for obj in imported if obj.type != "MESH"],
    "imported_cube_objects": [obj.name for obj in imported if obj.name.lower().startswith("cube")],
    "bounds_m": {"min": mins, "max": maxs, "dimensions": dimensions},
    "vertex_total": sum(len(obj.data.vertices) for obj in meshes),
    "polygon_total": sum(len(obj.data.polygons) for obj in meshes),
    "status": "FRESH_FBX_REOPEN_AUDIT_NOT_UE_VALIDATED"
}
with open(output, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2)
print(json.dumps(report))
