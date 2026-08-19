---
name: rebot-arm-environment-setup
description: 搭建 reBot Arm（B601-DM / B601-RS）的开发环境：安装 Miniforge 与 conda 环境、安装 motorbridge、配置串口（DM）或 SocketCAN/PCAN（RS）权限、首次接线供电上电检查。当用户需要从零开始准备电脑环境、解决"找不到串口/can0"、或准备首次上电时使用本技能。
---

# reBot Arm 环境搭建与首次上电

## 简介

本技能完成 reBot Arm 使用前的**软件环境**（conda + motorbridge + 通信接口）与**首次硬件上电**准备。所有后续技能（电机标定、遥操作、数据采集、训练推理）都依赖本技能的环境。

## 何时使用

- 用户新电脑/新环境首次使用 reBot Arm
- 报错"找不到串口 / can0 不存在 / 权限不足"
- 用户问"装环境 / 接线 / 上电步骤"

## 前置条件

- 已确认型号（**DM**：串口 + 24V 电源；**RS**：PCAN-USB + 48V 电源）
- 硬件已组装完成（未组装请先按官方 Wiki 组装视频完成，或购买预组装版）
- 已读 `rebot-arm-safety`（接线/上电是电气操作）

## 0. 安全要点

> ⚠️ 接线/上电前完成 `rebot-arm-safety` 检查清单：断电插拔、电压档位（220V→230V / 110V→115V）、正负极正确、周围 50cm 无人员、手边有电源开关。

## 1. 安装 Miniforge（推荐，隔离环境）

**Ubuntu / Jetson / Raspberry Pi：**

```bash
wget "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
```

**macOS：**

```bash
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-$(uname -m).sh"
bash Miniforge3-MacOSX-$(uname -m).sh
```

**Windows：** 从 <https://github.com/conda-forge/miniforge/releases> 下载 `Miniforge3-Windows-x86_64.exe` 安装。

安装后初始化并激活 bash（Ubuntu/macOS）：

```bash
~/miniforge3/bin/conda init bash
source ~/.bashrc
```

## 2. 创建 conda 环境并安装 motorbridge

```bash
conda create -y -n rebot python=3.12
conda activate rebot        # 每次打开新终端都要重新激活
pip install motorbridge
```

验证：

```bash
motorbridge --version   # 或 motorbridge -v，输出如 motorbridge 0.5.0
```

> macOS 提示：遥操作帧率低可能是旧版 WCH CH34x 驱动导致；macOS 10.14+ 自带 AppleUSBCHC0M 驱动，可卸载旧驱动切换。
> 不建议用 Windows 系统 Python 直接装（用 conda 环境），Linux 下务必用物理机而非虚拟机/WSL。

## 3. 配置通信接口（按型号）

### 3.1 DM：串口权限

连接 USB-CAN 桥接板后：

```bash
sudo chmod 666 /dev/ttyACM*      # Windows 无需此步
ls /dev/ttyACM*                  # 确认端口存在，通常为 /dev/ttyACM0
```

### 3.2 RS：PCAN-USB + SocketCAN

**Ubuntu / Raspberry Pi：**

```bash
# 加载驱动并查看接口
sudo modprobe peak_usb
ip -br link

# 配置 can0（按实际接口名调整），bitrate 1000000
sudo ip link set can0 down 2>/dev/null
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
```

**Jetson（JetPack 6.x）**：若 PCAN 驱动未装，需要编译安装 PEAK 驱动（netdev 模式，`make netdev`，不能用普通 `make`，因为 LeRobot/motorbridge-cli 依赖 SocketCAN）。安装前先移除占用串口的 brltty：

```bash
sudo apt remove -y brltty
```

安装依赖并编译：

```bash
sudo apt update
sudo apt install -y build-essential gcc g++ make libpopt-dev can-utils ethtool nvidia-l4t-kernel-headers
ls -l /lib/modules/$(uname -r)/build   # 确认内核头文件存在

# 下载并解压 peak-linux-driver-9.2.0.tar.gz 后：
cd ~/peak-linux-driver-9.2.0
make clean
make netdev                 # 必须 netdev 模式（注册为 SocketCAN 网卡）
sudo make install
sudo depmod -a
sudo modprobe pcan
echo pcan | sudo tee /etc/modules-load.d/pcan.conf
ip -br link | grep can      # 期望看到 can0/can1 DOWN
```

**找到机械臂对应的 PCAN 接口并持久化**（接口编号重启会变，推荐写入 ~/.bashrc）：

```bash
for i in /sys/class/net/can*; do [ "$(basename "$(readlink -f "$i/device/driver" 2>/dev/null)")" = "pcan" ] && basename "$i"; done
# 输出如 can1

grep -q '^pcan_refresh()' ~/.bashrc || cat >> ~/.bashrc <<'EOF'
pcan_refresh() {
    local iface
    iface=$(sudo setup-pcan-if) || return 1
    export PCAN_IF="$iface"
    echo "PCAN_IF=$PCAN_IF"
}
EOF
source ~/.bashrc
pcan_refresh                  # 输出如 PCAN_IF=can1，之后用 $PCAN_IF 代替硬编码
```

> **macOS RS 用户**：需要安装 PCBUSB 库并配置 `DYLD_FALLBACK_LIBRARY_PATH`（见官方 Wiki 的 PCAN-USB 章节），否则连接报 `load PCBUSB failed`。
> **Windows RS 用户**：安装 PCAN-USB 驱动；设备管理器不识别时需重刷固件（详见官方 Wiki"PCAN Firmware Download & Driver Repair"章节）。

## 4. 首次接线与供电上电

> 本节请严格按 `rebot-arm-safety` 的"首次上电前检查清单"执行。

1. **接线**（断电状态下）：
   - 电源输出（XT30）→ 机械臂电源输入
   - USB-CAN 桥接板（DM）或 PCAN-USB（RS）→ 电脑 USB
   - DM 还需确认电机 1↔2 之间的 3 芯线束连接（组装时易漏）
2. **确认电压档位**：电源侧面拨码 220V→230V、110V→115V。
3. **上电**：接通电源，机械臂指示灯点亮（电机使能前灯通常为其他状态）。
4. **确认通信**：
   - DM：`ls /dev/ttyACM*` 出现端口
   - RS：`ip -br link` 出现 can0 且 `sudo ip link set can0 up` 成功

**验证 motorbridge 能发现电机（可选，需使能前执行）：**

```bash
# DM：扫描 1-10 的 CAN ID
python3 - <<'EOF'
from motorbridge import Controller
def scan_damiao(start, end, channel="/dev/ttyACM0"):
    found = []
    for can_id in range(start, end + 1):
        ctrl = Controller.from_dm_serial(channel, 921600)
        try:
            m = ctrl.add_damiao_motor(can_id, 0x11 + can_id, "4340P")
            esc = m.get_register_u32(8, timeout_ms=100)
            print(f"[find] can_id=0x{esc:02X}")
            found.append(esc)
        except Exception:
            print(f"[no respond] 0x{can_id:02X}")
        finally:
            ctrl.close_bus(); ctrl.close()
    return found
scan_damiao(1, 10)
EOF
```

```bash
# RS：扫描 1-7
motorbridge-cli scan --vendor robstride --channel can0 --start-id 1 --end-id 7 --timeout-ms 300
```

> 提示：`motorbridge-gateway`（Web Studio 后端）的启动命令见 `rebot-arm-motor-config`；RS 初始化电机参数前，请先确认"rebot-arm-robstride 默认参数模板"已应用（见 `rebot-arm-motor-config`）。

## 5. 环境验证汇总

| 检查项 | 命令 | 期望 |
|--------|------|------|
| conda 环境 | `conda activate rebot && python --version` | Python 3.12 |
| motorbridge | `motorbridge --version` | 0.4.x/0.5.x |
| DM 串口 | `ls /dev/ttyACM*` | 有设备，权限 666 |
| RS CAN | `ip -br link show can0` | UP，bitrate 1000000 |
| 电机在线（可选） | 上面的扫描脚本 | 找到 1-7（RS）或对应 ID（DM） |

## 常见问题

- **找不到 /dev/ttyACM0**：检查 USB 线；Ubuntu 下 `brltty` 可能占用串口 → `sudo apt remove -y brltty` 后重插。
- **can0 不存在**：`sudo modprobe peak_usb`；Jetson 检查 pcan 驱动是否编译安装成功（`ip -br link | grep can`）。
- **权限不足**：DM 执行 `sudo chmod 666 /dev/ttyACM*`；该权限每次重启后需重新设置（或配置 udev 规则）。
- **虚拟机上控制异常**：官方明确建议 Ubuntu 物理机，虚拟机性能与配置问题多。

## 参考

- Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- motorbridge：<https://github.com/motorbridge/motorbridge> ｜ Studio：<https://motorbridge.github.io/motorbridge-studio/>
- 配套教程：本仓库同目录教程第 7 章（环境安装与 motorbridge）、第 6 章（组装供电上电）
- 下一步：电机 ID 与零点标定 → `rebot-arm-motor-config`
