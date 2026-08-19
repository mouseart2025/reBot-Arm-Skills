---
name: rebot-arm-motor-control
description: 用 MotorBridge Python API 对 reBot Arm（B601-DM / B601-RS）关节电机做底层控制：使能/失能、扫描电机、切换控制模式（MIT / POS_VEL / VEL / PVT/force_pos）、发送 MIT 力矩指令；并介绍 CAN 协议基础（DM 11 字节标准帧、RS 13 字节扩展帧、SocketCAN）。当用户需要单电机调试、测试电机是否正常、理解控制模式或 CAN 报文时使用本技能。
---

# reBot Arm 电机底层控制与 CAN 协议

## 简介

本技能使用 **MotorBridge Python API** 对 reBot Arm 的单个关节电机做底层调试：创建控制器、添加电机、使能/失能、扫描电机 ID、切换控制模式（MIT / POS_VEL / VEL / FORCE_POS）并发送控制指令；同时讲解 CAN 协议基础，帮助理解电机在总线上的通信方式。适用于 **B601-DM**（达妙电机，串口）与 **B601-RS**（灵足电机，SocketCAN）。

## 何时使用

- 用户要**单电机调试**、测试某个电机是否正常（使能、转动、反馈）
- 用户要理解**控制模式**（MIT / POS_VEL / VEL / PVT）区别与参数、**CAN 报文**（标准帧/扩展帧、CAN ID、Master ID）或 SocketCAN 用法
- 用户要扫描电机 ID、读取电机状态、设置零点

## 前置条件

- 已确认型号：**DM** = 串口 `/dev/ttyACM0` + 24V；**RS** = SocketCAN `can0` + 48V
- 已安装 conda 环境与 motorbridge，串口/CAN 接口已配置可用（见 `rebot-arm-environment-setup`）
- 电机 ID 与零点通常已按 `rebot-arm-motor-config` 配置好（本技能用于验证与控制）
- 已读 `rebot-arm-safety`（涉及真机运动）

## 安全要点

> ⚠️ 任何电机使能/控制前，完成 `rebot-arm-safety` 检查清单：**机械臂底座固定牢靠、周围无人无障碍、手边有电源开关**。

- **测试用小力矩、低速度**：初次调试 `tau` 从 0.1~0.3 Nm 起，`vlim` 从 1.0 rad/s 起，确认方向与响应后再加大。
- **异常立即断电**：异常抖动、撞击限位、突发摔落必须**立即断电**——高频抖动意味着电机在输出高频正反力矩，可能损坏电机（教程第 4 章急停原则）。
- **位置控制时 kd 不能为 0**，否则电机会震荡甚至失控。
- **只给 tau 时不要太大**，否则电机会越转越快以达到期望力矩。
- RS（QDD 低减速比）失能/断电瞬间自锁性弱，**扶稳机械臂**再失能。

## 1. MotorBridge Python API 基础

示例脚本仓库（教程第 7 章）：`git clone https://github.com/hopcan/motorbridge_ctrl.git`，DM 示例在 `dm_motor_ctrl/`，RS 示例在 `rs_motor_ctrl/`。

### 1.1 创建控制器与添加电机

| 型号 | 创建控制器 | 添加电机 | 说明 |
|------|-----------|---------|------|
| DM | `Controller.from_dm_serial("/dev/ttyACM0", 921600)` | `ctrl.add_damiao_motor(can_id, master_id, model)` | model：`4310` / `4340P` / `6001`；波特率 921600 |
| RS | `Controller("can0")` | `ctrl.add_robstride_motor(can_id, master_id, model)` | model：`rs-00` / `rs-06`；**master_id 固定 `0xfd`** |

```python
# DM：串口控制器（波特率 921600）
ctrl = Controller.from_dm_serial("/dev/ttyACM0", 921600)
motor = ctrl.add_damiao_motor(0x01, 0x11, "4340P")   # can_id, master_id, model

# RS：SocketCAN 控制器（master_id 固定 0xfd）
ctrl = Controller("can0")
motor = ctrl.add_robstride_motor(0x01, 0xfd, "rs-00")
```

### 1.2 使能 / 失能（3 秒后自动失能示例）

`ctrl.enable_all()` 使能总线上所有电机，`ctrl.disable_all()` 失能。DM 示例（`1_enable_dm.py`，使能后电机灯变绿，3 秒后失能）：

```python
from motorbridge import Controller, Mode
import time

motor_configs = {
    1: {"can_id": 0x01, "master_id": 0x11, "model": "4310"},  # master_id=0x10+1；model: 4310、4340P、6001
}

ctrl = Controller.from_dm_serial("/dev/ttyACM0", 921600)
motor = {num: ctrl.add_damiao_motor(cfg["can_id"], cfg["master_id"], cfg["model"])
         for num, cfg in motor_configs.items()}

ctrl.enable_all()    # 使能总线上所有电机
time.sleep(3)
ctrl.disable_all()   # 失能总线上所有电机
```

RS 用法相同，仅把 `Controller.from_dm_serial(...)` 换成 `Controller("can0")`、`add_damiao_motor` 换成 `add_robstride_motor(can_id, 0xfd, "rs-00")`（示例 `1_enable_rs.py`）。

### 1.3 扫描电机 ID

DM 扫描（`2_scan_DMmotor.py`）：逐个 can_id 创建电机并读取寄存器验证，可用于核对 can_id 与 master_id 是否与电机内保存的一致：

```python
from motorbridge import Controller

def scan_damiao_motors(start_can_id, end_can_id, channel="/dev/ttyACM0"):
    found_motors = []
    for motor_can_id in range(start_can_id, end_can_id + 1):
        ctrl = Controller.from_dm_serial(channel, 921600)
        temp_motor_master_id = 0x11 + motor_can_id
        try:
            motor = ctrl.add_damiao_motor(motor_can_id, temp_motor_master_id, "4340P")
            # 读取寄存器获取 can id / master id
            esc_id = motor.get_register_u32(8, timeout_ms=100)
            master_id = motor.get_register_u32(7, timeout_ms=100)
            print(f"[find] motor_can_id=0x{esc_id:02X} motor_master_id=0x{master_id:02X}")
            found_motors.append(esc_id)
        except Exception:
            print(f"[no respond] motor_can_id=0x{motor_can_id:02X}")
        finally:
            ctrl.close_bus()
            ctrl.close()
    return found_motors
```

RS 扫描（`2_scan_RSmotor.py`）用 `motor.robstride_ping()` 探测：

```python
def scan_robstride_motors(start_can_id, end_can_id, channel="can0"):
    found_motors = []
    for motor_can_id in range(start_can_id, end_can_id + 1):
        ctrl = Controller(channel)
        try:
            motor = ctrl.add_robstride_motor(motor_can_id, 0xfd, "rs-00")
            can_id, respond_id = motor.robstride_ping()
            found_motors.append(can_id)
            print(f"can_id={can_id:02X} respond_id={respond_id:02X}")  # respond id 不是 master id
        except Exception:
            print(f"[no respond] no this motor_can_id=0x{motor_can_id:02X}")
        finally:
            ctrl.close_bus()
            ctrl.close()
    return found_motors
```

### 1.4 切换控制模式

```python
motor.ensure_mode(Mode.MIT, timeout_ms=1000)      # 切换到 MIT 模式，超时 1000ms
motor.ensure_mode(Mode.POS_VEL, timeout_ms=1000)  # 位置速度模式
motor.ensure_mode(Mode.VEL, 1000)                 # 速度模式
motor.ensure_mode(Mode.FORCE_POS, 1000)           # 力位混控（DM）
```

### 1.5 MIT 控制

`send_mit(pos=, vel=, kp=, kd=, tau=)`：kp 是刚度、kd 是阻尼、tau 是前馈力矩。DM 示例（`4_mit_ctrl.py`，只给 tau，电机持续旋转）：

```python
from motorbridge import Controller, Mode
import time

motor_can_id = 0x01
motor_master_id = 0x11
channel = "/dev/ttyACM0"

ctrl = Controller.from_dm_serial(channel, 921600)
motor = ctrl.add_damiao_motor(motor_can_id, motor_master_id, "4340P")

ctrl.enable_all()
motor.ensure_mode(Mode.MIT, timeout_ms=1000)

motor.send_mit(
    pos=0.0,
    vel=0.0,
    kp=0.0,
    kd=0.0,
    tau=0.8   # 0.8Nm，注意只给 tau 时不要太大
)

time.sleep(5)

ctrl.disable_all()
ctrl.close_bus()
ctrl.close()
```

RS MIT 示例（`1_enable_rs.py` / `4_mit_ctrl.py`）：结构相同，`tau` 用更小的 0.3 Nm：

```python
ctrl = Controller("can0")
motor = ctrl.add_robstride_motor(0x01, 0xfd, "rs-00")

ctrl.enable_all()
motor.ensure_mode(Mode.MIT, timeout_ms=1000)

motor.send_mit(pos=0.0, vel=0.0, kp=0.0, kd=0.0, tau=0.3)  # 0.3Nm
time.sleep(3)
ctrl.disable_all()
```

## 2. 控制模式速查表

| 模式（Mode） | DM 实现 | RS 实现 | 特点与适用场景 |
|-------------|---------|---------|---------------|
| **MIT**（运控模式） | MIT 协议 | 运控模式 | 用 位置+速度+前馈力矩 控制：`电机输出 = 位置控制 + 速度控制 + 前馈力矩`（Pdes/Vdes/Kp/Kd/T_ff）。Kp=0、Kd≠0 给 Vdes 做速度控制；Kp=0、Kd=0 给 T_ff 做力矩控制。适合遥操作/学习控制等整臂动态控制 |
| **POS_VEL**（位置速度） | 位置串级模式（位置环→速度环→电流环三环串联） | 位置速度模式（PP 带梯形速度曲线规划，另有 CSP） | 参数 p_des/v_des/kp_pos/ki_pos/kp_vel/ki_vel；控制柔顺、精度较好，响应相对慢。**DM 官方推荐默认模式**；RS 的 pos_vel 接口对应 PP，且受力矩保护限幅 |
| **VEL**（速度） | 速度模式（速度环+电流环） | 速度模式（PI 速度环+力矩限制） | 参数 v_des/kp_vel/ki_vel；阻尼因子建议 2.0~10.0（推荐 4.0），过小会震荡、过大会上升时间变长。适合定速转动 |
| **FORCE_POS**（PVT 力位混控） | PVT 模式：在位置速度基础上加电流指令饱和，动态限制输出扭矩 | 无对应接口 | `send_force_pos(pos=, vlim=, ratio=)`，ratio 0=无力、1=全力。适合柔顺/接触场景（如夹取易碎物、力矩受限运动） |
| 电流模式 | — | 电流模式 | 直接把电流环暴露给用户，一般不会用到（可参考 FOC 算法） |

> 提示：DM 的位置速度/速度模式需要设置**非 0 正数阻尼因子**，否则会出现震荡与过冲（教程第 4 章）。

## 3. 10ms 控制循环示例（读取电机状态）

示例 `8_get_state.py`（DM）/ `7_get_state.py`（RS）：每 10ms 发送一次控制帧并读取电机应答帧，相当于一问一答，可同时观察 pos/vel/torque 反馈：

```python
from motorbridge import Controller, Mode
import time

motor_can_id = 0x01
motor_master_id = 0x11
channel = "/dev/ttyACM0"

ctrl = Controller.from_dm_serial(channel, 921600)
motor = ctrl.add_damiao_motor(motor_can_id, motor_master_id, "4340P")

ctrl.enable_all()
motor.ensure_mode(Mode.POS_VEL, 1000)

dt = 0.01  # 控制周期 10ms

start = time.perf_counter()
while time.perf_counter() - start < 5.0:
    now_time = time.perf_counter() - start
    motor.send_pos_vel(
        pos=2.0,    # target angle（rad）
        vlim=1.5    # max vel（rad/s）
    )
    time.sleep(dt)
    state = motor.get_state()
    if state:
        print(f"time:{now_time:.3f}")
        print(f"pos: {state.pos:.3f} rad")
        print(f"vel: {state.vel:.3f} rad/s")
        print(f"torque: {state.torq:.3f} Nm\n")
    else:
        print("no respond\n")

ctrl.disable_all()
ctrl.close_bus()
ctrl.close()
```

RS 版仅把 `Controller.from_dm_serial(channel, 921600)` 换成 `Controller("can0")`、`add_damiao_motor` 换成 `add_robstride_motor(0x01, 0xfd, "rs-00")`。注意 `get_state()` 读取的是上一帧应答；只想取状态不想让电机运动时，用 `motor.request_feedback()`（见设置零点示例）。

## 4. 设置电机零点

示例 `9_set_zero.py`（DM）/ `8_set_zero.py`（RS），核心是 `motor.set_zero_position()`，把当前位置设为零点，然后读取状态确认：

```python
from motorbridge import Controller, Mode
import time

motor_can_id = 0x01
motor_master_id = 0x11
channel = "/dev/ttyACM0"

ctrl = Controller.from_dm_serial(channel, 921600)
motor = ctrl.add_damiao_motor(motor_can_id, motor_master_id, "4340P")

try:
    motor.set_zero_position()
    print("set zero successfully")
except Exception:
    print("set zero failed")
time.sleep(1)

ctrl.close_bus()
ctrl.close()
```

> 完整示例还会用 `motor.request_feedback()` + `motor.get_state()` 循环读取 1 秒，确认设置零点后位置为 0（DM `9_set_zero.py` / RS `8_set_zero.py`）。完整零点标定流程见 `rebot-arm-motor-config`。

## 5. CAN 协议基础

### 5.1 SocketCAN

SocketCAN 是 CAN 协议在 **Linux 系统**上的一种主流实现方式：使用套接字 API 与 Linux 网络栈技术，把 CAN 设备驱动实现为**网络接口**（如 `can0`），易用、兼容性好。RS 电机即通过 SocketCAN 通信，`Controller("can0")` 底层就是在该接口上收发 CAN 帧。RS 配置接口（套件为 PCAN-USB，通常直接出现 can0/can1）：

```bash
sudo modprobe peak_usb
ip -br link

# 设置 bitrate 并启动接口
sudo ip link set can0 down 2>/dev/null
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
```

> 提示：可以把 CAN 总线理解成"多人群聊"——所有设备（主控制器、电机等）共用一条总线，靠 CAN ID 区分消息。如需观察原始报文，可用 can-utils 的 `candump can0` 抓包（can-utils 安装见 `rebot-arm-environment-setup`）。详细用法见 SocketCAN 内核文档。

### 5.2 DM 标准数据帧（11 字节）与 RS 扩展数据帧（13 字节）

| | DM 标准数据帧（共 11 字节） | RS 扩展数据帧（共 13 字节） |
|---|---------------------------|---------------------------|
| **字节 1：帧信息** | FF=0（标准帧）、RTR=0（数据帧）、DLC=数据长度 | FF=1（扩展帧）、RTR=0（数据帧）、DLC=数据长度 |
| **帧 ID** | 字节 2~3，**11 位** ID（ID10~ID0），范围 `000~7FF` | 字节 2~5，**29 位** ID（ID28~ID0），范围 `00000000~1FFFFFFF` |
| **数据段** | 字节 4~11，DATA1~DATA8（8 字节） | 字节 6~13，DATA1~DATA8（8 字节） |

- 一条 CAN 帧在链路上依次为：**SOF → ID → 控制字段 → DLC → Data → CRC → ACK → EOF**；CRC 校验传输错误，ACK 表示接收方确认收到。**ID 数值越小，优先级越高**（`DLC=8` 表示 8 字节数据）。
- 每个字节代表什么（目标位置、速度、力矩…）由电机厂商的 CAN 通信协议定义，需对照数据手册。

### 5.3 CAN ID 与 Master ID 的作用

- **CAN ID（can_id）**：报文的"消息编号/身份"，总线上靠它区分发给哪个电机。reBot 上约定 `can_id` = 对应关节编号（1~7）。
- **Master ID（master_id）**：控制端（主机）标识，用于应答/校验。DM：`master_id = 0x10 + can_id`（电机 1 → `0x11`、电机 7 → `0x17`）；RS：**固定 `0xfd`**。
- 电机内保存的 can_id/master_id 必须与代码一致，否则扫描/通信失败（DM 扫描脚本即通过读取寄存器 7（master id）、8（can id）核对）。

## 6. 常见问题

| 现象 | 原因与处理 |
|------|-----------|
| **扫描不到电机** | ① can_id/master_id 与电机实际不符 → 重新扫描核对；② 接线问题（信号线未插紧、DM 电机 1↔2 之间 3 芯线束漏接）→ 见 `rebot-arm-environment-setup`；③ 电机未上电/电源未开；④ RS 的 can0 未 up 或 bitrate 不对 → `ip link set can0 up` |
| **模式切换超时**（ensure_mode 报 timeout） | 电机未使能、ID 不对或通信异常 → 先 `ctrl.enable_all()`，再确认扫描在线、接线与供电正常 |
| **使能后立即异响/剧烈抖动** | 参数问题：kp/kd 不当、位置控制 kd=0、tau 过大 → **立即断电**（高频正反力矩会损坏电机），再检查参数，疑难转 `rebot-arm-troubleshooting` |
| **电机一直加速不停** | MIT 只给 tau 且过大，电机越转越快以追求期望力矩 → 断电，改用小 tau，或带 kp/kd 做位置控制 |
| **RS 位置模式表现异常** | 可能未初始化 B601-RS 默认参数模板（loc_kp、vel_max、spd_kp 等）→ 先按 `rebot-arm-motor-config` 完成参数初始化与零点标定 |

## 参考

- 官方 Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- motorbridge：<https://github.com/motorbridge/motorbridge> ｜ Studio：<https://motorbridge.github.io/motorbridge-studio/>
- 电机示例代码：<https://github.com/hopcan/motorbridge_ctrl.git>
- SocketCAN 内核文档：<https://docs.linuxkernel.org.cn/networking/can.html>
- 配套教程：本仓库同目录《Seeed具身智能入门8个阶段40章节》第 4 章（关节执行器与运控模式）、第 5 章（CAN 总线与电机通信）、第 7 章（Python 代码控制 DM / RS 电机）
- 相关技能：`rebot-arm-safety`（安全）｜ `rebot-arm-environment-setup`（环境）｜ `rebot-arm-motor-config`（写 ID/标定零点）｜ `rebot-arm-troubleshooting`（排错）
