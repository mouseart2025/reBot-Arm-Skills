---
name: rebot-arm-teleoperation
description: 配置并启动 reBot Arm（B601-DM / B601-RS）与 reBot Arm 102 Leader 主臂的 LeRobot 主从遥操作：安装 LeRobot 环境、校准 Follower 臂与 Leader 臂、启动 lerobot-teleoperate、接入相机、理解控制频率与延迟。当用户需要"用主臂拖动控制从臂"、遥操作采集前校准、或解决"从臂不跟随/延迟大"问题时使用本技能。
---

# LeRobot 主从遥操作（Leader / Follower 校准与启动）

## 简介

本技能完成 reBot Arm（B601-DM / B601-RS）与 reBot Arm 102 Leader 示教主臂的 **LeRobot 主从遥操作**：从安装 LeRobot 环境、校准 Follower 从臂与 Leader 主臂，到启动 `lerobot-teleoperate` 实现"人握主臂拖动、从臂实时跟随"，并支持接入相机与调优控制频率。遥操作与数据采集共用同一条硬件链路，本技能是后续采集、训练的基础（见 `rebot-arm-data-collection`）。

## 何时使用

- 用户想"用主臂拖动控制从臂"（Leader/Follower 主从遥操作）
- 遥操作或数据采集前需要校准 Follower 从臂与 Leader 主臂
- 从臂不跟随、延迟大、控制频率异常
- 需要接入相机并验证画面

## 前置条件

- 已确认型号：**DM**（24V、串口 `/dev/ttyACM0`、达妙电机）或 **RS**（48V、SocketCAN `can0`、灵足电机）——两者命令结构相同，仅 robot 参数不同
- 从臂（B601-DM / B601-RS）已组装、**接线并供电**；主臂（reBot Arm 102）已接 **USB 转 UART 模块**（通常映射为 `/dev/ttyUSB*`）
- 已搭建基础环境（Miniforge/conda + motorbridge + 通信接口），见 `rebot-arm-environment-setup`
- 任何真机运动前先完成 `rebot-arm-safety` 检查清单

## 安全要点（重要）

> ⚠️ 遥操作过程中如果**主从臂电源脱落、电源接触不良、信号线脱落**：必须先**停止代码** → 机械臂恢复到**初始 0 点位置** → 再**通上电源**重新运行程序，避免数据错乱导致机械臂失控造成危险。

> ⚠️ 首次运行遥操作**必须有人值守，手放在电源开关旁**；先慢速验证 Leader→Follower 的映射方向与范围，再正常操作。任何异常（剧烈抖动、撞限位、异响）第一步是断电，紧急流程见 `rebot-arm-safety`。

> ⚠️ 校准过程中机械臂会**使能运动**：手远离夹爪开口与关节运动范围，机械臂周围 50 cm 内无人员与障碍物。

## 1. 环境安装

> 后续所有流程都必须在 conda 虚拟环境中进行；不要使用虚拟机或 WSL，官方建议 Ubuntu 22.04 物理机。

**第 1-2 步**：克隆 Seeed 的 LeRobot 仓库并安装环境：

```bash
mkdir ~/rebot_lerobot && cd ~/rebot_lerobot
git clone https://github.com/Seeed-Projects/lerobot.git

conda create -y -n rebot_arm python=3.12   # 教程原文此处有笔误（rebot_armpython），正确写法为 rebot_arm
conda activate rebot_arm                    # 每次打开新终端都要重新激活
pip install -e ./lerobot
pip install lerobot-teleoperator-rebot-arm-102   # Leader 主臂插件
pip install lerobot-robot-seeed-b601             # B601 从臂插件
pip install motorbridge
conda install ffmpeg -c conda-forge              # 视频编解码依赖
```

> 版本提示：默认安装 ffmpeg 7.X（支持 libsvtav1 编码器），可用 `ffmpeg -encoders | grep svtav1` 检查；版本冲突时可指定 `conda install ffmpeg=7.1.1 -c conda-forge`。

**第 3 步**：Nvidia Jetson（JetPack 6.0+）特殊配置（电脑端跳过；需先装适配 Jetson 的 PyTorch-gpu 与 Torchvision）：

```bash
conda install -y -c conda-forge "opencv>=4.10.0.84"
conda remove opencv
pip3 install opencv-python==4.10.0.84
conda install -y -c conda-forge ffmpeg
conda uninstall numpy
pip3 install numpy==1.26.0    # 该版本需与 Torchvision 兼容
```

**第 4 步**：检查 PyTorch GPU 是否可用：

```bash
python3 -c "import torch; print(torch.cuda.is_available())"   # 应输出 True
```

> 输出 False 说明装成了 CPU 版 PyTorch（pip 安装 lerobot 可能覆盖原有 GPU 版），需按官方教程重装 PyTorch/Torchvision。

## 2. 校准 Follower 从臂

- 校准前确认从臂**已接电源与数据线**。
- 主臂与从臂的校准文件分别保存在 `~/.cache/huggingface/lerobot/calibration/robots` 与 `~/.cache/huggingface/lerobot/calibration/teleoperators` 下；**重新校准需删除对应文件**，或运行校准指令后按提示 **C（重新校准）/ Enter（沿用旧校准）**。
- 零位姿态：把 Follower 臂移动到参考零位，**夹爪要完全闭合**。
- 同一电脑设备下，机械臂组装完成后**只需校准一次**。

> 如果无法连接 follower，请先用 motorbridge 提供的接口测试机械臂是否正常（见 `rebot-arm-environment-setup`）。

### 2.1 DM 从臂校准

```bash
sudo chmod 666 /dev/ttyACM*
cd ~/rebot_lerobot/lerobot
lerobot-calibrate \
    --robot.type=seeed_b601_dm_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=follower1 \
    --robot.can_adapter=damiao
```

### 2.2 RS 从臂校准

```bash
sudo ip link set can0 down 2>/dev/null
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
cd ~/rebot_lerobot/lerobot
lerobot-calibrate \
    --robot.type=seeed_b601_rs_follower \
    --robot.port=can0 \
    --robot.id=follower1 \
    --robot.can_adapter=socketcan
```

**Jetson（JetPack 6.x）可选**：查找机械臂对应的 PCAN 接口编号：

```bash
for i in /sys/class/net/can*; do
    [ "$(basename "$(readlink -f "$i/device/driver" 2>/dev/null)")" = "pcan" ] && basename "$i"
done
# 输出如 can2（也可能是 can0/can1），后续所有 follower 命令的端口号必须与此一致
```

> 若 Jetson 未安装 PCAN 驱动，通信会持续异常，请先按 `rebot-arm-environment-setup` 完成 PCAN netdev 模式驱动安装。

## 3. 校准 Leader 主臂（reBot Arm 102）

**校准说明**：

- 启动校准时，reBot Arm 102 的**每个舵机当前位置会被重设为 0 点**。
- `joint_ranges`（关节限位）取自配置文件 `config_rebot_arm_102_leader.py`，而非校准数据；若某关节总卡在限位附近，**优先检查 joint_ranges 配置**。
- 关节方向定义在配置文件中，**方向不一致需修改配置，而非重新校准**。
- reBot 102 Leader 使用 **USB 转 UART 模块**，通常映射为 `/dev/ttyUSB*`，用 `ls /dev/ttyUSB*` 查看实际端口。

**初次连接找不到串口**（brltty 占用）：

```bash
sudo dmesg | grep ttyUSB   # 查看最后一行显示 disconnected
sudo apt remove brltty     # 移除 brltty 后重插
```

**校准命令**（按提示把主臂移到零点后**保持静止，按 Enter 直到提示校准完成**）：

```bash
sudo chmod 666 /dev/ttyUSB0
lerobot-calibrate \
    --teleop.type=rebot_arm_102_leader \
    --teleop.port=/dev/ttyUSB0 \
    --teleop.id=rebot_arm_102_leader
```

## 4. 启动主从遥操作

> ⚠️ 所有机械臂运动场景同样需要注意：运行中若主从臂电源脱落、电源接触不良、信号线脱落，必须先停止代码，机械臂恢复到初始 0 点位置，再通上电源重新运行程序。

### 4.1 DM 遥操作

```bash
sudo chmod 666 /dev/ttyUSB* /dev/ttyACM*   # leader + follower 串口权限

lerobot-teleoperate \
    --robot.type=seeed_b601_dm_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=follower1 \
    --robot.can_adapter=damiao \
    --teleop.type=rebot_arm_102_leader \
    --teleop.port=/dev/ttyUSB0 \
    --teleop.id=rebot_arm_102_leader
```

### 4.2 RS 遥操作

```bash
sudo chmod 666 /dev/ttyUSB*                 # leader 串口权限
sudo ip link set can0 down 2>/dev/null      # follower CAN
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up

lerobot-teleoperate \
    --robot.type=seeed_b601_rs_follower \
    --robot.port=can0 \
    --robot.id=follower1 \
    --robot.can_adapter=socketcan \
    --teleop.type=rebot_arm_102_leader \
    --teleop.port=/dev/ttyUSB0 \
    --teleop.id=rebot_arm_102_leader
```

**参数说明**：

| 参数 | 含义 | DM | RS |
|------|------|----|----|
| `--robot.type` | 从臂插件类型 | `seeed_b601_dm_follower` | `seeed_b601_rs_follower` |
| `--robot.port` | 从臂通信端口 | `/dev/ttyACM0` | `can0` |
| `--robot.can_adapter` | CAN 适配器 | `damiao` | `socketcan` |
| `--teleop.type` | 主臂插件类型 | `rebot_arm_102_leader`（两型号相同） | 同左 |
| `--teleop.port` | 主臂串口 | `/dev/ttyUSB0` | 同左 |
| `--robot.id` / `--teleop.id` | 校准 ID | 与校准时一致（`follower1` / `rebot_arm_102_leader`） | 同左 |

## 5. 接入相机

先用 `lerobot-find-cameras opencv` 确认相机索引（输出 "Detected Cameras" 与每台相机编号/ID），再在 teleoperate 命令中加入 `--robot.cameras`。

单相机（front，索引 0）：

```bash
lerobot-teleoperate \
    --robot.type=seeed_b601_dm_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=follower1 \
    --robot.can_adapter=damiao \
    --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: "MJPG"}}" \
    --teleop.type=rebot_arm_102_leader \
    --teleop.port=/dev/ttyUSB0 \
    --teleop.id=rebot_arm_102_leader \
    --display_data=true
```

双相机（增加 side，索引 2，`--robot.cameras` 参数替换为）：

```bash
--robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: "MJPG"}, side: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, fourcc: "MJPG"}}"
```

> 提示：`fourcc: "MJPG"` 为压缩格式，可支持更高分辨率；YUYV 格式会降低分辨率与 FPS 导致操作卡顿。`index_or_path` 取相机 ID 的最后一位数字。**USB 相机建议直插电脑，不要经同一 USB HUB 接两台相机**。

## 6. 控制频率与延迟

- 遥操作回路默认 **60 Hz**——每秒 60 圈"读 Leader → 映射 → 发 CAN → 回读"，每圈时间预算 **16.7 ms**；可通过 teleoperate 配置中的 `fps` 参数调整。
- **上限由硬件回路耗时决定**：链路跑一圈本身就要十几毫秒，实用上限约 **60–100 Hz**，设得更高实际频率也跑不上去，只会看到周期超时警告。
- **60 Hz 已远超需要**：人手最快的有意识动作约 **5–10 Hz**，60 Hz 采样密度完全覆盖手的带宽。
- 若"从臂不跟随/延迟大"：先检查电源与信号线接触（见安全要点），再确认 `fps` 设置与相机格式（YUYV 会拖慢回路）。

## 7. 实操练习建议（抓取→搬运→放置）

遥操作"能动"与"能干活"之间需要刻意练习，按三个梯度：

| 练习 | 内容 | 目标 |
|------|------|------|
| 练习 1 | 空载移物：移动到目标上方 → 下降 → 闭合夹爪 → 抬起 | 10 次动作无碰撞、无中途掉落 |
| 练习 2 | 完整任务链：抓取 → 搬运 → 放入指定容器 | 连续完成 10 次，起终点姿态基本一致 |
| 达标标准 | 稳定节奏连续完成完整任务 | **20 次**不觉得勉强，可进入下一章 |

## 常见问题

| 问题 | 原因与解决 |
|------|-----------|
| 找不到 `/dev/ttyACM0` | `brltty` 占用串口 → `sudo apt remove brltty` 后重插；或检查 USB 线 |
| 找不到 `/dev/ttyUSB0` | 用 `ls /dev/ttyUSB*` 查看实际端口；brltty 占用时 `sudo dmesg | grep ttyUSB` 确认后移除 |
| 无法连接 follower | 用 motorbridge 接口测试机械臂是否正常（`motorbridge-cli scan`，见 `rebot-arm-environment-setup`） |
| macOS 遥操作帧率低 | 旧版 WCH CH34x 驱动导致；macOS 10.14+ 自带 AppleUSBCHC0M 驱动，可卸载旧驱动切换 |
| 关节总卡在限位附近 | 检查 `joint_ranges` 配置（`config_rebot_arm_102_leader.py`）而非重新校准 |
| 遥操作中从臂突然不动/抖动 | 立即断电（见 `rebot-arm-safety` 紧急流程），检查电源/信号线接触后按"停止 → 回 0 点 → 上电 → 重跑"流程恢复 |

## 参考

- 官方 Wiki（B601-DM LeRobot 教程）：<https://wiki.seeedstudio.com/rebot_arm_b601_dm_lerobot/>
- 官方 Wiki（B601-RS 快速入门，含 PCAN 配置）：<https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- 官方仓库：<https://github.com/Seeed-Projects/lerobot>
- pip 插件包：`lerobot-teleoperator-rebot-arm-102` ｜ `lerobot-robot-seeed-b601`
- motorbridge：<https://github.com/motorbridge/motorbridge>
- 配套教程：本仓库同目录《Seeed具身智能入门8个阶段40章节》第 11 章"Leader 与 Follower 校准及遥操作"
- 前置：`rebot-arm-safety` ｜ `rebot-arm-environment-setup` ｜ 下一步：`rebot-arm-data-collection`
