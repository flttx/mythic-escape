"""Blender pass 1: skin the prepared V5 Kraken mesh to the numpy-derived skeleton.

Run through the blender-cli runner with --blend SM_Kraken_Colossal_V5.blend. Writes
KrakenV5_Rigged.blend and bone_rest.json (Bone.matrix_local per bone) for pass 2.
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

OUT = Path(__file__).resolve().parent
rig_data = np.load(OUT / "cache/rig.npz")
positions = np.load(OUT / "cache/kraken_v5_prepared.npz")["positions"]
names = [str(n) for n in rig_data["names"]]
heads, tails, parents = rig_data["heads"], rig_data["tails"], rig_data["parents"]
bone_index, bone_weight = rig_data["bone_index"], rig_data["bone_weight"]

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if len(meshes) != 1:
    raise RuntimeError("Expected the single prepared Kraken mesh")
skin = meshes[0]
verts = skin.data.vertices
if len(verts) != len(positions):
    raise RuntimeError("Vertex count differs from the GLB analysis")
sample = np.linspace(0, len(verts) - 1, 4000).astype(int)
deviation = max(max(abs(verts[int(i)].co[k] - float(positions[i][k])) for k in range(3)) for i in sample)
if deviation > 0.01:
    raise RuntimeError("Vertex order/positions differ from the GLB analysis: %.4f m" % deviation)

arm = bpy.data.armatures.new("KrakenV5Rig")
rig = bpy.data.objects.new("KrakenV5Rig", arm)
bpy.context.scene.collection.objects.link(rig)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for i, name in enumerate(names):
    bone = arm.edit_bones.new(name)
    bone.head = tuple(float(v) for v in heads[i])
    bone.tail = tuple(float(v) for v in tails[i])
for i, name in enumerate(names):
    if parents[i] >= 0:
        arm.edit_bones[name].parent = arm.edit_bones[names[parents[i]]]
        arm.edit_bones[name].use_connect = False
bpy.ops.object.mode_set(mode="OBJECT")

skin.parent = rig
modifier = skin.modifiers.new("KrakenSkin", "ARMATURE")
modifier.object = rig
modifier.use_vertex_groups = True
groups = [skin.vertex_groups.new(name=n) for n in names]
# Batch by bone and quantised weight (1/1024) instead of ~4M single-vertex calls.
q = np.round(bone_weight * 1024).astype(np.int32)
assigned = 0
for k in range(bone_index.shape[1]):
    for b in range(len(names)):
        sel = np.flatnonzero((bone_index[:, k] == b) & (q[:, k] > 0))
        if not len(sel):
            continue
        for level in np.unique(q[sel, k]):
            idx = sel[q[sel, k] == level]
            groups[b].add(idx.tolist(), float(level) / 1024.0, "ADD")
            assigned += len(idx)

rest = {n: [[float(arm.bones[n].matrix_local.row[r][c]) for c in range(4)] for r in range(4)] for n in names}
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "KrakenV5_Rigged.blend"), compress=True)
report = {"bones": len(names), "vertices": len(verts), "max_position_deviation_m": deviation,
          "weight_entries": assigned, "mesh_object": skin.name, "armature": rig.name}
(OUT / "bone_rest.json").write_text(json.dumps({"rest": rest, "report": report}), encoding="utf-8")
print(json.dumps(report))
