"""Bind the Tripo straight arm to the previously validated authored 24-bone rig.
High source is retained; reduced deformation geometry still needs close-up QA.
"""
import bpy
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
SOURCE = ROOT / "ArtSource/Kraken/Tripo/tripo-out/m1-hero-tentacle-hd-v2-5e458213/model.glb"
LENGTH, BONES = 18.0, 24
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(SOURCE), import_pack_images=True)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if len(meshes) != 1:
    raise RuntimeError("Expected one source mesh")
skin = meshes[0]
bpy.context.view_layer.objects.active = skin
skin.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
def bounds():
    verts = skin.data.vertices
    lo = [min(v.co[i] for v in verts) for i in range(3)]
    hi = [max(v.co[i] for v in verts) for i in range(3)]
    return lo, hi
lo, hi = bounds()
if max(range(3), key=lambda i: hi[i] - lo[i]) != 1:
    raise RuntimeError("Inspect generated orientation: expected Blender Y longitudinal axis")
source_triangles = sum(len(p.vertices) - 2 for p in skin.data.polygons)
length = hi[1] - lo[1]
def section_width(at_start):
    vs = [v.co for v in skin.data.vertices if
          (v.co.y < lo[1] + length * 0.08 if at_start else v.co.y > hi[1] - length * 0.08)]
    return (max(v.x for v in vs) - min(v.x for v in vs)) * (max(v.z for v in vs) - min(v.z for v in vs))
base_is_positive = section_width(False) > section_width(True)
if base_is_positive:
    skin.rotation_euler = (0.0, 0.0, math.pi)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
lo, hi = bounds()
factor = LENGTH / (hi[1] - lo[1])
base = [v.co for v in skin.data.vertices if v.co.y < lo[1] + (hi[1] - lo[1]) * 0.025]
center_x = (min(v.x for v in base) + max(v.x for v in base)) / 2
center_z = (min(v.z for v in base) + max(v.z for v in base)) / 2
skin.scale = (factor, factor, factor)
skin.location = (-center_x * factor, -lo[1] * factor, -center_z * factor)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "HeroTentacle_Tripo_HighSource.blend"), compress=True)
reducer = skin.modifiers.new("DeformationMesh", "DECIMATE")
reducer.decimate_type = "COLLAPSE"
reducer.ratio = 0.16
reducer.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier=reducer.name, merge_customdata=False)
del reducer
triangles = sum(len(p.vertices) - 2 for p in skin.data.polygons)
if not 100000 < triangles < 400000 or len(skin.data.uv_layers) != 1:
    raise RuntimeError("Unexpected reduced mesh counts or missing UV")
stations = [v.co.y for v in skin.data.vertices]
skin.name = "HeroTentacle_Tripo_Skin"
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
blend_path = OUT / "HeroTentacle_Tripo_Rig.blend"
fbx_path = OUT / "HeroTentacle_Tripo_Rig.fbx"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)
bpy.ops.export_scene.fbx(filepath=str(fbx_path), use_selection=True,
    object_types={"MESH", "ARMATURE"}, add_leaf_bones=False,
    mesh_smooth_type="FACE", bake_anim=True, bake_anim_use_all_actions=True,
    bake_anim_use_nla_strips=False, bake_anim_simplify_factor=0.0,
    axis_forward="-Y", axis_up="Z")
audit = {"source": str(SOURCE), "source_triangles": source_triangles,
         "deformation_triangles": triangles, "vertices": len(skin.data.vertices),
         "bones": BONES, "length_m": LENGTH, "base_was_positive_y": base_is_positive,
         "actions": list(actions), "fps": 30, "uv_layers": len(skin.data.uv_layers),
         "status": "RIGGED_REQUIRES_INDEPENDENT_REOPEN_AND_UE_MOTION_QA",
         "limitations": ["Contact frame 73 is authored intent, not a wired collision event",
                          "Animation transitions and cup deformation need visual review",
                          "No full chapter or performance acceptance implied"]}
(OUT / "HeroTentacle_Tripo_Rig.audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
print(json.dumps(audit))
