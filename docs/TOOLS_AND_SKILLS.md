# Tool / Skill Decision Log

目标：用尽量少的上下文增强 GPT-6 Astra + Codex 的真实 UE5 编辑器能力。

## 已配置（2026-10-10）

**Unreal MCP**
- 来源：Epic Games 官方 https://github.com/EpicGames/unreal-engine-skills-for-claude-code-plugin
- 项目 Skill：`.agents/skills/unreal-mcp/SKILL.md`，带 setup/operations 按需参考。
- UE5.8.3 自带 `ModelContextProtocol`、`AllToolsets`，已在 `MythicEscape.uproject` 启用。
- 项目 Codex 配置：`.codex/config.toml`，指向 `http://127.0.0.1:8001/mcp`。
- 已实测编辑器启动后的 MCP initialize、tools/list 和 list_toolsets（HTTP 200）。
- 注意：8000 已由另一个 `UE58-MCP-Host` 工程占用，**不可误连**。

**Visual QA**
- 项目轻量 Skill：`.agents/skills/mythic-visual-qa/SKILL.md`，配合 `docs/VISUAL_QA.md`。
- 已更新 `mythic-visual-qa`：新增本机 UE MCP 真实截图采集脚本 `scripts/capture_ue.py`，以及截图证据哈希 / 对照图脚本 `scripts/visual_qa.py`。已对真实 UE 编辑器视口执行 MCP 截图并获得 PNG；**PIE 画面、游戏动画与审美门仍须通过后续真实试玩验证**。仅视觉任务触发。
- 已跑通 Editor 截图、PIE 暂时启动/停止 + 截图、PNG 元数据与 SHA256、参考图并排输出。**发现 PIE 和 Editor 两张截图像素几乎完全相同**，说明此 `CaptureViewport` 不是可直接信赖的玩家游戏相机采集；目前真正的实时游戏画面与帧率取证仍处于 NOT_VERIFIED。
- 不引入整套跨平台社区审查体系，避免额外 Token 和工具步骤。

**Blender CLI**
- 来源：https://github.com/thanhdongnguyen/Blender-Skill，2026-10-10 获取 HEAD `d4bc3847a45795d0b5682a32618e68deb354e5ad`。
- 安装到项目 `.agents/skills/blender-cli`（MIT），包含官方 API 5.2 离线资料和运行脚本，未更改全局 Skill。
- 本机 Blender 5.2.1 LTS 已验证可后台启动；`features.py overview` 和 `probe_blender.py --property RenderSettings.engine` 实测通过，运行时 API 5.2 匹配；**尚未做 Tripo 资产导入/导出压力测试**。
- Windows Python 默认 GBK 无法可靠读取包含特殊字符的 API 文档，必须以 `python -X utf8` 调用宿主工具。
- 该 Skill 对复杂任务有严格的离线 API 证据流程：能降低错误 API 使用，**但增加工具操作与 Token 消耗**，只在 Blender 建模/导出任务使用，不加载到普通 UE / 文档工作流。

## 环境与使用

- Engine：`D:\Program Files\Epic Games\UE_5.8`（5.8.3）。
- Project：`E:\Projects\ue projects\Mythic Escape\MythicEscape.uproject`
- Codex CLI：0.161.0。
- 一般从项目根目录启动 Codex，以确保项目级 Skill、AGENTS.md、MCP 配置被读取。
- UE 编辑器运行时自动启动项目配置的 MCP 服务，端口 8001；结束编辑器会失去连接。
- 默认只需三个元工具：`list_toolsets`, `describe_toolset`, `call_tool`。按需描述目标工具集，不将几十个完整工具 Schema 一次读入上下文。
- MCP 是编辑器工具；如需蓝图编译/画面验收必须获得编辑器结果或截图，不能仅看文件存在。

## Token economy
1. 普通逻辑任务不调用视觉 Skill；视觉任务只读取对应 QA 检查点。
2. 工具集仅按需发现，避免反复 list_all。
3. 日志只截取当前错误和关键尾部；按阶段记录结论到 PROGRESS.md。
4. 合并独立修改，保存之后只复测被影响的模块。
5. 截图和短视频是画质证据；不能把离线电影输出当作实时游戏质量证明。
