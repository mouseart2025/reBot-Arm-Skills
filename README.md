# reBot Arm AI Skills 技能仓库

一套**符合 Agent Skills 规范**的技能仓库（Skill Repository），让 AI 助手（Claude Code、DeepSeek、Cursor 等支持 skills/AGENTS 规范的 Agent）能够通过**自然语言**引导用户使用 [Seeed Studio](https://www.seeedstudio.com/) 的开源桌面机械臂 **reBot Arm B601**（含 **B601-DM** 与 **B601-RS** 两个型号）。

- 官方 Wiki（Quick Start）：[B601-DM](https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/) ｜ [B601-RS](https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/)
- 开源仓库：[Seeed-Projects/reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm)
- 配套中文教程：《Seeed具身智能入门8个阶段40章节：手把手教你造一台会学习的机械臂》（**仅本地参考，不随本仓库提交**——因包含约 680MB 图片/视频附件；本仓库各技能正文已内联教程中的关键命令）

---

## 一、这是什么

本仓库把 reBot Arm 的"接线组装 → 电机标定 → 底层控制 → Python SDK → LeRobot 遥操作/数据采集/ACT 训练 → VLA(GR00T) → 视觉抓取 → ROS2/MoveIt2 → 仿真( MuJoCo/Isaac Sim) → 故障排查"全链路，拆解为**一组可独立加载的技能（Skills）**。

每个技能是一个文件夹，内含一份 `SKILL.md`（YAML frontmatter + Markdown 正文）。AI Agent 会根据 frontmatter 中的 `description` 判断何时加载该技能，加载后将 `SKILL.md` 的内容注入上下文，从而"知道"如何一步步引导用户操作机械臂。

> 格式遵循 Anthropic **Agent Skills** 开放规范：每个技能目录下必须有 `SKILL.md`，其 YAML frontmatter 至少包含 `name`（技能名）与 `description`（何时使用该技能）。详见 [docs/skill-authoring-guide.md](docs/skill-authoring-guide.md)。

## 二、技能清单

| # | 技能目录 | 用途（AI 何时加载） |
|---|---------|-------------------|
| 1 | [skills/rebot-arm-overview](skills/rebot-arm-overview/SKILL.md) | 认识 reBot Arm、DM/RS 选型、硬件组成与规格、生态总览 |
| 2 | [skills/rebot-arm-safety](skills/rebot-arm-safety/SKILL.md) | **任何操作前必读**：电气/机械安全、检查清单、紧急处理流程 |
| 3 | [skills/rebot-arm-environment-setup](skills/rebot-arm-environment-setup/SKILL.md) | 环境搭建：Miniforge/conda、motorbridge、串口/CAN 权限、首次接线供电上电 |
| 4 | [skills/rebot-arm-motor-config](skills/rebot-arm-motor-config/SKILL.md) | 电机 ID 写入、零点标定、MotorBridge Studio、RS 参数模板初始化 |
| 5 | [skills/rebot-arm-motor-control](skills/rebot-arm-motor-control/SKILL.md) | 电机底层控制：MotorBridge Python API、MIT/POS_VEL/VEL/PVT 模式、CAN 协议 |
| 6 | [skills/rebot-arm-python-sdk](skills/rebot-arm-python-sdk/SKILL.md) | 用 Python SDK（reBotArm_control_py / rebotArm_ctrl）控制整臂：连接、运动、设零点、读状态 |
| 7 | [skills/rebot-arm-teleoperation](skills/rebot-arm-teleoperation/SKILL.md) | LeRobot 主从遥操作：Leader/Follower 校准、启动遥操作、相机接入、延迟调优 |
| 8 | [skills/rebot-arm-data-collection](skills/rebot-arm-data-collection/SKILL.md) | 数据采集：任务设计、相机配置、录制 Episode、数据集结构与质量检查 |
| 9 | [skills/rebot-arm-act-training](skills/rebot-arm-act-training/SKILL.md) | ACT 模仿学习：训练参数、checkpoint、真机推理、评估与失败驱动补数据 |
| 10 | [skills/rebot-arm-vla-gr00t](skills/rebot-arm-vla-gr00t/SKILL.md) | VLA 与 Isaac GR00T：语言标注、modality/embodiment 配置、微调、推理部署 |
| 11 | [skills/rebot-arm-vision-grasping](skills/rebot-arm-vision-grasping/SKILL.md) | RGB-D 视觉抓取：相机安装、YOLO 检测、手眼标定、抓取程序、位置补偿 |
| 12 | [skills/rebot-arm-ros2](skills/rebot-arm-ros2/SKILL.md) | ROS2 集成：工作空间构建、Topic/Service/Action 控制、状态机与故障码 |
| 13 | [skills/rebot-arm-moveit](skills/rebot-arm-moveit/SKILL.md) | MoveIt2 运动规划：启动链路、规划组、笛卡尔路径、抓取放置 demo |
| 14 | [skills/rebot-arm-simulation](skills/rebot-arm-simulation/SKILL.md) | 仿真：MuJoCo、Isaac Sim、真实机械臂与仿真同步（Real-to-Sim） |
| 15 | [skills/rebot-arm-troubleshooting](skills/rebot-arm-troubleshooting/SKILL.md) | 故障排查：诊断树、常见错误与修复、参数调优经验 |

## 三、如何让 AI 使用这些技能

**方式 A：把技能安装到你的 Agent 技能目录（推荐，随取随用）**

以 Claude Code 为例，将技能复制到项目或用户级技能目录：

```bash
# 项目级（仅当前项目生效）
mkdir -p .claude/skills
cp -r skills/* .claude/skills/

# 或用户级（所有项目生效）
mkdir -p ~/.claude/skills
cp -r skills/* ~/.claude/skills/
```

装好后，直接对 AI 说自然语言即可，例如：

- "帮我把机械臂初始化（写入电机 ID + 零点标定）"
- "我想采集 50 条'把方块放进盒子'的示范数据"
- "训练一个 ACT 策略，然后帮我在真机上评估成功率"
- "机械臂动起来抖得很厉害，帮我排查"

AI 会依据技能描述自动加载对应技能并逐步执行。**建议在第一次使用前先让 AI 加载 `rebot-arm-safety` 与 `rebot-arm-overview`。**

**方式 B：让 Agent 直接阅读本仓库**

把本仓库路径告诉 Agent（或设置 `AGENTS.md`），Agent 会按 `README.md` 的技能索引按需读取对应 `SKILL.md`。仓库根目录已附带一份精简的 [AGENTS.md](AGENTS.md) 帮助 Agent 快速定位。

## 四、技能内容约定

- **语言**：正文使用中文（保留英文技术术语/命令），面向中文用户。
- **安全优先**：任何涉及真机运动的技能都会内嵌"安全要点"提示；所有操作前必须先读 `rebot-arm-safety`。
- **命令即事实**：所有命令、参数、端口号均来自官方 Wiki 与本仓库配套教程；如与官方文档冲突，以官方文档为准。
- **可移植性**：每个技能自包含，`SKILL.md` 内联关键表格与命令，尽量不依赖仓库内跨目录文件；详细参考资料通过外部链接给出。

## 五、常见问题

**Q：B601-DM 和 B601-RS 有什么区别？该买哪个？**
A：两者外观/结构/软件生态相同，区别在关节电机与供电：**DM**（达妙行星减速，24V 供电）扭矩大、刚度高，适合重负载/高精度；**RS**（灵足 QDD 准直驱，48V 供电）速度快、可反驱、力控透明，适合遥操作/模仿学习/人机交互。详见 `rebot-arm-overview` 技能。

**Q：技能里的命令是否适用于两个型号？**
A：多数命令按型号给出独立分支（如 `seeed_b601_dm_follower` / `seeed_b601_rs_follower`、`/dev/ttyACM0` / `can0`）。请先确认用户型号再执行对应分支。

**Q：如何贡献新的技能？**
A：按 [docs/skill-authoring-guide.md](docs/skill-authoring-guide.md) 的规范新增一个目录与 `SKILL.md`，并在本 README 技能清单中登记。

## 六、相关链接

- reBot Arm 官方开源仓库：<https://github.com/Seeed-Projects/reBot-DevArm>
- LeRobot 适配仓库：<https://github.com/Seeed-Projects/lerobot>
- 底层 Python 控制库：<https://github.com/Seeed-Projects/reBotArm_control_py>
- 视觉抓取仓库：<https://github.com/Seeed-Projects/reBot-DevArm-Grasp>
- MotorBridge（电机控制中间件）：<https://github.com/motorbridge/motorbridge> ｜ Studio Web UI：<https://motorbridge.github.io/motorbridge-studio/>
- 官方 Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>

> ⚠️ 本仓库仅提供操作指引，不替代官方安全文档。使用机械臂前请务必阅读并遵守 `rebot-arm-safety` 技能与官方 Wiki 的安全声明。
