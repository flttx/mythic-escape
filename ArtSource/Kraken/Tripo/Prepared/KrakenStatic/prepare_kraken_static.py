"""Prepare and independently re-import a static Kraken diagnostic mesh.

This deliberately contains no armature, animation, or auto-rig operation.
"""
import argparse
import json
import sys
from pathlib import Path

import bpy


EPSILON = 1e-4


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("prepare", "verify"), required=True)
    parser.add_argument("--source")
    parser.add_argument("--blend")
    parser.add_argument("--fbx", required=True)
    parser.add_argument("--audit", required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def mesh_objects():
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def bounds(mesh):
    if not mesh.data.vertices:
        raise RuntimeError("Mesh has no vertices")
    first = mesh.matrix_world @ mesh.data.vertices[0].co
    minimum = [first.x, first.y, first.z]
    maximum = [first.x, first.y, first.z]
    for vertex in mesh.data.vertices[1:]:
        point = mesh.matrix_world @ vertex.co
        for axis, value in enumerate((point.x, point.y, point.z)):
            minimum[axis] = min(minimum[axis], value)
            maximum[axis] = max(maximum[axis], value)
    dimensions = [maximum[i] - minimum[i] for i in range(3)]
    return minimum, maximum, dimensions


def mesh_summary(mesh):
    minimum, maximum, dimensions = bounds(mesh)
    return {
        "object_name": mesh.name,
        "vertices": len(mesh.data.vertices),
        "polygons": len(mesh.data.polygons),
        "triangles": sum(len(polygon.vertices) - 2 for polygon in mesh.data.polygons),
        "material_slots": len(mesh.data.materials),
        "material_names": [material.name if material else None for material in mesh.data.materials],
        "uv_layers": len(mesh.data.uv_layers),
        "bounds_m": {"min": minimum, "max": maximum, "dimensions": dimensions},
    }


def assert_single_static_mesh(meshes):
    armatures = [obj.name for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if armatures:
        raise RuntimeError("Static diagnostic asset must not contain armatures: " + ", ".join(armatures))
    if len(meshes) != 1:
        raise RuntimeError("Expected exactly one mesh, got %d" % len(meshes))
    if meshes[0].parent is not None:
        raise RuntimeError("Expected source mesh to have no parent")


def prepare(args):
    if not args.source or not args.blend:
        raise RuntimeError("--source and --blend are required for prepare mode")
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(Path(args.source).resolve()), import_pack_images=True)
    meshes = mesh_objects()
    assert_single_static_mesh(meshes)
    mesh = meshes[0]
    source_summary = mesh_summary(mesh)
    source_min = source_summary["bounds_m"]["min"]
    source_max = source_summary["bounds_m"]["max"]
    source_dimensions = source_summary["bounds_m"]["dimensions"]
    maximum_dimension = max(source_dimensions)
    if maximum_dimension <= 0:
        raise RuntimeError("Source mesh has non-positive size")
    uniform_scale = 80.0 / maximum_dimension
    source_center_xy = [
        (source_min[0] + source_max[0]) / 2.0,
        (source_min[1] + source_max[1]) / 2.0,
    ]
    for vertex in mesh.data.vertices:
        point = mesh.matrix_world @ vertex.co
        vertex.co = (
            (point.x - source_center_xy[0]) * uniform_scale,
            (point.y - source_center_xy[1]) * uniform_scale,
            (point.z - source_min[2]) * uniform_scale,
        )
    mesh.location = (0.0, 0.0, 0.0)
    mesh.rotation_euler = (0.0, 0.0, 0.0)
    mesh.scale = (1.0, 1.0, 1.0)
    mesh.data.update()
    mesh.name = "SM_Kraken_Static_Diagnostic"
    prepared_summary = mesh_summary(mesh)
    prepared_bounds = prepared_summary["bounds_m"]
    if abs(max(prepared_bounds["dimensions"]) - 80.0) > EPSILON:
        raise RuntimeError("Prepared maximum dimension is not 80m")
    if abs(prepared_bounds["min"][0] + prepared_bounds["max"][0]) > EPSILON:
        raise RuntimeError("Prepared mesh is not horizontally centered on X")
    if abs(prepared_bounds["min"][1] + prepared_bounds["max"][1]) > EPSILON:
        raise RuntimeError("Prepared mesh is not horizontally centered on Y")
    if abs(prepared_bounds["min"][2]) > EPSILON:
        raise RuntimeError("Prepared mesh bottom is not at Z=0")
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    Path(args.blend).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.blend).resolve()), compress=True)
    bpy.ops.export_scene.fbx(
        filepath=str(Path(args.fbx).resolve()),
        use_selection=True,
        object_types={"MESH"},
        global_scale=1.0,
        apply_unit_scale=True,
        bake_anim=False,
        path_mode="COPY",
        embed_textures=True,
        axis_forward="-Y",
        axis_up="Z",
    )
    result = {
        "mode": "prepare",
        "source_path": str(Path(args.source).resolve()),
        "static_only": True,
        "source": source_summary,
        "uniform_scale_applied": uniform_scale,
        "prepared": prepared_summary,
        "blend": str(Path(args.blend).resolve()),
        "fbx": str(Path(args.fbx).resolve()),
        "texture_export_requested": {"path_mode": "COPY", "embed_textures": True},
    }
    Path(args.audit).write_text(json.dumps(result, indent=2), encoding="utf-8")


def verify(args):
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(Path(args.fbx).resolve()), global_scale=1.0, use_anim=False)
    meshes = mesh_objects()
    assert_single_static_mesh(meshes)
    result = {
        "mode": "fresh_fbx_reimport",
        "fbx": str(Path(args.fbx).resolve()),
        "static_only": True,
        "reimported": mesh_summary(meshes[0]),
    }
    Path(args.audit).write_text(json.dumps(result, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    if args.mode == "prepare":
        prepare(args)
    else:
        verify(args)


if __name__ == "__main__":
    main()
