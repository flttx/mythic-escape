"""Verify imported bone animation in real PIE; this is not a visual/performance pass."""
import datetime as dt
import json
import math
import time

from ue_mcp import ROOT, UnrealMCP

B = "editor_toolset.toolsets.blueprint.BlueprintTools"
A = "editor_toolset.toolsets.asset.AssetTools"
S = "editor_toolset.toolsets.scene.SceneTools"
O = "editor_toolset.toolsets.object.ObjectTools"
AC = "editor_toolset.toolsets.actor.ActorTools"
E = "EditorToolset.EditorAppToolset"
PATH = "/Game/MythicEscape/Chapters/Kraken/QA/BP_QA_TentacleMotion"
FOLDER = "/Game/MythicEscape/Chapters/Kraken/Art/Tripo/Tentacle_V2/"
DSL = """(event EventTick (DeltaSeconds)
  (Variables|Default|SetElapsed (+ (Variables|Default|GetElapsed) DeltaSeconds))
  (Variables|Default|SetTipPosition
    (Transformation|GetSocketLocation
      :self (Variables|SkeletalMeshActor|GetSkeletalMeshComponent) :InSocketName "tentacle_23"))
  (Variables|Default|SetBasePosition
    (Transformation|GetSocketLocation
      :self (Variables|SkeletalMeshActor|GetSkeletalMeshComponent) :InSocketName "tentacle_00")))"""


def ref(path):
    return {"refPath": path if "." in path else path + "." + path.rsplit("/", 1)[-1]}


def main():
    m = UnrealMCP()
    def call(group, name, args=None):
        return m.invoke(group, name, args or {})["returnValue"]
    def find(name):
        return call(S, "find_actors", {"name": name, "tag": "", "collision_channels": []})
    if call(E, "IsPIERunning"):
        raise RuntimeError("Stop existing PIE before isolated motion QA")
    level = call(S, "get_current_level")
    if "L_KrakenHeroReview" not in str(level):
        raise RuntimeError("This QA only runs in the saved HeroReview map")
    assert call(A, "save_assets", {"asset_paths": []})
    bp = ref(PATH)
    if not call(A, "exists", {"path": PATH}):
        call(B, "create", {"folder_path": PATH.rsplit("/", 1)[0],
             "asset_name": "BP_QA_TentacleMotion", "asset_type": ref("/Script/Engine.SkeletalMeshActor")})
    existing = call(B, "list_variables", {"blueprint": bp})
    for name, typ in (("TipPosition", "vector"), ("BasePosition", "vector"), ("Elapsed", "float")):
        if name not in existing:
            call(B, "add_variable", {"blueprint": bp, "name": name, "type_name": typ})
    call(B, "compile_blueprint", {"blueprint": bp, "warnings_as_errors": True})
    graph = call(B, "get_graph", {"blueprint": bp, "graph_name": "EventGraph"})
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence = ROOT / "Artifacts/QA/kraken" / ("tripo-motion-" + stamp)
    evidence.mkdir()
    (evidence / "graph-before.json").write_text(json.dumps(call(B, "read_graph_dsl", {"graph": graph})), encoding="utf-8")
    call(B, "write_graph_dsl", {"graph": graph, "code": DSL})
    call(B, "compile_blueprint", {"blueprint": bp, "warnings_as_errors": True})
    actors = find("QA_TentacleMotion")
    actor = actors[0] if len(actors) == 1 else call(S, "add_to_scene_from_asset", {
        "asset_path": PATH, "name": "QA_TentacleMotion", "xform": {"location": {"x": 0, "y": 500, "z": 150}}})
    for old in find("HeroTentacle_TripoRig_Review"):
        assert call(O, "set_properties", {"instance": old, "values": json.dumps({"bHidden": True})})
    components = call(AC, "get_components", {"actor": actor})
    assert len(components) == 1
    comp = components[0]
    assert call(O, "set_properties", {"instance": comp, "values": json.dumps({
        "skeletalMeshAsset": ref(FOLDER + "SK_HeroTentacle_Tripo_Rig"),
        "animationMode": "AnimationSingleNode",
        "visibilityBasedAnimTickOption": "AlwaysTickPoseAndRefreshBones"})})
    report = {"editor_pid": m.editor_pid, "map": level, "source": "PIE bone socket positions",
              "visual_status": "NOT_VERIFIED", "performance_status": "NOT_MEASURED", "clips": {}}
    for action in ("Idle", "Warning", "Strike", "Recover", "BoatLift", "Submerge"):
        anim = ref(FOLDER + "SK_HeroTentacle_Tripo_Rig_Anim_KrakenTentacleRig_Tentacle_" + action)
        assert call(O, "set_properties", {"instance": comp, "values": json.dumps({"animationData": {
            "animToPlay": anim, "bSavedLooping": True, "bSavedPlaying": True,
            "savedPosition": 0.0, "savedPlayRate": 1.0}})})
        samples = []
        clip = {"animation": anim, "samples": samples}
        report["clips"][action] = clip
        try:
            call(E, "StartPIE", {"options": {"bSimulate": False, "playMode": "PlayMode_InViewPort", "warmupSeconds": 0.2}})
            runtime = [a for a in find("QA_TentacleMotion") if "UEDPIE_" in a["refPath"]]
            assert len(runtime) == 1, runtime
            clip["runtime_actor"] = runtime[0]
            clip["actor_transform_start"] = call(AC, "get_actor_transform", {"actor": runtime[0]})
            for _ in range(8):
                time.sleep(0.35)
                sample = json.loads(call(O, "get_properties", {"instance": runtime[0],
                                    "properties": ["Elapsed", "TipPosition", "BasePosition"]}))
                sample["observed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
                samples.append(sample)
            clip["actor_transform_end"] = call(AC, "get_actor_transform", {"actor": runtime[0]})
            vectors = [tuple(s["TipPosition"][k] for k in "xyz") for s in samples]
            bases = [tuple(s["BasePosition"][k] for k in "xyz") for s in samples]
            clip["tip_max_displacement_cm"] = max(math.dist(a, b) for a in vectors for b in vectors)
            clip["base_max_displacement_cm"] = max(math.dist(a, b) for a in bases for b in bases)
            clip["all_positions_finite"] = all(math.isfinite(v) for row in vectors + bases for v in row)
            clip["passed"] = (clip["all_positions_finite"] and clip["tip_max_displacement_cm"] > 0.5
                and clip["base_max_displacement_cm"] < 0.01
                and clip["actor_transform_start"] == clip["actor_transform_end"]
                and samples[-1]["Elapsed"] > samples[0]["Elapsed"] > 0)
        finally:
            try:
                call(E, "StopPIE")
                clip["pie_stopped"] = not call(E, "IsPIERunning")
            except Exception as exc:
                clip["stop_error"] = str(exc)
                clip["pie_stopped"] = False
            (evidence / "receipt.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(action, {k: clip[k] for k in ("passed", "tip_max_displacement_cm", "base_max_displacement_cm", "pie_stopped")}, flush=True)
        if not clip["passed"] or not clip["pie_stopped"]:
            raise RuntimeError("Motion QA failed; inspect " + str(evidence))
    assert call(A, "save_assets", {"asset_paths": []})
    print(evidence)


if __name__ == "__main__":
    main()
