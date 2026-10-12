"""Read-only structural and evaluated-motion verification for the generated tentacle rig."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy


EPSILON = 1e-5


def args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("blend", "fbx"), required=True)
    parser.add_argument("--fbx")
    parser.add_argument("--output", required=True)
    forwarded = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return parser.parse_args(forwarded)


def scene_objects(kind):
    return [obj for obj in bpy.data.objects if obj.type == kind]


def require_one(kind):
    found = scene_objects(kind)
    if len(found) != 1:
        raise RuntimeError("Expected exactly one %s object, found %d: %s" % (kind, len(found), [obj.name for obj in found]))
    return found[0]


def vector_list(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def mesh_bounds(mesh):
    points = [mesh.matrix_world @ vertex.co for vertex in mesh.data.vertices]
    if not points:
        raise RuntimeError("Mesh has no vertices")
    minimum = [min(point[i] for point in points) for i in range(3)]
    maximum = [max(point[i] for point in points) for i in range(3)]
    return {"min": minimum, "max": maximum, "dimensions": [maximum[i] - minimum[i] for i in range(3)]}


def mesh_summary(mesh):
    return {
        "name": mesh.name,
        "vertices": len(mesh.data.vertices),
        "polygons": len(mesh.data.polygons),
        "uv_layers": len(mesh.data.uv_layers),
        "bounds_m": mesh_bounds(mesh),
    }


def weight_summary(mesh):
    sums = []
    nonfinite = 0
    unweighted = 0
    for vertex in mesh.data.vertices:
        weights = [group.weight for group in vertex.groups]
        if not weights:
            unweighted += 1
        if any(not math.isfinite(weight) for weight in weights):
            nonfinite += 1
        sums.append(sum(weights))
    return {
        "vertices": len(sums),
        "unweighted_vertices": unweighted,
        "nonfinite_weight_values": nonfinite,
        "weight_sum_min": min(sums) if sums else None,
        "weight_sum_max": max(sums) if sums else None,
        "outside_normalization_tolerance": sum(abs(total - 1.0) > EPSILON for total in sums),
        "normalization_epsilon": EPSILON,
    }


def evaluated_positions(mesh, frame):
    bpy.context.scene.frame_set(frame)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh.evaluated_get(depsgraph)
    vertices = evaluated.data.vertices
    values = [evaluated.matrix_world @ vertex.co for vertex in vertices]
    nonfinite = sum(not all(math.isfinite(component) for component in value) for value in values)
    return values, nonfinite


def action_motion(mesh, rig, action):
    if rig.animation_data is None:
        raise RuntimeError("Rig has no animation data")
    rig.animation_data.action = action
    start = int(math.floor(action.frame_range[0]))
    end = int(math.ceil(action.frame_range[1]))
    initial, initial_nonfinite = evaluated_positions(mesh, start)
    final, final_nonfinite = evaluated_positions(mesh, end)
    if len(initial) != len(mesh.data.vertices) or len(final) != len(mesh.data.vertices):
        raise RuntimeError("Evaluated vertex count differs from source mesh")
    base_index = min(range(len(mesh.data.vertices)), key=lambda index: mesh.data.vertices[index].co.y)
    tip_index = max(range(len(mesh.data.vertices)), key=lambda index: mesh.data.vertices[index].co.y)
    base_delta = final[base_index] - initial[base_index]
    tip_delta = final[tip_index] - initial[tip_index]
    return {
        "action": action.name,
        "frame_start": start,
        "frame_end": end,
        "evaluated_vertex_count": len(final),
        "nonfinite_vertices": initial_nonfinite + final_nonfinite,
        "base_vertex_index": base_index,
        "tip_vertex_index": tip_index,
        "base_start_m": vector_list(initial[base_index]),
        "base_end_m": vector_list(final[base_index]),
        "tip_start_m": vector_list(initial[tip_index]),
        "tip_end_m": vector_list(final[tip_index]),
        "base_displacement_m": float(base_delta.length),
        "tip_displacement_m": float(tip_delta.length),
    }


def blend_report():
    mesh = require_one("MESH")
    rig = require_one("ARMATURE")
    actions = sorted(bpy.data.actions, key=lambda action: action.name)
    required = ("Idle", "Warning", "Strike")
    named_actions = {}
    for required_name in required:
        candidates = [action for action in actions if action.name.lower().endswith(required_name.lower())]
        if len(candidates) == 1:
            named_actions[required_name] = candidates[0]
    missing = [name for name in required if name not in named_actions]
    if missing:
        raise RuntimeError("Required actions missing: " + ", ".join(missing))
    samples = {name: action_motion(mesh, rig, named_actions[name]) for name in required}
    return {
        "kind": "READ_ONLY_TRIPO_TENTACLE_BLEND_VERIFY_NOT_UE_QA",
        "mesh": mesh_summary(mesh),
        "armature": {"name": rig.name, "bones": len(rig.data.bones), "pose_bones": len(rig.pose.bones)},
        "actions": [{"name": action.name, "frame_range": [float(action.frame_range[0]), float(action.frame_range[1])]} for action in actions],
        "weights": weight_summary(mesh),
        "evaluated_motion": samples,
        "limitations": ["Structural and numeric Blender verification only; no animation aesthetics or UE import/runtime conclusion."],
    }


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def fbx_report(fbx):
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(Path(fbx).resolve()), global_scale=1.0, use_anim=True)
    mesh = require_one("MESH")
    rig = require_one("ARMATURE")
    return {
        "kind": "READ_ONLY_TRIPO_TENTACLE_FRESH_FBX_REIMPORT_NOT_UE_QA",
        "fbx": str(Path(fbx).resolve()),
        "mesh": mesh_summary(mesh),
        "armature": {"name": rig.name, "bones": len(rig.data.bones), "pose_bones": len(rig.pose.bones)},
        "actions": sorted(action.name for action in bpy.data.actions),
        "limitations": ["Fresh Blender FBX reimport only; no UE import/runtime conclusion."],
    }


def main():
    options = args()
    report = blend_report() if options.mode == "blend" else fbx_report(options.fbx)
    Path(options.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
