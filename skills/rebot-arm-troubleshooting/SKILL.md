---
name: rebot-arm-troubleshooting
description: reBot Arm（B601-DM / B601-RS）故障排查总入口：先做安全判断（异常立即断电）、按症状定位问题（通信/电机/运动/数据/训练/ROS2/仿真），含诊断树、常见错误与修复、性能与调参经验。当用户报告任何机械臂异常（乱动、抖动、连不上、抓不到、loss 不降、报错）时，先加载本技能定位方向，再转到对应技能。
---

# reBot Arm 故障排查（Troubleshooting）

## 简介

本技能是**所有故障排查的入口**：先判断是否紧急（涉及人身/设备安全 → 立即断电），再按症状表定位问题方向，然后进入对应技能的详细排查流程。

> 分工标记：🤖 AI 执行（终端可自动化）｜ 👤 用户执行（GUI/网页/按键/插线/物理操作）｜ 🔀 人机协作（sudo 需用户密码或需用户确认）

## 0. 紧急判断（第一步永远是安全）

> 🔴 出现以下情况**立即断电**（拔电源/按电源开关），不要先"按停程序"：
> - 机械臂剧烈抖动（高频正反力矩可能损坏电机）
> - 撞击限位 / 堵转（电机过热损坏）
> - 异响、冒烟、异味
> - 突发跌落、失控
> 断电后扶稳机械臂 → 检查外观 → 排查原因 → 低速小范围重试验证。

## 1. 症状 → 方向 速查表

| 症状 | 可能方向 | 进入技能 |
|------|---------|---------|
| 找不到串口 / can0 / 权限不足 | 环境与接口 | rebot-arm-environment-setup |
| 电机扫描不到 / 使能失败 / 电机乱动 | 电机 ID/参数/零点 | rebot-arm-motor-config、rebot-arm-motor-control |
| 遥操作不跟手 / 从臂不跟随 / 映射反向 | 校准与遥操作 | rebot-arm-teleoperation |
| 训练 loss 不降 / 模型乱动 / 抓不到 | 数据与训练 | rebot-arm-act-training、rebot-arm-data-collection |
| 视觉抓取位置偏 / 检测不准 | 手眼标定与补偿 | rebot-arm-vision-grasping |
| ROS2 接口报错 / 轨迹执行失败 | ROS2/MoveIt | rebot-arm-ros2、rebot-arm-moveit |
| 仿真不同步 / 延迟大 | Real-to-Sim | rebot-arm-simulation |

## 2. 通信与接口类

- **找不到 /dev/ttyACM0（DM）**：检查 USB 线；`ls /dev/ttyACM*`；Ubuntu 下 `brltty` 占用串口 → `sudo apt remove -y brltty` 后重插；权限 `sudo chmod 666 /dev/ttyACM*`（重启后需重设）。
- **can0 不存在（RS）**：`sudo modprobe peak_usb`；Jetson 需编译安装 PEAK 驱动（`make netdev`，勿用普通 make）；`ip -br link | grep can` 确认。
- **macOS RS 报 `load PCBUSB failed`**：安装 PCBUSB 并配置 `DYLD_FALLBACK_LIBRARY_PATH`（见官方 Wiki）。
- **虚拟机上控制异常**：官方建议 Ubuntu 物理机，虚拟机性能不足/配置问题多。

## 3. 电机类

- **扫描不到电机**：检查上电、接线（DM 电机 1↔2 之间 3 芯线束）、CAN ID/Master ID 是否与表一致、是否失能状态。
- **电机使能后立即异响**（DM）：参数被意外覆盖（写 ID 时触发参数校准），用 DM_Tools_v1.8.0.1.exe 从同型号完好电机导出参数导入故障电机，再重新标定零点。
- **所有电机 CAN ID 相同**（DM）：DM_Tools 调试界面不要点 CAN ID 旁的 Read/Set（会统一总线上所有电机 ID）。
- **robstride id-set 报 store_parameters failed 超时**（RS）：ID 实际已写入，扫描验证即可。
- **电机灯不亮/使能失败**：确认供电电压（DM 24V / RS 48V）、电源档位（230V/115V）、电机线插紧。

## 4. 运动与控制类

- **机械臂运动方向反向**（遥操作/ROS2）：检查 Leader 校准的关节方向配置（config_rebot_arm_102_leader.py）；ROS2 夹爪方向反了交换 pick_place.yaml 的 hardware_open/closed_gripper_position。
- **遥操作电源脱落/信号线脱落**：先停代码 → 回 0 点 → 重新上电 → 再运行。
- **结束要用 ESC 不要 Ctrl+C**（数据采集/推理），Ctrl+C 可能导致异常退出、机械臂停在半空。
- **ROS2 轨迹执行失败**：首个轨迹点与当前关节角偏差 < 0.10 rad；确认 reBotArmController 已启动且使能。
- **MoveIt 规划失败**：检查起始状态在限位内（CheckStartStateBounds）、无碰撞（CheckStartStateCollision）、目标在工作空间内（ValidateWorkspaceBounds）、`ik_timeout`/`planning_time`（默认 5s）可增大。
- **joint6 旋转过多**：IK 多解，用 `tcp_yaw_offsets` 备选 yaw 或选关节变化最小的解。

## 5. 数据与训练类

- **loss 几乎不降（贴死）**：先加 steps / 加数据，仍不动再试 lr 2e-5（`--policy.optimizer_lr` 与 `--policy.optimizer_lr_backbone` 一起改）。
- **训练乱动/动作离谱**：先排除配置问题再怀疑数据——"乱动是配置病，够不到才是数据病"；检查推理场景光线/机位与采集时是否一致。
- **够不到（伸向错误位置）**：该位置数据覆盖不足 → 补录该区域示范（在原有位置旁 5-10cm 放物体扩展边界）。
- **抓不稳（碰到但夹不住/滑落）**：夹爪闭合时序学得不准 → 补录抓取瞬间的高质量示范。
- **数据按键没反应**（录制）：pynput 版本问题 → `pip install pynput==1.6.8`。
- **RTX50 训练报错**：加 `--dataset.video_backend=pyav`。
- **GR00T 训练报 `mean is infinity` / loss 正常真机乱动**：见 vla-gr00t 技能常见问题；Flash Attention 安装失败试预编译 wheel（`pip install flash-attn --no-build-isolation`，RTX50 试 `flash_attn==2.8.0.post2 torch==2.7.1`）。

## 6. 视觉抓取类

- **抓取位置偏移**：修改 `config/default.yaml` 的 `calibration.hand_eye_compensation_m` 的 x/y/z 补偿（示例 z: -0.02）。
- **手眼标定误差大**：检查 ArUco 标定板姿态、相机固定是否松动、标定矩阵是否更新。
- **相机读不到**：直插电脑不要接扩展坞；确认 SDK（pyrealsense2/pyorbbecsdk2）与相机型号匹配。

## 7. 排查方法论（AI 助手引导用户时）

1. **先复现**：让用户描述触发条件、完整报错文本、操作步骤。
2. **查日志**（🤖）：终端输出、`ros2 topic echo`、训练日志（loss/grdn/eta 字段）等终端诊断命令，AI 可直接执行。
3. **最小化**：一次只改一个变量（先环境后数据后参数）。
4. **分级处理**：环境类问题先重装/重配（涉及 sudo 需用户确认，🔀）；数据类问题补数据（需用户录制示范，👤）；参数类问题调参（🤖）。
5. **不编造**：不确定的报错先搜官方 Wiki FAQ / GitHub Issues，或建议联系官方支持。

## ✅ 验证与预期结果

| 运行 | 期望结果 | 失败处理 |
|------|---------|---------|
| 修复后机械臂低速小范围试跑（真机） | 运动正常，无异常抖动/异响 | 立即断电，回到对应小节继续排查 |
| `ros2 topic echo /rebotarm/arm_status`（ROS2 场景） | 持续输出状态消息、无报错 | 检查 reBotArmController 是否启动且电机已使能 |
| 训练后推理试跑（训练类问题） | 动作符合示范、无乱动 | 回到第 5 节补数据或调参 |

## 参考

- 官方 Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- 配套教程：本地参考教程（未随本仓库发布）（各章 FAQ 汇总）
- 子技能：rebot-arm-safety（安全）｜ rebot-arm-environment-setup ｜ rebot-arm-motor-config ｜ rebot-arm-motor-control ｜ rebot-arm-python-sdk ｜ rebot-arm-teleoperation ｜ rebot-arm-data-collection ｜ rebot-arm-act-training ｜ rebot-arm-vla-gr00t ｜ rebot-arm-vision-grasping ｜ rebot-arm-ros2 ｜ rebot-arm-moveit ｜ rebot-arm-simulation
