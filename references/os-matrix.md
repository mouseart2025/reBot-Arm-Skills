# 参考：操作系统 × 型号 差异矩阵（os-matrix）

> 用途：AI 遇到平台相关问题时的快速对照表。同一问题在不同 OS/型号下解决方式不同，先查本表再进对应技能。
> 来源：官方 Wiki 与配套教程；细节以官方文档为准。

## 总览

| 维度 | B601-DM | B601-RS |
|------|---------|---------|
| 电机 | 达妙 Damiao（行星减速） | 灵足 Robstride（QDD 准直驱） |
| 供电 | 24V | **48V（高压，注意安全）** |
| 通信 | 串口 `/dev/ttyACM0`（921600） | SocketCAN `can0`（1 Mbps），PCAN-USB |
| 电机 ID | CAN 0x01-0x07 / Master 0x11-0x17 | 1-7 / master 固定 0xfd |
| 写 ID 工具 | DM_Tools（Windows）或 motorbridge | MotorBridge Studio / motorbridge-cli |

## 按 OS

### Ubuntu（推荐，物理机）

| 事项 | DM | RS |
|------|----|----|
| 端口权限 | `sudo chmod 666 /dev/ttyACM*` | 无需（SocketCAN） |
| CAN 配置 | — | `sudo ip link set can0 type can bitrate 1000000 && sudo ip link set can0 up` |
| 常见坑 | `brltty` 占用串口 → `sudo apt remove brltty` | 虚拟机/WSL 无法可靠运行（官方验证） |
| 注意 | 权限每次重启需重设 | 接口编号重启会变 → 用 `pcan_refresh`（写入 ~/.bashrc） |

### macOS

| 事项 | DM | RS |
|------|----|----|
| 端口 | 无需 chmod；`ls /dev/ttyACM*` | — |
| 驱动 | 遥操作帧率低 → 旧 WCH CH34x 驱动问题，macOS 10.14+ 自带 AppleUSBCHC0M，卸载旧驱动 | 需安装 PCBUSB：`libPCBUSB.dylib` + 符号链接 `PCBUSB`，并配置 `DYLD_FALLBACK_LIBRARY_PATH=/usr/local/lib`（写入 conda activate 脚本），否则报 `load PCBUSB failed` |
| 写 ID | 用 motorbridge Python（DM_Tools 仅 Windows） | MotorBridge Studio 网页 |

### Windows

| 事项 | DM | RS |
|------|----|----|
| 端口 | 无需 chmod | — |
| 驱动 | DM_Tools 官方上位机（仅 Windows，用于写 ID/恢复参数） | 安装 PCAN-USB 驱动；设备管理器不识别时需重刷固件（USB2CAN.zip + DFU 流程，官方 Wiki 有详细步骤） |
| 系统 Python | 不要直接用，用 Miniforge conda 环境 | 同左 |

### Jetson（JetPack 6.x）

| 事项 | DM | RS |
|------|----|----|
| 前置 | 装适配 Jetson 的 PyTorch-gpu/Torchvision | 同左 |
| 串口 | `brltty` 占用 → `sudo apt remove -y brltty` | 同左 |
| CAN | — | PCAN 驱动需**编译安装**：`make netdev`（勿用普通 make，LeRobot/motorbridge-cli 依赖 SocketCAN），`sudo make install && sudo modprobe pcan` |
| 找接口 | — | `for i in /sys/class/net/can*; do [ "$(basename "$(readlink -f "$i/device/driver"))" = "pcan" ] && basename "$i"; done` |
| 依赖 | conda 装 opencv>=4.10.0.84、numpy==1.26.0（与 Torchvision 兼容） | 同左 |

## 通用建议

- **不要用 Windows/WSL/虚拟机运行控制程序**（官方验证性能不足、配置问题多）——优先 Ubuntu 物理机；macOS 可部分使用（遥操作/写 ID）。
- 电源电压档位：220V→230V、110V→115V（两个型号相同）。
- 视频/图像采集：USB 相机直插电脑，不要接扩展坞。

## 相关

- `skills/rebot-arm-environment-setup/SKILL.md`（详细步骤）
- `skills/rebot-arm-troubleshooting/SKILL.md`（按症状排查）
