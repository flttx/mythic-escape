# Mythic Escape · 巨兽逃生

基于 **Unreal Engine 5.8.3** 的第一人称电影化神话巨兽逃生项目。首章开发目标：克拉肯「深渊苏醒」。

## 本地工程

- 工程入口：`MythicEscape.uproject`
- 引擎安装：`D:\Program Files\Epic Games\UE_5.8`
- 项目模板：Epic 官方 `TP_FirstPersonBP` 蓝图项目，加装 Characters / Input / LevelPrototyping 官方共享资源。
- 默认启动地图：`/Game/FirstPerson/Lvl_FirstPerson`（**模板测试场景，不是克拉肯场景**）。
- `Content/FirstPerson` 是官方基础角色及地图；后续克拉肯内容按 `Content/MythicEscape/Chapters/Kraken` 分层创建。

已有 UE 加载与蓝图编译验证；章节状态契约、运动学船、原生浮力、物理船输入分别通过真实 PIE 25/5/10/4 项检查。V5 高精克拉肯为静态候选，完整章节、电影级画面与打包性能尚未验收；最新证据和失败项见 [PROGRESS.md](PROGRESS.md)。

## 当前开发入口与验证

- 使用 Git LFS 保存 UE 资产、模型源文件和纹理；拉取工程后执行 `git lfs pull`，再用 UE 5.8 打开 `.uproject`。
- 当前可控物理船 QA 地图：`/Game/MythicEscape/Chapters/Kraken/QA/L_KrakenPlayableBoatQA`。在编辑器打开后运行 PIE，测试船上移动与独立观察；它不是正式首章。
- MCP 客户端单测：`python -X utf8 -m unittest discover -s Scripts/tests -p 'test_ue_mcp.py'`。
- 船与浮力验证：`Scripts/verify_kraken_boat.py`、`verify_boat_buoyancy.py`、`verify_physics_boat.py`，可先查看 `--help`。章节导演验证 `Scripts/verify_kraken_director.py` 会直接创建/运行 QA，不支持 `--help`；使用前先读入口源码。确认 8001 连接本工程且未处于 PIE，不能与手动试玩或其他写入并发执行。
- `Artifacts/QA/` 原始截图、CSV、采样凭据仅保留本地，不纳入 Git；已核对的结论与限制记录在进度文档。临时下载链接、`.tripo/` 会话状态、旧转换输出目录链接及自动备份也不提交；源 GLB、准备后的 FBX/Blend 和 UE 资产均保留版本。

## 关卡内容与时长路线（设计 v0.5）
- **M1 最终交付是克拉肯 14–18 分钟 FullChapter**。内部可用 5–7 分钟 PrototypeSlice（240s 主计时、170s 正常逃生目标）快速测试 K0→K6；目前已有独立系统与船控制 QA，**尚未连成完整可通关流程**。
- **FullChapter 目标**：克拉肯 14–18 分、利维坦 17–22 分、耶梦加得 17–22 分、贝希摩斯 14–18 分、齐兹 16–20 分。三个核心逃生阶段不变，新增探索、真实分支、巨兽环境连锁与观测节点。
- 正式版倒计时分别为 720/960/960/720/840s，仅覆盖巨兽关键揭示之后的逃生段；总时长还包含自由探索、登场和结尾。全为**未经试玩验证的设计初值**。
- 具体 `PrototypeSlice` / `FullChapter` 配置与容错见 [设计总纲](docs/GAME_DESIGN.md) 和 [阶段机制](docs/ARCHITECTURE.md)。

## Visual-First 开发路线
- **三大交付里程碑：M1 完成克拉肯 14–18 分钟 FullChapter，M2 完成其余四章，M3 五章最终验收与发布**。内容线和视觉品质线在每章开发时同步推进，电影级实机写实、高精度 3D 模型、骨骼动画与帧耗时从首章第一片可用海域开始就要求。5–7 分钟 PrototypeSlice 仅是 M1 内部快速验证配置，不是独立长期交付目标。
- **高精度 3D Hero Assets 是首章起就执行的视觉品质硬要求**：克拉肯可见主体结构、至少一条含立体吸盘的可变形触手、木船及第一人称近景可见部位，需要真实几何、PBR 材质和可用动画。优先 Tripo 生成/合法现成资产 + Blender 精修/绑定 + UE5.8 验证；允许隔离玩法灰盒和远景降精，但不以放大低模+特效冒充通过。精度按镜头距离和实时性能配置。
- 局部物理/路网允许用短期灰盒诊断，但不能把灰盒作为正式风格或电影级品质的视觉交付。早期高品质镜头必须能融入真正游戏，不能只做离线效果图。
- **视觉品质线**：每章先建立 A（登场巨物尺度）与 C（生物/环境近景交互）代表镜头，完整交付前再验证本章 A–E、真实 GameViewport 动画及性能；M1 结束后将 Tripo/Blender→UE、骨骼、PBR、光照、真实截图/性能 QA 的已验证经验整理为候选 Skill/工作流，并在 M2 的不同体型/环境中复测后确认通用。详见 [视觉品质生产线](docs/VISUAL_PIPELINE.md) 和 [实时视觉 QA](docs/VISUAL_QA.md)。

## Codex + Unreal MCP

- 项目专属 Skill：`.agents/skills/unreal-mcp`、`.agents/skills/mythic-visual-qa`
- Codex 连接配置：`.codex/config.toml`
- Mythic Escape MCP：`http://127.0.0.1:8001/mcp`，仅限本机。
- **端口 8000 已被其它 UE58-MCP-Host 工程使用，请勿连接错项目。**
- 编辑器开启时 MCP 才可用；已通过握手和实际工具集读取验证。结束编辑器后，需重新开启工程才能使用。

## 开发参考

- [游戏需求与流程](docs/GAME_DESIGN.md)
- [五章索引及特色机制](docs/CHAPTERS.md)
- [克拉肯](docs/levels/01_KRAKEN.md) / [利维坦](docs/levels/02_LEVIATHAN.md) / [耶梦加得](docs/levels/03_JORMUNGANDR.md) / [贝希摩斯](docs/levels/04_BEHEMOTH.md) / [齐兹](docs/levels/05_ZIZ.md)
- [模块架构](docs/ARCHITECTURE.md)
- [视觉验收](docs/VISUAL_QA.md)
- [Epic Demo 参考](docs/UE_REFERENCES.md)
  - 已在本机 UE5.8 引擎目录核验：自带 First/Third Person、Vehicle 等模板，Water/Water Extras 浮力和测试地图、Niagara/Control Rig/PCG 等插件内容。独立 Content Examples、Valley of the Ancient、Electric Dreams、Lyra、Game Animation Sample **未在本次检查的引擎目录找到**；引擎自带插件不等于 Mythic Escape 工程已启用。优先读该清单再决定是否获取外部 Demo。
- [Skill 和工具决策](docs/TOOLS_AND_SKILLS.md)
- [当前进度](PROGRESS.md)

已完成整体架构与五章独立设计文档（设计状态，尚未完成五章 UE 内容）；优先阅读目录索引并按当前章节加载文档，减少上下文。

下一步修复长帧下的浮力稳定性、船舱水体穿插和触手 Idle 接缝，继续接入生物接触事件、完整路线、游泳与恢复；可用 PrototypeSlice 快速调试，**最终交付仍为完整 14–18 分钟关卡及 A–E 视觉品质门**。首章完成后提炼并验证可复用工作流，再进入后四章。
