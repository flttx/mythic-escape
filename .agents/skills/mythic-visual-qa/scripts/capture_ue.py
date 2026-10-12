#!/usr/bin/env python3
"""Capture a UE 5.8 MythicEscape viewport through the project's live local Unreal MCP."""
import argparse
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

PORT = 8001
SERVER = "http://127.0.0.1:8001/mcp"
TOOLSET = "EditorToolset.EditorAppToolset"


def verify_local_project() -> str:
    script = (
        "$x=Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction Stop | "
        "Where-Object {$_.LocalAddress -eq '127.0.0.1'} | Select-Object -First 1;"
        "if($null -eq $x){exit 2};"
        "$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$x.OwningProcess);"
        "if($null -eq $p){exit 3};"
        "Write-Output ($p.ProcessId.ToString()+'|'+$p.CommandLine)"
    )
    res = subprocess.run(["pwsh", "-NoProfile", "-Command", script],
                         text=True, capture_output=True, timeout=12, encoding="utf-8", errors="replace")
    if res.returncode or "|" not in res.stdout:
        raise RuntimeError("Could not verify the local MCP server owner's process")
    process_line = res.stdout.strip().splitlines()[-1]
    pid, command = process_line.split("|", 1)
    project = str((Path.cwd() / "MythicEscape.uproject").resolve())
    if "UnrealEditor.exe" not in command or project.casefold() not in command.casefold():
        raise RuntimeError("PORT 8001 BELONGS TO WRONG ENGINE PROJECT; refusing capture")
    return pid


class MCP:
    def __init__(self):
        self.counter = 1
        self.session = None
        init = self.post("initialize", {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "mythic-visual-qa-capture", "version": "1.0"},
        })
        if "result" not in init:
            raise RuntimeError("Unreal MCP initialize failed")

    def post(self, method, params):
        data = json.dumps({"jsonrpc": "2.0", "id": self.counter, "method": method, "params": params}).encode()
        self.counter += 1
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(SERVER, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=50) as resp:
            if not self.session:
                self.session = resp.headers.get("Mcp-Session-Id")
            result = json.loads(resp.read())
        if "error" in result:
            raise RuntimeError("MCP error: " + str(result["error"])[:400])
        return result

    def call(self, name, arguments):
        response = self.post("tools/call", {
            "name": "call_tool", "arguments": {
                "toolset_name": TOOLSET, "tool_name": name, "arguments": arguments,
            },
        })
        result = response.get("result", {})
        if result.get("isError"):
            raise RuntimeError("Unreal tool error: "+str(result.get("content"))[:420])
        for block in result.get("content", []):
            if block.get("type") == "text":
                parsed = json.loads(block["text"])
                return parsed.get("returnValue", parsed) if isinstance(parsed, dict) else parsed
        if result.get("content") == []:
            return None
        raise RuntimeError("Tool response had no structured text result")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, help="Capture PNG inside ignored Artifacts/QA")
    cli.add_argument("--mode", choices=["editor", "pie"], required=True)
    cli.add_argument("--auto-pie", action="store_true", help="Start and stop a temporary PIE session")
    cli.add_argument("--force", action="store_true")
    args = cli.parse_args()
    image_path = Path(args.output).resolve()
    if image_path.exists() and not args.force:
        raise RuntimeError("Output exists; refusing to overwrite")
    if args.auto_pie and args.mode != "pie":
        raise RuntimeError("--auto-pie requires --mode pie")
    pid = verify_local_project()
    mcp = MCP()
    own_pie = False
    try:
        active = bool(mcp.call("IsPIERunning", {}))
        if args.mode == "editor" and active:
            raise RuntimeError("PIE already running; editor capture mislabeled")
        if args.mode == "pie" and not active:
            if not args.auto_pie:
                raise RuntimeError("PIE is not running, use --auto-pie")
            mcp.call("StartPIE", {"options": {
                "bSimulate": False, "playMode": "PlayMode_InViewPort", "warmupSeconds": 2,
            }})
            own_pie = True
            active = bool(mcp.call("IsPIERunning", {}))
            if not active:
                raise RuntimeError("PIE did not start")
        transform = mcp.call("GetCameraTransform", {})
        annotations = {
            "gridSpacing": 0, "gridExtent": 0, "gridHeight": 0,
            "maxLabelDistance": 0, "classFilter": {"refPath": ""}, "maxLabels": 0,
        }
        image = mcp.call("CaptureViewport", {
            "captureTransform": transform, "annotations": annotations, "bShowUI": False,
        })["image"]
        if image["mimeType"] != "image/png":
            raise RuntimeError("Unexpected screenshot encoding: " + image["mimeType"])
        binary = base64.b64decode(image["data"], validate=True)
        if not binary.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("MCP image is not a PNG")
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(binary)
        receipt = {
            "schema": "mythic-ue-capture/1",
            "project": str((Path.cwd() / "MythicEscape.uproject").resolve()),
            "server": SERVER, "editor_pid": pid,
            "tool": TOOLSET + ".CaptureViewport",
            "mode_claim": args.mode, "pie_active_at_capture": active,
            "image_surface": "Editor viewport camera, NOT independently validated as player camera",
            "runtime_gameplay_frame_verified": False,
            "camera_transform": transform, "image_sha256": hashlib.sha256(binary).hexdigest(),
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "note": "Viewport image + PIE session status; does not independently prove camera is the gameplay camera or guarantee visual quality",
        }
        image_path.with_suffix(".capture.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        print(f"CAPTURE={image_path}")
        print(f"MCP_TOOL={receipt['tool']} PIE_ACTIVE={active} SIZE_BYTES={len(binary)}")
        print("WARNING=CaptureViewport is editor-camera output. PIE active does NOT prove in-game player-camera content.")
        print(f"RECEIPT={image_path.with_suffix('.capture.json')}")
    finally:
        if own_pie:
            mcp.call("StopPIE", {})


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print("CAPTURE_ERROR="+str(err), file=sys.stderr)
        sys.exit(2)
