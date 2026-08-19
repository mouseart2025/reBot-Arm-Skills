---
name: rebot-arm-simulation
description: 在仿真环境中使用 reBot Arm（B601-DM / B601-RS）：MuJoCo（MJCF 模型、关节滑块 GUI、运动学/轨迹控制、物理抓取）与 Isaac Sim（USD 导入、Articulation/Drive 配置、Python 控制）的运行方法，以及真实机械臂与仿真机械臂同步（Real-to-Sim、JointState 话题、单位转换、安全设计）。当用户需要"先在仿真里跑机械臂"、做数字孪生同步或学习仿真控制时使用本技能。
---

# reBot Arm 仿真（MuJoCo / Isaac Sim / Real-to-Sim）

## 简介

本技能覆盖 reBot Arm（B601-DM / B601-RS）的三种仿真玩法：在 **MuJoCo** 中跑 MJCF 模型（轻量、快，适合运动学/轨迹/控制算法验证）、在 **Isaac Sim** 中导入 USD 并做 Articulation 控制（完整物理/传感器/场景，适合数字孪生）、以及把**真实机械臂状态实时同步到仿真**（Real-to-Sim，数字孪生/示教复现）。仿真不需要真机也能完整跑通（工作空间自带 mock 硬件接口，如 `start_fake_bringup.sh`）。

## 何时使用

- 用户说"先在仿真里跑机械臂 / 不想接真机 / 先验证算法"
- 需要数字孪生、真机实时镜像、示教复现（Real-to-Sim）
- 学习或演示正/逆运动学、轨迹规划、PD 控制、物理抓取
- 选择仿真平台（MuJoCo vs Isaac Sim）或模型格式（URDF/MJCF/USD）

## 前置条件

- **先确认型号**：DM（24V，串口 `/dev/ttyACM0`）与 RS（48V，SocketCAN `can0`）的命令分支不同（环境搭建见 `rebot-arm-environment-setup`）。
- **纯 MuJoCo 仿真**：Python 3.x + `pip3 install mujoco` 即可；走 ROS2 路径需 Ubuntu + ROS2 Jazzy + 对应工作空间（`~/reBot_Arm_Mujoco-RS` 或 `~/reBot_Arm_Mujoco-DM`）。
- **Isaac Sim**：必须 NVIDIA RTX 显卡（官方建议至少 3060 起步），4.x+ 版本。
- **Real-to-Sim**：需要真机 + 完整工作空间；**任何真机运动前先读 `rebot-arm-safety`**。

## 安全要点

> ⚠️ **Real-to-Sim 同步时真机会运动**：启动真机控制器前必须完成 `rebot-arm-safety` 检查清单（周围 1 m 无人、手在电源开关旁、先低速验证）；RS 断电后关节自锁性弱，失能瞬间必须扶稳机械臂。
>
> ⚠️ **重力补偿示教**：用户用手拖动真臂，属于高风险人机交互——拖动时扶稳机械臂、避开夹爪开口；重力补偿期间控制器拒绝网页关节命令/轨迹回放/夹爪命令，只有"停止重补"和失能请求能打断（第 39 章"重力补偿期间安全规则"）。
>
> ✅ **纯显示跟随是安全的**：只订阅 JointState、不发送力矩、不打开 SocketCAN 的 MuJoCo 跟随节点，即使崩溃也不影响真机，无需硬件确认门控。

## 仿真选型速览

| 对比维度 | MuJoCo | Isaac Sim |
|---|---|---|
| 定位 | 轻量物理实验室（CPU 即可，可跑 10 倍速以上） | 企业级数字孪生平台（PhysX 5 + GPU，必须 RTX ≥3060） |
| 渲染 | 简陋（OpenGL） | 电影级 RTX 光线追踪 |
| 典型场景 | RL 训练、最优控制、实时真机镜像、低算力设备 | 合成数据、传感器仿真、工厂整线仿真 |
| 选型建议 | 动力学/扭矩分析、轨迹验证、真机实时镜像 | 视觉感知、大规模 RL 训练、照片级渲染 |

**URDF / MJCF / USD 格式对比**：

| 格式 | 全称 / 起源 | 特点 | 适用场景 |
|---|---|---|---|
| URDF | Unified Robot Description Format（ROS 标配） | 树状结构（不能闭环），运动学强、动力学弱，collision 只能复用 visual mesh | 传统机械臂、RViz、MoveIt2 |
| MJCF | MuJoCo XML Format | 专为多体动力学/接触优化，摩擦/阻尼/惯性细腻，支持凸包自动生成、场景元素（桌面/物体/相机） | RL、高精度接触（抓取）、灵巧操作 |
| USD | Universal Scene Description（皮克斯开源） | 层叠引用/覆盖、超大场景、材质光影逼真 | Isaac Sim、数字孪生、合成数据 |

开发路径建议：传统算法用 URDF；RL/灵巧操作用 MJCF；高保真数据生成选 USD。

## MuJoCo 仿真

### 1. 安装与验证

```bash
# 方式一：使用工作空间自带 venv（推荐，自动加载 ROS2 + PYTHONPATH）
# RS：
cd ~/reBot_Arm_Mujoco-RS
source scripts/rs_env.sh
# DM：
cd ~/reBot_Arm_Mujoco-DM/reBotArmController_ROS2-main
source scripts/source_rebotarm_env.sh

# 方式二：手动安装（MuJoCo 3.x 是纯 pip 包，自带二进制库）
pip3 install mujoco

# 验证（期望输出 3.x，如 3.2.0）
python3 -c "import mujoco; print(mujoco.__version__)"
```

### 2. MJCF 模型结构

| 顶层元素 | 作用 | reBot Arm 中的体现 |
|---|---|---|
| `<compiler>` | 编译选项 | `angle="radian" coordinate="local" meshdir="../meshes"` |
| `<option>` | 物理参数 | `timestep="0.001" gravity="0 0 -9.81" iterations="100"` |
| `<visual>` | 渲染参数 | `headlight`、`azimuth="135"` |
| `<asset>` | mesh/材质/纹理 | 10 个 STL mesh + 多种材质 |
| `<default>` | 默认值 | `damping="0.8" armature="0.01"` |
| `<worldbody>` | 世界体（地面/相机/物体/机械臂） | 桌面、三个物体、完整运动链 |

模型文件位置：RS（`rebotarm_mujoco_rs` 包）`src/rebotarm_mujoco_rs/models/rs_arm.xml`（物理模型，STL mesh + 完整惯性 + 7 执行器）、`rs_grasp_scene.xml`（抓取场景含物体）；DM（`rebotarm_mujoco` 包）`src/rebotarm_mujoco/models/rebotarm_b601_stl.xml`（物理）、`rebotarm_b601_kinematic.xml`（运动学，简化几何无惯性）、`rebotarm_b601_colored.xml`、`simple_rebotarm.xml`（编译 ROS2 包后同样位于 share 目录）。

关节范围（DM，URDF/MJCF 一致；RS 以 `rs_arm.xml`/URDF 为准，如 joint2/joint3 为 `0~3.14`）：joint1 `-2.8~2.8`、joint2 `-3.14~0`、joint3 `-3.14~0`、joint4 `-1.87~1.57`、joint5 `-1.57~1.57`、joint6 `-3.14~3.14`（单位 rad）。

### 3. 编译 ROS2 包并启动 sim

```bash
# 编译（RS / DM 二选一）
cd ~/reBot_Arm_Mujoco-RS/rebotarm_ros2              # RS
# cd ~/reBot_Arm_Mujoco-DM/reBotArmController_ROS2-main   # DM
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

```bash
# 通过 launch 启动
# RS：
ros2 launch rebotarm_mujoco_rs mujoco_rs.launch.py use_viewer:=true
# DM：
ros2 launch rebotarm_mujoco real2sim.launch.py
```

```bash
# 启动完整仿真环境（fake 驱动 + MuJoCo + 状态发布）
# RS：
./scripts/start_rs_sim.sh
# DM：
./rebotarm start sim
# 或直接调用脚本：~/reBot_Arm_Mujoco-DM/reBotArmController_ROS2-main/scripts/start_rebot_mujoco_all.sh
```

### 4. 关节滑块 GUI 控制

先启动 sim（见上），**另开终端**运行 Tkinter 滑块 GUI：

```bash
# RS：
source /opt/ros/jazzy/setup.bash
source ~/reBot_Arm_Mujoco-RS/rebotarm_ros2/install/setup.bash
ros2 launch rebotarm_mujoco_rs joint_slider_gui.launch.py

# DM：
source /opt/ros/jazzy/setup.bash
source ~/reBot_Arm_Mujoco-DM/reBotArmController_ROS2-main/install/setup.bash
ros2 launch rebotarm_mujoco joint_slider_gui.launch.py
```

### 5. 运动学与轨迹控制

**关节空间 vs 笛卡尔空间**：关节空间直接给 6 个关节角 `[j1..j6]`（弧度），无需求解、无奇异点；笛卡尔空间给末端 `[x, y, z, qx, qy, qz, qw]`，直观但需要 IK 求解（有奇异点风险）。典型接口：`/rebotarm/follow_joint_trajectory`（关节）与 `/rebotarm/move_to_pose`（笛卡尔）。

**读取 TCP 位姿**（`tcp` 是 MJCF 中定义的 site，Tool Center Point）：

```python
import mujoco
model = mujoco.MjModel.from_xml_path("rebotarm_b601_stl.xml")
data = mujoco.MjData(model)
data.qpos[:] = [0, -0.5, -1.0, 0, 0, 0, 0]
mujoco.mj_forward(model, data)              # 只算运动学，不积分物理
tcp_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "tcp")
pos = data.site_xpos[tcp_id]                # [x, y, z]
rot = data.site_xmat[tcp_id].reshape(3, 3)  # 3x3 旋转矩阵
```

**正/逆运动学**：FK 完全依赖 MuJoCo 自身运动学引擎（`mj_forward`，无外部 IK 库）；IK 用数值方法——基于 Jacobian 的**阻尼最小二乘法（DLS）**，`dq = Jᵀ(J·Jᵀ + λ²I)⁻¹·dx`，避免奇异点爆炸。参数：`ik_iterations=360`、`ik_tolerance=0.004`（4mm 收敛阈值）、`ik_damping=0.035`、`ik_orientation_weight=0.75`。纯位置目标（单位四元数）只解位置，带姿态目标同时优化位置和姿态。

**轨迹插值**：线性插值起停速度突变会抖动；默认 **Smoothstep**（`ratio²·(3-2·ratio)`，起停速度为零）；高精度可用 **Minimum Jerk**（`10r³-15r⁴+6r⁵`，加速度连续）。

**轨迹参数**：`command_hz=60`（指令发送）、`max_joint_speed=1.4 rad/s`（约 80 deg/s 速度上限，`duration` 必须留足余量：最短时间 = max(|q1-q0| / 速度上限)）、`record_hz=30`。控制层级：物理控制环 500 Hz（`mujoco_physics_grasp`，PD 力矩）→ 轨迹控制环 60 Hz（`sim_task_server`，位置目标）→ 状态发布环 30 Hz（`real2sim_sync`）→ 录制采样环 30 Hz。

### 6. 四个 Demo（第 37 章）

| Demo | 目标 | 运行方式 |
|---|---|---|
| 1 正运动学 | 三组关节角算末端位姿 | 无需 ROS2：`source scripts/source_rebotarm_env.sh; python3 demo1_fk.py` |
| 2 逆运动学 | 给定目标求关节角 | 终端 1 启动仿真栈，终端 2 运行 IK 客户端 |
| 3 轨迹控制 | 依次经过 8 个航点，smoothstep 平滑过渡 | Action 接口 `/rebotarm/move_to_pose` |
| 4 简单抓取 | pick-and-place | **需 physics 模式**才能抓住物体 |

```bash
# Demo 2 逆运动学：终端 1 启动仿真 + 终端 2 运行 IK 客户端
./scripts/start_rebot_mujoco_all.sh
source scripts/source_rebotarm_env.sh
python3 demo2_ik.py        # Service /rebotarm/move_to_pose_ik，目标如 (0.34, -0.13, 0.20)

# Demo 4 简单抓取：物理模式（PD 力矩驱动，夹爪闭合靠碰撞力抓住物体）
MUJOCO_GRASP_MODE=physics ./scripts/start_rebot_mujoco_all.sh
source scripts/source_rebotarm_env.sh
python3 demo4_pick_place.py
```

### 7. kinematic 模式 vs physics 模式

| 模式 | 实现 | 特点 |
|---|---|---|
| kinematic | 直接写 `data.qpos` + `mj_forward` | 无物理交互，适合运动学/轨迹调试、纯展示 |
| physics | PD + 重力补偿 `tau = qfrc_bias + kp·(q_target - q) - kd·qvel` + `mj_step` | 可抓取物体，物理交互 |

切换：`MUJOCO_GRASP_MODE=kinematic|physics ./scripts/start_rebot_mujoco_all.sh`。物理模式 PD 参数：`arm_kp=[140,140,110,55,38,28]`、`arm_kd=[7,7,5.5,2.5,1.8,1.4]`、`gripper_kp=1800`、`gripper_kd=18`、`arm_torque_limit=30`（Nm）、`gripper_force_limit=32`（N）、`control_hz=500`；抓取物体被弹飞时降低力矩限幅（见常见问题）。

## Isaac Sim 仿真

### 1. 安装与启动

Isaac Sim 基于 NVIDIA Omniverse，需 RTX GPU。桌面应用从 NVIDIA 官网下载；Python 脚本方式（Isaac Sim 4.x+）：`./python.sh my_script.py`。所有功能通过 Python API（`omni.isaac.*` / `isaacsim.*`）暴露，GUI 操作与脚本操作等价。

### 2. USD 模型基础

| 特性 | URDF | USD |
|---|---|---|
| 格式 | XML | 二进制/文本 |
| 层叠覆盖 | 不支持 | 支持 Layer 引用和覆盖（Reference/Override/Payload/Variant） |
| 碰撞/视觉分离 | `<visual>`/`<collision>` 标签 | Collision API / Mesh API |
| 关节驱动 | 无（需外部控制器） | Joint Drive 属性内建 |
| 物理引擎耦合 | 不耦合 | 可绑定 PhysX 属性 |

reBot Arm 运动链（RS URDF）：`base_link → joint1..joint6（revolute）→ gripper_end（fixed）→ gripper_joint1/gripper_joint2（prismatic）`。六个旋转关节加两个棱柱关节驱动左右夹爪。

### 3. URDF Importer 导入 reBot Arm

菜单路径 `Isaac Utils → Workflows → URDF Importer`，或 Python API：

```python
from isaacsim.import_config.urdf import ImportConfig
from omni.importer.urdf import _urdf

config = ImportConfig()
config.merge_fixed_joints = False        # 保留 fixed joint 结构
config.make_default_prim = True
config.create_physics_scene = False      # 已有场景时不重复创建
config.fix_base = True                   # 底座固定，防止重力坠落
config.default_drive_type = _urdf.UrdfJointTargetType.JOINT_DRIVE_POSITION
_urdf.import_urdf(urdf_path, output_usd_path, config)
```

导入后检查结构：Stage Tree 中 revolute→`PhysicsRevoluteJoint`、prismatic→`PhysicsPrismaticJoint`、fixed→`PhysicsFixedJoint`；碰撞体用 `UsdPhysics.CollisionAPI` 标注、渲染网格是 `UsdGeom.Mesh`（挂 CollisionAPI 的 mesh 才参与物理）。URDF 网格在 `meshes_rs/` 目录，导入器自动解析 `package://rebotarm_bringup/description/meshes_rs/` 前缀，失败时检查 `ROS_PACKAGE_PATH`。

### 4. Articulation Root 与关节 Drive

**Articulation Root**（MuJoCo 没有对应物）：告诉 PhysX 整条运动链用 Featherstone 算法统一求解，而不是独立约束。必须加在**运动链根 link（base_link）**上，放错位置会截断运动链：

```python
from pxr import UsdPhysics
base_link = stage.GetPrimAtPath("/rebotarm_rs/base_link")
UsdPhysics.ArticulationRootAPI.Apply(base_link)
```

**关节 Drive**：Isaac Sim 的 Drive 是关节内建 PD 控制器，力矩在 PhysX 内部计算（`tau = kp·(target-pos) + kv·(target-vel) + feedforward`）。`Stiffness`/`Damping` 对应真机 MIT 模式的 kp/kd，可直接使用真机配置值：

```python
joint = UsdPhysics.Joint.Get(stage, "/rebotarm_rs/base_link/link1/joint1")
drive = UsdPhysics.DriveAPI.Get(joint, "angular")   # 旋转关节 angular，棱柱 linear
drive.GetTargetPositionsAttr().Set([0.0])           # 目标角度
drive.GetTargetVelocitiesAttr().Set([0.0])
drive.GetStiffnessAttr().Set(80.0)                  # kp
drive.GetDampingAttr().Set(5.0)                     # kv
drive.GetMaxForceAttr().Set(36.0)                   # 力矩上限
```

推荐起始刚度/阻尼（对应真机 RS MIT 增益 `mit_kp=[80,150,150,50,50,50]`、`mit_kd=[5,10,10,5,4,4]`）：

| 关节 | Stiffness (kp) | Damping (kd) | Max Force |
|---|---|---|---|
| joint1 | 80 | 5 | 36 |
| joint2 | 150 | 10 | 36 |
| joint3 | 150 | 10 | 36 |
| joint4 | 50 | 5 | 14 |
| joint5 | 50 | 4 | 14 |
| joint6 | 50 | 4 | 14 |

调参原则：先低值确保不振荡，逐步提高刚度，再提阻尼消除残余振荡。**夹爪联动**：Isaac Sim 用 Mimic Joint（MuJoCo 用 `<equality>` 约束）；当前 RS URDF 无 `<mimic>` 标签，需手动配置（`MimicAPI.Apply(left_joint)`，multiplier=1.43，即 `0.0715/0.05`），或在控制代码里按行程比例软件联动。

### 5. Python 控制：Articulation API 与 4 个 Demo

```python
from isaacsim.core.api import World
from isaacsim.core.primitives import Articulation
world = World(stage_units_in_meters=1.0)
world.scene.add_default_ground_plane()   # Z=0 地面碰撞面
robot = Articulation(prim_path="/rebotarm_rs"); world.reset()
```

| Demo | 内容 | 关键 API |
|---|---|---|
| 1 加载 USD | 地面 + 工作台（`FixedCuboid`）+ 任务物体（`DynamicCuboid`）+ 机械臂 | `Articulation(prim_path="/rebotarm_rs")`、`num_joints`、`get_dof_names()` |
| 2 关节状态读取 | 每帧从 PhysX 读铰接体状态数组 | `get_joint_positions()`、`get_joint_velocities()`、`get_local_pose()`（末端位姿） |
| 3 关节位置控制 | 发一次 Drive 目标，PD 环在引擎内部驱动到位 | `set_joint_position_targets(targets)` + `world.step(render=True)` |
| 4 夹爪控制 | 左右行程不同（0.05m / 0.0715m），按同一开合比例缩放 | `positions[arm_joints]=ratio*0.05`、`positions[arm_joints+1]=ratio*0.0715` |

> ⚠️ **关节名称顺序要与真机一致**：`get_dof_names()` 的数组顺序即关节索引顺序（臂关节 + 夹爪关节），与真机 SDK 配置、ROS 话题中的命名必须一一对应，否则关节错位（详见 Real-to-Sim 章节）。

## Real-to-Sim：真实机械臂与仿真机械臂同步（第 39 章，重点）

### 1. 思路与数据流

真机发布关节状态 → 仿真跟随复现。核心链路（RS 工程）：

```text
真实 RobStride 电机 → SocketCAN can0 → MotorBridge SDK 状态缓存
→ HardwareManager._get_arm_state() → ROS JointState 话题（60 Hz）
→ MuJoCo Sync 节点订阅 → MuJoCo qpos 更新 → 虚拟机械臂运动
```

### 2. 三处关节定义映射

真机 SDK 配置、MuJoCo 模型、同步节点**三处的关节名称/顺序必须一致**：

1. 真机 SDK 配置（`rebotarm_rs.yaml`）：`arm: [joint1..joint6]`、`gripper: [gripper]`
2. MuJoCo 模型（`rs_arm.xml`）：`joint1..joint6`（hinge）+ `joint7/joint_left/joint_right`（slide，equality 约束 1:1 联动）
3. 同步节点：`_ARM_JOINTS = tuple(f"joint{index}" for index in range(1, 7))`

同步时**按名称匹配而非按数组索引**（更安全，消息顺序变了也能正确映射）：

```python
values = dict(zip(msg.name, msg.position))
for index, name in enumerate(_ARM_JOINTS):
    if name in values and np.isfinite(values[name]):
        self.target_arm[index] = float(values[name])
```

### 3. DM / RS 单位转换

**臂关节**：DM 和 RS 都是弧度，MuJoCo 也是弧度（`<compiler angle="radian"/>`），**无需转换**。

**夹爪单位差异**（易错点，共四种量）：

| 量 | 范围 | 单位 | 用途 |
|---|---|---|---|
| RS 夹爪电机角度 | 0 ~ 5 | rad | 真机 SDK 命令与反馈 |
| 网页/任务夹爪开口宽度 | 0 ~ 0.0715 | m | 用户命令语义 |
| ROS 单指状态 | 0 ~ 0.045 | m | 状态发布器映射后的视觉位移 |
| MuJoCo 夹爪位移 | 0 ~ 0.05 | m | 仿真 joint7 滑动行程 |

转换链路（RS）：`电机反馈 0-5 rad → 比例映射 → ROS 单指 0-0.045 m → 比例映射 → MuJoCo joint7 0-0.05 m → equality 约束联动 joint_left/joint_right`。夹爪看起来超行程或不对称，根因几乎都是把四种量当成同一单位。

DM 夹爪硬件电机位置为 **-5.0（全开）~ 0（全闭）rad**，对应仿真夹爪关节 **0.045（单侧全开）~ 0（全闭）**（教程第 34 章 MoveIt 章节的仿真值/硬件值对照表，两套参数不同，真机执行前需确认 `hardware_open_gripper_position` / `hardware_closed_gripper_position`，默认开 `-5.0`、闭 `0.0`）。

### 4. 通信选型：ROS2 vs UDP

| 特性 | ROS2 话题 | UDP |
|---|---|---|
| 延迟 | 毫秒级（有 DDS 中间件开销） | 最低，微秒级 |
| 可靠性 | 可配置 BEST_EFFORT / RELIABLE | 需自行实现 |
| 多订阅 | 原生支持 | 需自行实现广播 |
| 调试工具 | `ros2 topic echo / hz` | 需自行实现 |
| 适用场景 | 多节点协作、需要生态 | 点对点超低延迟 |

本工程场景（60 Hz 状态、人眼可接受）选 **ROS2**：`sensor_msgs/JointState` 标准消息 + `qos_profile_sensor_data`（BEST_EFFORT）+ rosbridge 直接桥接 WebSocket。

话题拓扑：`/rebotarm/joint_states`（真机控制器发布，60 Hz）→ MuJoCo Sync 节点订阅 → `/rebotarm/mujoco/joint_states`（MuJoCo 发布，250 Hz）→ rosbridge WebSocket → 浏览器。

命名空间隔离：真机 `/rebotarm`（`scripts/start_rs_hardware.sh`）；Fake Driver + MuJoCo `/rebotarm_rs`（`scripts/start_rs_sim.sh`）；MuJoCo 跟随真机 `/rebotarm`（`scripts/start_rs_mujoco_follow.sh`）。`rs_env.sh` 将 DDS 发现范围限制为本地主机，避免 Wi-Fi 漫游后节点互相找不到：`export ROS_AUTOMATIC_DISCOVERY_RANGE="${REBOTARM_ROS_DISCOVERY_RANGE:-LOCALHOST}"`。

### 5. 状态刷新与延迟

频率链（排查卡顿的基础）：RS 真机控制循环 125 Hz（MIT 指令）→ 同步硬件反馈查询 20 Hz（刷新缓存）→ ROS 关节状态发布 60 Hz → MuJoCo 仿真同步 250 Hz → 浏览器接收 MuJoCo 状态 ≤ 25 Hz（rosbridge 订阅节流 40 ms）→ 浏览器绘制约 60 Hz（requestAnimationFrame）。

关键设计：**异步缓存与反馈频率分离**——60 Hz 发布中只有 1/3 帧（20 Hz）触发同步 CAN 读取，其余帧直接返回缓存（原子替换的 NumPy 快照），既保证高刷新率又不占满 CAN 总线；实时控制环绝不做同步 CAN 参数查询。**MuJoCo 侧陈旧超时**：`stale_timeout=1.0 s` 内收不到 JointState 就停止更新，防止真机断连后仿真用旧数据运动。

延迟排查沿链路逐层测量：① 真机反馈层 `ros2 topic hz /rebotarm/joint_states` 是否稳定 60 Hz → ② MuJoCo 同步层 `last_input_time` 是否持续更新 → ③ 网页接收层 rosbridge 节流 → ④ 显示插值层（浏览器 32-120 ms 插值）。

### 6. 同步程序安全设计（重要）

| 机制 | 说明 |
|---|---|
| **硬件确认门控** | 启动真机控制器要求显式确认：`REBOTARM_RS_HARDWARE_CONFIRM=I_UNDERSTAND_RS_WILL_MOVE`，防止误操作导致机械臂运动 |
| **进程互斥锁** | `flock` 防止两个控制器同时竞争电机；识别 Ctrl+Z 暂停的控制器，清理 Fast DDS 共享内存残留 |
| **状态机仲裁** | 状态机 `IDLE / LOWLEVEL_STREAMING / TRAJ_RUNNING / GRAVITY_COMP / SAFE_HOMING`，每个状态只接受特定命令，其余拒绝（如重力补偿期间拒绝低级流命令） |
| **安全回零** | 失能前若不在零位附近（角度 > 2° 或速度 > 0.15 rad/s），先进入 `SAFE_HOMING`：清旧目标 → 关夹爪 → 回零 → 验证到位 → 才失能 |

> ✅ 显示跟随（只订阅 JointState，不发送力矩、不打开 SocketCAN）**无需硬件确认**：MuJoCo wrapper only subscribes to the real JointState topic and never sends torque commands or opens SocketCAN, so no hardware-confirm flag is required.

### 7. 三个 Demo

**Demo 1：真机同步到 MuJoCo**

```bash
# 终端 1：真机控制器（需要硬件确认）
REBOTARM_RS_HARDWARE_CONFIRM=I_UNDERSTAND_RS_WILL_MOVE ./rebotarm start rs
# 或：REBOTARM_RS_HARDWARE_CONFIRM=I_UNDERSTAND_RS_WILL_MOVE ./scripts/start_rs_hardware.sh
# 终端 2：MuJoCo 跟随（只订阅，无需硬件确认）
./scripts/start_rs_mujoco_follow.sh
# 终端 3：网页
./rebotarm start web
```

RS 需先配置 CAN 接口：`sudo ip link set can0 down 2>/dev/null || true && sudo ip link set can0 type can bitrate 1000000 && sudo ip link set can0 up`。此 Demo 安全的原因：MuJoCo 跟随节点是被动观察者，崩溃也不影响真机。

**Demo 2：真机同步到 Isaac Sim**：`真实 reBot Arm → Joint State Reader → UDP/ROS2 → Isaac Sim → 数字机械臂同步`（关节映射/单位转换/安全设计同上，直接迁移到 Isaac Sim 场景）。

**Demo 3：重力补偿手动示教同步**：网页启动重力补偿 → 真机进入 `GRAVITY_COMP` → 用户手动拖动真臂 → JointState 照常发布 → 虚拟臂实时复现。三终端与 Demo 1 相同，浏览器打开 `http://localhost:3002`。

网页操作：命名空间选"RS 真机（`/rebotarm`）"→ ROS WebSocket 填 `ws://localhost:9090` 并连接 → 勾选控制锁 → 使能 → 点击"重力补偿启动"（调用服务 `/rebotarm/gravity_compensation/start`，`std_srvs/Trigger`；另有 `/stop`、`/status`）。

重力补偿原理：从当前姿态 `q_hold` 起步（不回零）→ Pinocchio 计算重力力矩 → smoothstep 0.5 s 内从硬增益 `[80,150,150,50,50,50]`/`[5,10,10,5,4,4]` 渐变到柔顺增益 `kp=2, kd=1` → 125 Hz 循环中目标跟随测量角（`q_target=q`）+ 重力前馈（用 20 Hz 缓存，不做同步 CAN 读）。用户拖到哪臂跟到哪，松手后悬停。

> ⚠️ **重力补偿期间安全规则**：`GRAVITY_COMP` 状态下控制器拒绝所有网页关节命令、TCP 拖拽、轨迹回放和夹爪命令，只有"停止重补"按钮和失能请求能打断。拖动时扶稳机械臂、手远离夹爪，完成示教后点击"重力补偿停止"回到位置保持模式。

## 常见问题

- **MuJoCo 版本检查**：`python3 -c "import mujoco; print(mujoco.__version__)"` 输出 3.x 正常；报 `ModuleNotFoundError` 说明未安装或 venv 未 source。
- **viewer 黑屏/崩溃**：`export MUJOCO_GL=egl`（推荐，无显示器）/ `glfw`（桌面）/ `osmesa`（软件渲染，最兼容）。
- **滑块 GUI 无法控制**：先确认 sim 已启动；检查 fake 驱动 `ros2 topic echo /rebotarm/joint_states --once`、real2sim 订阅话题名（默认 `/rebotarm/joint_states`）、viewer 终端应显示 "MuJoCo real2sim ready"；话题名不匹配用 `REAL2SIM_JOINT_STATE_TOPIC=... ./scripts/start_real2sim.sh` 指定。
- **夹爪只动一边**：检查 `joint_map_kinematic.yaml` 是否正确配置 `finger_left → finger_right` 映射（`scale: -1.0`）。
- **抓取时物体被弹飞**：PD 力矩过激，降低力矩限幅：`ros2 launch rebotarm_mujoco mujoco_physics_grasp.launch.py arm_torque_limit:=10.0`，或增大下降 `duration`。
- **IK 求解失败（error > 4mm）**：目标超出工作空间（臂展约 50cm）/ 奇异点 / 限位阻止收敛；调整目标或 `ros2 launch rebotarm_mujoco mujoco_sim_task_server.launch.py ik_tolerance:=0.010 ik_damping:=0.05`。
- **同步延迟大**：按频率链逐层排查（`ros2 topic hz /rebotarm/joint_states` 是否 60 Hz、MuJoCo `stale_timeout`、rosbridge 节流、网络/DDS 发现范围）。
- **`mj_forward` vs `mj_step`**：`mj_forward` 只算运动学（FK/IK 用），`mj_step` 做物理积分（仿真用）。

## 参考

- 官方 Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- MuJoCo：<https://mujoco.org/> ｜ Isaac Sim：<https://docs.isaacsim.omniverse.nvidia.com/>
- GitHub：<https://github.com/Seeed-Projects/reBot-DevArm>
- 配套教程：本仓库同目录《Seeed具身智能入门8个阶段40章节》第 35 章（仿真基础）、第 36 章（MuJoCo 运行）、第 37 章（运动学与轨迹控制）、第 38 章（Isaac Sim）、第 39 章（Real-to-Sim）
- 相关技能：`rebot-arm-safety`（真机操作前必读）｜ `rebot-arm-ros2`（Topic/Service 接口）｜ `rebot-arm-troubleshooting`（故障排查）
