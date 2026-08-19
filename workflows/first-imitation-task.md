# 工作流：首个模仿学习任务（first-imitation-task）

> 目标：用 LeRobot 跑通**首个完整模仿学习任务**——主从遥操作 → 采集数据集 → 训练 ACT → 真机评估 →（失败则补数据）。这是第三阶段（模仿学习）的完整闭环，适用于"想教机械臂做一个新任务"。
> 每步有检查点（✅）；每完成一步更新 `memory/local-machine-env.md`。

## 前置

- 已完成 `workflows/first-run.md`（机械臂可安全控制）
- 已准备：reBot Arm 102 Leader 主臂（USB 转 UART）、相机（俯视 + 腕部）、NVIDIA GPU 电脑
- 先读 `skills/rebot-arm-safety/SKILL.md`

## 步骤总览

```
1 环境 ──> 2 校准 ──> 3 遥操作 ──> 4 任务设计 ──> 5 采集 ──> 6 质量检查 ──> 7 训练 ──> 8 真机评估 ──> 9 数据迭代
```

---

## Step 1 安装 LeRobot 环境（🤖/🔀）

见 `skills/rebot-arm-environment-setup` 与 `skills/rebot-arm-teleoperation`

```bash
mkdir ~/rebot_lerobot && cd ~/rebot_lerobot
git clone https://github.com/Seeed-Projects/lerobot.git
conda create -y -n rebot_arm python=3.12 && conda activate rebot_arm
pip install -e ./lerobot
pip install lerobot-teleoperator-rebot-arm-102 lerobot-robot-seeed-b601 motorbridge
conda install ffmpeg -c conda-forge
```

✅ **检查点**：`python3 -c "import torch; print(torch.cuda.is_available())"` → True
→ 更新 memory：「软件环境」

## Step 2 校准主从臂（🔀/👤）

见 `skills/rebot-arm-teleoperation`

1. 校准 Follower：`lerobot-calibrate --robot.type=seeed_b601_dm_follower|seeed_b601_rs_follower ...`（🤖/🔀，交互提示按 C/Enter 时由用户操作）
2. 校准 Leader：`lerobot-calibrate --teleop.type=rebot_arm_102_leader --teleop.port=/dev/ttyUSB0 ...`（零位姿态，夹爪闭合）

✅ **检查点**：校准完成无报错；标定文件出现在 `~/.cache/huggingface/lerobot/calibration/`（robots + teleoperators）
→ 更新 memory：「电机配置状态」Follower/Leader 已标定

## Step 3 启动遥操作并接入相机（🔀/👤）

见 `skills/rebot-arm-teleoperation`

```bash
lerobot-find-cameras opencv        # 🤖 确认相机索引
lerobot-teleoperate --robot.type=seeed_b601_dm_follower|seeed_b601_rs_follower \
    --robot.port=/dev/ttyACM0|can0 --robot.can_adapter=damiao|socketcan \
    --robot.cameras="{ front: {...}, side: {...} }" \
    --teleop.type=rebot_arm_102_leader --teleop.port=/dev/ttyUSB0 --teleop.id=rebot_arm_102_leader \
    --display_data=true
```

✅ **检查点**：人握主臂拖动，从臂实时跟随（60Hz 回路），两路相机画面正常显示
> ⚠️ 遥操作中电源/信号线脱落：先停程序 → 回 0 点 → 重新上电 → 再运行。

## Step 4 任务设计（🤖 引导用户）

见 `skills/rebot-arm-data-collection` 第 1 节：定义起点/结束条件、成功标准、一致性（同一种做法）与多样性（目标位置覆盖）。

## Step 5 采集数据集（🔀/👤）

见 `skills/rebot-arm-data-collection`

```bash
lerobot-record --robot.type=seeed_b601_dm_follower|seeed_b601_rs_follower ... \
    --dataset.repo_id=seeed_rebot_b601_dm/test|rs/test \
    --dataset.num_episodes=5 --dataset.single_task="Grab the crayfish into the box" \
    --dataset.push_to_hub=false --dataset.episode_time_s=30 --dataset.reset_time_s=20
```

- 先录 5 条测试 → 回放 OK → 正式采集 50 条（铅笔五点定位法：每点 1 条、5 点一轮、10 轮）
- 按键控制（👤）：→ 结束本条、← 重录、ESC 结束会话（**不要按 Ctrl+C**）

✅ **检查点**：数据在 `~/.cache/huggingface/lerobot/<repo_id>/`；`lerobot-dataset-viz --repo-id ... --episode-index 0` 可回放
→ 更新 memory：「数据集」表

## Step 6 质量检查（🤖 引导）

见 `skills/rebot-arm-data-collection` 第 5 节：回放第 0/中间/最后一条；坏条删除（`lerobot-edit-dataset`）或整集重录。

✅ **检查点**：画面完整清晰、动作与画面同步、起止正确

## Step 7 训练 ACT（🤖）

见 `skills/rebot-arm-act-training`

```bash
lerobot-train --dataset.repo_id=seeed_rebot_b601_rs/test --policy.type=act \
    --output_dir=outputs/train/act_rebot_test --job_name=act_rebot_test \
    --policy.device=cuda --wandb.enable=false --policy.push_to_hub=false --steps=100000
```

- 50 条数据 → 80000-100000 步；显存不足调小 `--batch_size` 并按比例加大 steps
- 训练中可 Ctrl+C 中断（会保存 checkpoint）

✅ **检查点**：日志中 loss 前期陡降后期趋稳；`outputs/train/act_rebot_test/checkpoints/last/pretrained_model` 存在
→ 更新 memory：「已训练模型」

## Step 8 真机评估（🔀/👤）

见 `skills/rebot-arm-act-training` 第 6-8 节：用 `lerobot-record` 加载 `--policy.path=.../checkpoints/last/pretrained_model`，连测 20 次记录成功率。

✅ **检查点**：成功率 ≥50%（第一次正常开局），成功用时稳定；失败方式已记录
> ⚠️ 推理结束用 **ESC**，不要 Ctrl+C；自动运行前先空载验证。

## Step 9 失败驱动补数据（🔀）

见 `skills/rebot-arm-act-training` 第 10 节：归类失败（够不到=位置覆盖不足/抓不稳=抓取时序/乱动=配置或场景不一致）→ 针对失败场景补录 10-20 条 → 重训。

✅ **检查点**：针对同一失败场景再评估，成功率提升或边界扩大

## 完成标准

- [ ] 完成一次「采集→训练→评估→补数据」闭环
- [ ] `memory/local-machine-env.md` 已记录数据集与模型
- [ ] 用户能独立描述任务设计与成功率

## 后续

- 想让机械臂按**自然语言指令**工作 → `skills/rebot-arm-vla-gr00t`（GR00T VLA）
- 想自动识别并抓取物体 → `workflows/vision-grasping-project.md`
