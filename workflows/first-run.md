# 工作流：新臂初始化（first-run）

> 目标：把一台**新出厂的 reBot Arm（B601-DM / B601-RS）**从拆箱带到"可以安全地编程控制"。适用于新臂/重装环境/更换电脑后。
> 每个检查点（✅）通过后才能进入下一步；完成一步就在 `memory/local-machine-env.md` 中更新状态。

## 前置

- 机械臂已按官方 Wiki 组装完成（或购买预组装版）
- 已准备：电脑（Ubuntu 22.04 物理机优先）、电源（DM 24V / RS 48V）、USB-CAN（DM）或 PCAN-USB（RS）、工具夹具 ×2
- 先读 `skills/rebot-arm-safety/SKILL.md` 完成安全清单

## 步骤总览

```
1 环境搭建 ──> 2 接线供电 ──> 3 电机 ID ──> 4 零点标定 ──> 5 首次控制验证
```

---

## Step 1 环境搭建（🤖/🔀）

见 `skills/rebot-arm-environment-setup/SKILL.md`

1. 安装 Miniforge + conda 环境 `rebot`（Python 3.12）
2. `pip install motorbridge`，验证 `motorbridge --version`
3. 配置通信接口：
   - DM：`sudo chmod 666 /dev/ttyACM*`（🔀 需用户密码）
   - RS：`sudo ip link set can0 type can bitrate 1000000 && sudo ip link set can0 up`（🔀）；Jetson 需先编译 PCAN netdev 驱动

✅ **检查点**：`motorbridge --version` 有输出；`ls /dev/ttyACM*`（DM）或 `ip -br link show can0` UP（RS）
→ 更新 memory：「软件环境」「通信接口」

## Step 2 接线供电（👤 用户执行）

1. 断电状态下接好：电源（XT30）→ 机械臂；USB-CAN/PCAN-USB → 电脑
2. 确认电源电压档位（220V→230V / 110V→115V）
3. 上电，确认指示灯亮

✅ **检查点**：上电后无异常、无异响
→ 更新 memory：「通信接口」已就绪

## Step 3 电机 ID 写入（🔀/👤）

见 `skills/rebot-arm-motor-config/SKILL.md`

- **DM**：用 DM_Tools（👤 Windows GUI）或 motorbridge Python（🤖/🔀）逐个写入 Motor 1-7 → CAN ID 0x01-0x07、Master ID 0x11-0x17；**只连一个电机写一个**，断电切换
- **RS**：MotorBridge Studio（👤 网页）选 `rebot-arm-robstride`，扫描 1-7；写 ID（can_id=关节编号，master_id 固定 0xfd）
- 预组装套件：**不要重写 ID**，仅扫描确认 1-7 在线即可

✅ **检查点**：扫描到全部 7 个电机且 ID 与对照表一致（DM 用 Python 扫描 / RS 用 `motorbridge-cli scan --vendor robstride --channel can0 --start-id 1 --end-id 7`）
→ 更新 memory：「电机配置状态」ID 已写入

## Step 4 零点标定（🔀/👤）

见 `skills/rebot-arm-motor-config/SKILL.md`

1. 手动把机械臂摆到官方零位姿态（夹爪完全闭合）
2. DM：Web Studio 或 Python `set_zero_position`；RS：MotorBridge Studio 使能后 `Zero+Save`
3. RS 额外：执行参数初始化三步 Read → Apply Default Template → Write（写入中勿断电）

✅ **检查点**：设零后回读关节位置 ≈ 0（`motor.request_feedback()` + `get_state()`，或 Web 界面数值归零）
→ 更新 memory：「电机配置状态」零点已标定 + RS 参数模板

## Step 5 首次控制验证（🔀）

见 `skills/rebot-arm-python-sdk/SKILL.md` 与 `skills/rebot-arm-motor-control/SKILL.md`

1. 用 SDK 上下文连接（DM：`Controller.from_dm_serial("/dev/ttyACM0", 921600)` + `reBotArm_handle(ctrl,"rebotDM")`；RS：`Controller("can0")` + `"rebotRS"`）
2. 低速小角度：`handle.move_to_joint_positions([0,0,0,0.5,0.5,0,-1])` 等，确认方向正确
3. 结束后等机械臂自动归位再失能

✅ **检查点**：机械臂按预期低速运动、无抖动异响；`handle.motor_state` 可读
→ 更新 memory：「已完成的工作流」勾选「新臂初始化」

## 完成标准

- [ ] 环境/端口/电机 ID/零点全部记录在 `memory/local-machine-env.md`
- [ ] 已用 Python SDK 完成一次安全的小角度运动
- [ ] 用户已体验过 1-2 次使能→运动→失能全流程

## 后续

- 想主从遥操作 → `workflows/first-imitation-task.md`
- 想直接编程控制 → `skills/rebot-arm-python-sdk` ｜ 想 ROS2 → `skills/rebot-arm-ros2`
