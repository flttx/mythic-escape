"""Build a QA-only subclass and execute the real director functions inside PIE.

This verifies arbitration contracts with explicit event stimuli. It does not
simulate navigation, animation, collision, chapter length or player input.
"""
import datetime as dt
import json
from ue_mcp import ROOT, UnrealMCP
from build_kraken_director import BP, B, A, reference

QA = "/Game/MythicEscape/Chapters/Kraken/QA/BP_QA_KrakenDirector"
MAP = "/Game/MythicEscape/Chapters/Kraken/QA/L_KrakenSystemsQA"
S = "editor_toolset.toolsets.scene.SceneTools"
E = "EditorToolset.EditorAppToolset"
O = "editor_toolset.toolsets.object.ObjectTools"


def call(name, args=""):
    return f"(CallFunction|{name} {args})"


def get(name):
    return f"(Variables|Default|Get{name})"


def check(condition, label):
    return call("CheckContract", f':Condition {condition} :Label "{label}"')


def enter_swim():
    return "\n".join(call(n) for n in ("BeginReveal", "RevealComplete", "CompleteWhirlpool",
                                     "CompleteTentacleRoute", "CompleteWreckTransfer"))


def test_code():
    steps = ["(Variables|Default|SetQAAutoTick false)",
             "(Variables|Default|SetChecksPassed 0)", "(Variables|Default|SetChecksFailed 0)"]
    def emit(code): steps.append(code)
    emit(call("InitializeChapter", ":UsePrototype false"))
    emit(call("RevealComplete"))
    emit(call("CompleteTentacleRoute"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 30.0"))
    emit(check(f"(and (== {get('Phase')} 0) (== {get('RemainingSeconds')} 720.0))", "Calm ignores out-of-order events and time"))
    emit(call("BeginReveal"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 120.0"))
    emit(check(f"(and (== {get('Phase')} 1) (not {get('TimerStarted')}))", "Reveal does not start clock"))
    emit(check(f"(== {get('RemainingSeconds')} 720.0)", "Reveal preserves full budget"))
    emit(call("RevealComplete"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 10.0"))
    emit(call("RevealComplete"))
    emit(check(f"(and (== {get('Phase')} 2) (== {get('RemainingSeconds')} 710.0))", "Reveal starts exactly once"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds -10.0"))
    emit(check(f"(== {get('RemainingSeconds')} 710.0)", "Negative delta cannot grant time"))
    emit(check(f"(and (== {get('WhirlpoolTargetSeconds')} 160.0) (and (== {get('TentacleTargetSeconds')} 200.0) (== {get('SwimTargetSeconds')} 180.0)))", "Full phase targets remain independent"))
    emit(call("CompleteWhirlpool"))
    emit(call("FailChapter", ':Reason "TentacleStrike"'))
    emit(check(f"(== {get('Phase')} 7)", "Boat strike fails during K3"))
    emit(call("RetryCheckpoint"))
    emit(check(f"(and (== {get('Phase')} 3) (and {get('PracticeRun')} (== {get('RemainingSeconds')} 510.0)))", "K3 retry restores authored practice budget"))
    emit(call("CompleteTentacleRoute"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 999.0"))
    emit(call("FailChapter", ':Reason "ScriptedWreck"'))
    emit(check(f"(and (== {get('Phase')} 4) (== {get('RemainingSeconds')} 510.0))", "Scripted wreck pauses and cannot fail"))
    emit(call("CompleteWreckTransfer"))
    emit(call("FailChapter", ':Reason "HandoffStrike"'))
    emit(check(f"(and (== {get('Phase')} 5) (== {get('HandoffProtection')} 3.0))", "Swim handoff protects player"))
    emit(call("CompleteWreckTransfer"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 3.0"))
    emit(call("FailChapter", ':Reason "SwimStrike"'))
    emit(check(f"(== {get('Phase')} 7)", "Protection expires then hazards can fail"))
    emit(call("RetryCheckpoint"))
    emit(check(f"(and (== {get('Phase')} 5) (and (== {get('RemainingSeconds')} 240.0) (not {get('RouteComplete')})))", "K5 retry clears safety and restores budget"))
    emit(call("UpdateSafety", ":RoutePassed false :InsideShelter true :ThreatPresent false :ProtectedWater true"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 0.0"))
    emit(check(f"(== {get('Phase')} 5)", "Shelter alone cannot win"))
    emit(call("UpdateSafety", ":RoutePassed true :InsideShelter true :ThreatPresent true :ProtectedWater true"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 0.0"))
    emit(check(f"(== {get('Phase')} 5)", "Active threat prevents victory"))
    emit(call("UpdateSafety", ":RoutePassed true :InsideShelter true :ThreatPresent false :ProtectedWater false"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 0.0"))
    emit(check(f"(== {get('Phase')} 5)", "Chapter shelter contract required"))
    emit(call("UpdateSafety", ":RoutePassed true :InsideShelter false :ThreatPresent false :ProtectedWater true"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 0.0"))
    emit(check(f"(== {get('Phase')} 5)", "Route completion outside shelter cannot win"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 240.0"))
    emit(check(f"(and (== {get('Phase')} 7) (== {get('RemainingSeconds')} 0.0))", "Timeout fails and clamps clock"))
    emit(call("InitializeChapter", ":UsePrototype false"))
    emit(enter_swim())
    emit(call("AdvanceChapterClock", ":DeltaSeconds 719.0"))
    emit(call("UpdateSafety", ":RoutePassed true :InsideShelter true :ThreatPresent false :ProtectedWater true"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 1.0"))
    emit(check(f"(== {get('Phase')} 6)", "Safety wins on timeout update"))
    emit(call("FailChapter", ':Reason "LateStrike"'))
    emit(call("RetryCheckpoint"))
    emit(call("AdvanceChapterClock", ":DeltaSeconds 100.0"))
    emit(check(f"(and (== {get('Phase')} 6) (== {get('RemainingSeconds')} 1.0))", "Aftermath ignores hazards retry and time"))
    emit(call("InitializeChapter", ":UsePrototype true"))
    emit(check(f"(and (== {get('RemainingSeconds')} 240.0) (not {get('PracticeRun')}))", "Prototype reset is independent"))
    emit(check(f"(and (== {get('WhirlpoolTargetSeconds')} 45.0) (and (== {get('TentacleTargetSeconds')} 60.0) (== {get('SwimTargetSeconds')} 65.0)))", "Prototype phase targets"))
    emit(enter_swim())
    emit(call("AdvanceChapterClock", ":DeltaSeconds 240.0"))
    emit(check(f"(== {get('Phase')} 7)", "Prototype timeout still applies during handoff protection"))
    emit(call("RetryCheckpoint"))
    emit(check(f"(and (== {get('RemainingSeconds')} 90.0) (== {get('Phase')} 5))", "Prototype K5 retry budget"))
    for prototype, budget in (("false", 720.0), ("true", 240.0)):
        emit(call("InitializeChapter", ":UsePrototype " + prototype))
        emit(call("BeginReveal"))
        emit(call("RevealComplete"))
        emit(call("FailChapter", ':Reason "WhirlpoolCore"'))
        emit(call("RetryCheckpoint"))
        emit(check(f"(and (== {get('Phase')} 2) (and {get('PracticeRun')} (== {get('RemainingSeconds')} {budget})))", "K2 checkpoint budget " + prototype))
    emit("(Variables|Default|SetChecksComplete true)")
    emit(f'''(if (== {get('ChecksFailed')} 0)
      (Development|PrintString :InString "MYTHIC_DIRECTOR_QA_PASS" :bPrintToLog true)
      (else (Development|PrintString :InString "MYTHIC_DIRECTOR_QA_FAIL" :bPrintToLog true)))''')
    return "(event EventBeginPlay\n" + "\n".join(steps) + ")"


def main():
    m = UnrealMCP()
    if m.invoke(E, "IsPIERunning")["returnValue"]:
        raise RuntimeError("Existing PIE session; stop it deliberately before QA")
    bp = reference(QA)
    if not m.invoke(A, "exists", {"path": QA})["returnValue"]:
        m.invoke(B, "create", {"folder_path": QA.rsplit("/", 1)[0], "asset_name": QA.rsplit("/", 1)[1],
                              "asset_type": reference(reference(BP)["refPath"] + "_C")})
    variables = m.invoke(B, "list_variables", {"blueprint": bp})["returnValue"]
    for name, typ in [("ChecksPassed", "int"), ("ChecksFailed", "int"), ("ChecksComplete", "bool")]:
        if name not in variables:
            m.invoke(B, "add_variable", {"blueprint": bp, "name": name, "type_name": typ})
    old_graphs = m.invoke(B, "list_graphs", {"blueprint": bp})["returnValue"]
    fg = m.invoke(B, "add_function_graph", {"blueprint": bp, "graph_name": "CheckContract"})["returnValue"]
    if fg["refPath"] not in [g["refPath"] for g in old_graphs]:
        for n, t in [("Condition", "bool"), ("Label", "string")]:
            m.invoke(B, "add_function_param", {"graph": fg, "param_name": n, "param_type": t, "input_param": True})
    m.invoke(B, "compile_blueprint", {"blueprint": bp})
    eg = m.invoke(B, "get_graph", {"blueprint": bp, "graph_name": "EventGraph"})["returnValue"]
    for query in ("CallFunction|", "Variables|Default|", "Development|PrintString"):
        for node in m.invoke(B, "find_node_types", {"graph": eg, "type_id_filter": query, "context_pins": []})["returnValue"]:
            m.invoke(B, "get_node_type_pins", {"graph": eg, "type_id": node})
    m.invoke(B, "write_graph_dsl", {"graph": fg, "code": '''(fn CheckContract (Condition Label)
      (if Condition
        (Variables|Default|SetChecksPassed (+ (Variables|Default|GetChecksPassed) 1))
        (else
          (Variables|Default|SetChecksFailed (+ (Variables|Default|GetChecksFailed) 1))
          (Development|PrintString :InString Label :bPrintToLog true))))'''})
    code = test_code()
    expected_checks = code.count("(CallFunction|CheckContract ")
    m.invoke(B, "write_graph_dsl", {"graph": eg, "code": code})
    m.invoke(B, "compile_blueprint", {"blueprint": bp, "warnings_as_errors": True})
    if not m.invoke(A, "exists", {"path": MAP})["returnValue"]:
        m.invoke(A, "duplicate", {"path": "/Engine/Maps/Templates/Template_Default", "new_path": MAP})
    m.invoke(A, "save_assets", {"asset_paths": []})
    m.invoke(S, "load_level", {"level_path": MAP})
    actors = m.invoke(S, "find_actors", {"name": "KrakenDirectorContractQA", "tag": "", "collision_channels": []})["returnValue"]
    if not actors:
        m.invoke(S, "add_to_scene_from_asset", {"asset_path": QA, "name": "KrakenDirectorContractQA", "xform": {}})
    m.invoke(A, "save_assets", {"asset_paths": [MAP, QA, BP]})
    try:
        m.invoke(E, "StartPIE", {"options": {"bSimulate": False, "playMode": "PlayMode_InViewPort", "warmupSeconds": 1}})
        runtime = m.invoke(S, "find_actors", {"name": "KrakenDirectorContractQA", "tag": "", "collision_channels": []})["returnValue"]
        if len(runtime) != 1 or "UEDPIE_" not in runtime[0]["refPath"]:
            raise RuntimeError("Unable to independently identify the PIE QA actor")
        result = json.loads(m.invoke(O, "get_properties", {"instance": runtime[0],
            "properties": ["ChecksPassed", "ChecksFailed", "ChecksComplete", "Phase", "RemainingSeconds"]})["returnValue"])
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        output = ROOT / "Artifacts/QA/kraken" / ("director-pie-" + stamp + ".json")
        receipt = {"editor_pid": m.editor_pid, "runtime_actor": runtime[0], "map": MAP,
                   "result": result, "expected_checks": expected_checks,
                   "scope": "Blueprint arbitration only; not full gameplay or visual QA"}
        output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(json.dumps(receipt, indent=2))
        print(output)
        if not result.get("ChecksComplete") or result.get("ChecksFailed") != 0 or result.get("ChecksPassed") != expected_checks:
            raise RuntimeError("Director contract QA did not pass")
    finally:
        if m.invoke(E, "IsPIERunning")["returnValue"]:
            m.invoke(E, "StopPIE")


if __name__ == "__main__":
    main()
