---
name: rebot-arm-moveit
description: 为 reBot Arm（B601-DM / B601-RS）使用 MoveIt2 运动规划：仿真/真机启动链路、SRDF 与 Planning Group、关节限制与碰撞模型、Planning Scene、笛卡尔路径、障碍物规划、轨迹执行（follow_joint_trajectory）、画矩形与抓取放置 demo。当用户需要"让机械臂规划避障轨迹、画图形、或做 pick-and-place"时使用本技能。
---

# reBot Arm MoveIt2 运动规划

## 简介

MoveIt 2 是 ROS2 生态中最主流的机械臂运动规划框架，负责**逆运动学求解、碰撞检测、轨迹规划和轨迹执行**。对于 reBot Arm，MoveIt 2 将上层规划与底层驱动隔离开：规划在 `move_group` 节点中完成，执行通过 `follow_joint_trajectory` action 下发给 `reBotArmController`。本技能覆盖 MoveIt2 系统架构、仿真/真机启动链路、SRDF 与 Planning Group、关节限制与碰撞模型、Planning Scene、笛卡尔路径、障碍物规划、轨迹执行，以及画矩形（`draw_square`）与抓取放置（`pick_place`）两个官方 demo，让机械臂在复杂环境中自动规划安全运动。

> 分工标记：🤖 AI 执行（终端可自动化）｜ 👤 用户执行（GUI/网页/按键/插线/物理操作）｜ 🔀 人机协作（sudo 需用户密码或需用户确认）

## 何时使用

- 用户想让机械臂"自动规划避障轨迹 / 画图形 / 做 pick-and-place"
- 需要 RViz MotionPlanning 可视化、IK 求解、笛卡尔路径规划
- 需要理解 SRDF、Planning Group、Planning Scene、`follow_joint_trajectory` 轨迹执行链路

## 前置条件

- 已确认型号（**DM** 串口 / **RS** SocketCAN），并完成 `rebot-arm-environment-setup`（can0 配置 / 串口权限）
- 已构建 `rebotarm_ros2` 工作空间（含 `rebotarm_bringup`、`rebotarm_moveit_config`、`rebotarm_moveit_demos` 等包），见 `rebot-arm-ros2`
- 真机操作前已读 `rebot-arm-safety` 并完成检查清单

## 🔀 0. 安全要点

> ⚠️ MoveIt 会**自主规划并执行轨迹**，机械臂可能沿非预期的路径运动。**先仿真验证、再真机执行**；真机执行前确认工作区无障碍物与人员；轨迹执行中出现异常（抖动、撞限位、异响）第一步是 `/rebotarm/disable` 或直接断电（详见 `rebot-arm-safety`）。

- 真机运行前先确认夹爪开闭方向和限位（见 9.2 的夹爪参数）。
- 首次运行 demo 必须有人值守，手在电源开关旁，先低速空载试跑。

## 🤖 1. 系统架构

MoveIt 2 的核心是 `move_group` 节点，它充当运动规划的总调度器。围绕 `move_group`，reBot Arm 的 MoveIt 2 集成涉及以下组件：

| 组件 | 作用 | 对应文件/包 |
|------|------|-------------|
| `move_group` | 规划总调度：接收目标、调用 IK 和 planner、生成轨迹、下发执行 | `rebotarm_moveit_config` |
| URDF/Xacro | 机器人模型描述（连杆、关节、mesh、夹爪、gripper_tcp） | `rebotarm.urdf.xacro` |
| SRDF | 语义模型：规划组、末端执行器、默认状态、自碰撞矩阵 | `rebotarm.srdf` |
| Kinematics Plugin | IK 求解器 | `kinematics.yaml`（KDL） |
| OMPL Planner | 采样运动规划器 | `ompl_planning.yaml`（RRTConnect） |
| Trajectory Execution | 轨迹执行控制器 | `moveit_controllers.yaml` |
| Planning Scene | 环境模型：物体、碰撞、ACM | `pick_place.py` 中的场景操作 |
| RViz MotionPlanning | 可视化交互界面 | `moveit.rviz` |

## 🔀 2. 启动链路

### 🤖 2.1 仿真环境（不需要真实机械臂）

```bash
ros2 launch rebotarm_moveit_config demo.launch.py
```

该命令启动 `move_group`、`robot_state_publisher`、`ros2_control_node`（mock 硬件）、`joint_state_broadcaster`、`rebotarm_controller`、`gripper_controller` 和 RViz。仿真环境使用 `mock_components/GenericSystem` 作为虚拟硬件。**先启动 MoveIt 仿真，再另开终端运行 demo**（见第 9 节）。

### 🔀 2.2 真机环境（两个终端）

**终端 1：启动硬件驱动** 🔀

```bash
# RS：先配置 can0（bitrate 1000000），再启动驱动
sudo ip link set can0 down 2>/dev/null || true
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
ros2 launch rebotarm_bringup bringup.launch.py model:=rs channel:=can0
```

```bash
# DM：启动驱动（串口通道）
sudo chmod 666 /dev/ttyACM*        # 串口权限（如需）
ros2 launch rebotarm_bringup bringup.launch.py model:=dm channel:=/dev/ttyACM0
# 或使用一键启动（可加 use_rviz:=true 开启 RViz）：
./rebotarm start dm
```

**终端 2：启动 MoveIt（连接到已运行的驱动）** 🤖

```bash
ros2 launch rebotarm_moveit_config hardware.launch.py
```

`hardware.launch.py` 不启动 `ros2_control_node`，而是通过 remap 将 `/joint_states` 指向 `/<arm_namespace>/joint_states`，直接读取真实驱动发布的关节状态，并将规划好的轨迹通过 `follow_joint_trajectory` action 下发给 `reBotArmController`。

## 🤖 3. SRDF 与 Planning Group

SRDF（Semantic Robot Description Format）是 URDF 的语义补充层：URDF 描述物理结构（连杆、关节、mesh），但不知道哪些关节"一起动"、哪个连杆是"末端"、哪些连杆"不会碰"，SRDF 回答这些问题。

reBot Arm 的 SRDF 定义了两个规划组：

| 规划组 | 组成 | 用途 |
|--------|------|------|
| `arm` | 运动链 `base_link` → `gripper_tcp` | 6 轴机械臂运动规划 |
| `gripper` | `gripper_joint1`、`gripper_joint2` | 夹爪开闭控制 |

- `arm` 组使用 `<chain>` 定义，覆盖 6 个关节加夹爪连杆；`gripper` 组使用 `<joint>` 逐个列举。
- 命名状态（`group_state`）方便快速复位：

| 状态名 | 组 | 含义 |
|--------|-----|------|
| `home` | `arm` | 6 关节全零位 |
| `open` | `gripper` | 夹爪关节 `0.0715` rad（全开） |
| `closed` | `gripper` | 夹爪关节 `0.0` rad（全闭） |

末端执行器与虚拟关节声明（`rebotarm.srdf`）：

```xml
<end_effector name="gripper" parent_link="gripper_link"
              group="gripper" parent_group="arm"/>

<virtual_joint name="FixedBase" type="fixed"
               parent_frame="world" child_link="base_link"/>
```

`end_effector`：夹爪安装在最末连杆 `gripper_link` 上，规划组 `gripper`，从属于父规划组 `arm`；`virtual_joint` 将机械臂固定到世界坐标系 `world`。

## 🤖 4. 关节限制与碰撞模型

**关节限制分两层**：

- **URDF 层**：每个关节的角度范围（min/max position），是硬件级别的硬限制。
- **MoveIt 层**：`joint_limits.yaml` 中定义速度和加速度限制，用于轨迹时间参数化：

```yaml
joint_limits:
  joint1:
    has_velocity_limits: true
    max_velocity: 1.0          # rad/s
    has_acceleration_limits: true
    max_acceleration: 1.0      # rad/s^2
  # joint2 ~ joint6 同上
  gripper_joint1:
    has_velocity_limits: true
    max_velocity: 0.2          # rad/s
    has_acceleration_limits: true
    max_acceleration: 0.5      # rad/s^2
```

全局缩放因子（默认只使用 20% 最大速度/加速度，保守安全；demo 可单独覆盖，如 `pick_place.yaml` 中 `velocity_scaling: 1.0` 表示全速规划）：

```yaml
default_velocity_scaling_factor: 0.2
default_acceleration_scaling_factor: 0.2
```

**碰撞模型与自碰撞**：碰撞检测基于 FCL（Flexible Collision Library），使用 URDF 中的 mesh 或基本几何体。为加速，SRDF 预定义了自碰撞矩阵（ACM，AllowedCollision Matrix），声明哪些连杆对"永远不需要检测碰撞"，分两类：

| 类别 | 连杆对 | 原因 |
|------|--------|------|
| Adjacent（相邻） | `base_link`-`link1`、`link1`-`link2`、…、`gripper_link`-`gripper_left/right/tcp` | 通过关节直接连接，物理上必然接触 |
| Never（永不） | `gripper_left`-`gripper_tcp`、`gripper_right`-`gripper_tcp`、`gripper_left`-`gripper_right` | 几何上不可能接触 |

未出现在 ACM 中的连杆对（如 `base_link` 和 `link6`）会被正常检测碰撞，OMPL 会在采样空间中避开导致碰撞的关节配置。

## 🤖 5. Planning Scene

Planning Scene 是 MoveIt 对"世界"的建模，包含机器人本体、环境物体和碰撞关系。它是规划的前提：每次规划前，MoveIt 都会检查起始状态是否与场景中的物体碰撞。核心操作通过三个 service 完成：

| Service | 类型 | 作用 |
|---------|------|------|
| `/apply_planning_scene` | `ApplyPlanningScene` | 增删物体、修改 ACM、附加物体 |
| `/get_planning_scene` | `GetPlanningScene` | 查询当前场景 |
| `/plan_kinematic_path` | `GetMotionPlan` | 请求规划（不执行） |

`pick_place` demo 完整演示了场景操作流程：

1. **添加碰撞物体**：放置一个长方体作为待抓取物体（`CollisionObject`，`operation=CollisionObject.ADD`）；
2. **修改 ACM**：允许夹爪连杆与物体碰撞（抓取时夹爪需要接触物体，`_set_allowed_collision(acm, object_id, link, True)`）；
3. **附加物体**：将物体"粘"到末端连杆上，随机械臂一起运动（`AttachedCollisionObject`）；
4. **分离物体**：到达放置位后从末端分离，重新作为场景物体（`operation=CollisionObject.REMOVE` + 重新 `ADD`）。

## 🤖 6. 笛卡尔路径

笛卡尔路径是指末端在笛卡尔空间中沿直线或曲线运动，而不是在关节空间中逐点插值。MoveIt 2 通过 `compute_cartesian_path` 实现。reBot Arm 的 `draw_square` demo 使用笛卡尔路径思路：控制 `gripper_tcp` 遍历同一平面矩形的四个角点：

1. 对每个角点用 IK 求解对应关节角（`compute_ik_joint_target`）；
2. 用 OMPL 规划从当前关节角到目标关节角的轨迹（`pipeline_id="ompl"`、`planner_id="RRTConnect"`、`allowed_planning_time = 5.0`）；
3. 通过 `/execute_trajectory` action 执行轨迹。

`draw_square` 关键参数（默认在 `src/rebotarm_moveit_demos/config/draw_square.yaml`）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `rectangle_center` | `[0.28, 0.0, 0.12]` | 矩形中心，坐标系 `base_link` |
| `rectangle_width` | `0.04` | 矩形宽度（m） |
| `rectangle_height` | `0.08` | 矩形高度（m） |
| `tcp_rpy` | `[0.0, 1.57, 0.0]` | 末端姿态，默认夹爪竖直朝下 |
| `tcp_yaw_offsets` | `[0.0, 3.1416, -3.1416]` | IK 备选 yaw，避免 joint6 大幅绕转 |
| `avoid_collisions` | `true` | IK 求解时是否避碰 |

> 💡 `tcp_yaw_offsets` 是实用技巧：IK 可能返回多个解，其中某些解会导致 `joint6` 大幅旋转。通过提供多个备选 yaw，demo 会**选择关节变化最小的解**，减少不必要的绕转。

## 🤖 7. 障碍物规划

当 Planning Scene 中存在障碍物时，OMPL 会在规划过程中自动避开它们。reBot Arm 的 OMPL 配置要点（`ompl_planning.yaml`）：

| 配置 | 值 | 说明 |
|------|-----|------|
| 默认 planner | `RRTConnect` | 双向快速随机树，适合大多数场景 |
| 投影评估器 | `joints(joint1,joint2)` | 采样空间投影维度，影响规划效率 |
| 最长有效段比例 | `0.005` | 碰撞检测插值粒度，越小越安全但越慢 |

请求适配器链（`request_adapters`）在规划前做四件事：`ResolveConstraintFrames`（约束坐标系对齐到 planning frame）→ `ValidateWorkspaceBounds`（验证目标在工作空间内）→ `CheckStartStateBounds`（检查起始状态在关节限位内）→ `CheckStartStateCollision`（检查起始状态不碰撞）。响应适配器链（`response_adapters`）在规划后做三件事：`AddTimeOptimalParameterization`（添加时间参数）→ `ValidateSolution`（验证轨迹）→ `DisplayMotionPath`（RViz 预览）。

`pick_place` 完整展示了障碍物规划流程：**添加物体 → 规划到抓取位（避碰）→ 附加物体 → 规划到放置位（物体随臂运动，仍需避碰）→ 分离物体 → 清理场景**。

## 🤖 8. 轨迹执行

MoveIt 2 规划出的轨迹通过 controller 下发给硬件执行，仿真与真机使用不同配置。

**仿真环境**（`moveit_controllers.yaml`）：`rebotarm_controller` 与 `gripper_controller` 都是 `ros2_control` 的 mock 硬件 controller，轨迹直接在虚拟硬件上执行：

```yaml
moveit_simple_controller_manager:
  controller_names:
    - rebotarm_controller
    - gripper_controller    # 同构配置，joints: [gripper_joint1, gripper_joint2]
  rebotarm_controller:
    action_ns: follow_joint_trajectory
    type: FollowJointTrajectory
    default: true
    joints: [joint1, joint2, joint3, joint4, joint5, joint6]
```

**真机环境**（`moveit_hardware_controllers.yaml`）：只有一个 `rebotarm` controller，指向 `reBotArmController` 的 `/rebotarm/follow_joint_trajectory` action（`control_msgs/action/FollowJointTrajectory`，即 MoveIt2 标准接口，详见 `rebot-arm-ros2`）；夹爪真机模式通过独立的 `/rebotarm/gripper/command` action（`GripperCommand` 类型）控制，不走 `follow_joint_trajectory`。

轨迹执行容差：

```yaml
trajectory_execution:
  allowed_execution_duration_scaling: 1.2   # 允许执行时间放大 20%
  allowed_goal_duration_margin: 0.5          # 到位后额外等待 0.5s
  allowed_start_tolerance: 0.05              # 起始状态偏差容差 0.05 rad
  execution_duration_monitoring: true        # 启用执行时间监控
```

真机执行流程：① `move_group` 规划出 `RobotTrajectory` → ② 通过 `/execute_trajectory` action 发给 `MoveItSimpleControllerManager` → ③ 转换为 `follow_joint_trajectory` goal 发给 `reBotArmController` 的 `/rebotarm/follow_joint_trajectory` → ④ `reBotArmController` 内部执行轨迹（校验 → pos_vel 模式 → 定时下发 → 到位检查）→ ⑤ 执行结果回传 `move_group`。执行失败（超时、到位偏差过大）时 `move_group` 返回错误码，demo 脚本据此决定是否中止。

## 🔀 9. 运行 Demo

### 🤖 9.1 画矩形 demo（draw_square）

先启动 MoveIt 仿真环境（第 2.1 节），再另开终端运行：

```bash
source install/setup.bash
ros2 launch rebotarm_moveit_demos draw_square.launch.py
```

`draw_square` 控制 `gripper_tcp` 遍历矩形的四个角点，验证 IK、轨迹规划和执行链路是否正常。默认参数在 `src/rebotarm_moveit_demos/config/draw_square.yaml`（见第 6 节参数表）。

### 🔀 9.2 抓取放置 demo（pick_place）

```bash
source install/setup.bash
ros2 launch rebotarm_moveit_demos pick_place.launch.py
```

`pick_place` 会在规划场景中添加一个待抓取物体，流程：**添加物体 → 夹爪打开 → 移动到抓取位 → 闭合夹爪 → 附加物体 → 移动到放置位 → 释放物体**。默认参数在 `src/rebotarm_moveit_demos/config/pick_place.yaml`。

> ⚠️ **真机运行前，请先确认夹爪开闭方向和限位**。仿真夹爪关节位置和真实硬件夹爪电机位置是两套不同参数：

| 参数 | 仿真值 | 硬件值 |
|------|--------|--------|
| 夹爪全开 | `0.045`（单侧 rad） | `-5.0`（电机位置） |
| 夹爪全闭 | `0.0`（单侧 rad） | `0.0`（电机位置） |

> 🔴 **真机上夹爪方向反了**：检查 `pick_place.yaml` 中的 `hardware_open_gripper_position` 与 `hardware_closed_gripper_position`。B601-DM 默认开 `-5.0`、闭 `0.0`；如果电机方向相反，**交换这两个值**。

## ✅ 验证与预期结果

| 运行 | 期望结果 | 失败处理 |
|------|----------|----------|
| 仿真启动 `demo.launch.py`（第 2.1 节） | RViz 打开并显示机械臂模型（含 `gripper_tcp`），MotionPlanning 插件可用 | 模型/插件不显示：确认 `demo.launch.py` 已启动、RViz 加载了 `moveit.rviz`；手动打开 RViz 需手动添加 MotionPlanning 显示 |
| `draw_square.launch.py`（第 9.1 节） | `gripper_tcp` 遍历矩形四角，RViz 显示规划轨迹并执行完成，无规划失败报错 | 规划失败：按 FAQ 检查起始限位/碰撞/工作空间（`ik_timeout`、`planning_time` 默认 5s 可增大）；`joint6` 绕转：调 `tcp_yaw_offsets` |
| `pick_place.launch.py`（第 9.2 节，真机前确认夹爪方向） | 添加物体 → 夹爪打开 → 抓取位 → 闭合 → 附加物体 → 放置位 → 释放，流程走通 | 仿真正常真机失败：检查 `/joint_states` remap、`reBotArmController` 已启动且使能、首点偏差 < `0.10 rad`、到位偏差 < `0.03 rad`；夹爪反向：交换 `hardware_open/closed_gripper_position` |

## 10. 常见问题（FAQ）

**MoveIt 规划失败怎么办？**

- 起始关节状态是否在限位内（`CheckStartStateBounds` 适配器会报错）
- 起始状态是否与场景物体碰撞（`CheckStartStateCollision` 适配器会报错）
- 目标位姿是否在工作空间范围内（`ValidateWorkspaceBounds` 适配器会报错）
- IK 是否能求解到目标（`ik_timeout` 默认 5s，可增大）
- 规划时间是否足够（`planning_time` 默认 5s，可增大）

**RViz 中 MotionPlanning 插件不显示？**

确认 `demo.launch.py` 已启动，且 RViz 配置文件加载了 `moveit.rviz`。如果手动打开 RViz，需要手动添加 MotionPlanning 显示。

**仿真正常但真机执行失败？**

检查 `hardware.launch.py` 是否正确 remap 了 `/joint_states` 到 `/<arm_namespace>/joint_states`；确认 `reBotArmController` 已启动且使能。轨迹**首点偏差需小于 `0.10 rad`**，**最终到位偏差需小于 `0.03 rad`**；可用 `ros2 topic echo /rebotarm/joint_states --once` 查看当前关节角。

**joint6 旋转过多？**

IK 可能返回多个解，导致 `joint6` 大幅绕转。`draw_square` 通过 `tcp_yaw_offsets` 参数提供备选 yaw 来缓解；自定义应用可以在 IK 求解后**选择关节变化最小的解**。

## 参考

- 官方 Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- 官方仓库：<https://github.com/Seeed-Projects/reBot-DevArm>
- 配套教程：本地参考教程《Seeed具身智能入门8个阶段40章节》（未随本仓库发布）第 33 章（ROS2 集成）、第 34 章（MoveIt2 运动规划）
- 相关技能：`rebot-arm-ros2`（ROS2 工作空间与 Action 接口）｜ `rebot-arm-safety`（真机操作前置必读）｜ `rebot-arm-troubleshooting`（故障排查）
