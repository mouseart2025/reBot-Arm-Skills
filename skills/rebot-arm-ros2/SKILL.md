---
name: rebot-arm-ros2
description: 在 ROS2 中使用 reBot Arm（B601-DM / B601-RS）：构建 rebotarm_ros2 工作空间（RS 为 ReBot_Arm_web_RS、DM 为 Borot-Arm_Mujoco/reBotArmController_ROS2）、启动 bringup（launch + RViz）、Topic/Service/Action 三种控制接口（enable/safe_home/disable/move_to_pose_ik/gripper/set、move_to_pose/follow_joint_trajectory）、状态机监控与故障码排查、安全停车。当用户需要"用 ROS2 控制机械臂"、写 ROS2 节点或排查 ROS2 接口问题时使用本技能。
---

# reBot Arm ROS2 集成与控制

## 简介

本技能把 reBot Arm（B601-DM / B601-RS）封装进标准 ROS2 生态：构建 `rebotarm_ros2` 工作空间、一条命令启动 bringup（驱动节点 + RViz 可视化），并通过 **Topic / Service / Action** 三种标准接口控制机械臂，最后给出安全停车、状态机监控与故障码排查方法。所有命令来自官方教程第 31/32/33 章，DM 与 RS 分支请严格按型号执行。

> 分工标记：🤖 AI 执行（终端可自动化）｜ 👤 用户执行（GUI/网页/按键/插线/物理操作）｜ 🔀 人机协作（sudo 需用户密码或需用户确认）

## 何时使用

- 用户说"用 ROS2 控制机械臂"、"启动 bringup / RViz"
- 需要写 ROS2 节点（Topic/Service/Action）控制 reBot Arm，或把机械臂接入 MoveIt2 / 其他 ROS2 生态
- 排查 ROS2 接口问题：话题不发布、轨迹执行失败、找不到串口、RViz 模型不显示
- 状态机异常 / 故障码排查、ROS2 层安全停车

## 前置条件

| 项目 | 要求 |
|------|------|
| 操作系统 | **Ubuntu 24.04 + ROS2 Jazzy** 或 **Ubuntu 22.04 + ROS2 Humble**（官方推荐） |
| 硬件接线 | USB2CAN/串口桥接板已插入主机；**RS**：SocketCAN `can0`（bitrate 1000000）可用；**DM**：`/dev/ttyACM*` 可读写；已按型号上电（DM 24V / RS 48V） |
| 底层环境 | motorbridge 已安装（`rebot-arm-environment-setup` 第 2 节） |
| 安全 | **必须先读 `rebot-arm-safety`**：机械臂运动快、力矩大，运行前完成检查清单 |

> ⚠️ 接线/上电前完成 `rebot-arm-safety` 检查清单：断电插拔、电压档位（220V→230V / 110V→115V）、正负极正确、周围 50cm 无人员、手边有电源开关。

## 🔀 0. 安全要点

> ⚠️ **`/rebotarm/move_to_pose_ik` 只做 IK 求解并直接更新目标关节角，机械臂运动很快**——首次运行前先清空运动范围、降低速度参数，人守在电源开关旁。
> ⚠️ **轨迹执行期间，低层 cmd 话题默认被拒绝**（`cmd_arbitration:=reject`），不会抢占轨迹；如需强制覆盖，启动时传 `cmd_arbitration:=preempt`。
> 🔴 **任何异常（剧烈抖动/撞限位/异响）**：第一步调用 `/rebotarm/disable` 服务停止控制循环并失能，然后**立即断电**。硬件断电永远是最可靠的急停。

## 1. ROS2 理论速览（第 31 章）

| 概念 | 一句话解释 | 适用场景 |
|------|-----------|---------|
| **Node 节点** | 机器人软件的基本工作单元，专事专办、独立运行 | 相机节点、电机驱动节点等 |
| **Topic 话题** | 发布/订阅的异步单向通信，像"公众号"，支持一对多/多对多 | 高频持续数据：关节角度、图像、点云 |
| **Service 服务** | 客户端/服务端同步一问一答，像"打电话问路" | 短暂快速指令：使能、开夹爪、切换模式 |
| **Action 动作** | Topic+Service 结合体，含 Goal/Feedback/Result，可中途取消，像"点外卖" | 耗时长的运动：机械臂移动到指定位置 |
| **Message 消息** | 标准数据结构：`.msg`（Topic）、`.srv`（Request/Response，`---` 分隔）、`.action`（Goal/Result/Feedback，`---` 分隔） | 统一节点间"交流格式" |
| **QoS 服务质量** | 传输规则：**Reliable** 可靠（必须送达）vs **Best Effort** 尽力而为（低延迟） | 急停指令用 Reliable，视频流用 Best Effort |
| **Parameter 参数** | 节点运行时的"控制面板"，动态修改、即时生效，无需重新编译 | 调速度、调曝光、调频率 |
| **Launch 启动** | "一键启动键"，编排多个节点启动顺序并分发参数 | 一条命令拉起整个机器人系统 |
| **rosbag 工具** | "行车记录仪"，按时间戳录制/回放话题数据 | 离线调试、事故复盘、AI 数据集采集 |

> 配套理论（第 32 章）：URDF/Xacro 描述机械臂"骨骼与关节"，TF 坐标树 + Robot State Publisher 结合实时关节角发布坐标变换，RViz 据此画出机械臂实时姿态——这正是 bringup 可视化链路的原理。

## 🤖 2. 工作空间构建

### 2.1 获取工作空间（官方仓库）

```bash
# RS（灵足电机，48V，SocketCAN）：
git clone https://github.com/Yang-Ci/ReBot_Arm_web_RS.git ReBot_Arm_web_RS

# DM（达妙电机，24V，串口）：
git clone https://github.com/Yang-Ci/Borot-Arm_Mujoco.git ~/reBot_Arm_Mujoco-DM
```

> 工作空间目录名两型号不同：**RS 为 `rebotarm_ros2`，DM 为 `reBotArmController_ROS2-main`**（位于 `~/reBot_Arm_Mujoco-DM` 下）。

### 2.2 七个 ROS2 包

| 包名 | 作用 |
|------|------|
| `rebotarm_msgs` | 自定义消息、服务、动作接口（`.msg` / `.srv` / `.action`） |
| `rebotarmcontroller` | 驱动节点，核心控制器 `reBotArmController` |
| `rebotarm_bringup` | 启动文件、配置文件、URDF 模型和 RViz 资源 |
| `rebotarm_moveit_config` | MoveIt 2 配置文件 |
| `rebotarm_moveit_demos` | MoveIt 2 示例程序 |
| `rebotarm_mujoco` / `rebotarm_mujoco_rs` | MuJoCo 仿真同步节点（DM 为 `rebotarm_mujoco`，RS 为 `rebotarm_mujoco_rs`） |
| `rebotarm_agent` | DM 版本的上层 Agent 节点 |

### 2.3 安装底层 SDK（reBotArm_control_py）

`reBotArm_control_py` 是底层 Python 控制库，`rebotarm_ros2` 把它"封装"成 ROS2 标准接口：

```bash
# 在对应工作空间的 third_party 目录下克隆（RS 在 rebotarm_ros2/third_party；
# DM 的 setup.sh 会依次检查 reBotArmController_ROS2-main/third_party、
# reBotArmController_ROS2-main/sdk、~/reBotArm_control_py 三个候选路径）：
git clone https://github.com/Seeed-Projects/reBotArm_control_py.git third_party/reBotArm_control_py
```

`reBotArm_control_py` 默认 yaml 配置为 dm，需将 `reBotArm_control_py/config` 中的 `hardware_yaml` 改成适配选项：

```text
# RS：
hardware_yaml: "rebotarm_rs.yaml"

# DM：
hardware_yaml: "rebotarm_dm.yaml"
```

### 2.4 安装 motorbridge（电机↔上层软件中间件）

```bash
python3 -m pip install motorbridge

# 验证（输出示例：motorbridge 0.5.0）
motorbridge -v
```

### 2.5 编译工作空间

```bash
source /opt/ros/${ROS_DISTRO}/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### 2.6 验证可执行入口

```bash
# RS：
cd ~/reBot_Arm_Mujoco-RS/rebotarm_ros2
source install/setup.bash
ros2 pkg executables rebotarmcontroller

# DM：
cd ~/reBot_Arm_Mujoco-DM/rebotarm_ros2
source install/setup.bash
ros2 pkg executables rebotarmcontroller
```

期望至少看到：

```text
rebotarmcontroller GravityCompensation
rebotarmcontroller GripperControl
rebotarmcontroller MoveTo
rebotarmcontroller MoveToPose
rebotarmcontroller reBotArmController
```

| 型号 | 额外可执行入口 | 备注 |
|------|---------------|------|
| RS | `FakeRsDriver`、`CancelAction` | MuJoCo 仿真假驱动；取消正在执行的 Action 目标 |
| DM | `FakeReBotArmDriver` | MuJoCo 仿真假驱动 |

> 注意：RS 版本还包含 `motion_profiles.py` 和 `trajectory_profiles.py` 两个运动规划文件，DM 版本没有。

> 状态记忆：工作空间编译成功后更新 memory/local-machine-env.md（见 AGENTS.md 第 3 节）。

## 🤖 / 👤 3. 启动完整系统（bringup + RViz）

### 3.1 启动命令

```bash
# RS：model:=rs，channel:=can0
cd ~/reBot_Arm_Mujoco-RS/rebotarm_ros2
ros2 launch rebotarm_bringup bringup.launch.py model:=rs channel:=can0 use_rviz:=true

# DM：使用工作空间根目录的 ./rebotarm 脚本
cd ~/reBot_Arm_Mujoco-DM
./rebotarm start dm use_rviz:=true
```

启动后，`reBotArmController` 节点持续发布机械臂状态（由 `JointStatePublisher` 类统一管理，默认 100 Hz）；RViz 基于 URDF 模型显示机械臂实时运动，"所见即所得"。

### 3.2 启动后的话题一览

| 话题 | 消息类型 | 说明 |
|------|---------|------|
| `/rebotarm/joint_states` | `sensor_msgs/msg/JointState` | 6 轴关节位置、速度、力矩，附带夹爪 `finger_left` |
| `/rebotarm/arm_status` | `rebotarm_msgs/msg/ArmStatus` | 控制模式、使能状态、状态机、关节状态码、错误码（latched QoS） |
| `/rebotarm/joints/<joint>/state` | `rebotarm_msgs/msg/JointMotorState` | 单关节电机级状态，`<joint>` 为 `joint1` 到 `joint6` |
| `/rebotarm/gripper/state` | `rebotarm_msgs/msg/JointMotorState` | 夹爪电机级状态，未配置夹爪时不发布 |

> `ArmStatus` 使用 `TRANSIENT_LOCAL` durability（latched QoS），晚加入的订阅者也能立即收到最近一次状态快照，适合 UI 和健康监控组件做状态同步。

### 3.3 查看状态

```bash
# 显示活跃话题名
ros2 topic list

# 列出话题及其消息类型（-t 参数）
ros2 topic list -t

# 查看关节状态
ros2 topic echo /rebotarm/joint_states --once

# 查看整体状态（含状态机和错误码）
ros2 topic echo /rebotarm/arm_status --once

# 查看单关节电机状态
ros2 topic echo /rebotarm/joints/joint1/state --once
```

`ArmStatus` 消息字段：

```text
std_msgs/Header header
string mode               # 当前控制模式：mit / pos_vel / vel
bool enabled              # 机械臂是否使能
bool control_loop_active  # 内部 pos_vel 控制循环是否运行
string state_machine      # 状态机：IDLE / TRAJ_RUNNING / LOWLEVEL_STREAMING / GRAVITY_COMP
string[] joint_names      # 关节名列表
uint8[] per_joint_status_code  # 每个关节电机的状态码
string[] error_codes      # 错误码列表
```

## 🤖 4. 三种控制接口

所有接口默认挂在 `/rebotarm` 命名空间下，可通过 launch 参数 `arm_namespace` 覆盖。**统一单位：角度为弧度 rad，时间为秒。**

### 4.1 标准控制流程

```bash
# 1. 电机上电使能
ros2 service call /rebotarm/enable std_srvs/srv/Trigger

# 2. 回安全原点（验证零点是否正常）
ros2 service call /rebotarm/safe_home std_srvs/srv/Trigger

# 3. 此时就可以发送 move_to_pose / follow_joint_trajectory action 目标
# ...执行运动...

# 4. 结束后失能
ros2 service call /rebotarm/disable std_srvs/srv/Trigger
```

### 4.2 Service：触发式控制

适用于使能/失能、安全回零、模式切换等触发式操作（定义在 `ros_services.py` 的 `ArmServices` 类）：

| Service | 类型 | 说明 |
|---------|------|------|
| `/rebotarm/enable` | `std_srvs/srv/Trigger` | 使能机械臂和夹爪，启动 pos_vel 控制循环 |
| `/rebotarm/disable` | `std_srvs/srv/Trigger` | 停止控制循环并失能机械臂 |
| `/rebotarm/safe_home` | `std_srvs/srv/Trigger` | 以安全速度回零（关节 + 夹爪） |
| `/rebotarm/set_zero` | `rebotarm_msgs/srv/SetZero` | 设置全部或指定关节零点 |
| `/rebotarm/move_to_pose_ik` | `rebotarm_msgs/srv/MoveToPoseIK` | 只做 IK 求解并更新目标关节角 |
| `/rebotarm/gripper/set` | `rebotarm_msgs/srv/SetGripper` | 设置夹爪开合距离和最大力矩 |
| `/rebotarm/gravity_compensation/start` | `std_srvs/srv/Trigger` | 启动 controller 内部重力补偿闭环 |
| `/rebotarm/gravity_compensation/stop` | `std_srvs/srv/Trigger` | 停止重力补偿闭环 |
| `/rebotarm/gravity_compensation/status` | `std_srvs/srv/Trigger` | 查询重力补偿状态，`success=true` 表示运行中 |

常用命令示例：

```bash
# 使能
ros2 service call /rebotarm/enable std_srvs/srv/Trigger

# 安全回零
ros2 service call /rebotarm/safe_home std_srvs/srv/Trigger

# IK 求解（！！！注意机械臂运动很快）
ros2 service call /rebotarm/move_to_pose_ik rebotarm_msgs/srv/MoveToPoseIK \
  "{target_pose: {position: {x: 0.30, y: 0.0, z: 0.30}, orientation: {w: 1.0}}}"

# 设置夹爪开口（rad 弧度制 0-5）
ros2 service call /rebotarm/gripper/set rebotarm_msgs/srv/SetGripper \
  "{position: 2.5, max_effort: 0.5}"
```

> ⚠️ `move_to_pose_ik` 是即时 IK 求解 + 目标更新，**不会按轨迹平滑执行，机械臂运动很快**；日常控制更推荐下面的 `move_to_pose` Action（带 `duration` 与反馈）。

### 4.3 Action：面向过程的控制

适用于需要反馈和取消的长时间运动（定义在 `ros_actions.py` 的 `ArmActions` 类）：

| Action | 类型 | 说明 |
|--------|------|------|
| `/rebotarm/move_to_pose` | `rebotarm_msgs/action/MoveToPose` | 末端笛卡尔位姿轨迹，内部走 `ArmEndPos.move_to_traj()` |
| `/rebotarm/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | 标准关节轨迹接口，MoveIt2 的标准接口 |
| `/rebotarm/gripper/command` | `control_msgs/action/GripperCommand` | 标准夹爪 action |

`move_to_pose` 示例：运动到指定位姿，总耗时 3 秒，并打印运动过程实时反馈：

```bash
ros2 action send_goal /rebotarm/move_to_pose rebotarm_msgs/action/MoveToPose \
  "{target_pose: {position: {x: 0.30, y: 0.0, z: 0.30}, orientation: {w: 1.0}}, duration: 3.0}" \
  --feedback
```

查看 Action 的消息定义（Goal / Feedback / Result 字段）：

```bash
ros2 interface show rebotarm_msgs/action/MoveToPose
```

### 4.4 Topic：低层单电机直通

用于调试和低层控制实验（`motor_passthrough.py`）提供 per-joint sparse raw command：

| 话题 | 消息类型 | 说明 |
|------|---------|------|
| `/rebotarm/joints/<joint>/cmd` | `rebotarm_msgs/msg/JointMotorCmd` | 单关节 sparse raw command |
| `/rebotarm/gripper/cmd` | `rebotarm_msgs/msg/JointMotorCmd` | 夹爪 sparse raw command |

`JointMotorCmd` 采用 **sparse-flag** 设计：只有 `use_pos`、`use_vel`、`use_kp`、`use_kd`、`use_tau`、`use_vlim` 为 `true` 的字段才覆盖默认值。`mode` 可选 `0`（MIT）、`1`（POS_VEL）、`2`（VEL）。

```bash
# 单关节 MIT 模式指令（joint1 位置 0.2 rad）
ros2 topic pub --once /rebotarm/joints/joint1/cmd/mit \
  rebotarm_msgs/msg/JointMitCmd \
  "{pos: 0.2, vel: 0.0, kp: 80.0, kd: 4.0, tau: 0.0}"
```

> ⚠️ 轨迹运行期间，低层 cmd 默认被拒绝（`cmd_arbitration:=reject`）；如需抢占式覆盖，在 launch 时传 `cmd_arbitration:=preempt`。

### 4.5 演示示例

所有示例都假设已启动 `reBotArmController`（示例源文件位于 `src/rebotarmcontroller/rebotarmcontroller/examples/`；启动方式见第 3.1 节）：

```bash
# 末端 Pose 示例：通过 /rebotarm/move_to_pose action 发送 geometry_msgs/Pose 目标，单次动作 demo（不自动 safe_home/disable）
ros2 run rebotarmcontroller MoveToPose -- --x 0.30 --y 0.0 --z 0.30 --qw 1.0 --duration 2.0

# 重力补偿示例：先调 /rebotarm/enable 再启动补偿；Ctrl+C 退出时依次 stop → safe_home → disable
ros2 run rebotarmcontroller GravityCompensation
```

## 🤖 / 👤 5. 安全停车与故障排查

### 5.1 安全停车

**`/rebotarm/safe_home`**：让机械臂以安全速度回到预设零位。服务内部会先停止重力补偿，再切入 `pos_vel` 模式，然后执行回零：

```bash
ros2 service call /rebotarm/safe_home std_srvs/srv/Trigger
```

**`/rebotarm/disable`**：停止控制循环并失能机械臂，**是紧急停车的首选**：

```bash
ros2 service call /rebotarm/disable std_srvs/srv/Trigger
```

> **hold_current_position**：在轨迹取消或异常时，控制器会自动调用此方法锁住当前关节位置，防止机械臂自由滑落。

> 🔴 软件急停后**再断电**：`disable` 只停止控制循环，电机仍带电；异常场景（抖动/撞限位/异响）先 `disable` 再切断电源，硬件断电是最可靠的急停。

### 5.2 状态机监控

`/rebotarm/arm_status` 话题中的 `state_machine` 字段反映当前运行状态，是排查问题的第一入口：

| 状态 | 含义 |
|------|------|
| `IDLE` | 空闲，等待指令 |
| `TRAJ_RUNNING` | 轨迹执行中 |
| `LOWLEVEL_STREAMING` | 低层单电机指令流式下发中 |
| `GRAVITY_COMP` | 重力补偿闭环运行中 |

```bash
# 持续监控状态机
ros2 topic echo /rebotarm/arm_status --field state_machine
```

### 5.3 故障码排查

`ArmStatus` 消息中的 `per_joint_status_code` 和 `error_codes` 字段用于故障定位：

- `per_joint_status_code`：每个关节电机的状态码（`uint8`），来自底层 SDK 的 `motor.get_state().status_code`，**非零值表示电机异常**；
- `error_codes`：控制器级别的错误码字符串。

查看完整状态（含故障码）：`ros2 topic echo /rebotarm/arm_status --once`

## ✅ 验证与预期结果

| 运行 | 期望结果 | 失败处理 |
|------|---------|---------|
| `ros2 pkg executables rebotarmcontroller` | 列出 GravityCompensation / GripperControl / MoveTo / MoveToPose / reBotArmController 等入口 | 确认 `colcon build` 成功且已 `source install/setup.bash` |
| `ros2 topic list` | 看到 `/rebotarm/joint_states`、`/rebotarm/arm_status`、`/rebotarm/joints/jointN/state` | 确认 bringup 已启动，硬件接线与串口/CAN 权限正常 |
| `ros2 service call /rebotarm/enable std_srvs/srv/Trigger` | 返回 `success: true`（使能成功） | 查看 `/rebotarm/arm_status` 的 `error_codes` / `per_joint_status_code` |

## 🔀 6. 常见问题（FAQ）

| 问题 | 排查与修复 |
|------|-----------|
| **找不到串口**（启动报 `open serial port /dev/ttyACM0 failed`） | `ls /dev/ttyACM*` 查看实际设备，然后用 `channel:=/dev/ttyACM1` 覆盖（DM） |
| **权限不足**（串口存在但无权限） | `sudo usermod -a -G dialout $USER`，重新登录后生效 |
| **RViz 模型不显示** | 确认 URDF mesh 路径为 `package://rebotarm_bringup/description/meshes/...` |
| **轨迹执行失败** | 检查首个轨迹点是否接近当前关节角（**偏差需小于 0.10 rad**），最终位置误差需小于 `0.03 rad`；用 `ros2 topic echo /rebotarm/joint_states --once` 查看当前关节角 |

## 参考

- 官方 Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- 工作空间：<https://github.com/Yang-Ci/ReBot_Arm_web_RS>（RS）｜ <https://github.com/Yang-Ci/Borot-Arm_Mujoco>（DM）
- 底层 SDK：<https://github.com/Seeed-Projects/reBotArm_control_py> ｜ motorbridge：<https://github.com/motorbridge/motorbridge>
- 配套教程：本地参考教程《Seeed具身智能入门8个阶段40章节》（未随本仓库发布）第 31 章（ROS2 通信与机器人软件架构）、第 32 章（URDF、TF 与机器人模型）、第 33 章（reBot Arm ROS2 集成）
- 相关技能：`rebot-arm-safety`（操作前必读）｜ `rebot-arm-environment-setup`（环境/接线）｜ `rebot-arm-moveit`（MoveIt2 规划）｜ `rebot-arm-troubleshooting`（故障排查）
