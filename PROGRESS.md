# PROGRESS · Mythic Escape

## Current
**M1 正在实施，尚未完成。章节状态已有真实 PIE 25 项契约记录；可控物理船与长帧物理/波浪同步修复已有运行证据。环境 R4 已保存；V5 高精主体已完成骨骼绑定、4 个动画片段和 UE 导入，QA 图已放置动画主体，不再是纯静态展示。骨骼版本的实时性能、打击视觉和浮力回归尚未通过，最近一轮受 D3D12/GPU 环境问题阻塞。完整路线、游泳/HUD/检查点恢复、接触水效及 14–18 分钟全章首通仍未完成；电影级实时视觉未验收。**


## 进度核对与提交 · 2026-10-12

### Completed
- 整理本地已保存的环境 R4、物理/波浪时钟同步配置、V5 骨骼/动画源资产与 UE 资产，以及导入、放置、采集和海况验证脚本，作为 M1 开发恢复点。
- 修正 Current 的静态主体旧描述；动画数值以当前 `ArtSource/Kraken/Rig/anim.report.json` 为准：StrikeA 最大梢速为 101.5m/s，求解误差 1.81m。
- 移除 UE 自动写入的本机 Android 服务令牌；保留原网络设置。历史记录注明的无关自动重存 `BP_QA_BuoyantBoat.uasset` 保留在工作区，不纳入本次提交。

### Evidence
- 本轮实际执行：`python -m unittest discover -s Scripts/tests -v`，6/6 通过；Scripts 与新 Rig 目录共 30 个 Python 文件 AST 解析通过，新 Rig JSON 全部解析通过；`git diff --check` 通过。
- 只读复核本地原始凭据：`kraken-rig-import.json` 为 976,414 顶点、152 骨、保存成功；`seakeeping-final-3fps-20261012-142744/receipt.json` 与 `seakeeping-final-12fps-20261012-142857/receipt.json` 的正常、限帧、恢复阶段均有有效样本，无相机入水和上浪。
- 上述是既有运行凭据核对；本轮没有重跑 UE/Blender、蓝图编译、实时性能或视觉验收。原始 QA 数据仍在本地忽略目录 `Artifacts/QA/kraken/`，不随 Git 推送。

### Blockers
- 骨骼版本性能与 GPU 稳定性仍未验证；此前浏览器 GPU 负载为历史观察，本轮未复测当前占用。
- QA 工具限制：海况脚本的 `passed` 仅检查相机入水，空有效样本也可能返回通过，后续验收必须同时检查样本数、干舷和无效查询；环境脚本在已有 PPV 上重做后不能完整回滚旧后期设置。当前提交保留实现并明确限制，不将其作为完整自动验收/回滚保证。

### Next
1. GPU 环境稳定后，对已保存骨骼版本复测浮动 PIE、带游戏时间戳的动作画面、帧耗时与海况，先修正上述 QA 工具边界。
2. 接通导演状态到动画、水面接触事件和 K4 托举，同时推进船舱遮罩、白沫/溅水。
3. 补齐 FullChapter 路线、游泳、HUD、检查点恢复与全章首通；内容线及 A–E 真实玩家视角/性能均通过后才关闭 M1。

## 克拉肯骨骼动画（进行中）· 2026-10-12

### Completed
- **现状盘点**：V5 主体为单一静态网格（976,414 顶点、1.9M 三角面，臂展 1000m），无骨骼。旧 V2 独立触手只有正弦摆动，且 Idle 有 1.35m 接缝，不作为主体方案。决定复用 V5 高精网格，不重做模型，也不减面。
- **自动绑定**（`ArtSource/Kraken/Rig/`，numpy 实现，不经 Blender 猜测）：
  - 焊接 UV 缝后，从触手枢纽计算表面测地距离。150m 阈值下稳定分出外套膜和 8 条腕（150–300m 区间结果一致）；腕与外套膜在接触处相连，通过流域分割回填到枢纽。
  - 在各部位内部用受限测地距离（避免经接触点抄近路）提取环形质心作为中心线，生成 151 骨：root/head、外套膜 5 节、8×18 腕节，腕长 405–647m。
  - 蒙皮用高斯平滑多骨权重（最多 4 个影响骨），腕根与头部在 45m 内过渡，权重和为 1。
  - 预览：`segmentation.report.json`、`rig.report.json`、`preview_rig.py`。
- **程序化表演**（`animate_kraken.py`，正向运动学，所有片段首尾都落在 Idle 第 0 帧的姿态上，接缝误差均为 0m）：
  - Idle：48s 无缝循环。每条腕有独立相位、波数和周期（24/16/9.6s 谐波），由根向梢传递，幅度向梢递增。外套膜做 12s 呼吸脉动，身体缓慢升沉、偏航和横滚。最大梢速 19.6m/s。
  - Emerge：26s，从 -330m 上浮，约 6.6s 破水，外套膜先出水，腕拖在后面再由梢向外展开。
  - StrikeA：32s，arm4。0–3.5s 起势；约 9.5s 立起，梢部高出海面约 260m，并朝船道倾身；3.5–14s 为可读的预警段，包括盘绕和蓄力；之后 6.5s 加速下砸，落点用数值求解，误差 1.8m，位置在船前 45m、偏侧 30m 的海面；最后拖拽并缓慢收回。
  - Submerge：22s，下沉 340m。
  - 瞬态动作叠加在 Idle 上，并经过逐骨延迟的阻尼弹簧，梢部更重、更慢，产生惯性、过冲和回稳。下砸的梢速受“不快于从约 240m 处坠落”约束：首版峰值 175m/s，通过放慢时长并缩短弧线降到约 101.5m/s（以当前 anim.report.json 为准）。
- **Blender 两遍处理**（blender-cli 证据计划已封存：`assemble_plan.json`、`bake_plan.json`）：
  - 第 1 遍：顶点顺序与 GLB 逐点一致（偏差 0.0m），写入 3.73M 条权重，导出 `Bone.matrix_local`。
  - 第 2 遍：numpy 把骨骼空间旋转换算为骨骼局部旋转（P = BᵀQB，根骨平移 = BᵀT），静止姿态骨骼与推导结果误差 0.04mm；以 10Hz 打四元数关键帧，导出包含全部动作的 `SK_Kraken_V5.fbx`。
- **UE 导入**（`Scripts/import_kraken_rig.py`）：`/Game/.../Kraken_V5/Rig/SK_Kraken_V5`（976,414 顶点、152 骨）及 4 个 AnimSequence，使用湿皮肤材质，包围盒与静态版完全一致。`Scripts/place_kraken_animated.py` 在 QA 图中放置 `Kraken_V5_Animated`（与静态版同一变换，播放 Idle，关闭碰撞，离屏仍更新骨骼），静态版移到海面下 5km 留作对照，已保存。
- 用场景射线验证坐标映射：UE 导入时 Blender 的 Y 轴取反。四个预测点在该假设下均在预期高度 ±4m 内命中，因此打击落点所用的船体局部坐标是正确的。
- 真实 PIE 玩家视角下 Idle 和 StrikeA 均正常渲染并播放，未见撕裂：`kraken-anim-idle-20261012-151422/`、`kraken-strikea-play-20261012-152536/contact-sheet.png`。

### Blockers / 问题
- **GPU 环境阻塞**：加入骨骼克拉肯后，编辑器三次 D3D12 设备崩溃（两次在 PIE 启动时创建 16384×4096×2 的 VSM 页池；一次在启动时出现 E_OUTOFMEMORY，而本进程显存只用了 2.9/7.3GB）。随后发现编辑器退出后 GPU 仍有 100% 占用，Chrome(PID 5796) 约占 100% GPU 和 1.8GB 显存，Edge 另占 1.4GB。这与早先的 SW Power Cap 和 GPU 帧时间 31–63ms 波动一致。需要用户处理浏览器负载后再继续实机验证。
- 骨骼网格尚未启用 Nanite（在编辑器崩溃前未能保存），目前是 976k 顶点在每个渲染通道里做顶点着色器蒙皮，性能未测（NOT_MEASURED）。
- 打击片段的实时视觉尚未判定：首轮截帧缺少游戏时间戳，无法与动画时间对应。已在 `BP_QA_ViewportProbe` 加入 `GameTimeSeconds`/`RealTimeSeconds`，并写入 `capture_boat_motion.py` 的回执。
- 尚未完成：遭遇时间线（导演状态 → 片段播放）、水面交互事件点（骨骼世界位置与水面高度比较）、K4 托举触手、seakeeping 回归。

## 船体淹没修复：物理与波浪时钟同步 · 2026-10-12

### Completed
- 新增 `Scripts/verify_boat_seakeeping.py`：PIE 浮动窗口中不截图连续采样，记录相机距局部水面高度（负值即入水）、最小干舷（负值即上浪）、浮筒入水数，并记录运行时的物理和时间设置。可用 `t.MaxFPS` 模拟长帧。测试期间临时关闭编辑器后台限帧，结束后恢复。浮筒离开水体时 waterHeight 会返回约 -100000 的哨兵值，这类样本已排除。
- **根因：长帧导致物理与波浪不同步。** 波浪使用世界时间（`UWaterSubsystem::GetWaterTimeSeconds`），每帧最多推进 0.4s；物理每帧最多推进 1/30s，且未开子步。帧时长超过 33ms 时（截图、着色器编译、后台限帧、低端机卡顿），波浪跑在船前面，船先悬空再被浪淹没。确定性对照：同样的原浮力参数，在高且稳定的帧率下 30 秒采样 775 次，相机入水 0 次、上浪 0 次；在 12FPS 下相机入水 46/88 次（最深 -225cm）。
- **修复（仅改 Config，浮力参数保持原值）**：`DefaultEngine.ini` 开启物理子步（`MaxSubstepDeltaTime=1/60`、`MaxSubsteps=4`）；`DefaultGame.ini` 设置 `WorldSettings.MaxUndilatedFrameTime=0.066667`，QA 地图实例也已存为相同值。效果：15FPS 以上物理与波浪完全同步；更低帧率时整体均匀放慢，计时器同步放慢，不会出现船体与波浪脱节。
- 排除方案：变体 B（系数 0.7、浮筒 +45cm）俯仰最大 45°，浮筒频繁出水，不采用；Blueprint 已恢复并保存为原值（0.25 / 0cm / 阻尼 1000）。注意 UE 浮力阻尼只抵抗上升速度（`BuoyancyComponent.cpp:359-364`）。
- 发现测试工具陷阱：编辑器主窗口最小化时，`AreAllWindowsHidden()` 会把视口内 PIE 限到 3FPS；浮动窗口失去焦点时还会触发后台限帧。早期视口内采样结论（4/4 输入、10/10 浮力）可能是在 3FPS 下测得的，需在浮动窗口中重测。
- 波形源码核实：`GerstnerWaves_Ocean` 的振幅与波长共用同一插值参数（最大 60m 波长对应 0.8m 振幅），属于平缓长涌。实测周期 5–7s，水面标准差约 1.3m。

### Evidence
- 重启编辑器后，PhysicsSettings 和 WorldSettings 的 CDO 读到 ini 中的值（0.016667 / 0.066667）。在 Config 生效状态下：`seakeeping-final-3fps-20261012-142744/`（正常阶段 782 次采样：相机最低高于水面 26cm，干舷最小 20cm；3FPS 与恢复阶段均通过）；`seakeeping-final-12fps-20261012-142857/`（12FPS 阶段：相机最低高于水面 28cm，干舷最小 22cm，无入水/上浪）。对照组：`seakeeping-T3-orig-12fps-*`、`seakeeping-T3-sync-12fps-*`、`seakeeping-orig-detail-*`、`seakeeping-T1-B-*`。
- 连续 4 张截图不再淹船：`boat-motion-synced-20261012-143017/`（4 帧中船高与局部水面一致，4 个浮筒均入水）。
- 性能：子步开/关/开 A/B 测试中，游戏线程耗时 5.91 / 5.90 / 5.80ms，无可测 CPU 成本（`boat-performance-20261012-143318/`、`-143401/`、`-143443/`）。但本轮 GPU 处于软件功耗限制（SW Power Cap Active），且不受开关影响地在 31–63ms 间波动，因此**本轮绝对帧耗时 NOT_MEASURED**，不能与之前的 17ms 比较。

### Blockers / Next
- 船舱内水面穿插（遮罩）未处理；风暴波形尚未加强（当前涌浪已较大，视觉缺的主要是浪尖白沫和碎浪细节）。
- 编辑器每次启动会向 DefaultEngine.ini 写入 Android 文件服务令牌，已手动移除，提交前需检查。`BP_QA_BuoyantBoat.uasset` 的启动自动重存仍未纳入。
- 下一步候选：浪尖/接触白沫与溅水；船舱水体遮罩；在浮动窗口中重测早期输入与浮力用例。

## 环境视觉 Pass R4 · 2026-10-12

### Completed
- 用户反馈视觉不满意并选择“环境先行”。诊断原因：雾密度 0.0005 近乎无雾，导致 1000m 巨兽失去空气透视；模板 `SM_SkySphere`（`M_SimpleSkyDome`）遮挡物理天空并造成硬地平线；无 PostProcessVolume；太阳位于相机后方，正面平光；云覆盖偏低；水体散射偏青。
- 新增 `Scripts/apply_kraken_environment.py`，修改前回读并写入凭据，可用 `--revert` 回滚。改动仅涉及 `L_KrakenPlayableBoatQA` 的天空/雾/光照/后期，以及共享的 `MI_KrakenOcean_Storm`（散射、法线强度）和 `MI_KrakenStormClouds`（覆盖、密度）。**未改动波形和浮力**。两个材质实例同时被 BoatControl、OceanReview、BuoyancyQA 三张 QA 图引用。
- 迭代 4 轮真实 PIE 玩家视角画面：R1 雾过浓且偏棕；R2 雾消失，并发现 `Cloud_GlobalCoverage` 方向相反（数值越大云越少）；R3/R4 收敛为低空海雾、厚云层、冷灰色调、前左方低角度太阳形成轮廓光和海面反光带。已保存地图和两个材质实例。
- `capture_boat_motion.py` 增加 `--frames/--label/--warmup` 参数。刚启动的编辑器在 8 秒预热时船尚未稳定，对比采集改用 25 秒预热。

### Evidence
- 最终凭据（before 字段为原始基线）：`Artifacts/QA/kraken/env-look-20261012-135726/receipt.json`。基线/R1–R4 画面：`env-before-20261012-134934/`、`env-r1…r4-*/`；并排对比 `env-look-r4-compare.png`。
- 同一会话 A/B 性能（RTX 3050，1914×994，20 秒原生 CSV，采样窗口内不截图）：平均帧耗时 **16.87→17.41ms**，GPU **16.23→16.76ms**，P95 23.13→23.99ms：`boat-performance-20261012-135648/` 与 `-135736/`。另有一次测量因编辑器处于后台被节流到 3FPS，已作废（`-135530/`）。测量期间临时关闭 `bThrottleCPUWhenNotForeground`，测后已恢复。
- 脚本 py_compile 通过，MCP 单测 6/6。

### Blockers / Next
- 实时视觉门仍为 **PARTIAL**：氛围和尺度已改善，但缺少浪尖白沫、巨兽与水面接触泡沫/溅水、湿润皮肤材质；巨兽静止，近景仍有黏土感。画面未获用户认可。
- R4 第 2 帧再次出现船淹没、镜头入水（浮力在截帧停顿下的已知问题，z≈-55→-66cm），与本次环境改动无关，仍待修。
- 编辑器启动时自动回写 Android 文件服务令牌（已用 git 还原）并重存了 `BP_QA_BuoyantBoat.uasset`（签出失败后的自动保存，非本次改动，未纳入）。
- 下一步候选：①风暴波形加强及浮力复测；②接触白沫/Niagara 溅水；③巨兽湿皮肤材质。

## 提交快照 · 2026-10-12

### Completed
- 按用户要求暂停新增内容，整理首个本地 Git 开发基线：设计/架构、UE 工程与已保存资产、高精模型源文件、绑定与导入脚本、玩法/采集/性能 QA 工具。保留被否决候选作对照，未将它们记为最终资产。
- 补充 Git LFS 规则，排除原始 QA 产物、缓存、自动备份、临时下载链接、Tripo 本地会话和转存到 D 盘的旧转换目录链接；源 GLB、准备后的 FBX/Blend、UE 资产纳入版本。移除模板配置内的本机 Android 文件服务令牌，未变更网络开关。
- README 同步当前状态、QA 地图入口、验证方式和版本范围；下方历史记录保留日期，不作为当前完成状态。

### Evidence
- 提交前重新运行 MCP 客户端单测 **6/6**，解析 **29 个 Python 文件**、工程 JSON 和 Codex TOML 全部通过。
- 只读复核本地凭据：章节导演 **25/25**、运动学船 **5/5**、浮力 **10/10**、物理船输入 **4/4**，以及同尺寸性能 **25.37→17.26ms**，与记录一致。这是已有真实 PIE 证据复核，未在本次整理中重跑全部 UE 测试。
- 原始凭据路径见下一节 Evidence；`Artifacts/QA/` 保留本地且不进 Git，Git 中进度摘要不替代原始采样/截图。
- 暂存内容共 543 个文件，362 个二进制文件由 LFS 管理（约 2.078GiB）；暂存区空白检查、常见凭据/签名链接模式扫描及本地产物排除检查通过。已消除文本末尾多余空行。

### Blockers / Next
- 本提交是开发恢复点，**M1 未完成**：长帧浮力/水穿船、触手 Idle 接缝、主体骨骼与接触同步、完整路线/游泳/HUD/恢复及全章首通仍待完成；电影级视觉与打包验收未通过。
- 旧 `verify_kraken_director.py` QA 创建和 `capture_game_viewport.py --build-helper` 仍含空路径 SaveAll 调用，后续使用前应改为保存明确资产；本次整理不执行这些写入分支。
- 提交后继续当前最小复现与修复路径；仅本地提交，不推送远端。

## 空间恢复与续接 · 2026-10-12

### Completed
- 用户选择继续使用 E 盘；恢复开始时可用约 71GiB，未迁移工程。最初连接旧 PID 33652；其退出后已重开，收尾时 PID 23424、MythicEscape.uproject、MCP 8001，PIE 停止。提交前 E 盘约 54.8GiB 可用。
- 从 D 盘恢复副本回拷缺失的 `Scripts/build_kraken_boat.py`，SHA256 一致并通过 Python 语法检查；保留 D 盘备份。回收 V4 实拍及凭据到原工程，未覆盖有效内容。
- 已将上次只存在编辑器内存的 `L_KrakenOceanReview`、风暴水/云材质保存到原工程，工具明确返回成功。
- `ue_mcp.py` 增加模板保护：对 `/Game/FirstPerson` 的两种危险图读取在派发前拒绝，普通查询及 Kraken 蓝图仍可用；6/6 单测通过。
- 实际运行船控制 author 脚本，修复 Enhanced Action Value 创建 ID 与 DSL 二元乘法语法；`BP_KrakenBoatPawn` 已编译保存，真实 Enhanced Input 注入的前进、松键减速、转向、独立观察、阻挡碰撞 **5/5 通过**。持续前进约 10.99m 后停在墙前，未穿透；这是隔离运动学测试，未代替浮力验收。
- 新建 `BP_QA_BuoyantBoat` / `L_KrakenBuoyancyQA`，验证 UE Water 原生四浮筒、500kg 船体。修正浮力不足，并确认 `BuoyancyData` 为 EditDefaultsOnly：模板反射修改不会同步已放置实例，QA author 仅重建自身生成的测试实例。30 秒采样 **10/10 通过**：平均浮力/重力 1.016、稳定窗口相对水面漂移 4.42cm、最大俯仰/横滚 18.73°；不代表所有帧停顿和视觉水线通过。
- 在独立 `BP_KrakenPhysicsBoatPawn` / `L_KrakenPlayableBoatQA` 接入真实力推进、力矩转舵、原生浮力和船上第一人称相机，保留旧运动学船。解决隐藏展示船仍有碰撞的问题：反射设置 CollisionProfileName 不足以改变该已有实例的 PIE 碰撞，将仅此 QA 副本的展示道具移出航道，原 HeroReview 保留。
- 物理船真实输入 **4/4 通过**：4 秒前进约 11.50m，末速 4.77m/s；松键 4 秒从 4.85m/s 降至 0.006m/s；2 秒转向约 59.8°；独立观察使控制器转 72.5°，扣除无输入海况后船体偏航差约 0.33°。转向后的惯性等待单独保留采样，未通过放宽阈值掩盖残余转速。
- V5 使用单独 `M_HeroKrakenV5_WetSkin` 材质变体，降低粉色、置非金属、保留源高精网格与原 PBR；可玩 QA 中将主体朝向调整为 yaw 150°、Z=-280m，抬高可见头部。增加厚云并修正曝光；这些是候选画面调整，未视为用户接受。
- 新建原生 CSV 性能采样与真实视口尺寸 Probe，性能窗口内不截图。RTX 3050 / 驱动 32.0.16.1062、Epic 3、实际视口 **1914×994**（请求 1920×1080 被窗口约束）、自动屏幕百分比：云阴影范围/分辨率/射线采样优化后，同尺寸 20 秒平均帧耗时 **25.37→17.26ms**，GPU **24.51→16.42ms**，云阴影 **8.99→0.47ms**；未降低模型精度。末轮 P95 23.36ms、最大 152.27ms，约 58FPS 平均不等于稳定 60FPS。CSV RenderThreadTime 部分样本接近零，不能当作可靠的渲染线程成本。

### Evidence
- `Scripts/build_kraken_boat.py`；`Scripts/tests/test_ue_mcp.py`；`Artifacts/QA/kraken/boat/20261012-094302/receipt.json`。
- 上次末帧恢复：`Artifacts/QA/kraken/kraken-v5-ocean-player-v4.png` 与 `.capture.json`。它是历史证据，包含当时未保存标记；本次保存行为单独记录。
- 运动学船：`Artifacts/QA/kraken/boat-input-pie-20261012-101814/receipt.json`；原生浮力：`boat-buoyancy-pie-20261012-111530/receipt.json`；物理船输入：`physics-boat-pie-20261012-112716/receipt.json`。
- 脚本：`Scripts/verify_kraken_boat.py`、`verify_boat_buoyancy.py`、`build_physics_boat.py`、`verify_physics_boat.py`、`profile_kraken_boat.py`、`capture_boat_motion.py`。
- 性能基线/优化后：`Artifacts/QA/kraken/boat-performance-20261012-113014/`、`boat-performance-20261012-113159/`，各有原生 CSV 副本、逐项 CVar、视口、停止 PIE/恢复窗口配置凭据；修改参数见 `cloud-shadow-optimization.json`。
- 真实连续 PIE 采样原帧：`Artifacts/QA/kraken/boat-motion-20261012-113107/`（HighResShot）及 `boat-motion-20261012-113944/`（原生 Shot）。每帧包含船体位置/姿态、浮筒水位、哈希和真实采样间隔。**不是实时视频**；其中出现短暂淹船/水穿船，必须保留失败帧，不可只拿较好单帧宣称通过。

### Blockers / Next
- 磁盘阻塞已解除；当前 UE 进程已重新打开，8001 仍属本工程。实际模型路由仍无后端回执；本次使用 explorer/ue_worker 的指定角色，未假定配置等于路由验证。
- 普通连续采样的浮力/输入已通过；重复截帧产生约 0.5–0.8 秒停顿时仍会出现水线偏差、镜头短暂入水及船舱水体穿插。原生 Shot 降低采集干扰但尚未解决此问题。隔离试验了异步物理及 120Hz 子步：异步样本水位输出保持零、未证实随波；子步缩小偏差但失败帧仍入水。**两种试验均未接受，已回读确认物理设置恢复，未写入项目 Config**。证据：`async-physics-trial.json`、`substep-physics-trial.json`、`boat-motion-20261012-114211/`、`boat-motion-20261012-114346/`。
- V5 主体尚无骨骼和接触同步，独立触手 Idle 接缝未修；完整路线、游泳、危险/恢复、HUD、14–18 分钟首通仍未实现。可控船 QA 不是正式章节，实时视觉门仍 **FAIL / PARTIAL**，全章与打包性能仍 **NOT_VERIFIED**。
- 下一步先以不截帧的低帧率/人为长帧对照复现水线偏差，分清采集干扰与正常运行问题，再处理浮力时序和船舱水面裁切；同步修独立触手循环，接入船体接触事件。当前已保存 `L_KrakenPlayableBoatQA`，PIE 已停止，实验配置已恢复。
- 以下 2026-10-10 记录为历史状态，恢复日期以上节为准。

## 本次续接 · 2026-10-10

### Completed
- 核实恢复点：此前仅有 Blender 制作证据计划和第一人称模板；未发现可复用的既有 Kraken 成品模型。保留工程全部原有内容，未重新初始化。
- 工具端已加载 `explorer` Luna Low、`ue_worker` Terra Medium 角色定义，并实际调用对应角色；项目默认 Terra Low、最多 3 个子 Agent 配置仍在。**未获得后端推理模型回执，不能独立证实主 Agent Astra Ultra 或每次调用的实际模型路由。**
- 修复 `Scripts/ue_mcp.py`：读取结构化 MCP 返回、识别外层和嵌套工具错误；5 项针对性单元测试通过。
- 创建原生 `BP_KrakenChapterDirector`（11 个图）和 QA 子类/地图，覆盖 K0–K6、失败、Reveal 后计时、K4 暂停、落水保护、安全优先仲裁与阶段练习重试。FullChapter 720s 与 PrototypeSlice 240s 独立。真实 PIE **25/25** 通过；这仅验证状态仲裁，未证明实际路线/载具/全章时长。
- Blender 创建 7 米木船结构候选、18 米触手骨骼候选；触手有 24 变形骨、96 个立体吸盘及 Idle/Warning/Strike/Recover/BoatLift/Submerge 六段动画。已实际导入 UE 静态船网格、触手骨骼网格/骨架/六个动画。它们属于开发候选，**未通过电影级近景质量门**。
- 用户明确授权不限制 Tripo API 积分，以高精度优先。首批 V1 木船/主体/触手均已生成并下载：源三角面约 198/195/187 万；原始颜色 8192²，ORM/NormalGL 4096²。不能把所有通道都称作 8K。
- 修复结构船误含默认 Cube 的导出，fresh FBX 重开确认无多余对象，另导入 `SM_HeroBoat_StructureV2`。Tripo 船标准化为 7×2.4×1.605m，保留完整源几何并启用 UE Nanite；真实 1920×1080 GameViewport 已显示木材/PBR。
- 实际建立 PBR 材质：颜色 sRGB；ORM 线性 R/AO、G/Roughness、B/Metallic；OpenGL 法线翻转绿色通道。主体 V1 已导入 80m 静态诊断资产并拍摄；**该版已被用户明确否决，不再作为 Hero 接受候选**，源和 UE 资产保留作对照。
- V1 独立触手姿态过度弯曲，保留但未绑定；另用伸直图生生成 V2（1939826 三角面），保留高精源并制作 310371 三角面/180101 顶点变形网格，24 变形骨、六段动作。fresh Blend/FBX 独立核验：无未加权/非有限值，权重和约 0.99999997–1.00000003；UE 实际导入 25 骨（含导入根）及六个动画。
- 六段触手动画均经过真实 PIE 采样：Actor 变换不变、根位置固定、末端发生位移，确认骨骼动画确实播放。**发现 Idle 首尾末端接缝约 1.351m，运行摆幅过大，不能通过动画质量门**，待修动作后再做接触同步。
- 新增 `Scripts/capture_game_viewport.py`：由 UEDPIE 原生 QA 蓝图经 PlayerController 执行 HighResShot，独立固定游戏相机与编辑器相机不同，记录 PNG 尺寸/哈希/日志/停止 PIE 凭据。采集路径已验证；静帧不是短运动片段或性能验收。
- 用户要求先图后模型：内置图像工具生成新参考，第一版普通章鱼体量被否决；岛屿级八臂 V3 通过 Tripo 图生成功下载（任务 `874ea600-4dbf-4127-a8fb-c51ebff6de2c`，87,506,240-byte GLB），但用户指出头部太扁。保留结果，**未导入 UE、未作为新 Hero 接受**。拉高头部的 V4 图片又因比例怪异被否决，未提交 Tripo。
- 最新按用户要求整体重设 V5：从海上概念制作八臂干净参考，实际调用 Tripo 图生（任务 `137eba30-533d-469f-9fd6-aebe46391af6`）；保留 976414 顶点 / 1911124 三角面、单 UV/PBR，颜色 8K、ORM/NormalGL 4K。Blender 导出及独立 FBX 回读几何一致，最大水平臂展均匀归一至 1000m（XYZ 约 760×1000×549m），导入 UE Nanite 静态审查资产。尚无主体骨骼与动画，也未得到用户质量认可。
- 新建 `QA/L_KrakenOceanReview`，保留原 HeroReview；配置原生 WaterBodyOcean / WaterZone、水材质实例、7m 木船与近海平面游戏相机。首张真实 1080p 玩家图已获得；继续修朝向、出水位置与光照。
- 发现 UE 工具 `get_node_type_pins` 会创建/删除临时节点，`read_graph_dsl` 对 Enhanced Input 仅跟随 Then，存在读操作副作用和遗漏。模板 IA_Move 确实缺失；已备份原文件，最小重建事件、BreakVector2D 并接回原 Move 函数，核验 5 项引脚连接、编译/单资产保存。之后禁止对模板使用这两个读取 API；材质脚本改为只保存本次材质/纹理。
- E 盘满导致风暴云保存及第二张截图失败；将本轮三组旧 Tripo FBX 转换输出完整转存至 `D:/codex/MythicEscape-source-archive/tripo-conversions/`，保留原路径 Junction，FBX SHA256 前后一致，未删除源资产。释放约 626MiB 后纹理/风暴云/地图保存重试成功。

### Evidence
- `Scripts/build_kraken_director.py`；`Scripts/verify_kraken_director.py`；`Scripts/tests/test_ue_mcp.py`。
- `Artifacts/QA/kraken/director/20261010-161123/receipt.json`；`Artifacts/QA/kraken/director-pie-20261010-162018.json`（UEDPIE_0 actor，25 passed / 0 failed）；`Artifacts/QA/kraken/candidate-import.json`。
- UE：`/Game/MythicEscape/Chapters/Kraken/Blueprints/BP_KrakenChapterDirector`、`QA/L_KrakenSystemsQA`、`Boat/SM_HeroBoat_Candidate`、`Creature/SK_HeroTentacle_Candidate`。
- 源：`ArtSource/Kraken/Boat/`、`ArtSource/Kraken/Creature/`；Tripo 参数与追踪：`ArtSource/Kraken/Tripo/hero_batch_v1.json` 及相邻 plan/result/receipt 文件。
- 高精源与审计：`ArtSource/Kraken/Tripo/source-boat-v1/mesh-audit.json`、`source-kraken-v1/mesh-audit.json`、`Prepared/Boat/`、`Prepared/KrakenStatic/`、`Prepared/TentacleRig/HeroTentacle_Tripo_Rig.verify.json` 和 `HeroTentacle_Tripo_Rig.fbx-reimport.verify.json`。
- UE 导入：`Artifacts/QA/kraken/boat-cube-fix-ue.json`、`tripo-boat-prepared-ue.json`、`tripo-kraken-prepared-ue.json`、`tripo-tentacle-prepared-ue.json`。静态 Nanite 网格工具返回的 LOD0 三角面是 fallback 查询值，不能替代源几何面数。
- 实拍：`Artifacts/QA/kraken/tripo-boat-gameviewport-v1.png`、`tripo-kraken-scale-gameviewport-v1.png`（被否决版）、`tripo-tentacle-warning-gameviewport-v1.png` 及配对 `.capture.json`；六动作运行采样 `tripo-motion-20261010-170630/receipt.json`。
- 新美术目标：`ArtSource/Kraken/Tripo/KrakenV2/Reference/kraken-colossal-scale-v3.png`；模型输入 `kraken-colossal-eight-arm-v3.png`；提示词和 `KrakenV2/colossal-generation.plan.json`。**这些图片是概念/生产参考，绝不是 UE 渲染证据。**
- 最新整体重设计：`ArtSource/Kraken/Tripo/KrakenV2/Reference/kraken-redesign-scale-v5.png` 与 `redesign-v5-prompt.txt`。V3 图生保存在 `KrakenV2/tripo-out/m1-kraken-colossal-image-v3-874ea600/`；V4 拒绝图 `kraken-tall-rejected-v4.png`。

- V5 源：`ArtSource/Kraken/Tripo/KrakenV5/`；准备与 fresh FBX 审计 `Prepared/KrakenColossal/SM_Kraken_Colossal_V5.*.audit.json`；导入/PBR `Artifacts/QA/kraken/tripo-kraken-v5-*.json`。
- 新海面实拍：`Artifacts/QA/kraken/ocean-initial-player-view.png`、`kraken-v5-ocean-player-v1.png` 及 capture 凭据。V2 截图因磁盘满损坏，不能作为证据。模板修复凭据 `template-repair/`；转存及哈希 `tripo-conversion-archive.json`。

### Blockers / 尚未验证
- 蓝图 DSL 英文节点标识在中文编辑器会失配；已正常保存/关闭并以 `-culture=en` 重开当前项目（8001），本次编译成功，未修改用户持久语言设置。
- Tripo 船非均匀缩放后的 corner normal 采样有少量偏差，`NormalsV2` 的 transform_apply 实验未改善，保留但不作为已修复版本导入。需近景决定是否显式重建法线。
- 触手权重/动作导入已核验，但 Idle 周期接缝与幅度有实测问题；尚未接入接触碰撞、AnimBP 混合、水面反馈，主体新形态也需要独立骨骼方案。
- 主体美术仍未定型。V5 已导入并实际拍摄；第一张暴露侧向过多、主体出水过高和晴天皮肤偏粉，正在调整。模型静态，未做主体骨骼/接触同步；1000m 臂展仍是场景候选尺度，不能视为验收。
- 船/游泳 Pawn、完整海域/分支/遭遇/检查点实体恢复、HUD 及全章首通尚未实现；QA 地图不是正式关卡。
- `Scripts/build_kraken_boat.py` 仍为未执行草稿。已修正属性 JSON 解码、独立 Actor 转舵等问题；Enhanced Input 事件无法通过当前节点发现创建/连松开输出，脚本在资产写入前明确阻断。只读源码调查建议复用模板已有事件节点，后续需要真实节点/PIE验证，不能记作可玩船。
- Director CDO 实测 `QA_AutoTick=true`、`PrototypeSlice=false`，正式 Tick 已接好且默认使能；实时秒数递减待额外验证。早先只读报告称“未接线”已纠正，未据此重复改实现。
- 真实 GameViewport **采集渠道已验证**；电影级视觉、连续动画片段、硬件帧耗时仍 **NOT_VERIFIED / NOT_MEASURED**。

### Next
1. 完成 V5 朝向、水线、阴天光照的真实 GameViewport 对比，随后推进主体骨骼与海面响应；被否决的 V1/V3/V4 不作为接受基准。
2. 修复触手动作接缝/幅度与船操纵草稿，推进可控船和海域视觉锚点的真实运行。
3. 沿已验证章节状态系统实现 FullChapter 路线、危险、载具切换和恢复；并行推进 A/C 玩家镜头、接触同步和实时性能。

以下为此前历史记录；涉及“尚未创建”的旧状态以上述本次续接为准。

## Completed · 2026-10-10
- 2026-10-10（Codex 多模型子 Agent 路由）：项目 `.codex/config.toml` 保留 Unreal MCP 8001、默认子 Agent `gpt-5.6-terra` Low 和并发上限 3；新增 `.codex/agents/explorer.toml`（GPT-6 Luna Low、只读资料/日志/资源定位）及 `.codex/agents/ue_worker.toml`（GPT-5.6 Terra Medium、独立常规 UE 实现/测试），在 `AGENTS.md` 增加最小任务路由约定。主 Agent Astra Ultra 由会话选择，不在 TOML 强制覆盖。配置已写入但**未实测新子 Agent 的实际模型选择、时延或额度消耗**，需在重载配置的新会话中确认。
- 2026-10-10（五章交付与视觉品质线更新）：已取消将 V0/V1/V2/V3 作为长期交付主线，改为 M1 完成 14–18 分钟克拉肯 FullChapter、M2 复用已验证视觉流程完成后四章、M3 全五章整体品质/性能/发布验收。内容线与**视觉品质线**从每章首个场景起同步进行；创建 `docs/VISUAL_PIPELINE.md`，定义高精 Hero Asset→Blender/Tripo→UE 骨骼/材质/灯光→真实玩家游戏镜头/性能 QA→复盘与跨章复用验证。M1 首章**实际验收通过后**才能提炼真正可用的 Skill，且须在另一章复测通用性。同步 `AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/GAME_DESIGN.md`、`docs/CHAPTERS.md`、`docs/VISUAL_QA.md`、`README.md`。**本轮仅文档设计：没有创建新 Skill、UE 地图、正式模型或任何已通过的画质证据。**
- 2026-10-10（高精度资产质量规则）：用户确认 V0 起即应采用高精度 3D 模型制作代表性的克拉肯巨兽、立体吸盘触手和木船，而非等到 V2 才将简陋几何统一替换。已更新 `AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/GAME_DESIGN.md`、`docs/VISUAL_QA.md`、`README.md`。架构定义 Tripo/许可合规资产→Blender 几何/拓扑/绑定→UE5.8 实际镜头与性能验证，高精模型源资产与运行时网格可分层，骨骼/LOD/Nanite 需按实际资产类型验证；视觉 QA 增加几何细节、吸盘厚度/船壳结构、蒙皮变形、PBR、LOD 和帧耗时门。**仅文档设计，尚未生成、导入或测试上述高精模型，当前 V0 仍 NOT_IMPLEMENTED/NOT_VERIFIED。**
- 2026-10-10（UE 官方 Demo 参考升级与本机检查）：已重写 `docs/UE_REFERENCES.md`，同步 `AGENTS.md`、`docs/ARCHITECTURE.md`、`README.md`。只读检查 `D:\Program Files\Epic Games\UE_5.8`，证实 Templates/FeaturePacks 内有 FirstPersonBP/ThirdPersonBP/VehicleAdvBP 等模板；Water、WaterExtras、WaterAdvanced、Buoyancy、Niagara、NiagaraFluids、ControlRig、IKRig、Chaos/GeometryCollection、PCG 等插件文件存在。
  - Water 插件内 `BP_BuoyancyExample.uasset` 与 `Fluidsim_Terrain.umap`/`WaterFluidSimtestShallow.umap` 存在；WaterExtras 含 `WaterTestMap.umap`、`WaterVelocityTest.umap`、`WaterSplitscreenTestMap.umap`、`CausticsMap.umap`；PCG 含 `SimpleForest.umap`、`HiGenForest.umap` 等地图。
  - 引擎根目录没有 `Samples`，在检查的引擎目录路径未找到独立 Content Examples、Valley of the Ancient、Electric Dreams、Lyra、Game Animation Sample 项目；**并不代表它们在其他磁盘/Fab Vault 中不存在**。本轮未启用插件、未运行这些地图、未导入/下载任何独立 Demo。
- 2026-10-10（Visual-First 策略更新）：正式把电影级写实目标前置到 V0。已同步 `AGENTS.md`、`docs/GAME_DESIGN.md`、`docs/ARCHITECTURE.md`、`docs/VISUAL_QA.md` 与 `README.md`。V0 建立真实可复用的局部海洋/木船/巨兽轮廓/一条动态触手及 A/C 两镜头；V1 在同一美术基准上打通 5–7 分钟 Kraken PrototypeSlice；V2 细化高精巨兽骨骼、海水/特效和性能；V3 扩展 14–18 分钟正式版。视觉与玩法同步开发，不推迟到全部灰盒完成之后。本轮**仅调整执行文档和视觉验收标准，没有在 UE 中实现或证明电影级画质**。
- 2026-10-10（骨骼动画架构补充）：在 `docs/ARCHITECTURE.md` 增补分阶段动画管线与职责分配，说明 Tripo/Blender/Mixamo/UE Control Rig 和动画系统的适用边界；为第一人称玩家、克拉肯主体及独立触手、其他四只巨兽列出动作与交互要求，规定动画接触帧与碰撞、环境响应的同步契约，并划分 P0 占位接口、P1 运行时事件同步、P2 正式骨骼和动画质量验收。`AGENTS.md` 只加简短硬约束与文档入口。本轮仅修改设计文件，尚未实际绑定/导入/播放资产。
- 2026-10-10（规模扩展 v0.5）：将五章目标由电影短篇升级为首次完整游玩约 14–22 分钟的中等篇幅关卡；保留 3 个核心逃生阶段，通过阶段内部的 `EncounterBeat`、可选探索点、长短分支、巨兽连锁环境事件、短暂可观察缓冲区和独立检查点延长有意义的玩法。同步更新 `docs/GAME_DESIGN.md`、`docs/ARCHITECTURE.md`、`docs/CHAPTERS.md`、五个 `docs/levels/*.md`。完整版主倒计时/正常目标：克拉肯 720/540s、利维坦 960/720s、耶梦加得 960/720s、贝希摩斯 720/540s、齐兹 840/630s；各有约 25% 主计时容错。克拉肯 P0/P1 使用独立 `PrototypeSlice` 5–7 分钟，240/170s 旧短版计时，独立于 FullChapter；本轮仅设计文档变更，**没有 UE 玩法、渲染或真实首通时间的通过证据**。
- 已创建 `MythicEscape.uproject`，基于官方 `TP_FirstPersonBP` 蓝图模板。
- 安装了模板正常创建时自动注入的 Characters、Input、LevelPrototyping 三组共享资产（Content 合计 239 个文件）。
- 使用 UE 5.8.3（`D:\Program Files\Epic Games\UE_5.8`）进行命令行验证，最终日志 **Success - 0 error(s), 0 warning(s)**。
- 第一人称模板蓝图编译初次因 GameFeatureData 资产管理规则缺失而被阻断；已修复，最终完整 `CompileAllBlueprints` 复测退出码 0：0 errors / 0 warnings / 0 blueprints failed。
- 已配置 `ModelContextProtocol` 和 `AllToolsets`；项目专属 `unreal-mcp` + `mythic-visual-qa` Skill 已就位。
- Codex CLI 可读取 `.codex/config.toml` 中的 Unreal MCP 连接配置。
- 发现本机 8000 端口属于另一 UE 项目 `D:\codex\UE58-MCP-Host`，保留原服务，Mythic Escape 改用独立端口 **8001**。
- 在当前项目编辑器启动时对 8001 执行真实 MCP initialize（HTTP 200）、tools/list（3 个元工具）、list_toolsets（HTTP 200）。
- 完成 MCP 读操作测试后，测试用的 Mythic Escape 编辑器已正常关闭（退出码 0）；后续可从 `.uproject` 重新打开，项目配置会启动 8001 服务。
- 已初始化本地 Git 仓库（尚未创建首个提交）。
- 2026-10-10（设计阶段）：完成全局游戏架构 v0.2、章节索引、克拉肯/利维坦/耶梦加得/贝希摩斯/齐兹五章的阶段流程、差异机制、动态危险、安全区、资产与 QA 详细设计，并更新总体 GDD 与视觉 QA 规则。设计状态 PENDING USER REVIEW，不代表关卡实装。
- 2026-10-10（设计修订 v0.3）：修订 GDD、全局架构、章节索引、五个章节详情。区分各章独有玩法节奏；修改 240/300/300/270/270 秒计时为正常目标 170/215/215/185/185 秒加 70/85/85/85/85 秒容错；定义可预警和可恢复失误、强制剧情与失败分离、检查点标准时间、各章路线+安全区+危险解除的通关条件；修正利维坦 B→C→D 路线与贝希摩斯地下震波/空中飞石的规则。仍为 DESIGN v0.3 / PENDING USER REVIEW，不代表玩法或平衡已实测。
- 2026-10-10（后四章逃生修订 v0.4）：已更新 `docs/levels/02_LEVIATHAN.md` 至 `05_ZIZ.md`、`docs/CHAPTERS.md`、`docs/GAME_DESIGN.md`、`docs/ARCHITECTURE.md`。利维坦加入察觉等级影响巨鲸转身、巨颚与尾鳍引发的连锁坍塌；耶梦加得加入短险/长稳航路、蛇身活动拱口与洪峰登高双选择；贝希摩斯增强稳定地面选路、飞石绕行与最后巨足落地的拉门逃生高潮；齐兹在 Z0 提前学习滑翔，翼影预警、抗风择路、宽阔峡谷借升流形成递进。保留所有既有主计时与容错预算，安全/失败规则延续 v0.3。文档设计完成，尚未试玩确认。
- 2026-10-10（工具阶段）：安装项目级 `blender-cli` Skill（来源 Blender-Skill HEAD d4bc3847a45795d0b5682a32618e68deb354e5ad，MIT）。本机 Blender 5.2.1 LTS 后台运行、离线功能目录查询与单项 Blender API runtime probe 均已通过。初次默认大量 RNA 探测超时，缩为单属性探测后成功。
- 将 `mythic-visual-qa` 升级为可执行工具：`capture_ue.py`（MCP 视口截图 + 项目 PID 校验 + JSON 凭据），`visual_qa.py`（截图尺寸/哈希记录与复核、Pillow 并排概念图）。测试记录存于忽略的 `Artifacts/QA/_toolchecks`。
- UE MCP Editor 视口 PNG 截图与临时 PIE 启动/停止 + 视口 PNG 均已实际执行；**两次图片几乎相同，CaptureViewport 不能视为玩家游戏画面**，所以电影级真实游戏画质和视觉审美仍 NOT_VERIFIED。

## Evidence / Status
- `MythicEscape.uproject`：真实 UE 工程，可由 UE5.8.3 引擎加载。
- 引擎加载验证：PASS（0 错误、0 警告）。
- UE MCP HTTP 会话与读取工具集：PASS（编辑器开启时）。
- Codex 配置发现：PASS；Codex Agent 新会话是否自动加载两个 Skill 尚需日常任务检验。
- PIE 角色移动、关卡阶段、巨兽、视觉/帧率：NOT_VERIFIED / NOT_IMPLEMENTED。
- 蓝图完整编译：PASS（修复配置后重跑，退出码 0，0 错误、0 警告、0 加载失败）。
- 无实际克拉肯游戏素材或截图通过视觉验收。

- 五章 GDD / 架构 / 章节索引 / 关卡详情均已更新至 **v0.5**：DESIGNED / PENDING PLAYTEST。原型与正式关卡具有独立时长档；全部探索、节奏、计时和分支仍属设计假设。新增巨兽关卡地图、蓝图、真实游玩时长与视觉性能：NOT_IMPLEMENTED / NOT_VERIFIED。

## Current risks
- `AllToolsets` 提供完整 UE 编辑器功能，加载可能较重；后续可按实际需求精简，不要盲目追求全插件。
- MCP 只允许本机访问，不应操作别的 UE 工程，也不可把 8001 暴露公网。
- Unreal 头显/海水/船只/游泳玩法尚未创建；第一人称模板测试地图不是游戏关卡。
- 本次 GUI 编辑器启动日志中有 13 条 `LogAutomationTest: Error: Condition failed`，来源于自动化测试模块，尚未定位和完成独立回归；不等于 P0 PIE 已通过。
- 真实 GameViewport/运行时截图采集通道尚未验证；已确认 UE MCP CaptureViewport 取编辑器相机，不能用 PIE 会话标志替代真实画面。
- v0.5 的 14–22 分钟首次体验与更长倒计时尚未由真人首通/灰盒校准；主要新风险是冗长的重复攻击、长时间无行动观察、地图资产规模及超长章节失败后重试疲劳。
- 角色与巨兽骨骼绑定、蒙皮、动画混合和 UE 运行时碰撞/特效同步仍属设计规范，尚未实测；Tripo 自动绑骨在非人角色上的质量也必须以实际导出和动作回放判断。
- V0 的代表性高品质场景、真实玩家 GameViewport 截图/动作片段和帧耗时仍全部未验证；60 FPS 只能作为待指定硬件验证的候选目标。MCP `CaptureViewport` 为编辑器镜头，不能作为游戏画质 PASS。
- 高精度 Hero Assets 的几何结构、拓扑、PBR 材质、骨骼权重、近景形变与性能质量门均未得到实际网格/UE 运行证据，不能因为 Tripo 模型面数高或材质截图好看就标记通过。
- `docs/VISUAL_PIPELINE.md` 是设计规范，不是已经存在的自动化 Skill。已有 `mythic-visual-qa`/`blender-cli` 也不自动具备真实 GameViewport 采集或跨章整套资产生产能力；须在 M1/M2 取得可复现证据后逐项扩展。
- 官方 Water/WaterExtras/WaterAdvanced 等实验性插件虽已在 UE5.8 引擎目录找到，但当前工程未显式启用/执行测试；文件存在性仅为 LOCAL_FILES_VERIFIED，不能宣称浮力、水面、巨兽动画或性能已可用。

## Next
0. **M1 双线同步开工**：克拉肯首章完整海域/路线/事件，及可复用的高精风暴海面、木船、主体/触手、骨骼/PBR/光照；先验证 A/C 真正 GameViewport 镜头及 GPU/CPU 性能，但最终验收要 A–E 全覆盖。
1. 搭建 Kraken 原生 Map、章节目录、船/游泳 Pawn、动画/危险接口与必要玩法，正式目标是 14–18 分钟 FullChapter；可用 5–7 分钟 PrototypeSlice 独立时间配置验证关键互动，但不要把它变成长期独立交付。
2. 同时验证 PrototypeSlice（240s）和 FullChapter（720s）的独立时间/Profile 数据，补齐 K0–K6 状态、HUD、失误恢复、安全区/失败重试与剧情船毁，运行真实 PIE 进行全章测试。
3. **视觉品质线不等待玩法结束**：随着场景区域解锁持续制作真实高精资产、触手动态和接触事件、海洋与天气、近景材质/骨骼、交互 VFX、灯光与性能优化；每一批边开发边验收，避免一次性全图高模。
4. M1 完整首章内容线/视觉品质线均达标后，依据 `docs/VISUAL_PIPELINE.md` 提炼可运行、可复现、可回滚的候选 Skill/工作流；M2 至少在一个异类巨兽/场景复用实测成功才标记 `REUSABLE_VALIDATED`，随后完成后四章；M3 全五章质量/性能/打包验收。
