"""Build the Kraken Hero Boat candidate as separated, editable static-mesh parts.

The dimensions in this script are authored in metres and recorded in the audit
JSON.  It intentionally contains no rig, collision or UE import settings.
"""
import json
import math
import os
import sys

import bpy


def argument(name):
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    try:
        return args[args.index(name) + 1]
    except (ValueError, IndexError):
        raise RuntimeError("missing " + name)


OUT_BLEND = argument("--blend")
OUT_FBX = argument("--fbx")
OUT_AUDIT = argument("--audit")


def mat(name, color, metallic=0.0, roughness=0.5):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1.0)
    material.metallic = metallic
    material.roughness = roughness
    return material


WOOD_HULL = mat("M_Boat_Wood_Hull", (0.155, 0.052, 0.018), 0.0, 0.72)
WOOD_TRIM = mat("M_Boat_Wood_Trim", (0.075, 0.022, 0.008), 0.0, 0.64)
METAL = mat("M_Boat_Iron_Fastener", (0.055, 0.06, 0.065), 0.88, 0.36)


def create_mesh(name, vertices, faces, material):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    if mesh.validate(verbose=True):
        raise RuntimeError("invalid mesh corrected: " + name)
    mesh.materials.append(material)
    # UV0 is a deliberately simple longitudinal wood-grain coordinate set that
    # remains usable as a UE material starting point before a bespoke texture pass.
    uv_layer = mesh.uv_layers.new(name="UV0")
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex = mesh.vertices[mesh.loops[loop_index].vertex_index]
            uv_layer.data[loop_index].uv = (vertex.co.x / 7.0 + 0.5, vertex.co.z / 1.8)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def box(name, center, size, material):
    cx, cy, cz = center
    sx, sy, sz = (v * 0.5 for v in size)
    verts = [
        (cx - sx, cy - sy, cz - sz), (cx + sx, cy - sy, cz - sz),
        (cx + sx, cy + sy, cz - sz), (cx - sx, cy + sy, cz - sz),
        (cx - sx, cy - sy, cz + sz), (cx + sx, cy - sy, cz + sz),
        (cx + sx, cy + sy, cz + sz), (cx - sx, cy + sy, cz + sz),
    ]
    return create_mesh(name, verts, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                                     (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], material)


def longitudinal_plank(name, side, z_inner, z_outer, y_inner, y_outer, material):
    # A thick clinker strake sampled along a hull curve, with an upturned stem/stern.
    samples = 17
    thick = 0.065
    verts, faces = [], []
    for index in range(samples):
        t = index / (samples - 1)
        x = -3.45 + 6.90 * t
        end_factor = abs(2.0 * t - 1.0)
        beam_factor = 0.26 + 0.74 * math.sin(math.pi * t)
        sheer = 0.47 * (end_factor ** 1.7)
        yi = side * y_inner * beam_factor
        yo = side * y_outer * beam_factor
        verts.extend(((x, yi, z_inner + sheer), (x, yi, z_outer + sheer),
                      (x, yo, z_inner + thick + sheer), (x, yo, z_outer + thick + sheer)))
    for index in range(samples - 1):
        a, b = index * 4, (index + 1) * 4
        faces.extend(((a, b, b + 1, a + 1), (a + 2, a + 3, b + 3, b + 2),
                      (a, a + 2, b + 2, b), (a + 1, b + 1, b + 3, a + 3)))
    faces.extend(((0, 1, 3, 2), (4 * (samples - 1), 4 * (samples - 1) + 2,
                   4 * (samples - 1) + 3, 4 * (samples - 1) + 1)))
    return create_mesh(name, verts, faces, material)


def rib(name, x, side):
    # Three connected boxes approximate an internal timber rib without requiring a modifier.
    boxes = []
    boxes.append(box(name + "_Foot", (x, side * 0.56, 0.42), (0.105, 0.11, 0.47), WOOD_TRIM))
    boxes.append(box(name + "_Mid", (x, side * 0.93, 0.73), (0.105, 0.11, 0.35), WOOD_TRIM))
    boxes.append(box(name + "_Top", (x, side * 1.13, 1.04), (0.105, 0.11, 0.30), WOOD_TRIM))
    return boxes


def cylinder(name, center, radius, height, material, segments=8):
    cx, cy, cz = center
    verts = []
    for z in (cz - height * 0.5, cz + height * 0.5):
        verts.extend((cx + radius * math.cos(i * 2 * math.pi / segments),
                      cy + radius * math.sin(i * 2 * math.pi / segments), z)
                     for i in range(segments))
    faces = [tuple(range(segments)), tuple(range(segments, segments * 2))]
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, segments + j, segments + i))
    return create_mesh(name, verts, faces, material)


# The root is an explicit non-exported scene marker.  Parts remain independently editable.
root = bpy.data.objects.new("SM_HeroBoat_Root", None)
bpy.context.scene.collection.objects.link(root)

parts = []
parts.append(box("SM_HeroBoat_Keel", (0.0, 0.0, 0.13), (6.90, 0.22, 0.25), WOOD_TRIM))
parts.append(box("SM_HeroBoat_ForeStem", (-3.38, 0.0, 0.73), (0.24, 0.22, 1.30), WOOD_TRIM))
parts.append(box("SM_HeroBoat_AftStem", (3.38, 0.0, 0.67), (0.24, 0.22, 1.17), WOOD_TRIM))

# Seven overlapping strakes per side form the thickened hull skin.
for side_name, side in (("Port", 1), ("Starboard", -1)):
    for i in range(7):
        z0 = 0.24 + i * 0.115
        y0 = 0.15 + i * 0.145
        parts.append(longitudinal_plank("SM_HeroBoat_%s_Strake_%02d" % (side_name, i + 1),
                                        side, z0, z0 + 0.145, y0, y0 + 0.15, WOOD_HULL))
    parts.append(box("SM_HeroBoat_%s_Gunwale" % side_name, (0.0, side * 1.135, 1.13),
                     (6.68, 0.13, 0.14), WOOD_TRIM))
    for rib_index, x in enumerate((-2.45, -1.62, -0.81, 0.0, 0.81, 1.62, 2.45), 1):
        parts.extend(rib("SM_HeroBoat_%s_Rib_%02d" % (side_name, rib_index), x, side))

for i, x in enumerate((-1.60, 0.0, 1.60), 1):
    parts.append(box("SM_HeroBoat_Seat_%02d" % i, (x, 0.0, 0.93), (0.27, 2.02, 0.13), WOOD_TRIM))
for i, x in enumerate((-2.55, 2.55), 1):
    parts.append(box("SM_HeroBoat_DeckBeam_%02d" % i, (x, 0.0, 0.84), (0.14, 1.75, 0.14), WOOD_TRIM))

# Iron pegs are actual separate geometry, intentionally retained for UE material reassignment.
peg_index = 1
for x in (-2.45, -1.62, -0.81, 0.0, 0.81, 1.62, 2.45):
    for side in (-1, 1):
        for z in (0.52, 0.82, 1.03):
            parts.append(cylinder("SM_HeroBoat_IronPeg_%03d" % peg_index, (x, side * 1.165, z), 0.033, 0.045, METAL))
            peg_index += 1

for obj in bpy.context.scene.objects:
    obj.select_set(False)
for obj in parts:
    obj.parent = root
    obj.select_set(True)
root.select_set(False)

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, check_existing=False)
bpy.ops.export_scene.fbx(filepath=OUT_FBX, use_selection=True, apply_unit_scale=True,
                         bake_anim=False, add_leaf_bones=False, use_mesh_modifiers=True)

vertices = sum(len(obj.data.vertices) for obj in parts)
polygons = sum(len(obj.data.polygons) for obj in parts)
audit = {
    "asset": "HeroBoat_Kraken_Candidate",
    "dimensions_m": {"length": 7.0, "beam": 2.40, "hull_plank_thickness": 0.065},
    "parts": len(parts),
    "mesh_vertices": vertices,
    "mesh_polygons": polygons,
    "strakes": 14,
    "ribs": 14,
    "seats": 3,
    "iron_pegs": peg_index - 1,
    "materials": [WOOD_HULL.name, WOOD_TRIM.name, METAL.name],
    "uv_status": "UV0 authored as longitudinal wood-grain coordinates; bespoke texture packing/PBR maps remain pending",
    "ue_status": "NOT_IMPORTED_NOT_VISUALLY_VERIFIED",
}
with open(OUT_AUDIT, "w", encoding="utf-8") as handle:
    json.dump(audit, handle, ensure_ascii=False, indent=2)
print("HERO_BOAT_AUDIT=" + json.dumps(audit, ensure_ascii=False))
