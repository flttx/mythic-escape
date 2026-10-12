"""Blender pass 2: key the procedural Kraken clips on the rigged V5 and export the UE FBX.

Run through the blender-cli runner with --blend KrakenV5_Rigged.blend.
"""
import json
from pathlib import Path

import bpy
import numpy as np

OUT = Path(__file__).resolve().parent
data = np.load(OUT / "cache/anim_blender.npz")
names = [str(n) for n in data["names"]]
clips = ["Kraken_Emerge", "Kraken_Idle", "Kraken_StrikeA", "Kraken_Submerge"]

rigs = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if len(rigs) != 1 or len(meshes) != 1:
    raise RuntimeError("Expected one armature and one skinned mesh")
rig, skin = rigs[0], meshes[0]
scene = bpy.context.scene
scene.render.fps = 30
pose_bones = [rig.pose.bones[n] for n in names]
for pb in pose_bones:
    pb.rotation_mode = "QUATERNION"

animation = rig.animation_data_create()
keyed, actions = {}, {}
for clip in clips:
    frames = data[clip + "__frames"]
    quat = data[clip + "__quat"]
    loc = data[clip + "__root_loc"]
    action = bpy.data.actions.new(clip)
    action.use_fake_user = True
    actions[clip] = action
    animation.action = action
    for f, frame in enumerate(frames.tolist()):
        for b, pb in enumerate(pose_bones):
            pb.rotation_quaternion = tuple(float(v) for v in quat[f, b])
            if not pb.keyframe_insert(data_path="rotation_quaternion", frame=frame):
                raise RuntimeError("Rotation keyframe insertion failed")
        pose_bones[0].location = tuple(float(v) for v in loc[f])
        if not pose_bones[0].keyframe_insert(data_path="location", frame=frame):
            raise RuntimeError("Root location keyframe insertion failed")
    keyed[clip] = {"keys": len(frames), "last_frame": int(frames[-1])}

animation.action = actions["Kraken_Idle"]
scene.frame_start = 1
scene.frame_end = keyed["Kraken_Idle"]["last_frame"]
scene.frame_set(1)
skin.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "KrakenV5_Animated.blend"), compress=True)
bpy.ops.export_scene.fbx(filepath=str(OUT / "SK_Kraken_V5.fbx"), use_selection=True,
    object_types={"MESH", "ARMATURE"}, add_leaf_bones=False,
    mesh_smooth_type="FACE", bake_anim=True, bake_anim_use_all_actions=True,
    bake_anim_use_nla_strips=False, bake_anim_simplify_factor=0.0,
    axis_forward="-Y", axis_up="Z")
print(json.dumps({"clips": keyed, "bones": len(names)}))
