# AGENTS.md — AI 会话守则（Session Protocol）

本仓库是一套面向 AI Agent 的 **reBot Arm（B601-DM / B601-RS）技能仓库**。本文件规定 AI 在协助用户操作机械臂时**每次会话必须遵循的流程与规则**。

## 0. 每次会话开始（固定动作）

1. **读环境状态记忆**：`memory/local-machine-env.md`（不存在则跳过，完成后创建）。据此判断哪些步骤已完成、哪些需要重做，避免重复初始化。
2. **确认型号与平台**：B601-**DM**（24V、串口 `/dev/ttyACM0`、达妙电机）还是 B601-**RS**（48V、SocketCAN `can0`、灵足电机）？操作系统（Linux/macOS/Windows/Jetson）？不确定则先问用户。
3. **加载安全技能**：任何涉及真机操作的任务，**先读 `skills/rebot-arm-safety/SKILL.md`** 并带领用户完成检查清单，再开始操作。
4. 按任务加载对应技能（见下表）。

## 1. 技能路由表

| 用户意图 | 加载技能 |
|---------|---------|
| 认识机械臂 / 选型 / 看规格 | `skills/rebot-arm-overview/SKILL.md` |
| 任何操作前的安全检查 | `skills/rebot-arm-safety/SKILL.md` |
| 装环境 / 接线 / 首次上电 | `skills/rebot-arm-environment-setup/SKILL.md` |
| 写电机 ID / 标定零点 | `skills/rebot-arm-motor-config/SKILL.md` |
| 电机底层控制 / CAN / MIT | `skills/rebot-arm-motor-control/SKILL.md` |
| Python SDK 控制整臂 | `skills/rebot-arm-python-sdk/SKILL.md` |
| 主从遥操作 / LeRobot | `skills/rebot-arm-teleoperation/SKILL.md` |
| 采集数据 / 数据集质量 | `skills/rebot-arm-data-collection/SKILL.md` |
| 训练/推理 ACT | `skills/rebot-arm-act-training/SKILL.md` |
| VLA / GR00T 微调 | `skills/rebot-arm-vla-gr00t/SKILL.md` |
| 视觉抓取 / 手眼标定 | `skills/rebot-arm-vision-grasping/SKILL.md` |
| ROS2 接口 | `skills/rebot-arm-ros2/SKILL.md` |
| MoveIt2 规划 | `skills/rebot-arm-moveit/SKILL.md` |
| MuJoCo / Isaac Sim 仿真 | `skills/rebot-arm-simulation/SKILL.md` |
| 故障排查 | `skills/rebot-arm-troubleshooting/SKILL.md` |
| 从头开始完整流程 | `workflows/first-run.md`（初始化）、`workflows/first-imitation-task.md`（模仿学习）、`workflows/vision-grasping-project.md`（视觉分拣） |

## 2. 执行分工（每个技能内都有标记）

- `🤖 AI 执行` — 直接运行，无需打断用户。
- `👤 用户执行` — 必须由用户操作（GUI/网页/按键/插线/物理搬动）；AI 负责指导与等待。
- `🔀 人机协作` — AI 运行命令但需要用户配合（sudo 密码、确认硬件状态、交互式提示）。

**AI 行为红线**：
- 凡 `sudo` 或改动系统配置的命令：先向用户说明目的并征得同意（标 `🔀`/`👤`），不要静默执行。
- 网页/GUI/按键/插线/物理搬动：**不要让 AI 假装能完成**，明确交给用户并给出操作指引。
- 运动类命令（使能、move、遥操作、推理）：执行前确认工作区无人、用户已读安全清单、手边有电源开关。

## 3. 环境状态记忆（每步之后更新）

`memory/local-machine-env.md` 是跨会话的状态记录。规则：

- **会话开始**：读它 → 已完成的步骤跳过。
- **每完成一个关键步骤**（装好环境、配好端口、写完 ID、标定完成、数据集创建、训练完成、ROS2 启动成功…）：**追加/更新对应字段**（见模板），确保下次会话可续。
- **失败/回退**：把失败的步骤标为未完成（删掉对应已完成标记），避免下次误跳过。

## 4. 命令与文档冲突时的处理

- 本仓库命令以官方 Wiki（wiki.seeedstudio.com）与官方 GitHub 仓库为准；冲突时以官方为准，并提示用户"以官方文档为准"。
- 技能中标注"以仓库/源码为准"的内容（如故障码表、配置文件名），不要臆造具体值，必要时引导用户查官方源码。
- 不确定的操作：明确告知用户不确定性，建议查官方 Wiki / GitHub Issues 或联系官方支持。

## 5. 会话结束（固定动作）

- 检查机械臂已安全收尾（回零/失能/断电状态由用户确认）。
- 更新 `memory/local-machine-env.md`（完成后标记完成）。
- 向用户总结：已完成什么、验证结果、下一步建议。
