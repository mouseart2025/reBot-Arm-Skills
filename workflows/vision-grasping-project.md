# 工作流：视觉分拣项目（vision-grasping-project）

> 目标：搭建一个**桌面视觉分拣工作站**——RGB-D 相机识别目标物体，机械臂自动抓取并放入指定容器。端到端覆盖：相机安装 → 环境配置 → 手眼标定 → 抓取运行 → 精度调优。适用于"自动抓取/分拣"类项目。
> 每步有检查点（✅）；每完成一步更新 `memory/local-machine-env.md`。

## 前置

- 已完成 `workflows/first-run.md`（机械臂可安全控制）
- 已准备：RGB-D 深度相机（RealSense D405/D435i 或 Orbbec Gemini2）、腕部/俯视相机支架（3D 打印件）、ArUco 标定板（仓库提供 PDF）、NVIDIA GPU 电脑
- 先读 `skills/rebot-arm-safety/SKILL.md`

## 步骤总览

```
1 相机安装 ──> 2 环境配置 ──> 3 手眼标定 ──> 4 运行抓取 ──> 5 位置补偿调优 ──> 6 验收
```

---

## Step 1 相机安装与 SDK（👤/🤖）

见 `skills/rebot-arm-vision-grasping` 第 2 节

1. 3D 打印相机支架（`D435_Gemini2_Mount.step` / `D405_305_Mount.step`），将相机装在机械臂腕部（Eye-in-Hand）
2. USB 3.0 直插电脑（不要接扩展坞）
3. 安装 SDK（🤖）：RealSense → `pip install pyrealsense2`；Orbbec → `pip install pyorbbecsdk2`（或源码）

✅ **检查点**：`python -c "import pyrealsense2"` 或 `import pyorbbecsdk` 成功；相机能出图
→ 更新 memory：「软件环境」+ 相机型号

## Step 2 环境配置（🤖/🔀）

见 `skills/rebot-arm-vision-grasping` 第 3 节

```bash
git clone https://github.com/Seeed-Projects/reBot-DevArm-Grasp.git rebot_grasp
cd rebot_grasp
conda env create -f environment.yml && conda activate rebotarm
git clone https://github.com/vectorBH6/reBotArm_control_py.git sdk/reBotArm_control_py
cd sdk/reBotArm_control_py && pip install -e . && cd ../..
```

- 配置型号：编辑 `sdk/reBotArm_control_py/config/rebotarm.yaml`，`hardware_yaml: "rebotarm_rs.yaml"`（RS）或 `"rebotarm_dm.yaml"`（DM）
- RS 运行前先启动 CAN：`sudo ip link set can0 type can bitrate 1000000 restart-ms 100 && sudo ip link set can0 up`

✅ **检查点**：`python scripts/main.py` 能启动到"等待检测"阶段不报错
→ 更新 memory：「已完成的工作流」（视觉分拣进行中）

## Step 3 手眼标定（🔀/👤 协作）

见 `skills/rebot-arm-vision-grasping` 第 4 节

1. 打印 ArUco 标定板（100mm×100mm，**避免缩印**，打印后直尺实测）
2. 标定板固定在桌面视野内
3. 运行标定程序（🤖）：

```bash
python scripts/collect_handeye_eih.py            # 自动遍历 50 个位姿
# 或 python scripts/collect_handeye_eih.py --manual
```

- 至少 5 个样本，建议 ≥15 个；自动模式正常结束或中断都会尝试计算并保存标定结果

✅ **检查点**：标定矩阵已生成并保存（`config/default.yaml` 中 `hand_eye_method: TSAI` 生效）；用测试物体试抓方向正确

## Step 4 运行抓取（🔀/👤）

见 `skills/rebot-arm-vision-grasping` 第 6 节

```bash
python scripts/main.py    # 主抓取：检测 → 按 G 冻结帧 → 手眼变换 → 抓取
python scripts/set.py     # 抓取并放置到盒子：按 Q 退出并回零
```

- 流程：实时预览 + YOLO 检测 → 按 `G`（👤）冻结帧 → OBB 短轴估计夹爪朝向 → 深度分位数估计抓取高度 → 移动→下降→闭合→提升→回预备位
- > ⚠️ 自动运行前**先空载验证轨迹**；运行时保持距离，异常立即断电。

✅ **检查点**：对同一物体连续抓取 5 次，成功 ≥3 次；放置位置在盒内

## Step 5 位置补偿调优（🔀）

见 `skills/rebot-arm-vision-grasping` 第 7 节

- 抓取位置偏：修改 `config/default.yaml` 的 `calibration.hand_eye_compensation_m` 的 x/y/z（如 z: -0.02），小步调整后重试
- 误差来源排查：视觉定位误差 / 手眼标定偏差 / 轨迹规划 / 夹爪力度

✅ **检查点**：同一物体连续抓取 10 次，成功 ≥8 次；不同位置（网格 5-10cm 间隔）也能抓

## Step 6 验收（🔀）

- [ ] 完成一次"识别 → 抓取 → 放入容器"全自动循环（无人值守至少 1 次）
- [ ] 记录成功率与补偿参数到 `memory/local-machine-env.md`（备注/已知问题）
- [ ] 用户已了解安全规则（空载验证、异常断电）

## 完成标准

- [ ] 视觉分拣工作站可重复完成"抓取并放入盒子"任务
- [ ] 手眼标定结果、补偿参数、成功率已记录

## 后续

- 想提升复杂物体抓取（点云 + 六自由度抓取姿态） → `skills/rebot-arm-vision-grasping`（GraspNet 选修）
- 想让抓取由模型端到端决策 → `workflows/first-imitation-task.md`（模仿学习）或 `skills/rebot-arm-vla-gr00t`
- 想接入 ROS2/MoveIt2 规划抓取 → `skills/rebot-arm-ros2` ｜ `skills/rebot-arm-moveit`
