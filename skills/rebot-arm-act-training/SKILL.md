---
name: rebot-arm-act-training
description: 用 LeRobot 在 reBot Arm（B601-DM / B601-RS）数据集上训练 ACT 模仿学习策略并在真机推理评估：训练参数（batch size / learning rate / steps）与显存关系、启动 lerobot-train、查看 loss 与 GPU、checkpoint 管理、真机推理（lerobot-record 加载策略）、成功率与完成时间评估、失败类型分析与数据迭代补录。当用户需要训练 ACT 模型、评估模型效果、或"模型乱动/抓不到"需要排查迭代时使用本技能。
---

# reBot Arm ACT 训练、真机推理与数据迭代（LeRobot）

## 简介

本技能覆盖 reBot Arm（B601-DM / B601-RS）模仿学习的完整闭环：在已采集的 LeRobot 数据集上训练 **ACT（Action Chunking with Transformers）** 策略，用 `lerobot-record` 加载策略在真机推理评估，再根据失败类型补数据迭代重训。训练需要 NVIDIA GPU（conda 的 `lerobot` 环境），推理使用与采集时完全一致的机器人与相机配置。

> 分工标记：🤖 AI 执行（终端可自动化）｜ 👤 用户执行（GUI/网页/按键/插线/物理操作）｜ 🔀 人机协作（sudo 需用户密码或需用户确认）

## 何时使用

- 用户问"怎么训练 ACT / 跑 lerobot-train / 模型效果差"
- 需要评估模型成功率、泛化能力，或排查"模型乱动 / 够不到 / 抓不稳"
- 需要针对失败场景补录数据并重训（数据迭代闭环）

## 前置条件

| 项目 | 要求 | 说明 |
|------|------|------|
| 数据集 | 已采集并通过质量检查 | 见 `rebot-arm-data-collection`（50 条示范起步） |
| 软件环境 | conda 环境已安装 lerobot | 见 `rebot-arm-environment-setup` |
| 硬件 | NVIDIA GPU（训练）；真机 + 双相机（推理） | 只有核显/无 N 卡用云服务器训练 |
| 安全 | 已完成安全检查清单 | 先读 `rebot-arm-safety` |

## 👤 0. 安全要点

> ⚠️ **推理是自动运行**，无人值守风险高。运行前完成 `rebot-arm-safety` 检查清单（周围无人、障碍清除、手在电源开关旁），并**先空载验证一遍轨迹**再放任务物体。

1. **结束用 ESC，不要用 Ctrl+C**：停之前先让机械臂完成当前动作块或手动回安全位，避免停在半空受力姿态。
2. **随时准备断电**：运行异常（剧烈抖动、撞限位、异响）立即断电——硬件断电永远是最可靠的急停。
3. 注意区分：**训练阶段**可用 Ctrl+C 中断（已存 checkpoint 自动保存、可续训）；**推理阶段**必须用 ESC 结束。
4. 首次推理必须有人值守；评估回合之间（`reset_time_s` 时间）及时复位物体，保证每次初始状态尽量一致。

## 👤 1. 概念速览：ACT 与 Action Chunking（第 15 章）

ACT = **Action Chunking + Transformer**，LeRobot 内置的标准策略之一。

**输入与输出：**

| 方向 | 内容 | 维度 |
|------|------|------|
| 输入 | 前置 + 腕部两路 RGB 画面 + 关节状态（6 关节角 + 夹爪开合） | 2 路图像 + 7 维向量 |
| 输出 | 未来 k 步动作块，每步 7 维（6 关节 + 夹爪） | k × 7 动作矩阵（默认 k=100） |

ACT **只看当前帧**：每次根据"现在看到什么 + 关节在哪"输出一整块未来动作计划，不记忆过去的画面。

**内部结构（三个车间一条流水线）：**

| 模块 | 职责 |
|------|------|
| ResNet18 视觉骨干 | 两路图像各自压缩成视觉特征（ImageNet 预训练） |
| Transformer 编码器 | 融合视觉特征 + 关节状态，理解"目标在哪、我在哪、任务到哪一步" |
| Transformer 解码器 | 一次性生成未来 k 步动作序列——块内动作高度连贯 |
| CVAE | 条件变分自编码器：承认动作有多种风格，防止"平均值会抓空" |

**Action Chunk 与 Action Horizon 的区别（两个独立参数）：**

- **Chunk（动作块）**：模型一次预测的动作序列长度，默认 100 步；
- **Horizon（`n_action_steps`）**：预测出 100 步后，实际**开环执行多少步**再重新观测。

"预测的块可以很长，但每次只信任它的前一小段"——开环执行太久 = 闭着眼睛开车。

**适合的任务**：桌面级抓取/放置/整理、单任务或少数任务、秒级到一分钟内的短周期、视觉信息充足、算力有限的设备（消费级显卡可训练，CPU 也能推理）。

## 🤖 2. 三个关键配置：Batch Size、Learning Rate、Steps

先在终端输入 `nvidia-smi` 查看自己的显卡和显存，消费级显卡（如 RTX 3050）也能训。

### 2.1 Batch Size 与显存

| 显存 | 建议 batch size |
|------|-----------------|
| 8 GB 及以下 | 可以训，用小值：8GB → batch=4；4GB → batch=2 |
| 12 GB 以上 | 舒适区，用默认值即可；显存足够多可设 batch=16 |
| 只有核显 / 没有 N 卡 | 用云服务器训 |

> 显存富裕可以调大 batch 加速收敛，但**不要超过显存余量硬撑**。显存不足时加 `--batch_size=4`（或 2）。

### 2.2 Learning Rate

ACT 自带预设（`use_policy_training_preset` 默认启用，`lerobot-train` 自动生效，你什么都不用写）：

| 项目 | 值 |
|------|-----|
| 优化器 | AdamW |
| 学习率 lr | 1e-5 |
| weight decay | 1e-4 |
| 视觉骨干学习率 | 1e-5（单独设置） |

- **第一次训练不要动学习率**（原论文和大量实践调好的值）；修改了 batch size / steps 也**不需要**改学习率；
- **续训**（从已训练 checkpoint 微调）：学习率降至 `1e-6` ~ `3e-6`（降 3-10 倍）；
- **train loss 几乎不降（平滑贴死）**：先别升学习率，先加 steps / 加数据；仍不动再试 `2e-5`——两条指令**一起改、改成一样**：

```bash
--policy.optimizer_lr=1e-6 \
--policy.optimizer_lr_backbone=1e-6
```

### 2.3 Steps（训练步数）

50 条数据，直接**按 80,000 跑**。步数要按比例调整：batch size 减半，每步"看"到的样本就减半，想让模型把数据看够同样的遍数（epoch），步数就要翻倍：

| batch size | steps（50 条数据基准） |
|------------|------------------------|
| 16 | 40,000（÷2） |
| 8（默认） | 80,000 |
| 4 | 160,000（×2） |
| 2 | 320,000（×4） |

步数设大点也没关系：训练中可用 Ctrl+C 中断，也可以训练完挑选步数合适的 checkpoint 使用，丢弃训练不够或过拟合的存档。概念对照：**总帧数** ≈ 录像的总长度；**epoch（一轮）** = 把录像从头到尾完整看一遍；**步数** = 总共看了多少小段。

## 🤖 3. 启动训练

在 conda 的 `lerobot` 环境里运行（`--dataset.repo_id` 用采集时的数据集名；全部参数可用 `lerobot-train --help` 查看）。

**RS 版本（教程示例）：**

```bash
lerobot-train \
    --dataset.repo_id=seeed_rebot_b601_rs/test \
    --policy.type=act \
    --output_dir=outputs/train/act_rebot_test \
    --job_name=act_rebot_test \
    --policy.device=cuda \
    --wandb.enable=false \
    --policy.push_to_hub=false \
    --steps=100000
```

**DM 版本（官方 Wiki 示例）：**

```bash
lerobot-train \
    --dataset.repo_id=seeed_rebot_b601_dm/test \
    --policy.type=act \
    --output_dir=outputs/train/act_rebot_test \
    --job_name=act_rebot_test \
    --policy.device=cuda \
    --wandb.enable=false \
    --policy.push_to_hub=false \
    --steps=300000
```

> 步数按任务难度与数据量调整：教程建议 50 条数据 80,000 步起步，Wiki 示例用 300,000；`--job_name` 是本次训练的名字，日志里用它区分不同 run。

**RTX 50 系列显卡**：训练需增加 `--dataset.video_backend=pyav`，绕过 torchvision 预览版缺失的 API：

```bash
lerobot-train \
    --dataset.repo_id=seeed_rebot_b601_rs/test \
    --dataset.video_backend=pyav \
    --policy.type=act \
    --output_dir=outputs/train/act_rebot_test \
    --job_name=act_rebot_test \
    --policy.device=cuda \
    --wandb.enable=false \
    --policy.push_to_hub=false \
    --steps=100000
```

**显存不足**：加 `--batch_size=4`（或 2）设置批量大小（对应 2.3 节把 steps 翻倍）。

参数说明：

| 参数 | 含义 |
|------|------|
| `--dataset.repo_id` | 采集时的数据集名（本地名直接填；Hub 上的填 `${HF_USER}/xxx`） |
| `--policy.type=act` | 策略类型，也可换 diffusion、smolvla 等，本技能用 ACT |
| `--output_dir` | 本次训练所有产物的存放目录 |
| `--job_name` | 本次训练的名字，日志里用它区分不同 run |
| `--policy.device=cuda` | 用 GPU 训练（Apple Silicon 可 `mps`） |
| `--wandb.enable=false` | 不开 wandb 在线看板（想用需先 `wandb login`） |
| `--policy.push_to_hub=false` | 模型先不传 Hub，评估满意后再传 |
| `--steps` | 训练步数 |
| `--batch_size` | 批量大小（显存不足时调小） |
| `--dataset.video_backend=pyav` | RTX 50 系列必需 |

**时间预期**：10 万步在消费级显卡上通常是**几个小时**的量级，具体看显卡和 batch size。

## 🤖 4. Checkpoint 管理

不用手动保存：训练每 **20,000 步（`save_freq`）自动存一个 checkpoint**，训练结束还会存一份最后的。产物结构：

```text
outputs/train/act_rebot_test/
├── train_config.json              ← 本次训练的完整配置（恢复训练要用它）
└── checkpoints/
    ├── 0020000/pretrained_model/  ← 各步数模型的存档
    ├── 0040000/pretrained_model/
    ├── ...
    └── last/pretrained_model/     ← 最后一个 checkpoint，推理就用它
```

- **磁盘占用**：每个 checkpoint 是一份完整模型权重，几十个累积下来很可观；训练稳定后，早中期的小存档可以删，留 `last` 和最近一两个即可；
- 推理时 `--policy.path` 指向的就是 `checkpoints/last/pretrained_model` 这个**目录**；也可把模型传到 Hub 后填 `${HF_USER}/xxx`。

### 恢复中断的训练

训练跑到一半断电、断网、手滑关了终端，只要已经存过至少一个 checkpoint（即训练过 20,000 步）：

```bash
lerobot-train \
    --config_path=outputs/train/act_rebot_test/train_config.json \
    --resume=true
```

- 续训**以存档配置为准**（`train_config.json` 里保存的配置），命令行再传参数也会被忽略；想改参数（换步数、换 batch size）就开一个新 run，别用 resume；
- 从最近的 checkpoint 接着跑：优化器状态、步数计数都会还原，loss 曲线无缝衔接。

> 状态记忆：训练完成后更新 memory/local-machine-env.md 的「已训练模型」表（见 AGENTS.md 第 3 节）。

## 🤖 5. 查看 Loss 与 GPU

训练日志每隔一段时间（默认每 200 步，由 `--log_freq` 控制）打印一行汇总：

```text
step: 10000  smpl: 80K  ep: 35.6  loss: 1.832  grdn: 12.4  lr: 1.0e-05  updt_s: 0.21  data_s: 0.003  eta: 3:42:10
```

字段逐个看（不同版本字段名可能略有出入）：

| 字段 | 含义 | 看什么 |
|------|------|--------|
| `step` | 当前步数 | 对照 `--steps` 看进度 |
| `smpl` | 已处理的样本数（sample） | 进度参考 |
| `ep` | 已训练多少 epoch | 对应"看了几遍录像" |
| `loss` | 训练损失 | 前期快降、后期缓降、小幅波动是正常形状 |
| `grdn` | 梯度范数 | 突然爆到几百上千，说明训练不稳 |
| `lr` | 当前学习率 | 确认是预期值 |
| `updt_s` / `data_s` | 每步更新/取数据耗时 | `data_s` 大说明数据加载拖后腿 |
| `eta` | 预计剩余时间 | 安排时间用 |

**这些指标各自的正常走势**，分三类：

1. **应该一路下降的：`loss`**——三段式：**初期陡降 → 中期缓降 → 后期低位小幅波动、整体走平**。异常形态：一直不降（数据或配置有问题，回数据质量曲线、查相机 key）；降下去又反弹回升（训练发散，学习率减半重训）；
2. **应该整体收敛、允许抖动的：`grdn`**——大趋势跟随 loss 走低并稳定，毛刺正常；怕的是持续放大、一波比一波高（发散前兆，处理同上：降学习率）；
3. **应该保持不变的：`lr`、`updt_s`、`data_s`、GPU 利用率**——用 `watch -n 1 nvidia-smi` 观察，利用率持续偏低或忽高忽低，说明 GPU 在等数据，瓶颈在数据加载而不在显卡。

## 🤖👤 6. 真机推理（评估）

用 `lerobot-record` 加载策略即可，机器人和相机参数与采集时**完全一致**。训练时模型吃的是归一化数据，推理时按同一套规则处理进出（图像 resize + ImageNet 均值方差、state 减均值除标准差、action 乘标准差加均值，统计量来自训练集的 `meta/stats.json`）——所以相机 key（front/side）与采集严格一致至关重要。

**RS 版本：**

```bash
lerobot-record \
  --robot.type=seeed_b601_rs_follower \
  --robot.port=can0 \
  --robot.can_adapter=socketcan \
  --robot.cameras='{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: "MJPG"}, side: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, fourcc: "MJPG"} }' \
  --robot.id=follower1 \
  --display_data=false \
  --dataset.repo_id=seeed/eval_test18 \
  --dataset.single_task="Grab the crayfish into the box" \
  --dataset.num_episodes=10 \
  --dataset.episode_time_s=60 \
  --dataset.reset_time_s=10 \
  --policy.path=outputs/train/act_rebot_test/checkpoints/last/pretrained_model \
  --policy.push_to_hub=false
```

**DM 版本：**

```bash
lerobot-record \
  --robot.type=seeed_b601_dm_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.can_adapter=damiao \
  --robot.cameras='{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: "MJPG"}, side: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, fourcc: "MJPG"} }' \
  --robot.id=follower1 \
  --display_data=false \
  --dataset.repo_id=seeed/eval_test18 \
  --dataset.single_task="Grab the crayfish into the box" \
  --dataset.num_episodes=10 \
  --dataset.episode_time_s=60 \
  --dataset.reset_time_s=10 \
  --policy.path=outputs/train/act_rebot_test/checkpoints/last/pretrained_model \
  --policy.push_to_hub=false
```

参数说明：

| 参数 | 含义 |
|------|------|
| `--robot.type` | follower 型号：RS 用 `seeed_b601_rs_follower`；DM 用 `seeed_b601_dm_follower` |
| `--robot.port` / `--robot.can_adapter` | RS：`can0` + `socketcan`；DM：`/dev/ttyACM0` + `damiao` |
| `--robot.cameras` | 相机配置；key（front/side）与采集时严格一致 |
| `--dataset.repo_id` | 评估输出数据集名，**以 `eval_` 开头**（如 `seeed/eval_test18`）；会单独录制视频和数据 |
| `--dataset.single_task` | 与采集时使用的任务描述一致 |
| `--dataset.num_episodes` | 录多少个回合（评估 10 个） |
| `--dataset.episode_time_s` | 每回合最长秒数：按任务耗时设 **30-40 s**（抓取一次约 20-30 s，留余量）；只想快速测效果可设 300（回合间有间隔） |
| `--dataset.reset_time_s` | 回合之间留的时间，用于摆放物体复位（评估时要保证每次初始状态尽量一致） |
| `--policy.path` | 训练产物权重目录（`.../checkpoints/last/pretrained_model`）或 Hub 模型名 |
| `--policy.push_to_hub=false` | 评估结果不传 Hub |

> 提示：评估阶段报 `File exists: 'home/xxxx/.cache/huggingface/lerobot/xxxxx/seeed/eval_xxxx'`，先删除 `eval_` 开头的旧文件夹再运行。

### Action Chunk 的执行

- 一次推理输出 **100 步动作块**，只**开环执行前 n 步（`n_action_steps`）**就重新观测——预测越远越不可信；
- 开启**时间集成（`temporal_ensemble_coeff`）**时，每个时间步的动作是多次预测的加权平均，曲线几乎无毛刺；
- 真机看起来"一顿一顿"，多半是每次重新推理的计算停顿（chunk 执行完、新一块还没算出来的间隙）。适当增大 `n_action_steps` 能缓解，**代价是抗干扰变弱**。

### 推理安全

> ⚠️ 结束用 **ESC**，切记**不要用 Ctrl+C**。停之前先让机械臂完成当前动作块或手动回安全位，避免停在半空受力姿态；机械臂运行异常随时准备断电。

## 🤖👤 7. 评估：成功率、完成时间与泛化

### 7.1 成功率与完成时间

固定起始条件，连测 20 次，逐次记录：

- **成功率 = 成功次数 ÷ 20**。第一次训出的模型，**50% 以上算正常开局，80% 以上算优秀**；
- **完成时间看稳定性**：成功的那几次用时是否接近，忽快忽慢说明策略在"犹豫"；
- 失败的那几次**不要只记一个 ✗**——记下失败方式（对应 7.3 节分析）。

### 7.2 泛化能力测试

标准条件测完，逐项改变条件，看成功率掉多少（50 条数据的 ACT 泛化性有限，建议增加数据集）：

| 测试 | 做法 | 预期 |
|------|------|------|
| 位置泛化 | 物体放到训练覆盖范围之外、但未出覆盖范围太多 | 应基本不掉；掉了说明位置多样性不够 |
| 轻微干扰 | 桌面上放无关物体 | 视觉干净的模型应不受影响 |
| 明显出分 | 全新物体、镜面反光台面 | 失效是预期行为，不必救 |

泛化测试的意义不是证明模型多强，而是**画出它的能力边界**——边界之内放心用，边界之外补数据集慢慢扩。

### 7.3 失败类型分析

| 失败类型 | 最可能原因 | 对策 |
|----------|------------|------|
| 够不到：伸向错误位置 | 该位置数据覆盖不足（出分布） | 补录该区域示范 |
| 抓不稳：碰到但夹不住/滑落 | 夹爪闭合时序学得不准；抓握段示范太少 | 补录抓取瞬间的高质量示范 |
| 全程乱动、动作离谱 | 训练根本没收敛；或场景、光线变化较大 | 检查采集数据场景光线是否和推理一致 |

> **先排除配置问题，再怀疑数据问题——乱动是配置病，够不到才是数据病。**

## 👤🤖 8. 数据迭代闭环

把失败变成数据，闭环的最后一步：

1. **归类**：确定失败类型和对应场景（用 7.3 节的表）；
2. **补录**：针对失败场景录 **10-20 条**新示范——够不到就录那个位置，抓不稳就录抓取瞬间；**有意识地对边界慢慢扩张**：比如在原有物体位置附近按 5-10 cm 的点放置方块采集数据集，从而扩张覆盖范围；
3. **重训**：根据新的数据集重新训练。

至此完整闭环跑通：遥操作 → 采集 → 检查 → 训练 → 推理 → 评估 → 迭代，这套流程对任何新任务原样复用。

## ✅ 验证与预期结果

| 运行 | 期望结果 | 失败处理 |
|------|----------|----------|
| 训练日志 `loss` | 三段式下降：初期陡降 → 中期缓降 → 后期低位小幅波动走平 | 一直不降：加 steps / 加数据，仍不动再试 `--policy.optimizer_lr=2e-5`；降后反弹回升：学习率减半重训 |
| `outputs/train/act_rebot_test/checkpoints/last/pretrained_model` 目录 | 训练完成（每 20,000 步自动保存）后存在 | 不存在：确认训练跑过 20,000 步，未到则继续训练 |
| 固定条件连测 20 次的成功率 | ≥50% 正常开局，≥80% 优秀 | 按失败类型分析表补录 10-20 条后重训 |

## 👤 9. 常见问题

| 问题 | 处理 |
|------|------|
| loss 一直不降 | 先加 steps / 加数据，仍不动再试 `--policy.optimizer_lr=2e-5`（与 `--policy.optimizer_lr_backbone` 一起改）；还不行回数据质量检查曲线与相机 key |
| 显存不足（CUDA OOM） | 减小 `--batch_size`（8→4→2），对应按 2.3 节把 steps 翻倍 |
| RTX 50 系列报 torchvision 预览版 API 缺失 | 训练加 `--dataset.video_backend=pyav` |
| 推理报 `mean is infinity` | 相机 key（front/side）必须与采集时严格一致 |
| 推理报 `File exists: eval_xxx` | 先删除 `eval_` 开头的旧文件夹再运行 |
| 真机"一顿一顿" | 适当增大 `n_action_steps`（代价：抗干扰变弱） |

## 参考

- 官方 Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- LeRobot（Seeed 分支）：<https://github.com/Seeed-Projects/lerobot>
- 配套教程：本地参考教程《Seeed具身智能入门8个阶段40章节》（未随本仓库发布）第 15 章（ACT 模型与 Action Chunking）、第 16 章（训练第一个 ACT 策略）、第 17 章（真机推理、评估与数据迭代）
- 相关技能：`rebot-arm-data-collection`（数据集采集）｜ `rebot-arm-safety`（安全）｜ `rebot-arm-troubleshooting`（故障排查）
