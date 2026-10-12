import json
import math
import sys
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
def value(flag): return args[args.index(flag) + 1]
source, fbx_path, output = value("--source"), value("--fbx"), value("--output")

def imported_meshes(before):
    return [obj for obj in bpy.context.scene.objects if obj.name not in before and obj.type == "MESH"]

def audit(label, obj):
    mesh = obj.data
    polygon_count = len(mesh.polygons)
    step = max(1, polygon_count // 4096)
    sampled = list(range(0, polygon_count, step))[:4096]
    dots, corner_lengths, reversed_corners = [], [], 0
    for polygon_index in sampled:
        poly = mesh.polygons[polygon_index]
        face = mesh.polygon_normals[polygon_index].vector
        face_len = math.sqrt(sum(component * component for component in face))
        for loop_index in poly.loop_indices:
            corner = mesh.corner_normals[loop_index].vector
            corner_len = math.sqrt(sum(component * component for component in corner))
            corner_lengths.append(corner_len)
            dot = sum(face[i] * corner[i] for i in range(3)) / (face_len * corner_len) if face_len and corner_len else float("nan")
            dots.append(dot)
            if math.isfinite(dot) and dot < 0.0:
                reversed_corners += 1
    finite_dots = [dot for dot in dots if math.isfinite(dot)]
    return {
        "label": label,
        "object": obj.name,
        "vertices": len(mesh.vertices),
        "polygons": polygon_count,
        "triangles": sum(1 for poly in mesh.polygons if poly.loop_total == 3),
        "has_custom_normals": bool(mesh.has_custom_normals),
        "corner_normal_count": len(mesh.corner_normals),
        "sampled_polygons": len(sampled),
        "sampled_corners": len(dots),
        "corner_vs_winding_normal_dot": {
            "min": min(finite_dots), "max": max(finite_dots),
            "mean": sum(finite_dots) / len(finite_dots),
            "negative_count": reversed_corners,
            "nonfinite_count": len(dots) - len(finite_dots)
        },
        "corner_normal_length": {"min": min(corner_lengths), "max": max(corner_lengths)}
    }

def transformed_normal_agreement(source_obj, prepared_obj):
    source_mesh, prepared_mesh = source_obj.data, prepared_obj.data
    source_min = [min(vertex.co[i] for vertex in source_mesh.vertices) for i in range(3)]
    source_max = [max(vertex.co[i] for vertex in source_mesh.vertices) for i in range(3)]
    source_dimensions = [source_max[i] - source_min[i] for i in range(3)]
    scale = [7.0 / source_dimensions[0], 2.4 / source_dimensions[1], 1.605 / source_dimensions[2]]
    corner_count = min(len(source_mesh.corner_normals), len(prepared_mesh.corner_normals))
    step = max(1, corner_count // 12288)
    dots = []
    for index in list(range(0, corner_count, step))[:12288]:
        source_normal = source_mesh.corner_normals[index].vector
        expected = [source_normal[i] / scale[i] for i in range(3)]
        expected_len = math.sqrt(sum(component * component for component in expected))
        prepared_normal = prepared_mesh.corner_normals[index].vector
        prepared_len = math.sqrt(sum(component * component for component in prepared_normal))
        dots.append(sum(expected[i] * prepared_normal[i] for i in range(3)) / (expected_len * prepared_len))
    return {
        "source_position_scale": scale,
        "sampled_corners": len(dots),
        "expected_inverse_transpose_vs_prepared_corner_dot": {
            "min": min(dots), "max": max(dots), "mean": sum(dots) / len(dots),
            "below_0_999": sum(1 for dot in dots if dot < 0.999),
            "below_0_99": sum(1 for dot in dots if dot < 0.99)
        }
    }

before_glb = {obj.name for obj in bpy.context.scene.objects}
bpy.ops.import_scene.gltf(filepath=source, import_pack_images=False)
source_meshes = imported_meshes(before_glb)
if len(source_meshes) != 1:
    raise RuntimeError("expected one source GLB mesh, found %d" % len(source_meshes))
before_fbx = {obj.name for obj in bpy.context.scene.objects}
bpy.ops.import_scene.fbx(filepath=fbx_path)
fbx_meshes = imported_meshes(before_fbx)
if len(fbx_meshes) != 1:
    raise RuntimeError("expected one FBX mesh, found %d" % len(fbx_meshes))
report = {
    "method": "Read-only sampled comparison of each corner normal to its polygon winding/position normal; smooth shading may lower dot products, while negative dots evidence opposing orientation.",
    "source_glb": audit("source_glb", source_meshes[0]),
    "prepared_fbx": audit("prepared_fbx", fbx_meshes[0]),
    "nonuniform_scale_normal_check": transformed_normal_agreement(source_meshes[0], fbx_meshes[0]),
    "status": "NORMALS_AUDIT_ONLY_NOT_UE_VALIDATED"
}
with open(output, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2)
print(json.dumps(report))
