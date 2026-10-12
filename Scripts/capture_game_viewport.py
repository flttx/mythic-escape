"""Capture the actual PIE GameViewport through PlayerController console routing.

QA-only helper; does not use EditorAppToolset.CaptureViewport. A screenshot and
receipt establish capture provenance, not a visual-quality or performance pass.
"""
import argparse
import datetime as dt
import hashlib
import json
import struct
import time
from pathlib import Path

from ue_mcp import ROOT, UnrealMCP

B = "editor_toolset.toolsets.blueprint.BlueprintTools"
A = "editor_toolset.toolsets.asset.AssetTools"
S = "editor_toolset.toolsets.scene.SceneTools"
O = "editor_toolset.toolsets.object.ObjectTools"
E = "EditorToolset.EditorAppToolset"
BP = "/Game/MythicEscape/Chapters/Kraken/QA/BP_QA_GameCapture"
DSL = """(event EventTick (DeltaSeconds)
  (if (Variables|Default|GetCaptureRequested)
    (Variables|Default|SetCaptureRequested false)
    (Development|ExecuteConsoleCommand
      :Command (Variables|Default|GetCaptureCommand)
      :SpecificPlayer (Game|GetPlayerController :PlayerIndex 0))))"""


def build(m):
    bp = {"refPath": BP + ".BP_QA_GameCapture"}
    if not m.invoke(A, "exists", {"path": BP})["returnValue"]:
        m.invoke(B, "create", {"folder_path": BP.rsplit("/", 1)[0],
                              "asset_name": "BP_QA_GameCapture",
                              "asset_type": {"refPath": "/Script/Engine.Actor"}})
    existing = m.invoke(B, "list_variables", {"blueprint": bp})["returnValue"]
    for name, typ in (("CaptureRequested", "bool"), ("CaptureCommand", "string")):
        if name not in existing:
            m.invoke(B, "add_variable", {"blueprint": bp, "name": name, "type_name": typ})
        m.invoke(B, "set_variable_instance_editable", {"blueprint": bp,
                 "variable_name": name, "instance_editable": True})
    m.invoke(B, "compile_blueprint", {"blueprint": bp, "warnings_as_errors": True})
    graph = m.invoke(B, "get_graph", {"blueprint": bp, "graph_name": "EventGraph"})["returnValue"]
    old = m.invoke(B, "read_graph_dsl", {"graph": graph})
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / "Artifacts/QA/kraken" / ("game-capture-graph-before-" + stamp + ".json")
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
    m.invoke(B, "write_graph_dsl", {"graph": graph, "code": DSL})
    m.invoke(B, "compile_blueprint", {"blueprint": bp, "warnings_as_errors": True})
    actors = m.invoke(S, "find_actors", {"name": "QA_GameCapture", "tag": "", "collision_channels": []})["returnValue"]
    if not actors:
        m.invoke(S, "add_to_scene_from_asset", {"asset_path": BP, "name": "QA_GameCapture", "xform": {}})
    if not m.invoke(A, "save_assets", {"asset_paths": []})["returnValue"]:
        raise RuntimeError("Could not save QA capture helper")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--warmup", type=float, default=5)
    parser.add_argument("--build-helper", action="store_true")
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "Artifacts/QA") or out.suffix.lower() != ".png":
        raise ValueError("Output must be a .png inside project Artifacts/QA")
    if out.exists() or out.with_suffix(".capture.json").exists():
        raise FileExistsError(out)
    if not (64 <= args.width <= 3840 and 64 <= args.height <= 2160):
        raise ValueError("Capture dimensions outside supported QA bounds")
    out.parent.mkdir(parents=True, exist_ok=True)
    m = UnrealMCP()
    if m.invoke(E, "IsPIERunning")["returnValue"]:
        raise RuntimeError("Stop the existing PIE session before an isolated QA capture")
    if args.build_helper:
        build(m)
    level = m.invoke(S, "get_current_level")["returnValue"]
    editor_camera = m.invoke(E, "GetCameraTransform")
    log = ROOT / "Saved/Logs/MythicEscape.log"
    log_start = log.stat().st_size if log.exists() else 0
    # Quoted absolute paths support a project directory containing spaces.
    command = f'HighResShot {args.width}x{args.height} filename="{out.as_posix()}"'
    receipt = {"source": "PIE GameViewport via PlayerController ExecuteConsoleCommand",
               "editor_pid": m.editor_pid, "map": level, "command": command,
               "capture_started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "editor_camera_for_comparison": editor_camera,
               "visual_status": "NOT_VERIFIED", "performance_status": "NOT_MEASURED"}
    try:
        m.invoke(E, "StartPIE", {"options": {"bSimulate": False,
                 "playMode": "PlayMode_InViewPort", "warmupSeconds": args.warmup}})
        actors = m.invoke(S, "find_actors", {"name": "QA_GameCapture", "tag": "", "collision_channels": []})["returnValue"]
        actors = [a for a in actors if "UEDPIE_" in a["refPath"]]
        if len(actors) != 1:
            raise RuntimeError(f"Expected one runtime capture actor; got {actors}")
        receipt["runtime_capture_actor"] = actors[0]
        receipt["player_controllers"] = m.invoke(S, "find_actors", {"name": "PlayerController", "tag": "", "collision_channels": []})["returnValue"]
        ok = m.invoke(O, "set_properties", {"instance": actors[0], "values": json.dumps({
            "CaptureCommand": command, "CaptureRequested": True})})["returnValue"]
        if not ok:
            raise RuntimeError("Failed to request capture on runtime actor")
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if out.exists() and out.stat().st_size > 32:
                break
            time.sleep(1)
        if not out.exists():
            raise RuntimeError("GameViewport did not produce the requested file")
        data = out.read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError("Capture is not PNG")
        receipt["dimensions"] = list(struct.unpack(">II", data[16:24]))
        receipt["sha256"] = hashlib.sha256(data).hexdigest()
        receipt["capture_file_mtime_utc"] = dt.datetime.fromtimestamp(
            out.stat().st_mtime, dt.timezone.utc).isoformat()
        if receipt["dimensions"] != [args.width, args.height]:
            raise RuntimeError("Captured size differs from the requested game render")
        receipt["file_verified"] = True
        receipt["requires_image_review"] = True
    except Exception as exc:
        receipt["error"] = str(exc)
        raise
    finally:
        try:
            m.invoke(E, "StopPIE")
            receipt["pie_stopped"] = not m.invoke(E, "IsPIERunning")["returnValue"]
        except Exception as stop_error:
            receipt["stop_error"] = str(stop_error)
            receipt["pie_stopped"] = False
        # Engine file logging may flush after the screenshot has already landed.
        # Record only evidence mentioning this unique output, never earlier shots.
        try:
            with log.open("rb") as handle:
                handle.seek(log_start)
                lines = handle.read().decode("utf-8", errors="replace").splitlines()
            receipt["log_evidence"] = [line for line in lines if out.name in line or out.stem in line]
        except OSError as log_error:
            receipt["log_error"] = str(log_error)
        out.with_suffix(".capture.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    if not receipt.get("pie_stopped"):
        raise RuntimeError("Capture finished but PIE stop was not verified; see receipt")
    print(json.dumps({"capture": str(out), "dimensions": receipt["dimensions"],
                      "runtime_actor": receipt["runtime_capture_actor"], "visual_status": "NOT_VERIFIED"}))


if __name__ == "__main__":
    main()
