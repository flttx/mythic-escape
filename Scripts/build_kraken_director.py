"""Author the Kraken director through the live, project-verified UE MCP connection.

Run the editor with -culture=en: UE 5.8's DSL currently hardcodes English IDs.
Generated graphs are source-controlled here; existing graphs are backed up before
replacement. This is chapter arbitration, not a complete playable chapter.
"""
import datetime as dt
import json
from pathlib import Path

from ue_mcp import ROOT, UnrealMCP

BP = "/Game/MythicEscape/Chapters/Kraken/Blueprints/BP_KrakenChapterDirector"
B = "editor_toolset.toolsets.blueprint.BlueprintTools"
A = "editor_toolset.toolsets.asset.AssetTools"
P = "editor_toolset.toolsets.programmatic.ProgrammaticToolset"

VARIABLES = {
    "Phase": "int", "CheckpointPhase": "int", "PracticeRun": "bool",
    "PrototypeSlice": "bool", "TimerStarted": "bool", "RemainingSeconds": "float",
    "RouteComplete": "bool", "InSafeWater": "bool", "ActiveThreat": "bool",
    "ShelterConfirmed": "bool", "HandoffProtection": "float", "FailureReason": "string",
    "WhirlpoolTargetSeconds": "float", "TentacleTargetSeconds": "float",
    "SwimTargetSeconds": "float", "QA_AutoTick": "bool",
}
PARAMS = {
    "InitializeChapter": [("UsePrototype", "bool")], "BeginReveal": [],
    "RevealComplete": [], "CompleteWhirlpool": [], "CompleteTentacleRoute": [],
    "CompleteWreckTransfer": [],
    "UpdateSafety": [("RoutePassed", "bool"), ("InsideShelter", "bool"),
                     ("ThreatPresent", "bool"), ("ProtectedWater", "bool")],
    "AdvanceChapterClock": [("DeltaSeconds", "float")],
    "FailChapter": [("Reason", "string")], "RetryCheckpoint": [],
}

# Phase 0..6 = K0..K6; 7 = failed. Only this director changes phase/result.
# Phase targets describe pacing. They are never used as forced stage timeouts.
GRAPHS = {
"InitializeChapter": """(fn InitializeChapter (UsePrototype)
  (Variables|Default|SetPrototypeSlice UsePrototype)
  (Variables|Default|SetPhase 0)
  (Variables|Default|SetCheckpointPhase 2)
  (Variables|Default|SetPracticeRun false)
  (Variables|Default|SetTimerStarted false)
  (Variables|Default|SetRemainingSeconds (select UsePrototype 240.0 720.0))
  (Variables|Default|SetWhirlpoolTargetSeconds (select UsePrototype 45.0 160.0))
  (Variables|Default|SetTentacleTargetSeconds (select UsePrototype 60.0 200.0))
  (Variables|Default|SetSwimTargetSeconds (select UsePrototype 65.0 180.0))
  (Variables|Default|SetRouteComplete false)
  (Variables|Default|SetInSafeWater false)
  (Variables|Default|SetActiveThreat false)
  (Variables|Default|SetShelterConfirmed false)
  (Variables|Default|SetHandoffProtection 0.0)
  (Variables|Default|SetFailureReason ""))""",
"BeginReveal": """(fn BeginReveal ()
  (if (== (Variables|Default|GetPhase) 0) (Variables|Default|SetPhase 1)))""",
"RevealComplete": """(fn RevealComplete ()
  (if (and (== (Variables|Default|GetPhase) 1) (not (Variables|Default|GetTimerStarted)))
    (Variables|Default|SetTimerStarted true)
    (Variables|Default|SetPhase 2)
    (Variables|Default|SetCheckpointPhase 2)))""",
"CompleteWhirlpool": """(fn CompleteWhirlpool ()
  (if (== (Variables|Default|GetPhase) 2)
    (Variables|Default|SetPhase 3)
    (Variables|Default|SetCheckpointPhase 3)))""",
"CompleteTentacleRoute": """(fn CompleteTentacleRoute ()
  (if (== (Variables|Default|GetPhase) 3)
    (Variables|Default|SetPhase 4)))""",
"CompleteWreckTransfer": """(fn CompleteWreckTransfer ()
  (if (== (Variables|Default|GetPhase) 4)
    (Variables|Default|SetPhase 5)
    (Variables|Default|SetCheckpointPhase 5)
    (Variables|Default|SetHandoffProtection 3.0)
    (Variables|Default|SetActiveThreat false)))""",
"UpdateSafety": """(fn UpdateSafety (RoutePassed InsideShelter ThreatPresent ProtectedWater)
  (if (== (Variables|Default|GetPhase) 5)
    (Variables|Default|SetRouteComplete RoutePassed)
    (Variables|Default|SetInSafeWater InsideShelter)
    (Variables|Default|SetActiveThreat ThreatPresent)
    (Variables|Default|SetShelterConfirmed ProtectedWater)))""",
"AdvanceChapterClock": """(fn AdvanceChapterClock (DeltaSeconds)
  ; Check safety before timeout, including when both happen on this update.
  (if (and (== (Variables|Default|GetPhase) 5)
           (and (Variables|Default|GetRouteComplete)
                (and (Variables|Default|GetInSafeWater)
                     (and (not (Variables|Default|GetActiveThreat))
                          (Variables|Default|GetShelterConfirmed)))))
    (Variables|Default|SetPhase 6)
    (Variables|Default|SetActiveThreat false))
  (if (and (Variables|Default|GetTimerStarted)
           (or (== (Variables|Default|GetPhase) 2)
               (or (== (Variables|Default|GetPhase) 3) (== (Variables|Default|GetPhase) 5))))
    (bind step (select (> DeltaSeconds 0.0) DeltaSeconds 0.0))
    (Variables|Default|SetHandoffProtection
      (select (> (- (Variables|Default|GetHandoffProtection) step) 0.0)
        (- (Variables|Default|GetHandoffProtection) step) 0.0))
    (Variables|Default|SetRemainingSeconds
      (select (> (- (Variables|Default|GetRemainingSeconds) step) 0.0)
        (- (Variables|Default|GetRemainingSeconds) step) 0.0))
    (if (<= (Variables|Default|GetRemainingSeconds) 0.0)
      (Variables|Default|SetFailureReason "Timeout")
      (Variables|Default|SetPhase 7))))""",
"FailChapter": """(fn FailChapter (Reason)
  ; K4 wreck is a story event. It can never enter the failure path.
  (if (or (== (Variables|Default|GetPhase) 2)
          (or (== (Variables|Default|GetPhase) 3)
              (and (== (Variables|Default|GetPhase) 5)
                   (<= (Variables|Default|GetHandoffProtection) 0.0))))
    (Variables|Default|SetFailureReason Reason)
    (Variables|Default|SetPhase 7)))""",
"RetryCheckpoint": """(fn RetryCheckpoint ()
  (if (== (Variables|Default|GetPhase) 7)
    (Variables|Default|SetPhase (Variables|Default|GetCheckpointPhase))
    (Variables|Default|SetPracticeRun true)
    (Variables|Default|SetTimerStarted true)
    ; Authored starting budgets, pending playtest. A retry is explicitly practice.
    (Variables|Default|SetRemainingSeconds
      (select (== (Variables|Default|GetCheckpointPhase) 2)
        (select (Variables|Default|GetPrototypeSlice) 240.0 720.0)
        (select (== (Variables|Default|GetCheckpointPhase) 3)
          (select (Variables|Default|GetPrototypeSlice) 180.0 510.0)
          (select (Variables|Default|GetPrototypeSlice) 90.0 240.0))))
    (Variables|Default|SetRouteComplete false)
    (Variables|Default|SetInSafeWater false)
    (Variables|Default|SetActiveThreat false)
    (Variables|Default|SetShelterConfirmed false)
    (Variables|Default|SetHandoffProtection
      (select (== (Variables|Default|GetCheckpointPhase) 5) 3.0 0.0))
    (Variables|Default|SetFailureReason "")))""",
"EventGraph": """(event EventBeginPlay
  (CallFunction|InitializeChapter :UsePrototype (Variables|Default|GetPrototypeSlice)))
(event EventTick (DeltaSeconds)
  (if (Variables|Default|GetQAAutoTick)
    (CallFunction|AdvanceChapterClock :DeltaSeconds DeltaSeconds)))""",
}


def reference(path):
    return {"refPath": path if "." in path else path + "." + path.rsplit("/", 1)[-1]}


def author(m, path=BP):
    bp = reference(path)
    if m.invoke("EditorToolset.EditorAppToolset", "IsPIERunning")["returnValue"]:
        raise RuntimeError("Stop PIE before authoring")
    m.invoke(P, "get_execution_environment")
    m.invoke(B, "get_graph_dsl_docs")
    if not m.invoke(A, "exists", {"path": path})["returnValue"]:
        m.invoke(B, "create", {"folder_path": path.rsplit("/", 1)[0],
                 "asset_name": path.rsplit("/", 1)[1], "asset_type": reference("/Script/Engine.Actor")})
    existing = m.invoke(B, "list_variables", {"blueprint": bp})["returnValue"]
    for name, typ in VARIABLES.items():
        if name not in existing:
            m.invoke(B, "add_variable", {"blueprint": bp, "name": name, "type_name": typ})
    known_graphs = m.invoke(B, "list_graphs", {"blueprint": bp})["returnValue"]
    # list_graphs returns graph references. Reuse signatures already authored.
    known_paths = [item["refPath"] for item in known_graphs]
    for name, params in PARAMS.items():
        g = m.invoke(B, "add_function_graph", {"blueprint": bp, "graph_name": name})["returnValue"]
        if g["refPath"] not in known_paths:
            for param, typ in params:
                m.invoke(B, "add_function_param", {"graph": g, "param_name": param,
                         "param_type": typ, "input_param": True})
    m.invoke(B, "compile_blueprint", {"blueprint": bp})
    graph = reference(bp["refPath"] + ":EventGraph")
    # Discover every explicit node and its pins before sending DSL to the editor.
    catalog = {}
    for query in ("Variables|Default|", "CallFunction|", "AddEvent|EventBeginPlay", "AddEvent|EventTick"):
        for node in m.invoke(B, "find_node_types", {"graph": graph, "type_id_filter": query,
                            "context_pins": []})["returnValue"]:
            catalog[node] = m.invoke(B, "get_node_type_pins", {"graph": graph,
                                     "type_id": node})["returnValue"]
    if "Variables|Default|GetPhase" not in catalog:
        raise RuntimeError("UE DSL requires an editor started with -culture=en; no graph changed")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence = ROOT / "Artifacts/QA/kraken/director" / stamp
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence / "node_catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    for name, code in GRAPHS.items():
        g = m.invoke(B, "get_graph", {"blueprint": bp, "graph_name": name})["returnValue"]
        old = m.invoke(B, "read_graph_dsl", {"graph": g})["returnValue"]
        (evidence / (name + ".before.dsl")).write_text(old, encoding="utf-8")
        m.invoke(B, "write_graph_dsl", {"graph": g, "code": code})
        print("COMPILED", name, flush=True)
    cdo = m.invoke(B, "get_default_object", {"blueprint": bp})["returnValue"]
    m.invoke("editor_toolset.toolsets.object.ObjectTools", "set_properties",
             {"instance": cdo, "values": json.dumps({"QA_AutoTick": True, "PrototypeSlice": False})})
    m.invoke(B, "compile_blueprint", {"blueprint": bp, "warnings_as_errors": True})
    if not m.invoke(A, "save_assets", {"asset_paths": [path]})["returnValue"]:
        raise RuntimeError("Director save failed")
    (evidence / "receipt.json").write_text(json.dumps({"editor_pid": m.editor_pid,
        "blueprint": path, "graphs_compiled": list(GRAPHS),
        "runtime_verified": False}, indent=2), encoding="utf-8")
    print(evidence)


if __name__ == "__main__":
    author(UnrealMCP())
