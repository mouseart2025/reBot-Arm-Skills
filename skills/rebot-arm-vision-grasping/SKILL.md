---
name: rebot-arm-vision-grasping
description: 让 reBot Arm（B601-DM / B601-RS）通过 RGB-D 深度相机实现自主视觉抓取：相机选型与安装（RealSense D435i/D405、Orbbec Gemini2）、YOLO 目标检测与实例分割、手眼标定（ArUco）、运行抓取程序（reBot-DevArm-Grasp 的 main.py/set.py）、位置补偿与抓取精度调优、GraspNet 三维点云抓取（选修）。当用户需要"让机械臂自动识别并抓取物体"时使用本技能。
---

# reBot Arm RGB-D 视觉自主抓取

## 简介
本技能指导 reBot Arm（B601-DM / B601-RS）搭建一套完整的**视觉自主抓取**系统：RGB-D 深度相机观察工作区域 → YOLO 识别目标 → 深度信息定位 → 手眼标定坐标转换 → 机械臂自动抓取与放置。核心代码来自官方仓库 [Seeed-Projects/reBot-DevArm-Grasp](https://github.com/Seeed-Projects/reBot-DevArm-Grasp)（含 `main.py` 主抓取、`set.py` 抓取与放置），并配套本仓库教程第 27/28/29 章的理论与实践。
> 分工标记：🤖 AI 执行（终端可自动化）｜ 👤 用户执行（GUI/网页/按键/插线/物理操作）｜ 🔀 人机协作（sudo 需用户密码或需用户确认）

## 何时使用
- 用户想让机械臂"**自动识别并抓取物体**"（视觉抓取 / 自主抓取 / 抓取放置）
- 用户需要选型、安装或调试 RGB-D 深度相机（RealSense D435i/D405、Orbbec Gemini2）
- 用户需要做**手眼标定**（ArUco、TSAI 方法）或解决"抓偏、抓歪、抓不到"
- 用户想体验 **GraspNet 三维点云六自由度抓取**（选修）

## 前置条件
| 项目 | 要求 |
|------|------|
| 机械臂 | reBot Arm B601（DM / RS 任一），已完成电机标定、可正常控制 |
| 通信 | USB2CAN 适配器连接机械臂 CAN 总线（DM 串口 / RS SocketCAN 见 `rebot-arm-environment-setup`） |
| 深度相机 | Orbbec Gemini2 或 Intel RealSense D435i / D405，通过 **USB 3.0** 连接主机 |
| 主机 | Ubuntu 22.04+，Python 3.10+，x86_64；GraspNet 选修需 NVIDIA GPU 与 CUDA |
| 安全 | 已阅读 `rebot-arm-safety`（本技能命令均涉及真机运动） |

## 0. 安全要点
> ⚠️ 运行本技能任何程序前，先完成 `rebot-arm-safety` 检查清单。视觉抓取是**全自动运行**，机械臂自行运动，风险高于手动调试。

1. **自动运行前必须先空载验证轨迹**：第一次运行 `main.py`/`set.py` 前移开目标物体空跑一次，确认路径、抓取姿态与预备位安全。
2. **保持距离**：抓取/放置程序运行时人员保持 **≥1 m** 距离，手远离夹爪开口（夹爪闭合力大，可能夹伤）。
3. **异常立即断电**：出现剧烈抖动、撞限位、异响、冒烟、跌落，第一步是**断电**（电源开关放手边），而不是去"按停程序"。
4. 运行前确认机械臂周围 50 cm 内无人员与障碍物，夹爪无夹持物残留；注意线束与相机线缆不要被绞入。

## 1. 视觉抓取完整链路（理论速览）
```text
RGB 图像采集 → 目标检测/实例分割 → 匹配对应像素深度信息
→ 像素坐标→相机三维坐标 → 手眼标定坐标转换（相机→机械臂）→ 运动规划 + 抓取执行
```

### 1.1 为什么需要深度信息
二维坐标 `(u,v)` 只告诉机器人"目标在图片哪里"，无法告诉它距离、高度、是否在工作范围内。RGB-D 数据 = RGB（是什么）+ Depth（在哪里）。深度相机三大类：

| 类型 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| 双目相机 | 左右眼视差计算深度 | 不需主动发光、适合较远距离 | 纹理太少（白墙 + 纯色物体）时计算困难 |
| 结构光相机 | 主动投射点阵/条纹/网格，依形变测距 | 近距离精度高 | 受强光、室外环境影响 |
| TOF 相机 | 光飞行时间测距 | 实时性强 | 受反光、透明物体、多路径反射影响 |

### 1.2 像素坐标 → 三维坐标（相机内参）
相机**内参**描述"三维→二维"投影关系，含 `fx, fy, cx, cy` 与畸变系数 `k1,k2,k3,p1,p2`，实际工程中需**先去畸变**再计算。已知像素 `(u,v)` 与深度 `Z`：

```text
X = (u - cx) * Z / fx ； Y = (v - cy) * Z / fy ； Z = Depth
```

涉及四个坐标系：图像（像素 `u,v`）、相机（`Xc` 右、`Yc` 下、`Zc` 前）、机器人（机械臂控制使用）、工具（末端夹爪）。

### 1.3 YOLO 目标检测与抓取点
- YOLO（You Only Look Once）：一次输入整图，同时预测**类别、位置、置信度**，实时性强，适合机器人应用；输出 `类别 + Bounding Box + confidence`。
- **检测框不是抓取点**（如杯子检测框中心是杯身，最佳抓取点在杯柄附近）。抓取候选方法：**中心点抓取**（规则物体如方盒）、**关键点检测**（杯柄）、**结合三维信息**（深度找最高点/平面中心/可抓取区域）。
- **预训练模型**可直接用于快速验证 Demo；对工业零件等特殊目标识别不准时需**定制训练**（数据采集 → Bounding Box 标注 → 训练 `best.pt` → 部署替换）。

## 2. 相机选型与安装
### 2.1 相机选型（官方推荐） 👤
| 相机 | 特点 | 适用 |
|------|------|------|
| **RealSense D405** | 短距离双目深度相机，高精度近距离，典型工作范围 **7 cm – 50 cm** | 桌面级精密抓取 |
| **RealSense D435i** | 深度 + RGB + IMU，中近距离 | 3D 重建、SLAM、环境感知 |
| **Orbbec Gemini2** | RGB 与深度同步、深度-彩色对齐精确，立体深度 + 内置 6 轴 IMU | 目标检测、三维感知、抓取 |

> 腕部相机支架需自行 **3D 打印**：`D435_Gemini2_Mount.step`、`D405_305_Mount.step`（图纸见配套教程，没有打印机的可联系官方客服）。

### 2.2 接线与权限 👤/🔀
1. 深度相机通过 **USB 3.0** 直插主机（避免 USB HUB 引入不稳定）；USB2CAN 适配器连接机械臂 CAN 总线并插入主机 USB 口。
2. 确认 24V（DM）/ 48V（RS）电源、相机、机械臂连接可靠。
3. 配置设备权限：
```bash
sudo chmod a+rw /dev/bus/usb/*/*   # 深度相机 USB 权限
sudo chmod 666 /dev/ttyUSB0        # USB2CAN（端口号按实际调整）
```

### 2.3 安装相机 SDK 🤖/🔀
**RealSense D435i / D405（依赖 `pyrealsense2`）：**
```bash
pip install pyrealsense2
python -c "import pyrealsense2; print('pyrealsense2 OK')"
```
需要完整工具链或 udev 规则时，参考 RealSense SDK 官方文档安装 `librealsense2`。

**Orbbec Gemini2（依赖 `pyorbbecsdk`，SDK v2 的 Python 版）：**
```bash
# 方式一：pip 预编译包（推荐）
pip install pyorbbecsdk2
python -c "import pyorbbecsdk; print('pyorbbecsdk OK')"

# 方式二：源码安装
sudo apt-get install -y cmake build-essential libusb-1.0-0-dev
cd sdk && git clone https://github.com/orbbec/pyorbbecsdk.git && cd pyorbbecsdk && pip install -e .
```
中国大陆用户可用镜像：`git clone https://gitee.com/orbbecdeveloper/pyorbbecsdk.git`。源码安装需先经 CMake 编译生成原生扩展（确保 `install/lib` 中有 `pyorbbecsdk*.so`）再 `pip install -e .`。

**可选**：首次使用建议安装 Orbbec udev 规则，并用 OrbbecViewer 验证相机：
```bash
sudo bash scripts/install_udev_rules.sh && sudo udevadm control --reload-rules && sudo udevadm trigger
```

## 3. 环境安装与配置
### 3.1 克隆仓库并创建 conda 环境 🤖
```bash
git clone https://github.com/Seeed-Projects/reBot-DevArm-Grasp.git rebot_grasp
cd rebot_grasp
conda env create -f environment.yml
conda activate rebotarm
```
> 教程提示：如想用其他环境名，将命令中的 `rebotarm` 替换为自定义名称（环境由 `environment.yml` 定义，以仓库为准）。

### 3.2 安装机械臂控制库 🤖
```bash
git clone https://github.com/vectorBH6/reBotArm_control_py.git sdk/reBotArm_control_py
cd sdk/reBotArm_control_py
pip install -e .
cd ../..
```
> ⚠️ 若报 `Multiple top-level packages discovered in a flat-layout`，在 `reBotArm_control_py` 的 `pyproject.toml` 中加入显式包发现配置后重装：
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["reBotArm_control_py*"]
```
视觉抓取程序会读取该 SDK 配置，自动选择对应的机械臂控制模式与夹爪参数。

### 3.3 配置机械臂型号（DM / RS 差异，重点） 🤖/🔀
在 `rebot_grasp/sdk/reBotArm_control_py/config/rebotarm.yaml` 中修改 `hardware_yaml`：
```yaml
# reBotArm 全局配置（电机类型、通信参数、PID 等）
hardware_yaml: "rebotarm_rs.yaml"   # B601 RS
# hardware_yaml: "rebotarm_dm.yaml" # B601 DM
```
| 型号 | 供电 | hardware_yaml | 通信 |
|------|------|---------------|------|
| B601-DM | 24V DC | `rebotarm_dm.yaml` | 确认 SDK 配置中串口桥接器设备路径与实际一致 |
| B601-RS | 48V DC | `rebotarm_rs.yaml` | 运行标定/抓取脚本前先启动 CAN 接口 |

**RS 运行前启动 CAN：**
```bash
sudo ip link set can0 down 2>/dev/null
sudo ip link set can0 type can bitrate 1000000 restart-ms 100
sudo ip link set can0 up
ip -details link show can0
```

### 3.4 安装深度相机 SDK 🤖
按 §2.3 安装对应相机 SDK；若当前环境已能正常导入相机驱动可跳过。

## 4. 手眼标定（抓取前必做）
### 4.1 为什么需要手眼标定
相机有自己的坐标系，机械臂也有自己的坐标系，而机械臂控制使用**机器人坐标**，因此必须求解相机系 ↔ 机器人系的变换——即**手眼标定**（数学基础 `AX=XB`，用多组机械臂位姿 + 视觉观测数值求解变换矩阵 X）。两种结构：

| 结构 | 安装方式 | 特点 | 应用 |
|------|----------|------|------|
| **Eye-in-Hand**（本项目使用） | 相机装在机械臂末端 | 相机随臂运动 | 精密抓取、装配 |
| Eye-to-Hand | 相机固定 | 视野稳定 | 流水线 |

### 4.2 ArUco 标定板 👤
- 仓库根目录提供可直接打印的标定板：`aruco100x100.pdf`（100 mm × 100 mm，对应 `marker_length_m: 0.1`）、`arcuo30x30.pdf`。
- **避免缩印**：打印后用直尺实测，确认 ArUco 标定板实际尺寸为 **100 mm × 100 mm**，否则标定结果整体偏移。
- 标定流程：固定标定板（Eye-in-Hand 时固定在桌面视野内）→ 机械臂运动多个位置 → 相机拍摄 ArUco → 记录机器人姿态 → 计算转换关系 → 得到标定矩阵。

### 4.3 标定矩阵与 TSAI 方法
- 标定矩阵为 4×4 齐次变换矩阵 `[R T; 0 1]`：`R` 旋转（方向变化）、`T` 平移（位置变化），作用 `P_robot = T · P_camera`，把相机系下点变换到机器人系，机械臂才能运动。
- 本项目使用 **TSAI 手眼标定方法**（Eye-in-Hand），配置见 `config/default.yaml`：
```yaml
calibration:
  aruco:
    marker_length_m: 0.1
    dict_id: 0
    target_marker_id: 0
  hand_eye_method: TSAI
```

### 4.4 运行标定程序 🤖/👤
```bash
python scripts/collect_handeye_eih.py            # 自动模式
python scripts/collect_handeye_eih.py --manual   # 手动模式
```
- **自动模式**：机械臂自动遍历 **50 个预设位姿**，检测到 ArUco 稳定后自动采样；正常结束或中途打断都会尝试计算并保存标定结果。至少 **5 个样本，建议 ≥15 个**。
- **手动模式**：机械臂进入重力补偿状态，推到合适视角后按 `Enter` 采集，`c` 或 `q` 结束并计算。
- 结果保存在 `config/calibration/<camera_type>/`：`intrinsics.npz`（相机内参）、`hand_eye.npz`（手眼标定结果），相机类型目录如 `realsense_d435i`、`realsense_d405`、`orbbec_gemini2`。
> ⚠️ 标定完成后**相机位置不可移动**（含支架松动），否则标定失效；相机安装误差是抓取失败的主要来源之一。
> 状态记忆：标定完成后更新 memory/local-machine-env.md（见 AGENTS.md 第 3 节）。

## 5. 运行抓取程序
> 运行前：完成 `rebot-arm-safety` 检查清单、§3.3 型号配置正确、§4 标定完成；**第一次运行先空载验证轨迹**。

### 5.1 主抓取程序 `scripts/main.py` 🤖/👤
```bash
python scripts/main.py
```
完整流水线（教程原文）：
1. 初始化 RGB-D 相机，确认图像流可用；
2. 机械臂与夹爪使能，移动到预备高位；
3. 实时相机预览 + YOLO 目标检测与实例分割；
4. **OBB 短轴估计夹爪朝向**，**深度分位数估计抓取高度**；
5. 按 `G` 冻结帧，经手眼变换计算机械臂目标位姿；
6. 机械臂移动到预抓取点 → 下降 → 夹爪闭合 → 提升 → 回预备位。

### 5.2 抓取与放置程序 `scripts/set.py` 🤖/👤
```bash
python scripts/set.py
```
流程：相机与机械臂初始化并移动到预备点位 → 实时预览 + YOLO 检测与实例分割 → 按 `G` 冻结帧并手眼变换计算目标位姿 → 移动抓取（如香蕉）并抬高 → 放置到盒子内并回归初始姿态 → 按 `Q` 退出系统，机械臂回归零点。
> 键盘操作：`G` 冻结帧触发抓取，`Q` 退出并回零。代码细节（相机驱动、YOLO 权重、夹爪力控状态机等）以仓库源码为准。

### 5.3 其他辅助脚本 🤖
| 脚本 | 用途 |
|------|------|
| `scripts/object_detection.py` | 纯 YOLO 检测 Demo，实时显示检测框与置信度，无抓取逻辑 |
| `scripts/ordinary_grasp_pipeline.py` | 简化抓取测试，不依赖机械臂，仅验证 OBB 抓取姿态估计与可视化 |

## 6. 位置补偿与精度调优 🤖/👤
校准之后抓取精度仍不满足需求时，打开 `config/default.yaml`，修改 `calibration.hand_eye_compensation_m` 的 X（前后）、Y（左右）、Z（高低）参数：
```yaml
calibration:
  aruco:
    marker_length_m: 0.1
    dict_id: 0
    target_marker_id: 0
  hand_eye_method: TSAI
  hand_eye_compensation_m:
    x: 0.00
    y: 0.00
    z: -0.02
```
**常见误差来源与对策**（教程第 28 章）：
| 误差来源 | 表现 | 对策 |
|----------|------|------|
| 视觉定位误差（深度误差） | 抓偏 | 检查 Depth 图像空洞/噪声、光照与反光，物体处于相机最佳工作距离 |
| 手眼标定偏差 | 抓偏/抓歪 | 增加标定样本（≥15）、固定标定板、标定后相机不可移动 |
| 相机安装误差 | 系统性偏移 | 紧固支架，用 `hand_eye_compensation_m` 补偿 |
| 机器人自身误差（关节误差、机械间隙） | 抓不到 | 检查机械臂标定与零点，低速运行 |

## 7. GraspNet 三维点云抓取（选修）
### 7.1 概念
GraspNet 是基于**点云**的六自由度抓取姿态生成与评估框架：输入 RGB-D → 点云 → GraspNet → 抓取姿态，输出 `G = (x, y, z, roll, pitch, yaw)`：`x,y,z` 为夹爪位置，`roll,pitch,yaw` 为夹爪朝向。相比 YOLO + OBB 二维方案，对抓取姿态估计更准确。

### 7.2 配置 GraspNet 🤖
1. 确认 `nvcc` 可用且 CUDA 版本与 PyTorch 编译版本一致：
```bash
nvcc --version
python -c "import torch; print(torch.__version__, torch.version.cuda)"
```
2. 不一致时安装匹配的 CUDA 编译器（示例为 PyTorch 显示 13.0）：
```bash
conda install -c nvidia cuda-nvcc=13.0
```
> ⚠️ 两者必须一致，否则编译 `pointnet2` / `knn` 报 `The detected CUDA version (...) mismatches the version that was used to compile PyTorch (...)`。

3. 克隆并编译 graspnet-baseline：
```bash
cd sdk
git clone https://github.com/graspnet/graspnet-baseline.git
cd graspnet-baseline
pip install open3d tensorboard Pillow tqdm

# 编译本地算子前配置 CUDA 编译路径
export CUDA_HOME=$CONDA_PREFIX
export TORCH_CUDA_ARCH_LIST="12.0"
export CPATH=$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cu13/include:$CPATH
export CPLUS_INCLUDE_PATH=$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cu13/include:$CPLUS_INCLUDE_PATH
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib/python3.10/site-packages/nvidia/cu13/lib:$CONDA_PREFIX/lib:$LD_LIBRARY_PATH

cd pointnet2 && pip install . --no-build-isolation
cd ../knn && pip install . --no-build-isolation
cd ..

# 安装 GraspNet API
git clone https://github.com/graspnet/graspnetAPI.git
cd graspnetAPI
sed -i "s/'sklearn'/'scikit-learn'/" setup.py
pip install .
cd ../../..
```
> 建议用 `pip install . --no-build-isolation` 而非 `python setup.py install`，让扩展在当前 conda 环境中复用已安装的 PyTorch 与 CUDA 配置编译。报 `fatal error: cusparse.h: No such file or directory` 时，先 `find $CONDA_PREFIX -name cusparse.h`，把含该头文件的目录加入 `CPATH`。

4. 配置预训练模型：下载 GraspNet 官方权重 `checkpoint-rs.tar`（见 graspnet-baseline 仓库），放到 `sdk/graspnet-baseline/checkpoints/checkpoint-rs.tar`，并在 `config/default.yaml` 确认：
```yaml
graspnet:
  checkpoint: "checkpoint-rs.tar"
```
> `checkpoint` 支持三种写法：仅文件名自动从 `sdk/graspnet-baseline/checkpoints/` 查找；相对路径按项目根目录解析；绝对路径直接使用。

### 7.3 运行与调试 🤖/👤
```bash
python scripts/graspnet_camera_demo.py                # 仅相机估计，不连机械臂
python scripts/grasp.py --dry-run                     # 只打印目标位姿与候选筛选结果
python scripts/grasp.py --target-class "light blue coffee cup"
```
- `graspnet_camera_demo.py`：YOLO 检测框选择目标区域，从 GraspNet 全场景候选中筛选目标 bbox 内可行夹取；按 `G`/`Space` 推理、`R` 恢复预览、`Q`/`Esc` 退出，推理后可用 Open3D 查看点云与夹取候选。
- `grasp.py`：接入机械臂执行流程，经手眼标定转换到基坐标系，检查 IK 可达性后执行预夹取、夹取、退回；**调试时先 `--dry-run`**。

## ✅ 验证与预期结果

| 运行 | 期望结果 | 失败处理 |
|------|---------|---------|
| `python -c "import pyrealsense2; ..."` / `python -c "import pyorbbecsdk; ..."`（相机 SDK 验证） | 输出 `pyrealsense2 OK` / `pyorbbecsdk OK` | 检查 USB 3.0 直插与权限（`sudo chmod a+rw /dev/bus/usb/*/*`），重装对应 SDK |
| `python scripts/collect_handeye_eih.py`（自动模式，样本 ≥15） | 生成 `config/calibration/<camera_type>/hand_eye.npz` 与 `intrinsics.npz`（标定矩阵） | 固定标定板（实测 100 mm × 100 mm 防缩印）、增加标定样本 |
| `python scripts/main.py` / `python scripts/set.py`（按 `G` 触发） | 识别目标并连续多次抓取成功、位置一致；`set.py` 将物体放置到盒子 | 用 `calibration.hand_eye_compensation_m` 的 x/y/z 补偿；检查 Depth 空洞/噪声 |

## 常见问题
- **相机读不到**：检查 USB 3.0 直插与权限（`sudo chmod a+rw /dev/bus/usb/*/*`）；确认 SDK 导入成功（`import pyrealsense2` / `import pyorbbecsdk`）；用 OrbbecViewer / realsense-viewer 验证深度流。
- **手眼标定误差大**：样本数 ≥15；标定板贴平固定；直尺验证标定板实际 100 mm × 100 mm（防缩印）；标定后相机（含支架）不可移动。
- **抓取位置偏移**：先观察偏移方向，再用 `config/default.yaml` 的 `calibration.hand_eye_compensation_m` 的 x/y/z 补偿（X 前后、Y 左右、Z 高低）。
- **YOLO 检测不准**：先用 `scripts/object_detection.py` 单独验证；换更强预训练模型；特殊目标需定制训练（数据采集 → 标注 → 训练 `best.pt` → 部署）。
- **Depth 图像有空洞/噪声**：避免强光直射与反光物体；调整相机高度、角度、工作距离，保证目标完整出现在视野内且处于相机最佳测距范围。

## 参考
- 官方仓库：<https://github.com/Seeed-Projects/reBot-DevArm-Grasp>
- 机械臂控制库：<https://github.com/vectorBH6/reBotArm_control_py>
- Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- Orbbec SDK：<https://github.com/orbbec/OrbbecSDK_v2> ｜ pyorbbecsdk：<https://github.com/orbbec/pyorbbecsdk>
- RealSense SDK：<https://github.com/realsenseai/librealsense>
- graspnet-baseline：<https://github.com/graspnet/graspnet-baseline> ｜ graspnetAPI：<https://github.com/graspnet/graspnetAPI>
- 配套教程：本地参考教程《Seeed具身智能入门8个阶段40章节》（未随本仓库发布）第 27 章（机器人视觉与三维感知）、第 28 章（目标检测与手眼标定）、第 29 章（reBot Arm 自主视觉抓取）
- 相关技能：`rebot-arm-safety`（必读）｜ `rebot-arm-environment-setup` ｜ `rebot-arm-motor-config` ｜ `rebot-arm-troubleshooting`
