import json
import sys
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
fbx_path = args[args.index("--fbx") + 1]
out_path = args[args.index("--output") + 1]
baseline = {o.name for o in bpy.context.scene.objects}
bpy.ops.import_scene.fbx(filepath=fbx_path)
imported = [o for o in bpy.context.scene.objects if o.name not in baseline]
meshes = [o for o in imported if o.type == "MESH"]
coords = [v.co for o in meshes for v in o.data.vertices]
report = {
    "kind": "FRESH_FBX_REOPEN_AUDIT",
    "mesh_objects": len(meshes),
    "imported_non_mesh_objects": sorted(o.name for o in imported if o.type != "MESH"),
    "imported_cube_objects": [o.name for o in imported if "cube" in o.name.lower()],
    "bounds_m": {"length": max(v.x for v in coords)-min(v.x for v in coords),
                 "beam": max(v.y for v in coords)-min(v.y for v in coords),
                 "height": max(v.z for v in coords)-min(v.z for v in coords)},
    "vertex_total": sum(len(o.data.vertices) for o in meshes),
}
with open(out_path, "w", encoding="utf-8") as handle: json.dump(report, handle, indent=2)
print(json.dumps(report))
