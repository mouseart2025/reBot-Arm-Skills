---
name: rebot-arm-overview
description: 当用户想了解 Seeed reBot Arm（B601-DM / B601-RS）是什么、两个型号的区别与选型、硬件组成、规格参数、配套软件生态，或需要决定"做某任务该选哪个型号"时使用本技能。也适用于对话开始时确认用户硬件型号。
---

# reBot Arm 认识与选型（Overview）

## 简介

reBot Arm B601 是 Seeed Studio 发布的**完全开源**桌面机械臂（结构、BOM、软件、算法全部开源），用于机器人教学、算法开发与具身智能研究。本技能帮助你：
1. 快速确认用户手上的型号（**B601-DM** 还是 **B601-RS**）；
2. 理解两个型号的本质区别，做出选型/任务判断；
3. 掌握硬件组成、关节与规格，为后续操作技能提供背景。

> 分工标记：🤖 AI 执行（终端可自动化）｜ 👤 用户执行（GUI/网页/按键/插线/物理操作）｜ 🔀 人机协作（sudo 需用户密码或需用户确认）
> 本技能为**认知/选型类**技能，不含真机命令；执行类步骤见各操作技能。

## 何时使用

- 用户问"reBot Arm 是什么 / 有哪些型号 / 有什么区别 / 我该买哪个"
- 对话开始时需要确认用户型号（DM 还是 RS），从而决定后续命令分支
- 用户问"做 XX 任务该选 DM 还是 RS"

## 1. 一句话定位

> reBot Arm B601：约 **750 mm 臂展**、**6+1 自由度**（6 个关节 + 1 个夹爪）的开源桌面机械臂，通过 **USB-CAN（DM 为串口桥接 / RS 为 PCAN-USB）** 与电脑连接，支持机械臂控制、视觉抓取、模仿学习（LeRobot/ACT）、VLA（GR00T）、ROS2、仿真（MuJoCo/Isaac Sim）等全链路开发。

官方仓库：<https://github.com/Seeed-Projects/reBot-DevArm>

## 2. DM 与 RS：本质区别（必须先向用户确认型号）

两个版本**外观、机械结构、上层软件生态完全相同**，唯一核心区别是**关节电机方案**：

| 维度 | B601-DM | B601-RS |
|------|---------|---------|
| 关节电机 | 达妙（Damiao）**行星减速**关节电机（DM4310 约 10:1，DM4340P 约 40:1） | 灵足时代（Robstride）**QDD 准直驱**关节电机（低减速比） |
| 设计哲学 | "用机械减速器换大扭矩" | "用高性能电机换动态性能与力控" |
| 供电 | **24V**（官方 24V 14.6A MeanWell 电源） | **48V**（官方 48V 12.5A MeanWell 电源） |
| 通信 | 串口（`/dev/ttyACM0`，波特率 921600），USB-CAN 桥接板 | SocketCAN（`can0`，1 Mbps），PCAN-USB 适配器 |
| 扭矩/刚性 | 输出扭矩大、关节刚性好、抗冲击强 | 扭矩由电机直接承担，刚性较低 |
| 速度/反驱 | 转速较低、反驱性弱（减速比高，断电基本自锁） | 速度快、**可反驱**（可手动拖动）、力控透明、机械阻抗低 |
| 断电风险 | 高减速比有自锁性，坠落风险相对低 | 低减速比自锁性弱，**断电坠落风险更高** |
| 电机 ID | 出厂写入：Motor 1-7 → CAN ID 0x01-0x07，Master ID 0x11-0x17 | 出厂/写入：ID 1-7（master 固定 0xfd 等） |
| 适合场景 | 重负载、高精度、需要关节刚性的任务 | 遥操作、模仿学习、人机交互、力控、高动态运动 |

**选型建议（口诀）**：
- **要负载/刚性/大扭矩 → DM**（如搬运较重物体、精密定位）
- **要速度/反驱/力控/人机协作/模仿学习 → RS**
- 具身智能学习与 LeRobot 数据采集：RS 的 QDD 特性更接近"电机直驱负载"，手感与力交互更好；DM 同样完全支持全部课程，仅手感与安全细节不同。

> ⚠️ **安全提醒**：RS 为 48V 高压系统，且断电后关节自锁性弱，操作/断电时务必扶稳机械臂。详见 `rebot-arm-safety` 技能。

## 3. 硬件组成与关节

| 部件 | 电机 | 运动 | 作用 |
|------|------|------|------|
| Base（基座） | 1 号电机 | 绕基座垂直轴（Z）旋转 | 机械臂整体水平旋转 |
| Shoulder（肩） | 2 号电机 | 绕肩部水平轴（Y）旋转 | 大臂俯仰/抬升 |
| Upper Arm（大臂） | — | 随肩/肘联动 | 连接肩与肘 |
| Elbow（肘） | 3 号电机 | 绕肘部水平轴（Y）旋转 | 小臂相对大臂弯曲 |
| Forearm（小臂） | — | 随肘/腕联动 | 连接肘与腕 |
| Wrist（腕） | 4、5、6 号电机 | 俯仰/偏摆/自转 | 决定末端指向 |
| Gripper（夹爪） | 7 号电机 | 平移开合 | 夹取物体 |

关节运动范围（两个型号一致，夹爪除外）：

| 关节 | 范围 |
|------|------|
| J1 | -150° ~ +150° |
| J2 | -220° ~ 0° |
| J3 | -220° ~ 0° |
| J4 | -90° ~ +90° |
| J5 | -90° ~ +90° |
| J6 | -180° ~ +180° |
| 夹爪 | DM：-325° ~ 0° ｜ RS：-345° ~ 0° |

> 关节限位是物理硬边界（机械限位）。**不要让关节长时间堵转在限位处**，否则电机过热损坏。零位姿态是所有运动规划与位置计算的绝对基准。

## 4. 配套软件生态

| 层 | 工具/仓库 | 用途 |
|----|----------|------|
| 电机控制中间件 | [motorbridge](https://github.com/motorbridge/motorbridge) + [Studio Web UI](https://motorbridge.github.io/motorbridge-studio/) | 电机 ID/零点/参数、Web 拖拽控制、Python API |
| Python 控制库 | [Seeed-Projects/reBotArm_control_py](https://github.com/Seeed-Projects/reBotArm_control_py)（示例：hopcan/rebotArm_ctrl） | 整臂连接、关节运动、设零点、状态读取 |
| 模仿学习 | [Seeed-Projects/lerobot](https://github.com/Seeed-Projects/lerobot) + `lerobot-robot-seeed-b601`、`lerobot-teleoperator-rebot-arm-102` | 主从遥操作、数据采集、ACT 训练/推理、GR00T |
| VLA | NVIDIA GR00T（经 LeRobot groot policy） | 语言条件具身智能策略 |
| 视觉抓取 | [Seeed-Projects/reBot-DevArm-Grasp](https://github.com/Seeed-Projects/reBot-DevArm-Grasp) | RGB-D 相机 + YOLO + 手眼标定抓取 |
| ROS2 | rebotarm_ros2 工作空间（rebotarm_msgs / rebotarmcontroller / rebotarm_bringup / rebotarm_moveit_config 等 7 个包） | ROS2 Topic/Service/Action、MoveIt2 |
| 仿真 | MuJoCo（MJCF）、NVIDIA Isaac Sim（USD） | 运动学/动力学仿真、Real-to-Sim 同步 |

## 5. 系统要求（通用前提）

- **不要使用 Windows / WSL / 虚拟机运行控制程序**（官方验证性能不足、配置问题多）；推荐 **Ubuntu 22.04 物理机**（macOS 可部分使用，详见对应技能）。
- GPU：ACT 训练建议 NVIDIA 显卡（8 GB 显存可训，12 GB+ 舒适）；GR00T 微调需要 **40 GB+**（16 GB 仅推理）。
- 主控可选：Ubuntu 台式机/笔记本、Jetson Orin Nano Super 8G、reComputer Robotics J4012、Jetson AGX Thor 等。

## 6. 常见判断

- **"我该怎么确认我的型号？"** → 看电机铭牌/包装（Damiao=DM，Robstride/灵足=RS）；DM 用串口连接、24V 电源；RS 用 PCAN-USB、48V 电源。
- **"两个型号能共用教程吗？"** → 能。所有课程/命令仅通信分支与安全细节不同，其余完全一致。

## ✅ 验证与预期结果

| 运行/动作 | 期望结果 | 失败处理 |
|-----------|---------|---------|
| 请用户查看电机铭牌或包装（👤） | 明确是 Damiao（DM）还是 Robstride/灵足（RS） | 仍不确定：看电源电压（24V=DM / 48V=RS）或通信接口（串口 /dev/ttyACM*=DM，PCAN can0=RS） |
| 对照第 2 节选型表确认任务需求 | 能回答"做 XX 任务该选/该用哪个型号" | 需求模糊时询问负载、速度、是否需力控/遥操作 |
| 记录型号与平台到 `memory/local-machine-env.md` | 型号字段已填写 | — |

## 参考

- Wiki Quick Start：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- 开源仓库：<https://github.com/Seeed-Projects/reBot-DevArm>
- 配套教程：本地参考教程《Seeed具身智能入门8个阶段40章节》（未随本仓库发布）（第 1、2、4 章）
- 下一步：环境搭建见 `rebot-arm-environment-setup`；任何操作前先读 `rebot-arm-safety`。
