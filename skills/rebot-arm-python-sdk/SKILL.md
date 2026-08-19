---
name: rebot-arm-python-sdk
description: 使用 reBot Arm 的 Python SDK（reBotArm_control_py / rebotArm_ctrl 仓库）控制整臂：连接/断开（上下文管理）、设置零点、关节运动 move_to_joint_positions、读取电机状态（位置/速度/力矩）、修改 YAML 控制参数与切换模式。当用户需要编写脚本让机械臂按指定关节角度运动、或读取关节状态时使用本技能。
---

# reBot Arm Python SDK 整臂控制

## 简介

本技能使用 Python SDK（`reBotArm_control_py` / `rebotArm_ctrl` 示例仓库）对 reBot Arm 做**整臂级控制**：连接/断开（上下文管理自动收尾）、按关节角度运动（`move_to_joint_positions`）、读取电机状态（`motor_state`）、设置零点（`set_zero_position`），以及在 `config` YAML 中修改控制参数、切换 MIT / POS_VEL 模式。适用于 **B601-DM** 与 **B601-RS** 两个型号。

> 📌 本技能所有命令与代码均来自官方教程第 8 章及示例仓库；**完整可运行的示例（含 import 与主函数）以克隆仓库 `rebotArm_ctrl/example/rebotDM`、`example/rebotRS` 中的示例文件为准**，教程正文只给出核心代码片段，请勿凭空补写导入语句。

## 何时使用

- 用户想**编写 Python 脚本**让机械臂运动到指定关节角度（如 `[0,0,0,0.5,0.5,0,-1]`）
- 用户想**读取**各关节的位置 / 速度 / 力矩状态
- 用户想用 Python 给整臂**设置零点**
- 用户想修改关节控制参数或**切换 MIT / POS_VEL 控制模式**（改 YAML 配置）

## 前置条件

- 已确认型号：**DM**（串口 `/dev/ttyACM0` + 24V）或 **RS**（SocketCAN `can0` + 48V），分支命令不同
- 环境已装好：`pyyaml`、`motorbridge`（见 `rebot-arm-environment-setup`；motorbridge 需要 Python ≥ 3.10，推荐 conda 环境 `python=3.12`）
- 通信接口已配置：
  - DM：`ls /dev/ttyACM*` 能看到端口，且已赋权限（见下文 §3.1）
  - RS：`ip -br link` 能看到 `can0` 且已 `up`
- 已先读 **`rebot-arm-safety`**（本节属真机运动操作）

## 安全要点

> ⚠️ 运动前先完成 `rebot-arm-safety` 的检查清单：**工作区无人、无障碍物**；机械臂固定牢靠；手边有电源开关（失控立即断电）。

1. **先低速小角度测试**：新参数 / 新任务第一次运行，先给小的关节角度、有人值守试跑，确认方向与范围正常后再继续。
2. **Ctrl+C 退出要等归位**：教程明确——"使用 ctrl c 退出程序后**等待几秒，不要一直输入 ctrl c**，需要等待机械臂**自动归位后失能**"。反复连按 Ctrl+C 会打断安全收尾，导致机械臂停在不安全姿态。
3. 断电插拔线束、带电操作等更多规则见 `rebot-arm-safety`。

## 1. 安装依赖并拉取示例

```bash
python3 -m pip install pyyaml motorbridge
git clone https://github.com/hopcan/rebotArm_ctrl.git
```

克隆后目录结构（教程说明）：

| 内容 | 路径 |
|------|------|
| DM 控制示例 | `rebotArm_ctrl/example/rebotDM`（如 `1_rebotDM_connect.py`、`2_rebotDM_set_zero.py`、`3_rebotDM_move_joint.py`） |
| RS 控制示例 | `rebotArm_ctrl/example/rebotRS`（如 `1_rebotRS_connect.py`、`2_rebotRS_set_zero.py`、`3_rebotRS_move_joint.py`） |
| 配置文件 | `rebotArm_ctrl/config/rebotDM.yaml`（DM）与 `rebotArm_ctrl/config/rebotRS.yaml`（RS） |

## 2. 修改参数和切换模式（config YAML）

控制模式与参数都在 `rebotArm_ctrl/config` 下的 YAML 中修改。教程举例（DM，`Shoulder Pan` 关节）：

```yaml
- name: Shoulder Pan
    motor_can_id: 1   
    MIT:
        kp: 10.0
        kd: 1.0
    POS_VEL:
        vel_kp: 0.0125
        vel_ki: 0.004
        pos_kp: 150.0
        pos_ki: 0.5
        vlim: 5.0
    posmax: 2.6
    posmin: -2.6
    use_mode: POS_VEL
```

字段说明：

| 字段 | 含义 |
|------|------|
| `name` | 关节名（如 Shoulder Pan） |
| `motor_can_id` | 该关节电机的 CAN ID |
| `MIT.kp / MIT.kd` | MIT 模式的刚度 / 阻尼参数 |
| `POS_VEL.vel_kp / vel_ki` | POS_VEL 模式速度环参数 |
| `POS_VEL.pos_kp / pos_ki` | POS_VEL 模式位置环参数 |
| `POS_VEL.vlim` | 速度限制 |
| `posmax / posmin` | 关节位置限位（弧度） |
| `use_mode` | **切换控制模式**：可改成 `MIT` 或 `POS_VEL` |

- 教程明确**推荐 rebot DM 使用 `POS_VEL` 模式**；RS 模式以 `config/rebotRS.yaml` 默认值为准。
- MIT 的 `kp`/`kd`、POS_VEL 的 `vel_kp`/`vel_ki`/`pos_kp`/`pos_ki`/`vlim` 都是对应模式的参数，**根据机械臂的实际控制效果调整**。

> ⚠️ 教程提示：Python SDK 各关节控制器的参数需要按实际使用需求调节，**目前的参数只能满足精度不高的场景**。改参数后务必先低速小角度验证（见"安全要点"）。

## 3. 连接 / 断开机械臂（上下文管理）

### 3.1 先创建总线控制器

**注意（教程原文要点）**：1、检查端口是否存在；2、端口权限要在程序运行前赋予。

**DM（串口）：**

```python
channel = "/dev/ttyACM0"  
ctrl = Controller.from_dm_serial(channel, 921600)
```

**RS（PCAN / SocketCAN）：**

```python
channel = "can0"  
ctrl = Controller(channel)
```

端口检查与权限（DM）：

```bash
ls /dev/ttyACM*                  # 确认端口存在，通常为 /dev/ttyACM0
sudo chmod 666 /dev/ttyACM*      # 程序运行前赋予权限；每次重启后需重新设置
```

### 3.2 通过上下文管理器连接 / 断开

教程核心用法（`with reBotArm_handle(ctrl, "<型号>") as handle:`）：

```python
# DM
with reBotArm_handle(ctrl, "rebotDM") as handle:
    # ... 在这里控制机械臂

# RS
with reBotArm_handle(ctrl, "rebotRS") as handle:
    # ... 在这里控制机械臂
```

### 3.3 上下文管理器做了什么（教程核心实现）

| 阶段 | 行为 |
|------|------|
| `__enter__` | 调用 `connect` 自动连接机械臂；连接失败会输出对应日志 |
| `connect` 过程 | 添加电机到总线控制器 → 上电检查电机通信 → 校验电机 CAN ID 和 master ID 是否有效 → 校验配置文件是否有效 → 将电机控制模式改为目标控制模式 |
| `__exit__` | 调用 `disconnect` 自动断开：**先恢复初始状态，然后失能** |
| 替代方式 | 不想用上下文管理时，可直接调用 `connect` 函数和 `disconnect` 函数 |

## 4. 控制机械臂运动（move_to_joint_positions）

教程示例（`example/rebotDM/3_rebotDM_move_joint.py` 或 `example/rebotRS/3_rebotRS_move_joint.py`）：

```python
while True:
    handle.move_to_joint_positions([0,0,0,0.5,0.5,0, -1])
    for motor_id in list(range(1,8)):
        print(f"motor {motor_id}")
        print(f"pos: {handle.motor_state[motor_id].pos:.3f} rad")
        print(f"vel: {handle.motor_state[motor_id].vel:.3f} rad/s")
        print(f"torque: {handle.motor_state[motor_id].torq:.3f} Nm\n")
    time.sleep(0.002)
```

要点：

- `move_to_joint_positions([...])` 传入 **7 个关节的目标角度，单位弧度**（如 `[0,0,0,0.5,0.5,0,-1]`）。
- 运动前务必确认目标角度在配置的 `posmin / posmax` 限位内；第一次运行先小角度测试。

## 5. 读取电机状态（motor_state）

`handle.motor_state` 是一个**字典，包含所有关节的状态信息**（教程原文），按 `motor_id` 读取：

| 字段 | 含义 | 单位 |
|------|------|------|
| `handle.motor_state[motor_id].pos` | 关节位置 | rad（弧度） |
| `handle.motor_state[motor_id].vel` | 关节速度 | rad/s |
| `handle.motor_state[motor_id].torq` | 关节力矩 | Nm |

`motor_id` 取 `1..7`（教程循环 `list(range(1,8))`）。示例中的 `:.3f` 表示保留 3 位小数。

## 6. 设置零点（set_zero_position）

教程示例（`example/rebotDM/2_rebotDM_set_zero.py` 或 `example/rebotRS/2_rebotRS_set_zero.py`）：

```python
# RS
with reBotArm_handle(ctrl, "rebotRS") as handle:
    handle.set_zero_position()

# DM
with reBotArm_handle(ctrl, "rebotDM") as handle:
    handle.set_zero_position()
```

通过机械臂控制类调用 `set_zero_position` 即可给机械臂**所有关节设置零点**。

> ⚠️ 设置零点前把机械臂摆到安全姿态（物理上接近零位），避免把当前姿态当作零位；标定细节见 `rebot-arm-motor-config`。

## 常见问题

| 现象 | 原因与处理 |
|------|-----------|
| 连接报错 / 找不到端口 | DM：检查 `ls /dev/ttyACM*` 端口是否存在；程序运行前先 `sudo chmod 666 /dev/ttyACM*`（重启后需重新设置）。RS：确认 `can0` 已 `up`（`ip -br link`）。详见 `rebot-arm-environment-setup` |
| Ctrl+C 后机械臂未归位 / 姿态异常 | 教程明确要求：退出程序后**等待几秒，不要一直输入 Ctrl+C**，等机械臂**自动归位后失能**；反复连按会打断 `disconnect` 的安全收尾 |
| 运动精度不足 | 教程说明："目前参数只能满足精度不高的场景"。需要根据实际使用需求调节各关节控制器的参数（§2 中的 kp/kd、vel_kp/vel_ki/pos_kp/pos_ki/vlim），逐步微调并低速验证 |
| 切换 `use_mode` 后运动异常 | 确认改的是对应关节的 YAML 且 `use_mode` 值正确（`MIT` 或 `POS_VEL`）；检查该模式下参数是否合理（MIT 用 kp/kd，POS_VEL 用 vel_*/pos_*/vlim）；先低速小角度测试；仍异常请断电重启并检查配置 |
| 运动时抖动 / 撞限位 | 立即断电（见 `rebot-arm-safety` 紧急处理）；检查目标角度是否超出 `posmin/posmax`、参数是否过激 |
| 上下文管理器内代码报错 | `__exit__` 仍会执行 `disconnect`（恢复初始状态并失能），确认退出后机械臂已归位再排查代码逻辑 |

## 参考

- 官方 Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- 官方底层库 reBotArm_control_py（含 `config/rebotarm_dm.yaml` 与 `rebotarm_rs.yaml`）：<https://github.com/Seeed-Projects/reBotArm_control_py>
- 教程示例仓库 rebotArm_ctrl（`example/rebotDM`、`example/rebotRS`）：<https://github.com/hopcan/rebotArm_ctrl>
- MotorBridge（电机控制中间件）：<https://github.com/motorbridge/motorbridge>
- 配套教程：本仓库同目录《Seeed具身智能入门8个阶段40章节》**第 8 章"使用 Python SDK 控制 reBot Arm"**、第 7 章（Miniforge 环境与 motorbridge 安装）
- 相关技能：`rebot-arm-safety`（必读）｜ `rebot-arm-environment-setup`（环境与接口）｜ `rebot-arm-motor-config`（电机 ID / 零点标定）｜ `rebot-arm-motor-control`（MIT/POS_VEL 底层控制）｜ `rebot-arm-troubleshooting`（排错）
