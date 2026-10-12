# Epic / Unreal Engine 官方示例参考与本机资源清单

> 状态：2026-10-10 文档/文件系统审查（UE 5.8.3）。用于 Mythic Escape v0.5 的 Visual-First V0→V3 开发。**已存在文件 ≠ 已启用插件 ≠ 已在当前项目验证运行 ≠ 可直接商用成品。**
> 只在当前工作确有收益时读取本文件/官方示例；不要为了满足清单而批量下载、安装或迁移大型 Demo。

## 1. 本机已安装内容：以只读目录检查为依据

UE 安装根目录：`D:\Program Files\Epic Games\UE_5.8`。本次只检查此引擎目录以及当前 `MythicEscape.uproject`，**未扫描其他磁盘/用户的 Fab Vault 和独立 UE Projects**。

| 类别 | 本机验证结果 | 可直接利用的价值 |
|---|---|---|
| 官方项目模板 | `Templates/TP_FirstPersonBP`、`TP_ThirdPersonBP`、`TP_VehicleAdvBP`、`TP_VehicleAdv`、`TP_PhotoStudioBP` 等含 `.uproject`；另有 `FeaturePacks/TP_FirstPersonBP.upack`、`TP_ThirdPersonBP.upack`、`TP_VehicleAdvBP.upack` 等 | 无需重新下载模板。项目已由 FirstPersonBP 建立；车辆模板可用于输入/摄像机/组件方式参考，**不是船舶物理或海上模拟 Demo** |
| Water 插件（实验性） | `Engine/Plugins/Experimental/Water/Water.uplugin` 与 `Content/Blueprints/BP_BuoyancyExample.uasset` 存在；插件内还找到 `Fluidsim_Terrain.umap`、`WaterFluidSimtestShallow.umap` | **V0 优先**从浮力 Blueprint、海面材质/波浪入手，不认为自带巨漩涡、完整船控 |
| Water Extras（实验/测试） | `Engine/Plugins/Experimental/WaterExtras/WaterExtras.uplugin`；`Content/Maps/` 下实有 `WaterTestMap.umap`、`WaterVelocityTest.umap`、`WaterSplitscreenTestMap.umap`，`Content/Caustics/Maps/CausticsMap.umap` 也存在 | 可在隔离测试环境查看速度/测试水域/焦散；**官方定位为测试示例，不能直接作为正式打包功能依赖** |
| Water Advanced（实验性） / Buoyancy | `Engine/Plugins/Experimental/WaterAdvanced/WaterAdvanced.uplugin`、`Engine/Plugins/Experimental/Buoyancy/Buoyancy.uplugin` 存在；前者有 Content 资产 | 研究浅水/流体与 Water/Niagara 的组合时再评估，版本兼容、性能与实验状态需先过关；不默认启用 |
| Niagara / Niagara Fluids | `Engine/Plugins/FX/Niagara` 与 `NiagaraFluids` 的 `.uplugin` 和 Content 目录存在 | 水花/雾/触水事件与局部流体，可用本地插件内容做验证；**不等于独立 Content Examples 项目已安装** |
| Control Rig / IK Rig / Animation | `Engine/Plugins/Animation/ControlRig`、`IKRig`、`PoseSearch`、`MotionWarping` 等插件存在 | 触手 Rig/人形重定向与运行时控制技术参考；需在当前项目启用/导入实际资产后才能验证 |
| Chaos / Geometry Collection | `Engine/Plugins/Experimental/ChaosEditor`、`ChaosSolverPlugin`、`GeometryCollectionPlugin` 等存在，GeometryCollectionPlugin 有 Content | 预切碎船与少量实时 Chaos 碎片。仅插件存在，不等于已具备可直接使用的船毁成品 |
| PCG 插件内容 | `Engine/Plugins/PCG/PCG.uplugin`；已确认 `Content/SampleContent/SimpleForest/SimpleForest.umap` 与 `Content/SampleContent/HiGenForest/HiGenForest.umap`，另有 Grammar 等示例地图 | 未来山谷/森林关卡局部程序化参考，不优先用于 Kraken V0 |
| 独立大型官方 Demo | 引擎根目录无 `Samples`；未找到 `ContentExamples`、`ValleyOfTheAncient`、`ElectricDreams`、`LyraStarterGame`、`GameAnimationSample` 常见独立项目目录 | **不能当作已安装 Demo**；可能位于其他磁盘/Launcher Fab Library，本轮不推断全电脑不存在 |

**当前工程启用状态**：在项目 `.uproject` 的显式插件声明中，当前列出 `ModelingToolsEditorMode`、`GameplayStateTree`、`ModelContextProtocol`、`AllToolsets`；**没有显式启用 Water、Water Extras、Niagara Fluids 等**。UE 自动默认启用状态还可能受插件描述符、引擎配置影响，应由真正加载 Mythic Escape 的编辑器核实。**本轮没有实际开关插件、运行上述示例或修改引擎目录**。

## 2. 按阶段选择参考（绝不全部导入）

| 开发阶段 / 任务 | 首选来源与明确入口 | 决策与验收 |
|---|---|---|
| **V0 海洋与浮力（P0 优先）** | 本机 `Water Content/Blueprints/BP_BuoyancyExample`，Water Body、Water Waves、Single Layer Water；按需单独查看 `WaterExtras/WaterVelocityTest` | 在独立小场景验证可驾驶木船、海面浪形、视觉与实际浮力一致，记录 Water 实验性、帧耗时与回退方案；**漩涡力场自己做** |
| **V0 巨兽比例与电影感** | Epic 文档 **Valley of the Ancient**：Ancient One 的 Control Rig/Sequencer、巨物尺度构图、Lumen/Nanite 示例解析 | 优先读技术讲解，不默认下载原项目；这是 UE5 Early Access 展示项目，不能假定整个工程直接兼容 UE5.8 |
| **V0 单触手动画** | 本机 ControlRig/IKRig + Control Rig 官方文档；有明确需求再下载 **Content Examples** 中 `Control Rig` / `IKRig` 样例地图 | 一条真实弯曲/蓄力/命中/回收的可控触手，与船、水花及碰撞同步；**Game Animation Sample 是人形项目，不是触手基础** |
| **V0–V1 水花与雾** | 本机 Niagara 内容 + 官方 Niagara 文档；可选 Content Examples 的 `Niagara_Particles`、`Niagara_Advanced_Particles` | 粒子由真实触手接触、水面与船受力事件驱动；Niagara Fluids/高级体积效果需证明 GPU 开销可接受 |
| **V1–V2 碎船** | Chaos Destruction 官方教程 / Geometry Collection；Content Examples 的 `Chaos Destruction` 地图 | 优先预碎片/状态切换 + 必要的局部物理，不要求整船昂贵的完全动态断裂；剧情船毁不算玩家死亡 |
| **V0 起性能工具** | 已在本机确认 `Engine/Binaries/Win64/UnrealInsights.exe`；GPU Visualizer、stat GPU 等是引擎分析能力，**不是需下载的游戏 Demo** | A/C 代表镜头实际 GameViewport/打包画面记录硬件、分辨率、CPU/GPU 帧耗时、尖峰、内存；60 FPS 只是候选目标 |
| **V2 写实环境借鉴** | **Electric Dreams**：重点参考材质、光照和小型 `ElectricDreams_PCGCloseRange` 地图 | 大型完整地图昂贵且与海洋巨兽目标不同；不让下载/导入大项目阻塞 Kraken |
| **未来后四章** | 本机 PCG 内置地图、Electric Dreams PCG 专题、按需 World Partition | 山谷/高地等确有生态或分布需求时再采用，避免简单区域也引入大规模 PCG |
| **可选人形运动** | **Game Animation Sample**：Motion Matching、双足人形的 locomotion/vaulting/climbing | 仅在第一人称身体、攀爬等确有需求时使用；非人形巨兽不套用人形 Pose Search 库 |
| **可选模块工程** | **Lyra Starter Game** | 只研究必要的模块设计模式；本项目是 Blueprint-first 单人逃生，不强制导入 GAS/Lyra/多人框架 |

## 3. 样例类别与版本/授权防误用

1. **模板（Templates）**：引擎安装中自带项目骨架；例如 Vehicle 模板只提供车辆玩法结构，不包含完整船舶浮力。
2. **插件与插件自带 Content**：位于 `Engine/Plugins/**`；可能包含可运行测试 `.umap`、蓝图和材质。**安装在引擎目录不代表 Mythic Escape 已启用，更不代表可直接用于出货**。Water、Water Extras、Water Advanced 和部分 Buoyancy/Chaos 组件在 5.8 官方索引属于 Experimental。
3. **Content Examples 独立示例项目**：通常通过 Fab/Launcher 单独获取；诸如 `Control Rig`、`IKRig`、`Niagara_Particles`、`Niagara_Advanced_Particles`、`Niagara_Fluids`、`Chaos Destruction` 是**独立项目里的示例地图名称**，不能仅凭本机存在 Niagara 插件就声称已安装该 Demo。
4. **独立大型完整项目**：Valley of the Ancient（早期 UE5 技术展示）、Electric Dreams（PCG/写实环境）、Lyra、Game Animation Sample（人形 Motion Matching）。先用文档理解；只有存在明确阻塞且本机无足够示例时，才经确认下载兼容版本，并在独立 UE 工程中打开验证。
5. **授权核查**：使用引擎自带内容、Fab Marketplace 资源、官方 Samples、第三方素材时逐项记录具体许可、来源、版本和可商用范围。Fab Standard License 一般允许整合进商业项目，但禁止将素材作为独立资源转售/免费再分发；**不同资源不当然套用相同条款**。按具体素材 EULA 及项目交付方式核实。
6. **性能边界**：Electric Dreams 全量演示对硬件要求高；WaterAdvanced/NiagaraFluids/Chaos 等技术必须在实际硬件测试。远景高精原模型/离线电影渲染不能替代真实可玩画面。

## 4. Astra Ultra 的最小参考流程（按需执行）

`确定当前被阻塞的问题 → 检查本地引擎/插件是否已经具备示例 → 阅读匹配的官方 UE5.8 文档 → 在隔离场景最小验证 → 仅迁移自有项目所需代码/资产 → 编译/PIE/性能/视觉复测 → PROGRESS.md 记录来源及结果`

- 不擅自安装大包、下载独立 Demo、批量迁移 Sample Content；也不修改 `D:\Program Files\Epic Games\UE_5.8` 下的官方文件。
- 不为演示先进功能而超出任务范围。具体是否启用 `Water`、`WaterExtras`、`WaterAdvanced`、`NiagaraFluids`、`PCG` 以测试结果和任务实际需要决定，谨慎启用实验性插件。
- 本机测试关卡可以**直接在单独测试工程/编辑器中查看**，无需复制全部素材到主项目。游戏运行画面验收始终依 `docs/VISUAL_QA.md`；已知 MCP Editor `CaptureViewport` 不是可靠的 GameViewport 证据。
- 为每个采用的参考记录：官方 URL、实际本机相对路径/源示例版本、是否启用、移植对象、编译/运行结果、画面与性能证据、未解决兼容/授权风险。无法验证必须写 `NOT_VERIFIED`。

## 5. 官方入口（按需打开）

- [UE Water System](https://dev.epicgames.com/documentation/en-us/unreal-engine/water-system-in-unreal-engine)
- [Water Buoyancy Component 与 BP_BuoyancyExample](https://dev.epicgames.com/documentation/unreal-engine/water-buoyancy-component-in-unreal-engine)
- [Water Extras 插件说明](https://dev.epicgames.com/documentation/unreal-engine/API/PluginIndex/WaterExtras)
- [Water Advanced 插件说明](https://dev.epicgames.com/documentation/unreal-engine/API/PluginIndex/WaterAdvanced)
- [Valley of the Ancient（早期展示）](https://dev.epicgames.com/documentation/en-us/unreal-engine/valley-of-the-ancient-sample-game-for-unreal-engine)
- [Content Examples Sample Project](https://dev.epicgames.com/documentation/unreal-engine/content-examples-sample-project-for-unreal-engine)
- [Control Rig](https://dev.epicgames.com/documentation/en-us/unreal-engine/control-rig-in-unreal-engine)
- [Niagara Overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/niagara-overview-for-unreal-engine)
- [Chaos Destruction](https://dev.epicgames.com/documentation/en-us/unreal-engine/chaos-destruction-in-unreal-engine)
- [Game Animation Sample Project（人形）](https://dev.epicgames.com/documentation/en-us/unreal-engine/game-animation-sample-project-in-unreal-engine)
- [Electric Dreams Environment](https://dev.epicgames.com/documentation/en-us/unreal-engine/electric-dreams-environment-in-unreal-engine)
- [Unreal Insights](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-insights-in-unreal-engine)
- [Fab Standard License](https://www.fab.com/eula)

> 本文件内的本机清单是**本轮 Windows 文件系统实查**，不代表对插件、独立示例和运行性能的验证已完成。新版引擎和 Fab 资源可随时间变更，实施前确认当前安装与权限。
