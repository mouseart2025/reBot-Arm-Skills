# 参考：ROS2 故障码与状态解读（fault-codes）

> 用途：帮助 AI 在 ROS2 场景下**定位机械臂异常**。本文件说明故障信息从哪来、如何读取、如何定位；**具体错误码数值以仓库源码为准**（下方给出读取方法，不臆造码表）。

## 1. 故障信息从哪里来

`reBotArmController` 节点持续在话题 `/rebotarm/arm_status`（`rebotarm_msgs/msg/ArmStatus`）发布整体状态，包含：

| 字段 | 类型 | 含义 |
|------|------|------|
| `state_machine` | string | 状态机：`IDLE` / `TRAJ_RUNNING` / `LOWLEVEL_STREAMING` / `GRAVITY_COMP` |
| `per_joint_status_code` | uint8[] | **每个关节电机**的状态码，**非零值表示该电机异常**（来自底层 SDK `motor.get_state().status_code`） |
| `error_codes` | string[] | 控制器级别的错误码字符串列表 |
| `enabled` / `control_loop_active` | bool | 使能状态与控制循环状态 |

## 2. 如何读取

```bash
# 查看完整状态（含故障码）
ros2 topic echo /rebotarm/arm_status --once

# 持续监控状态机
ros2 topic echo /rebotarm/arm_status --field state_machine

# 单关节电机状态（position/velocity/torque）
ros2 topic echo /rebotarm/joints/joint1/state --once

# 底层电机状态码（Python SDK 方式）
state = motor.get_state()
print(state.status_code)   # 非零 = 异常
```

## 3. 如何定位（诊断流程）

```
1. ros2 topic echo /rebotarm/arm_status --once
        │
        ▼
2. 看 state_machine：是否在期望状态（IDLE/TRAJ_RUNNING...）？
   ├─ 不在 → 状态机仲裁拒绝命令（如重力补偿期间发轨迹命令被拒）→ 先回到 IDLE
        │
        ▼
3. 看 per_joint_status_code：哪个关节非零 → 该电机异常
        │
        ▼
4. 看 error_codes：控制器级错误（字符串）
        │
        ▼
5. 结合现象定位（见 troubleshooting 诊断树）：
   抖动/撞限位 → 立即断电；轨迹执行失败 → 首点偏差 <0.10 rad；使能失败 → 通信/参数
```

## 4. 已知的"状态 ≠ 错误"情况

- `state_machine=TRAJ_RUNNING` 时下发低层 cmd 话题默认被**拒绝**（`cmd_arbitration:=reject`）——这不是故障，是仲裁保护；需要抢占传 `cmd_arbitration:=preempt`
- `disable` 只停止控制循环，电机仍带电；异常场景软件急停后**再断电**

## 5. 获取权威码表（以源码为准）

- 底层状态码：`reBotArm_control_py`（<https://github.com/Seeed-Projects/reBotArm_control_py>）中电机驱动对 `status_code` 的解析
- 控制器错误码：`rebotarm_ros2` 工作空间 `src/rebotarmcontroller/`（`rebotarm_msgs` 消息定义 + controller 源码）
- 需要精确码值/含义时，引导用户按上述路径查源码，或联系 Seeed 官方支持

## 相关

- `skills/rebot-arm-ros2/SKILL.md`（接口与状态机）
- `skills/rebot-arm-troubleshooting/SKILL.md`（诊断树）
