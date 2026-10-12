"""Original Kraken near-view tentacle candidate: closed cups, continuous skin,
24 deform bones, UVs and authored actions. Run only through blender-cli's sealed plan.
This produces a rig/geometry candidate, not accepted final creature art.
"""
import json
import math
from pathlib import Path
import bpy

OUT = Path(__file__).resolve().parent
LENGTH, SECTIONS, SIDES, BONES = 18.0, 240, 64, 24
verts, faces, corner_uvs, stations = [], [], [], []


def vertex(x, y, z, station):
    verts.append((x, y, z))
    stations.append(station)
    return len(verts) - 1


def face(indices, uvs):
    faces.append(tuple(indices))
    corner_uvs.extend(uvs)


def radius(t):
    return 0.055 + 0.85 * (1.0 - t) ** 1.35


# Tapered muscular core, small longitudinal ridges with restrained asymmetry.
for i in range(SECTIONS + 1):
    t = i / SECTIONS
    for j in range(SIDES):
        a = 2 * math.pi * j / SIDES
        r = radius(t) * (1 + 0.025 * math.cos(a * 8 + t * 14))
        vertex(r * math.cos(a), LENGTH * t, r * math.sin(a) * 0.82, LENGTH * t)
for i in range(SECTIONS):
    for j in range(SIDES):
        k = (j + 1) % SIDES
        face((i * SIDES + j, (i + 1) * SIDES + j, (i + 1) * SIDES + k, i * SIDES + k),
             ((j / SIDES, i / SECTIONS), (j / SIDES, (i + 1) / SECTIONS),
              ((j + 1) / SIDES, (i + 1) / SECTIONS), ((j + 1) / SIDES, i / SECTIONS)))
face(tuple(range(SIDES)), [(0.5, 0.5)] * SIDES)
face(tuple(SECTIONS * SIDES + j for j in reversed(range(SIDES))), [(0.5, 0.5)] * SIDES)

# Two staggered rows, 96 physical concave cups. Rings describe the stalk,
# thick lip, recessed inner wall and bowl, rather than flat discs.
cup_count = 0
profile = [(0.40, 0.00), (0.57, 0.18), (0.84, 0.35), (1.00, 0.62),
           (1.03, 0.80), (0.92, 0.91), (0.75, 0.86), (0.66, 0.63),
           (0.47, 0.36), (0.12, 0.24)]
for row in (-1, 1):
    for c in range(48):
        t = 0.055 + 0.88 * (c + (0.45 if row == 1 else 0)) / 48
        y = LENGTH * t
        r = radius(t)
        cr = 0.26 * (1 - t) + 0.027
        cx = row * r * 0.40
        surface_z = -r * 0.82 * math.sqrt(1 - 0.4 ** 2)
        base = len(verts)
        for rr, depth in profile:
            for j in range(40):
                a = j * 2 * math.pi / 40
                ripple = 1 + 0.035 * math.sin(12 * a)
                vertex(cx + cr * rr * math.cos(a) * ripple,
                       y + cr * rr * math.sin(a), surface_z - cr * depth, y)
        for k in range(len(profile) - 1):
            for j in range(40):
                n = (j + 1) % 40
                ids = (base + k * 40 + j, base + k * 40 + n,
                       base + (k + 1) * 40 + n, base + (k + 1) * 40 + j)
                uv = [(0.5 + 0.47 * profile[ring][0] * math.cos(ang * 2 * math.pi / 40),
                       0.5 + 0.47 * profile[ring][0] * math.sin(ang * 2 * math.pi / 40))
                      for ring, ang in ((k, j), (k, j + 1), (k + 1, j + 1), (k + 1, j))]
                face(tuple(reversed(ids)), list(reversed(uv)))
        face(tuple(base + (len(profile) - 1) * 40 + j for j in reversed(range(40))), [(0.5, 0.5)] * 40)
        face(tuple(base + j for j in range(40)), [(0.5, 0.5)] * 40)
        cup_count += 1

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
mesh = bpy.data.meshes.new("TentacleSkinAndCups")
mesh.from_pydata(verts, [], faces, shade_flat=False)
if mesh.validate(verbose=True):
    raise RuntimeError("Generated mesh required topology correction")
skin = bpy.data.objects.new("SK_HeroTentacle_Candidate", mesh)
bpy.context.scene.collection.objects.link(skin)
uv_layer = mesh.uv_layers.new(name="SurfaceUV", do_init=False)
for i, uv in enumerate(corner_uvs):
    uv_layer.uv[i].vector = uv
material = bpy.data.materials.new("M_Tentacle_Base_Candidate")
material.diffuse_color = (0.085, 0.13, 0.12, 1.0)
material.roughness = 0.32
mesh.materials.append(material)

arm = bpy.data.armatures.new("KrakenTentacleRig")
rig = bpy.data.objects.new("KrakenTentacleRig", arm)
bpy.context.scene.collection.objects.link(rig)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for i in range(BONES):
    bone = arm.edit_bones.new(f"tentacle_{i:02d}")
    bone.head = (0, i * LENGTH / BONES, 0)
    bone.tail = (0, (i + 1) * LENGTH / BONES, 0)
    if i:
        bone.parent = arm.edit_bones[f"tentacle_{i - 1:02d}"]
        bone.use_connect = True
del bone
bpy.ops.object.mode_set(mode="OBJECT")
skin.parent = rig
modifier = skin.modifiers.new("ContinuousSkin", "ARMATURE")
modifier.object = rig
modifier.use_vertex_groups = True
# Linear skinning matches the UE import baseline; preserve-volume DQ is not assumed.
groups = [skin.vertex_groups.new(name=f"tentacle_{i:02d}") for i in range(BONES)]
max_weight_error = 0.0
for index, station in enumerate(stations):
    b = max(0.0, min(BONES - 1.0, station / (LENGTH / BONES) - 0.5))
    lo = int(b)
    hi = min(BONES - 1, lo + 1)
    blend = b - lo
    groups[lo].add([index], 1.0 - blend, "REPLACE")
    if hi != lo and blend > 0:
        groups[hi].add([index], blend, "REPLACE")
    max_weight_error = max(max_weight_error, abs((1.0 - blend) + blend - 1.0))

scene = bpy.context.scene
scene.render.fps = 30
scene.frame_start = 1
scene.frame_end = 121
animation = rig.animation_data_create()
actions = {}
for name in ("Idle", "Warning", "Strike", "Recover", "BoatLift", "Submerge"):
    action = bpy.data.actions.new("Tentacle_" + name)
    action.use_fake_user = True
    animation.action = action
    for frame in range(1, 122, 4):
        u = (frame - 1) / 120
        smooth = u * u * (3 - 2 * u)
        for i in range(BONES):
            t = i / (BONES - 1)
            base = 0.032 * math.sin(t * math.pi * 1.8)
            if name == "Idle":
                bend = base + 0.022 * math.sin(2 * math.pi * u - t * 3)
            elif name == "Warning":
                bend = base + 0.055 * smooth * math.sin(t * math.pi)
            elif name == "Strike":
                # Contact at frame 73, before recovery. No collision implied here.
                pulse = math.sin(min(1.0, u / 0.6) * math.pi / 2)
                bend = base + (0.055 - 0.125 * pulse) * math.sin(t * math.pi)
            elif name == "Recover":
                bend = base - 0.07 * (1 - smooth) * math.sin(t * math.pi)
            elif name == "BoatLift":
                bend = base + 0.08 * smooth * math.sin(t * math.pi * 1.3)
            else:
                bend = base - 0.065 * smooth * math.sin(t * math.pi)
            pb = rig.pose.bones[f"tentacle_{i:02d}"]
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (bend, 0.004 * math.sin(t * 7 + u), 0.012 * math.sin(t * 5 + u * 2))
            if not pb.keyframe_insert(data_path="rotation_euler", frame=frame):
                raise RuntimeError("Bone keyframe insertion failed")
    actions[name] = action

animation.action = actions["Idle"]
scene.frame_set(1)
skin.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
blend_path = OUT / "HeroTentacle_Candidate.blend"
fbx_path = OUT / "HeroTentacle_Candidate.fbx"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)
bpy.ops.export_scene.fbx(filepath=str(fbx_path), use_selection=True,
    object_types={"MESH", "ARMATURE"}, add_leaf_bones=False,
    mesh_smooth_type="FACE", bake_anim=True, bake_anim_use_all_actions=True,
    bake_anim_use_nla_strips=False, bake_anim_simplify_factor=0.0,
    axis_forward="-Y", axis_up="Z")
audit = {"length_m": LENGTH, "deform_bones": BONES, "vertices": len(verts),
         "triangles": sum(len(f) - 2 for f in faces), "physical_cups": cup_count,
         "uv": "body longitudinal seam, overlapping cup-local UV islands",
         "actions": list(actions), "fps": 30, "action_frames": [1, 121],
         "strike_contact_frame": 73, "weight_sum_max_error": max_weight_error,
         "limitations": ["PBR textures and close-up sculpt still pending",
                         "UE deformation/contact/collision and visual gates NOT_VERIFIED",
                         "Actions are individually authored; transition blending still pending"],
         "source": "Original procedural geometry and authored animation; no third-party art"}
(OUT / "HeroTentacle_Candidate.audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
print(json.dumps(audit))
