# AGENTS.md

本仓库是一套面向 AI Agent 的 **reBot Arm（B601-DM / B601-RS）技能仓库**。

## 快速开始

1. 先读 [README.md](README.md) 了解技能清单与用法。
2. 用户要操作/调试机械臂时，**首先加载 `skills/rebot-arm-safety/SKILL.md`**（安全规范），再按任务加载对应技能：

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

## 关键规则

- **先确认型号**：B601-DM（24V，串口 `/dev/ttyACM0`，达妙电机）与 B601-RS（48V，SocketCAN `can0`，灵足电机）命令分支不同，先向用户确认型号。
- **安全第一**：任何真机运动前，完成 `rebot-arm-safety` 中的检查清单；遇到失控立即断电。
- **命令来源**：本仓库命令以官方 Wiki（wiki.seeedstudio.com）与官方 GitHub 仓库为准，冲突时以官方为准。
