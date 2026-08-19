---
name: rebot-arm-motor-config
description: 配置 reBot Arm（B601-DM / B601-RS）的关节电机：初始化新机械臂（写入/校验电机 CAN ID 与 Master ID）、零点标定、MotorBridge Studio Web 界面操作、RS 电机参数模板初始化。当用户需要初始化新机械臂、写电机 ID、设零点、电机失联、或电机乱动/参数异常时使用本技能。
---

# reBot Arm 电机 ID 配置与零点标定（MotorBridge 流程）

## 简介

本技能完成 reBot Arm 关节电机的**初始化配置**：为 7 个关节电机写入/校验 CAN ID 与 Master ID、完成零点标定，并按型号完成后续准备（DM 用 DM_Tools / motorbridge Python，RS 用 MotorBridge Studio Web 界面 + 参数模板初始化）。电机 ID 错误会导致电机失联或"电机乱动/参数异常"，本技能也是这类问题的修复入口。

> 分工标记：🤖 AI 执行（终端可自动化）｜ 👤 用户执行（GUI/网页/按键/插线/物理操作）｜ 🔀 人机协作（sudo 需用户密码或需用户确认）

## 何时使用

- 新机械臂初始化（组装后首次写入电机 ID + 设零点）
- 电机失联 / 扫描不到某几个关节
- 需要重新设零点（更换装配、标定丢失、首次控制前）
- 电机启动后乱动、异响、位置/速度响应异常（可能需要 RS 参数模板初始化或恢复 DM 出厂参数）

## 前置条件

- 已完成 `rebot-arm-environment-setup`：
  - conda 环境 + `motorbridge` 已安装（`conda activate rebot` 后 `motorbridge --version` 可运行）
  - **DM**：串口已授权（`sudo chmod 666 /dev/ttyACM*`，端口通常为 `/dev/ttyACM0`）
  - **RS**：`can0` 已配置（`sudo ip link set can0 type can bitrate 1000000` 并 `up`；macOS/Windows 见环境技能）
- 已确认型号：**DM**（24V，串口 `/dev/ttyACM0`，达妙电机）或 **RS**（48V，SocketCAN `can0`，灵足电机），两型号流程不同
- 硬件：2 个 **≥3 英寸工具夹具**固定机械臂底座、正规品牌 XT30 输出电源（DM 24V / RS 48V）、USB-CAN 转接板（DM）或 PCAN-USB（RS）
- 已读 `rebot-arm-safety`（本操作涉及带电调试与电机运动）

> 状态记忆：写 ID/零点标定完成后更新 memory/local-machine-env.md（见 AGENTS.md 第 3 节）。

## 👤 0. 安全要点

> ⚠️ 写 ID / 切换电机线缆前，先完成 `rebot-arm-safety` 检查清单：
> - **断电插拔**：切换 3 芯线连接（电机 ↔ 转接板）前，必须确保当前电机**失能且电源断电**，**禁止热插拔**，否则可能造成电机参数异常甚至损坏；
> - **调试距离 ≥1 m**：调试/运行期间保持至少 1 米安全距离观察；
> - **工具夹具固定**：使用 ≥3 英寸工具夹具将机械臂底座固定牢靠，防止运动时跌落；
> - **防失控**：设置合理程序参数与急停；出现抖动、异响、撞限位等异常**立即断电**。

## 🔀 1. DM 流程（B601-DM）

### 🔀 1.1 电机 ID 对照表

reBot Arm 每个关节电机的 CAN ID 与 Master ID 按下表设置，**Master ID = 0x10 + CAN ID**（如 CAN ID 0x01 → Master ID 0x11）：

| 电机 | CAN ID | Master ID | 电机 | CAN ID | Master ID |
|------|--------|-----------|------|--------|-----------|
| Motor 1 | 0x01 | 0x11 | Motor 5 | 0x05 | 0x15 |
| Motor 2 | 0x02 | 0x12 | Motor 6 | 0x06 | 0x16 |
| Motor 3 | 0x03 | 0x13 | Motor 7 | 0x07 | 0x17 |
| Motor 4 | 0x04 | 0x14 | | | |

> 注意：组装时 **1 号电机和 2 号电机之间的 3 芯线束必须连接**（易漏）。

### 👤 1.2 方式一：DM_Tools（Windows 官方上位机）

官方推荐使用 DM_Tools 逐个电机写入 ID（Windows 独占，下载见官方 Wiki 软件链接）：

1. 打开 DM_Tools 主机软件，选择对应 USB COM 口，波特率 **921600**，连接成功后 Serial 界面会打印信息。
2. 用 **3 芯线**将 Motor 1 连接到 USB-CAN 转接板（一个电机一个电机地配）。
3. 进入**参数设置界面**：点击 `Read Parameters` 读取当前参数 → 设置 **CAN ID = 0x01、Master ID = 0x11** → 点击 `Write Parameters` 保存。
4. 切换到**调试界面**，确认 ID 正确后点击 `Enable` 使能测试，电机指示灯变为**绿色常亮**即成功；测试完记得点击 `Disable` 退出使能状态。
5. **断电**后换下一个电机（Motor 2→0x02/0x12，依次类推），重复步骤 2-4。

> ⚠️ **注意事项**：DM_Tools 调试界面走 CAN 总线通信，**不要点击 CAN ID 旁的 `Read` / `Set` 按钮**——点击 `Set` 会把 CANBUS 上连接的所有电机 CAN ID 统一改掉（官方 FAQ，见常见问题 2）。

### 🤖 1.3 方式二：motorbridge Python 扫描 / 写 ID（跨平台）

示例代码来自配套教程第 7 章（`motorbridge_ctrl/dm_motor_ctrl`），先拉取并激活环境：

```bash
git clone https://github.com/hopcan/motorbridge_ctrl.git
conda activate rebot
cd motorbridge_ctrl/dm_motor_ctrl
```

**① 扫描电机 ID**（`2_scan_DMmotor.py`，扫描 1-7 的 CAN ID 及其 Master ID，用于校验）：

```python
from motorbridge import Controller

def scan_damiao_motors(start_can_id, end_can_id, channel="/dev/ttyACM0"):
    found_motors = []
    print(f"start scanning {channel}, canID: {start_can_id} - {end_can_id}")
    for motor_can_id in range(start_can_id, end_can_id + 1):
        ctrl = Controller.from_dm_serial(channel, 921600)
        temp_motor_master_id = 0x11 + motor_can_id
        try:
            motor = ctrl.add_damiao_motor(motor_can_id, temp_motor_master_id, "4340P")
            try:
                # 读取寄存器：8=can id，7=master id
                esc_id = motor.get_register_u32(8, timeout_ms=100)
                master_id = motor.get_register_u32(7, timeout_ms=100)
                print(f"[find] motor_can_id=0x{esc_id:02X} motor_master_id=0x{master_id:02X}")
                found_motors.append(esc_id)
            except Exception:
                print(f"[no respond] motor_can_id=0x{motor_can_id:02X}")
            finally:
                motor.close()
        except Exception as e:
            print(f"[error] motor_can_id=0x{motor_can_id:02X}: {e}")
        finally:
            ctrl.close_bus()
            ctrl.close()
    print(f"\nfinish find {len(found_motors)} motor")
    return found_motors

if __name__ == "__main__":
    motors = scan_damiao_motors(start_can_id=1, end_can_id=7, channel="/dev/ttyACM0")
    for can_id in motors:
        print(f"  can_id=0x{can_id:02X}")
```

**② 设置 CAN ID 与 Master ID**（`3_set_id.py`，把旧 ID 的电机改写为新 ID 并保存参数）：

```python
from motorbridge import Controller, RID_MST_ID, RID_ESC_ID
import time

def set_DMmotor_ID(old_can_id, new_can_id, new_master_id, channel="/dev/ttyACM0"):
    ctrl = Controller.from_dm_serial(channel, 921600)
    temp_motor_master_id = 0x10 + old_can_id
    motor = ctrl.add_damiao_motor(old_can_id, temp_motor_master_id, "4340P")
    try:
        motor.write_register_u32(RID_MST_ID, new_master_id)   # 写 Master ID
    except Exception:
        pass
    try:
        motor.write_register_u32(RID_ESC_ID, new_can_id)      # 写 CAN ID
    except Exception:
        pass
    new_motor = ctrl.add_damiao_motor(new_can_id, new_master_id, "4340P")
    new_motor.store_parameters()                               # 保存参数（必须）
    print("change ID and save")
    time.sleep(1)
    ctrl.close_bus()
    ctrl.close()

if __name__ == "__main__":
    set_DMmotor_ID(old_can_id=0x06, new_can_id=0x01, new_master_id=0x11, channel="/dev/ttyACM0")
```

> 提示：逐个电机执行，`new_can_id`/`new_master_id` 按 1.1 对照表填写；写完后用 ① 扫描校验。

### 🔀 1.4 DM 零点标定

零点标定前，**先把机械臂手动摆到官方零位姿态**（见官方 Wiki / 教程第 3 章零位姿态图；**DM 零位姿态下夹爪要完全闭合**），再对每个关节设零。

**方式一（Web 界面）**：打开 <https://motorbridge.github.io/motorbridge-studio/> → 帮助中复制命令启动 gateway（Linux 示例）：

```bash
motorbridge-gateway -- \
  --bind 127.0.0.1:9002 --vendor damiao --transport dm-serial \
  --serial-port /dev/ttyACM0 --serial-baud 921600 \
  --dt-ms 20
```

回到页面 → 点击连接（右上角出现绿色"已连接"）→ 选择 DM 电机并扫描 → 点击**使能（Enable）**按钮，电机灯变绿后，再点击 **Zero+Save** 即可将当前位置设置为零点。

**方式二（Python，`9_set_zero.py`）**：

```python
from motorbridge import Controller
import time

motor_can_id = 0x01
motor_master_id = 0x11
channel = "/dev/ttyACM0"

ctrl = Controller.from_dm_serial(channel, 921600)
motor = ctrl.add_damiao_motor(motor_can_id, motor_master_id, "4340P")

try:
    motor.set_zero_position()      # 将当前位置设为零点
    print("set zero successfully")
except Exception:
    print("set zero failed")
time.sleep(1)

# 回读校验：请求反馈，确认角度已归零
motor.request_feedback()
time.sleep(0.05)
state = motor.get_state()
if state:
    print(f"pos: {state.pos:.3f} rad")

ctrl.close_bus()
ctrl.close()
```

## 🔀 2. RS 流程（B601-RS）

### 🔀 2.1 确认 can0 并启动 gateway

```bash
# can0 已按环境技能配置好（bitrate 1000000），确认：
sudo modprobe peak_usb
ip -br link

# 启动 Web Studio 后端（RS 走 socketcan）
motorbridge-gateway --bind 127.0.0.1:9002
```

> macOS 用户：需要先配置 PCBUSB 与 `DYLD_FALLBACK_LIBRARY_PATH`，否则连接报 `load PCBUSB failed`：

```bash
DYLD_FALLBACK_LIBRARY_PATH=/usr/local/lib motorbridge-gateway --bind 127.0.0.1:9002
```

### 👤 2.2 Web 界面：扫描与零点标定

1. 浏览器打开 <https://motorbridge.github.io/motorbridge-studio/>，点击连接（右上角绿色"已连接"）。
2. **Robot Model 选择 `rebot-arm-robstride`**，选择 RS 电机并点击扫描 Robstride 电机，**确认 1-7 关节全部在线**。
3. 零点标定：先把机械臂摆到官方零位姿态（参考官方 Wiki 零位图），点击**使能（Enable）**按钮后，再点击 **Zero+Save** 即可将当前位置设置为零点。

### 👤 2.3 RS 电机参数初始化（三步，首次使用必做）

B601-RS 大部分示例运行在 **MIT 模式**；`pos_vel` 位置模式直接使用位置环增益 `loc_kp`、最大速度 `vel_max`，运动行为还受速度环增益 `spd_kp` 与加速度 `acc_rad` 影响。**若未初始化推荐参数或各关节参数不一致，位置模式会出现响应、速度、加减速异常**。在 Robot Model 选择 `rebot-arm-robstride`、扫描确认 1-7 在线、完成零点标定后，按顺序执行：

1. **`Read Parameters`**：读取所有在线关节当前保存的参数。**此操作只读，不会修改电机**。等待页面提示"控制参数读取成功"，保留当前值为记录。
2. **`Apply Default Template`**：确认页面提示"reBot Arm RobStride 默认参数模板已应用到 1-7 关节"。**此操作仅把推荐值载入页面，尚未写入电机**。
3. **`Write Parameters`**：确认机械臂安全支撑、附近无人无障碍后，在对话框中确认写入。**写入过程中不要断电、不要插拔电机线缆**。

> 写入完成后，MotorBridge Studio **自动回读参数校验**；页面提示"写入后回读校验匹配"即初始化成功。

### 🔀 2.4 RS 写电机 ID

- Web 界面：设置电机 ID 时，**`can_id` 设置为对应关节的编号，`master_id` 固定**（灵足电机 master_id 固定为 `0xfd`，见教程示例）。
- Python（`3_set_id.py`）：

```python
from motorbridge import Controller
import time

def set_RSmotor_ID(old_can_id, new_can_id, channel="can0"):
    ctrl = Controller(channel)
    motor = ctrl.add_robstride_motor(old_can_id, 0xfd, "rs-00")   # master_id 固定 0xfd
    try:
        motor.robstride_set_device_id(new_can_id)
        print(f"change to new id: {new_can_id}")
    except Exception:
        print("set id failed")
    time.sleep(1)
    ctrl.close_bus()
    ctrl.close()

if __name__ == "__main__":
    set_RSmotor_ID(old_can_id=0x01, new_can_id=0x01, channel="can0")
```

> ⚠️ robstride 写 ID 时可能报 `store_parameters failed` 超时错误，但**实际已写入**；遇到该报错先不要重试，用下面的扫描命令验证。

RS Python 设零点（`8_set_zero.py`，与 DM 同思路）：

```python
from motorbridge import Controller
import time

motor_can_id = 0x01
motor_master_id = 0xfd
channel = "can0"

ctrl = Controller(channel)
motor = ctrl.add_robstride_motor(motor_can_id, motor_master_id, "rs-00")
try:
    motor.set_zero_position()      # 将当前位置设为零点
    print("set zero successfully")
except Exception:
    print("set zero failed")
time.sleep(1)
ctrl.close_bus()
ctrl.close()
```

## 🤖 3. 写完后验证（扫描确认所有电机在线）

**DM**（Python 扫描 0x01-0x07，见 1.3 ①，期望 7 个电机全部 `[find]`，且寄存器 8/7 与对照表一致）：

```bash
python 2_scan_DMmotor.py
```

**RS**（CLI 扫描 1-7）：

```bash
motorbridge-cli scan --vendor robstride --channel can0 --start-id 1 --end-id 7 --timeout-ms 300
```

期望输出 1-7 全部在线。若有缺失，检查对应关节的 ID 是否写对（或接线/断电插拔后重扫）。

## ✅ 验证与预期结果

| 运行 | 期望结果 | 失败处理 |
|------|----------|----------|
| DM：`python 2_scan_DMmotor.py`（扫描 0x01-0x07） | 7 个电机全部 `[find]`，寄存器 8/7 与 1.1 对照表一致 | 检查对应关节 ID/接线，断电插拔后重扫 |
| RS：`motorbridge-cli scan --vendor robstride --channel can0 --start-id 1 --end-id 7 --timeout-ms 300` | 1-7 全部在线 | 报超时先扫描验证是否已写入；缺失关节检查 ID/接线后重扫 |
| RS 参数初始化（2.3 三步 Write 后自动回读） | 页面提示"写入后回读校验匹配" | 位置模式响应/速度异常时重做 2.3 三步 |

## 常见问题

1. **电机启动后异响（尖锐噪声）**：通常是写 ID 时意外触发了参数校准，覆盖了出厂预设参数（如转动惯量）。用官方 **DM_Tools_v1.8.0.1.exe**（仅 Windows）：从**同型号完好电机**导出完整参数 → 导入故障电机 → 更新对应 CAN ID → 保存写入参数 → 再重新零点标定。见官方 Wiki FAQ。
2. **所有电机 CAN ID 相同**：DM_Tools 调试界面点击了 CAN ID 旁的 `Read`/`Set`，把 CANBUS 上所有电机 ID 统一了。扫描确认后，按 1.1 对照表逐个重写。
3. **macOS 遥操作帧率低**：旧版 WCH CH34x 驱动导致；macOS 10.14+ 自带 `AppleUSBCHC0M` 驱动，卸载旧驱动切换即可。
4. **RS 位置模式响应/速度异常**：各关节参数未初始化或不一致，回到 2.3 完成 Read → Apply Default Template → Write 三步。
5. **robstride 写 ID 报超时**：见 2.4 提示，用 `motorbridge-cli scan` 验证是否实际已写入。

## 参考

- 官方 Wiki（Getting Started）：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- MotorBridge：<https://github.com/motorbridge/motorbridge> ｜ Studio Web UI：<https://motorbridge.github.io/motorbridge-studio/>
- 配套教程：本地参考教程《Seeed具身智能入门8个阶段40章节》（未随本仓库发布）第 6 章（组装供电上电）、第 7 章（MotorBridge 电机控制库：Web 端控制、DM/RS 扫描与写 ID、设零点示例）
- 前置技能：`rebot-arm-environment-setup`（环境/接线/上电）｜ `rebot-arm-safety`（安全规范）
