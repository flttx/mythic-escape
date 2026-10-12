---
name: mythic-visual-qa
description: "Trigger for real Unreal Engine visual inspection of Mythic Escape creature scale, water, materials, lighting, cinema, animations, performance or visual regressions. Skip for prose/design docs and routine logic."
---

# Mythic Escape Visual QA v2

Goal: editable scene → real UE screenshot → traceable evidence → diagnose up to three issues → modify → recapture same gate. This workflow does NOT improve the vision model itself or infer runtime quality from a picture's existence.

## Capture through Unreal MCP
1. Verify live editor is the correct MythicEscape.uproject. This project's MCP port is 8001, **not 8000** (another UE project). Check active world/map and connection, not port alone.
2. Read only the affected gate (A–E) and chapter entry from docs/VISUAL_QA.md. Fix the map, in-game camera location/transform, FOV, exposure, quality preset, phase and random seed. Use only an **approved** reference image, if one exists.
3. Via the installed unreal-mcp Skill, discover on-demand the camera, PIE/gameplay, screenshot and/or automated-test toolset: list_toolsets → describe_toolset → call_tool. Do NOT invent a tool name or assume an Editor viewport capture is an actual gameplay capture.
4. Capture true PIE or packaged-game frames and keep screenshot path plus UE tool response/log. If only Editor viewport or Movie Render Queue works, record that separately and mark runtime visual quality **NOT_VERIFIED**. For moving water, attacks or cinematics, additionally capture clips/frames to verify motion timing.
5. If there is no live editor or no supported screenshot capture: STOP with blocker and NOT_VERIFIED; never generate a fake screenshot or claim pass.

## Real MCP screenshot helper (Windows)
- From the project root, launch the actual MythicEscape.uproject first. Run: python -X utf8 .agents/skills/mythic-visual-qa/scripts/capture_ue.py --mode editor --output Artifacts/QA/kraken/editor-diagnostic.png
- It checks the owner of **port 8001** is this project's UnrealEditor.exe process, reads IsPIERunning and camera transform, then invokes the verified EditorAppToolset.CaptureViewport with all required annotation parameters. It writes PNG plus adjacent .capture.json receipt. This **editor** image is diagnostic only, never a PIE visual PASS.
- For gameplay testing: python -X utf8 .agents/skills/mythic-visual-qa/scripts/capture_ue.py --mode pie --auto-pie --output Artifacts/QA/kraken/pie-test.png . The helper **has been tested** to start and stop temporary PIE and capture a PNG, but a controlled comparison showed the PIE and editor PNGs were almost identical. The tool captures the editor camera; **do NOT use this output as player-camera gameplay evidence**. A separate genuine in-game capture route (PIE GameViewport/functional screenshot) must be validated before runtime visual PASS.
- Never replay a screenshot over a previous file without an explicit --force. Saved files are in ignored Artifacts/QA. Other ports and projects are rejected.

## Evidence tools (host Python, no Unreal dependency)
Bundled script: .agents/skills/mythic-visual-qa/scripts/visual_qa.py

Once a **real, existing** image file is available:
- python -X utf8 .agents/skills/mythic-visual-qa/scripts/visual_qa.py record --capture Artifacts/QA/kraken/A.png --output Artifacts/QA/kraken/A.json --chapter kraken --gate A --source pie --scene /Game/MythicEscape/Chapters/Kraken/... --phase REVEAL --camera QA_A --preset High --seed 42 --hardware GPU
- python -X utf8 .agents/skills/mythic-visual-qa/scripts/visual_qa.py verify --manifest Artifacts/QA/kraken/A.json
- python -X utf8 .agents/skills/mythic-visual-qa/scripts/visual_qa.py sheet --capture Artifacts/QA/kraken/A.png --reference Art/References/approved_kraken.png --output Artifacts/QA/kraken/A-review.png

The record subcommand only verifies an existing image's dimensions and hashes it; it **does not capture from Unreal**. Source is caller-claimed, not independently authenticated. Verify checks file integrity, **not aesthetic success or real PIE origin**. Sheet creates a side-by-side comparison (needs Pillow), **not a numerical beauty score**. Tool examples are illustrative paths: replace with actual paths before execution.

## Visual review & verdicts
Inspect actual images plus motion evidence; compare scale/shape/shot, materials, lighting, water response and hazard readability. Keep up to 3 specific fixes and re-capture same camera/seed/preset. Capture actual CPU/GPU frame time for performance claims. Movie Render Queue is offline evidence only. Pass labels: PASS / PARTIAL / FAIL / NOT_VERIFIED. Never claim PASS from file existence, hash success or edited scene code alone.

Compact output: gate | original runtime evidence (path + tool) | status | top 3 defects | next actions.

No unrelated skills, mass logs or broad screenshot sweeps. Evidence stays in ignored Artifacts/QA/<chapter>. Do not overwrite captures or assets without explicit intent.
