# Mythic Escape · Agent Instructions

## Goal
Build a PC-first cinematic first-person mythological giant-creature escape game in Unreal Engine 5. Kraken is the first vertical slice. Player survives; never fights or kills the giant. Treat all other chapters as future scope.

## Execution
- Reply and update progress in Chinese. Read PROGRESS.md plus the relevant docs only; do not read every document on each turn.
- Analyze current result and risks, plan the next smallest testable step, execute, validate, then update PROGRESS.md.
- Prefer autonomous implementation. Avoid over-specifying asset details; prioritize working gameplay and measurable visuals.
- Never claim UE build, runtime, render, Skill installation or screenshots succeeded without tool evidence. If UE is unavailable, write preparation artifacts and mark implementation unverified.
- Keep a concise decision log and link to concrete files/evidence; do not dump full logs or repeatedly restate project background.
- Do not install unrelated Skill packs or invoke all Skill workflows globally. Load relevant Skill only for its trigger.
- Avoid speculative tools and uncontrolled network installers. Review third-party scripts before execution. Preserve existing files and user art.

## Game invariants
1. Flow: calm sea -> Kraken reveal -> whirlpool boat escape -> tentacle boat escape -> scripted launch and wreck -> swim escape -> safety & Kraken submerges.
2. Countdown starts only after the Kraken's reveal; pauses for unavoidable cinematic transitions.
3. Scripted wreck is NOT player failure. Movement and camera agency preserved when feasible.
4. Success requires safe distance and no active hazard, not timer alone. All attacks have readable warnings; random hazards must be fair.
5. Kraken body has coherent world-scale motion; independent animated tentacles sync with collisions and water FX.
6. Distinguish playable frame quality from offline Movie Render Queue quality. Visual gate requires real captures.
7. Develop toward film-grade photorealism from day one **alongside playable gameplay**. Establish an early reusable high-quality visual anchor; don't defer the game's visual identity until P2 or wait for every final asset before implementing controls.
8. Three finite delivery milestones: **M1 finish Kraken FullChapter**, **M2 build the other four complete chapters using M1-validated reusable workflows**, **M3 ship/verify all five**. The 5–7-minute Kraken PrototypeSlice (240s timer/170s expected escape) is only a fast internal test inside M1, not a separate long-term product phase; Kraken FullChapter keeps 14–18 minutes and 720s timer. Do not mix time profiles.
9. Full content length must come from meaningful exploration/branching/creature-driven events, not repeating hazards or simply lengthening clock. Preserve 3 main escape phases, safe observation pockets, fair checkpoints and chapter-specific safety contracts.

## Architecture
For overall modules read docs/ARCHITECTURE.md; for chapter scope start at docs/CHAPTERS.md and open ONLY the relevant docs/levels/XX_*.md. docs/GAME_DESIGN.md is the v0.5 product/timing contract. Write UE-native assets only during implementation and verify, never fabricate .uasset/.umap as text. Blueprint-first for Kraken MVP; move proven shared/performance-sensitive behavior to C++ when needed. UE Water/Niagara/Chaos/Sequencer/Control Rig are optional candidates, not blanket requirements.

## Visual-first quality policy

- **Film-grade photorealism is a day-one quality target, not a P2-only decoration.** Build one small, reusable Unreal gameplay-quality visual anchor early: storm ocean, correctly scaled wooden boat, credible Kraken silhouette, one animated tentacle, authored lighting/atmosphere/materials and their spatial relationships.
- **High-detail 3D geometry is mandatory for hero assets used in accepted visual shots from V0**, especially Kraken's near-view anatomy, independently deforming tentacle/suction cups, wooden boat and visible player parts. A low-poly proxy enlarged with shaders/VFX is NOT a final visual deliverable. Use Tripo/Blender or licensed suitable assets; validate shape, PBR materials, skinning and actual game-closeup before acceptance. See `docs/ARCHITECTURE.md` (high-detail asset pipeline) and `docs/VISUAL_QA.md` (asset quality gate).
- **Two mandatory parallel lines:** Content (complete routes/gameplay) and Visual Quality (high-detail models, rigs, PBR, lighting, environmental response, real-time performance). A chapter is not complete until BOTH pass. In M1 build a representative hero shot early while advancing the full Kraken chapter; use the 5–7-minute PrototypeSlice only for focused functional tests, never as the final milestone.
- Low-detail proxies are permitted ONLY for isolated gameplay/physics tests or distant appropriate LOD, never as accepted close-up hero geometry. Prioritize one production-quality creature section, one tentacle and one boat in V0, not every final creature component at once; use verified optimization, not unchecked polygon-count inflation.
- Use Tripo/Blender/Fab/UE native tools selectively for actual art needs, respecting availability and licenses; early priority is one convincing hero silhouette and tentacle motion, not five complete creatures or full high-res asset production.
- A cinematic quality preset or a beautiful offline render never proves film-grade **real-time** gameplay. The visual gate requires an independently verified player GameViewport/packaged capture, short motion evidence for animation, and measured frame cost on stated hardware/resolution. The current Unreal MCP `CaptureViewport` returns an editor-camera view even while PIE is active: never cite it as player-view evidence.
- Follow **M1→M2→M3** and the cross-chapter visual-quality pipeline in `docs/VISUAL_PIPELINE.md`, plus real-game evidence rules in `docs/VISUAL_QA.md`. After a validated full Kraken chapter, extract repeatable steps into actual project Skills/workflows and demonstrate reuse on another chapter before claiming reusable validation. Do not create pretend/unverified Skills. On blocked gameplay capture mark NOT_VERIFIED; never substitute a fake PASS.

## Animation and rigging
- For player/creature animation or asset-rigging tasks, read ONLY the relevant **Animation & Rigging** section of `docs/ARCHITECTURE.md`; avoid duplicating detailed pipelines here.
- Choose Tripo auto-rig, Blender custom rig/animation, Mixamo human animations, and UE Animation Blueprint / Control Rig / IK Retargeter as appropriate to each actual asset and available tools. Nonhumanoid automatic rigs require quality verification; avoid forcing a universal skeleton.
- Do not fake living motion by moving rigid static meshes alone. Synchronize animated contact frames with hitboxes, water/terrain/vehicle forces, VFX and sound. Kraken tentacles must support distinct controllable attack states and scripted boat-lift transition.
- During **M1**, validate a production-quality Kraken/tentacle hero asset early, then continue animation/contact/collision and real-time quality through the full chapter; use a short PrototypeSlice to debug interactions, not to defer hero rigs and cinematic closeups until a hypothetical later stage. Record reusable rig/import/QA operations for post-M1 Skill extraction without assuming they work for whales, snakes, quadrupeds or birds.

## Visual acceptance
For actual visual changes, consult docs/VISUAL_QA.md and docs/VISUAL_PIPELINE.md; start with Kraken A/C reference shots and expand to all five canonical chapter cameras within M1. Compare giant-to-player scale, silhouette, material, lighting, environmental interaction, movement and measured real-time frame cost. No actual screenshots/clips -> NOT_VERIFIED. Concept images are targets, not in-engine proof.

## Subagent cost / task routing
- The main Astra Ultra agent owns chapter planning, complex rigging/visual decisions and UE integration. Project config caps subagent concurrency at 3.
- Delegate focused read-only searches, UE asset inventory, log inspection and docs summaries to `explorer` (GPT-6 Luna Low).
- Delegate independent ordinary implementation or targeted tests to `ue_worker` (GPT-5.6 Terra Medium). Unspecified subagents use the Terra Low default.
- Do not delegate several writers to the same UE `.umap`/`.uasset` or shared source file at once. Route difficult tasks back to the main agent; custom role model routing is a preference, not proof of runtime usage or lower total cost.

## Skill routing / context economy
- Pure design/docs: follow AGENTS.md and relevant docs; unreal-mcp and visual QA explicitly do NOT trigger for documents.
- UE editor tasks: Epic unreal-mcp Skill only if live connected to the correct project (port 8001, not other host at 8000).
- For UE official Demo/template/plugin references, consult `docs/UE_REFERENCES.md` only when a concrete subsystem needs it; **prefer verified local UE_5.8 templates/plugin examples before downloading separate Fab sample projects**. Plugin present ≠ enabled ≠ working, and test maps/experimental plugins require isolated validation. No bulk asset migrations.
- Visual review: scoped visual QA checklist in docs/VISUAL_QA.md; optional community Skill only after audit.
- Current UE `CaptureViewport` returns editor camera imagery, even if PIE is active; NEVER treat it as proof of the player camera or runtime visual quality without independent capture verification.
- Tripo/Blender asset tasks: project-installed blender-cli Skill ONLY when Blender asset pipeline is relevant. Use host Python UTF-8 mode on Windows; do not preload its offline API index in ordinary UE tasks.
- Otherwise use standard tools and targeted official docs. Avoid repeated catalog/discovery and unnecessary long outputs.

## Safety & progress
Keep credentials out of commits. Do not silently enable remote HTTP interfaces or expose UE control endpoints publicly. User approval needed for destructive changes, deployment, or paid services.
Update PROGRESS.md with Completed / Evidence / Blockers / Next after each milestone.
