import json
import math
import sys
import bpy

out = sys.argv[sys.argv.index("--") + 1:]
out_path = out[out.index("--output") + 1]
skin = bpy.data.objects["SK_HeroTentacle_Candidate"]
rig = bpy.data.objects["KrakenTentacleRig"]
weights = [sum(g.weight for g in v.groups) for v in skin.data.vertices]
report = {"kind": "READ_ONLY_BLENDER_TENTACLE_VERIFY_NOT_UE_QA",
          "vertices": len(skin.data.vertices), "uv_layers": len(skin.data.uv_layers),
          "deform_bones": len(rig.pose.bones), "actions": sorted(a.name for a in bpy.data.actions),
          "weight_sum_min": min(weights), "weight_sum_max": max(weights),
          "nonfinite_weights": sum(not math.isfinite(w) for w in weights), "samples": {}}
for action_name, frame in (("Tentacle_Idle", 1), ("Tentacle_Warning", 61), ("Tentacle_Strike", 73), ("Tentacle_Strike", 121)):
    rig.animation_data.action = bpy.data.actions[action_name]
    bpy.context.scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    evaluated = skin.evaluated_get(dg)
    coords = [v.co for v in evaluated.data.vertices]
    tip = max(coords, key=lambda v: v.y)
    report["samples"][action_name + "_" + str(frame)] = {"tip": [tip.x, tip.y, tip.z], "nonfinite_vertices": sum(not all(math.isfinite(x) for x in v) for v in coords)}
with open(out_path, "w", encoding="utf-8") as f: json.dump(report, f, indent=2)
print(json.dumps(report))
