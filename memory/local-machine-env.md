# 本地机器环境状态记忆（memory）

> 本文件由 AI 在每次会话中**读取与更新**，用于跨会话避免重复初始化。规则见 `AGENTS.md` 第 3 节。
> 每次完成关键步骤后，把对应字段的值更新为最新状态；失败的步骤标记为「未完成」。

## 机器与平台

- 机械臂型号：`B601-DM` / `B601-RS`（二选一，删除另一项）
- 操作系统：`Ubuntu 22.04` / `Ubuntu 24.04` / `macOS` / `Windows` / `Jetson (JetPack x.x)`
- 主控设备：`x86 台式机/笔记本` / `Jetson Orin Nano Super 8G` / `reComputer Robotics J4012` / 其他：______
- GPU：`______`（显存 ____ GB）

## 软件环境

- conda 环境名：`rebot`（创建时间：______）
- Python 版本：`3.12`
- motorbridge 版本：`______`（`motorbridge --version`）
- LeRobot 安装：`~/rebot_lerobot`（editable）｜ pip 插件：`lerobot-robot-seeed-b601`、`lerobot-teleoperator-rebot-arm-102`
- 其他关键依赖：`ffmpeg`（conda）｜ `pynput==1.6.8`（如录制按键失灵）｜ `pyrealsense2` / `pyorbbecsdk2`（视觉抓取）

## 通信接口

- DM：串口设备 `______`（`ls /dev/ttyACM*`），权限已赋：是/否
- RS：CAN 接口 `______`（默认 can0），bitrate `1000000`，状态 up：是/否
- PCAN 驱动（Jetson）：已编译安装（`make netdev`）：是/否
- brltty：已移除（占用串口时）：是/否

## 电机配置状态

- 电机 ID：1-7 已写入并扫描验证：是/否（未完成则写「未完成」）
- 零点标定：Follower 已标定：是/否｜Leader（reBot Arm 102）已标定：是/否（标定文件在 `~/.cache/huggingface/lerobot/calibration/`）
- RS 参数模板初始化（Read/Apply/Write）：是/否

## 数据集

| repo_id | 任务 | 条数 | 位置 | 状态 |
|---------|------|------|------|------|
| `seeed_rebot_b601_dm/test` | Grab the crayfish into the box | 5 | `~/.cache/huggingface/lerobot/` | 测试完成 |
| ______ | ______ | ______ | ______ | ______ |

## 已训练模型

| 策略 | 数据集 | checkpoint 路径 | 成功率（20 次） | 备注 |
|------|--------|----------------|----------------|------|
| ACT | ______ | `outputs/train/______/checkpoints/last/pretrained_model` | ______ | ______ |
| GR00T | ______ | ______ | ______ | ______ |

## 已完成的工作流

- [ ] 新臂初始化（`workflows/first-run.md`）
- [ ] 首个模仿学习任务（`workflows/first-imitation-task.md`）
- [ ] 视觉分拣项目（`workflows/vision-grasping-project.md`）

## 备注 / 已知问题

- ______
