---
name: rebot-arm-vla-gr00t
description: 用 NVIDIA Isaac GR00T（经 LeRobot groot policy）在 reBot Arm（B601-DM / B601-RS）上训练 VLA 模型：VLA 概念与 ACT 区别、准备 VLA 数据集（语言任务描述、state/action/camera keys、modality.json、embodiment tag）、环境与硬件要求（40GB+ 显存）、单/多 GPU 微调（lerobot-train --policy.type=groot）、checkpoint 与真机推理评估。当用户需要"用自然语言指令控制机械臂"、训练 GR00T VLA 或排查 GR00T 训练问题时使用本技能。
---

# reBot Arm VLA 与 Isaac GR00T 微调部署

## 简介

本技能用 **NVIDIA Isaac GR00T**（经 LeRobot `groot` policy，基础模型 `nvidia/GR00T-N1.7-3B`）在 reBot Arm B601 上训练 **VLA（Vision-Language-Action）** 模型：把已有 LeRobot 数据升级为带语言标注的 VLA 数据集（`modality.json` + `embodiment_tag`），完成 `lerobot-train` 微调，并在真机用自然语言指令推理评估。

> 分工标记：🤖 AI 执行（终端可自动化）｜ 👤 用户执行（GUI/网页/按键/插线/物理操作）｜ 🔀 人机协作（sudo 需用户密码或需用户确认）

## 何时使用

- 用户想**用自然语言指令控制机械臂**（"把黑色方块放到蓝色托盘里"→ 换指令即换行为）
- 已有 ACT / 模仿学习数据，想升级为多任务 VLA（`rebot-arm-act-training` 的进阶）
- 训练或微调 GR00T VLA（`lerobot-train --policy.type=groot`）
- 排查 GR00T 训练 / 推理问题（loss 正常但真机乱动、mean is infinity、OOM 等）

## 前置条件

| 项目 | 要求 |
|------|------|
| 硬件 | reBot Arm **B601-RS 或 B601-DM** 已校准（含夹爪）；**CUDA GPU**（GR00T 不支持 CPU-only 训练） |
| 数据 | 已通过 `lerobot-record` 采集 LeRobot 数据集（单任务 ≥ **50 条**成功演示；多任务每种 ≥ 30 条） |
| 显存 | 微调 **40 GB+**（L40 / A100 80GB / H100）；**16 GB 仅推理**（RTX 4090 可推理）；24 GB 只能 LoRA/PEFT |
| 系统 | Linux（Ubuntu 22.04+）或 WSL2；微调建议 100 GB+ 存储（含模型缓存） |
| 账号 | Hugging Face 账号（`nvidia/Cosmos-Reason2-2B` 是 gated 模型，需先接受条款） |

> 若还没有数据集，先完成 `rebot-arm-data-collection`；显存不足 40 GB 时改用 `pip install "lerobot[peft]"` 做 LoRA / PEFT，**效果与官方全量微调不可等同**。

## 0. 👤 安全要点

> ⚠️ 真机推理/评估是**自动运行**：加载策略后机械臂自行执行任务，可能撞限位、夹伤或坠落。运行前完成 `rebot-arm-safety` 检查清单；**结束用 ESC**（让机械臂安全收尾，不要用 Ctrl+C）；停之前先把机械臂移回安全位；**手边电源开关，任何异常立即断电**。

## 1. 👤 VLA 基础速览

**VLA = Vision（视觉）+ Language（语言）+ Action（动作）**：模型同时接收图像、语言指令与当前状态，输出机器人动作序列。GR00T N1.7 的骨干是 **Cosmos-Reason2-2B**（基于 Qwen3-VL 架构），再接 **Diffusion Transformer（DiT）动作头**（Flow Matching 去噪）输出连续动作块。

### 1.1 👤 VLM 与 VLA 的区别
| 对比项 | VLM（Vision-Language Model） | VLA（Vision-Language-Action） |
|--------|------------------------------|-------------------------------|
| 输出 | 文本、描述、推理结果 | **机器人动作序列** |
| 典型应用 | 图像问答、场景理解、Caption | 抓取、放置、开关门等操控 |
| 代表模型 | LLaVA、Qwen-VL、Cosmos-Reason2 | GR00T、π0、OpenVLA |
| 与机器人关系 | 可辅助规划，不直接驱动电机 | 端到端输出控制量 |

### 1.2 👤 ACT 与 VLA 的区别（何时选哪个）
| 对比项 | ACT | VLA（以 GR00T 为例） |
|--------|-----|----------------------|
| 任务条件 | 通常**无语言**，隐式单任务 | **语言 + 视觉** 显式多任务 |
| 模型规模 | 较小（千万级参数） | 较大（数十亿参数基础模型） |
| 训练方式 | 从零训练或轻量微调 | 基础模型预训练 + 下游微调 |
| 动作表示 | 动作块（chunk） | 动作块 + Flow Matching 去噪 |
| 泛化能力 | 同分布内表现好，换任务需重训 | 语言条件支持零样本/少样本迁移 |
| LeRobot 策略类型 | `act` | `groot` |

| 场景 | 推荐 |
|------|------|
| 单一重复任务、边缘设备、低延迟 | **ACT** |
| 多任务、语言交互、愿意投入 GPU 与标注 | **VLA / GR00T** |
| 已有 ACT 数据、想扩展多任务 | 在现有 LeRobot 数据上补语言 → GR00T 微调 |

**动作窗口**：N1.5/N1.6 的 `action_horizon=16`；N1.7 扩展到 **40**；LeRobot `groot` 源码默认 `chunk_size=50`。本教程用 **`chunk_size=40`** 与预训练窗口对齐，**不要沿用 16**。

### 1.3 👤 语言条件任务与动作表示
- **语言条件**：训练时每条演示绑定一句任务描述；推理时只需换指令文本，无需换模型权重（数据覆盖范围内）。指令粒度分任务级（"把红色方块放进蓝色盒子"）、子目标级、约束级（"轻放"）。
- **连续动作 vs 动作 Token**：GR00T 输出**连续**动作向量（DiT + Flow Matching 在连续空间去噪），如 `action = [q1..q6, gripper]` shape `(7,)`；部分 VLA（如 π0-FAST）把连续值量化成**离散 token** 复用自回归 LLM 架构。reBot 走关节空间（`NON_EEF`）。
- **相对动作提示**：N1.7 预训练核心是 **Relative EEF（相对末端执行器）** 动作空间；LeRobot 的 `--policy.use_relative_actions=true` 只是框架层对关节维做 `action − state` 的相对预处理，**不等于 Relative EEF**。夹爪等非关节量用 `relative_exclude_joints` 保持绝对控制。

## 2. 🤖 环境准备

### 2.1 👤 硬件与系统要求
| 配置 | 推理最低 | 微调推荐 |
|------|----------|----------|
| GPU | 16 GB+（RTX 4090 可推理） | **40 GB+**（L40 / A100 80GB / H100）；官方仿真微调要求 ≥ 48 GB |
| 系统 | Linux（Ubuntu 22.04+） | 原生 Linux 或 WSL2 |
| 存储 | 50 GB 可用空间 | 100 GB+（含模型缓存） |

默认微调（projector + DiT head）峰值约 **35 GB**；**RTX 4090 / 24 GB 不能做全量微调**，只适合推理；24 GB 上训练请用 LoRA / PEFT（`pip install "lerobot[peft]"`）。

### 2.2 🤖 安装 LeRobot 与 GR00T 依赖
```bash
# 创建并激活 conda 环境后（如 lerobot，Python 3.12）：
# 安装 ffmpeg（视频解码，Linux + TorchCodec 场景）
conda install ffmpeg -c conda-forge

# 安装 LeRobot + GR00T + 训练工具
pip install "lerobot[groot,training]"
```

### 2.3 🤖 安装 Flash Attention（重要）
GR00T N1.7 依赖 Flash Attention 加速。先安装匹配 CUDA 的 PyTorch，再装 flash-attn：

```bash
# 示例：CUDA 12.8 + PyTorch 2.7（RTX 50 系列可参考此组合）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128   # 按 CUDA 版本调整

pip install ninja "packaging>=24.2,<26.0"
pip install "flash-attn>=2.5.9,<3.0.0" --no-build-isolation

python -c "import flash_attn; print(f'Flash Attention {flash_attn.__version__} OK')"
```

### 2.4 🤖 登录 HF 与下载基础模型
```bash
huggingface-cli login
wandb login   # 可选，用于训练曲线可视化

huggingface-cli download nvidia/GR00T-N1.7-3B --local-dir ./models/GR00T-N1.7-3B
huggingface-cli download nvidia/Cosmos-Reason2-2B   # gated，需先在 HF 接受条款
```

训练参数中通过 `--policy.base_model_path=nvidia/GR00T-N1.7-3B` 指定。版本注意：当前 LeRobot 仅支持 GR00T **N1.7**；N1.5 需固定旧版 `lerobot==0.5.1`。

## 3. 🤖 准备 VLA 数据集

GR00T 使用 LeRobotDataset v2/v3 格式，并**额外要求 `meta/modality.json`**。已有 ACT 数据只需补充语言标注和 Modality 配置即可用于 GR00T 微调，无需重新采集全部演示。

### 3.1 🤖 检查现有数据集
```python
from lerobot.datasets.lerobot_dataset import LeRobotDataset

dataset = LeRobotDataset("seeed_rebot_b601_rs/pick_cube")  # RS 示例；DM 改 seeed_rebot_b601_dm/pick_cube
print("特征键:", dataset.features.keys())
print("state/action shape:", dataset[0]["observation.state"].shape, dataset[0]["action"].shape)
```

期望：`observation.state` 与 `action` 均为 `(7,)`（6 关节 + 1 夹爪）；视频键如 `observation.images.front`；`tasks.jsonl` 每个 `task_index` 有语言描述。若不是 7 维，说明录制配置有误，**不要强行改 modality.json 凑维度**。

### 3.2 🔀 添加语言任务描述
**方式 A：录制时直接写入（推荐）**——每条 episode 录制时指定 `--dataset.single_task`（其余录制参数见 `rebot-arm-data-collection`；DM 换 `--robot.type=seeed_b601_dm_follower --robot.port=/dev/ttyACM0 --robot.can_adapter=damiao`）：

```bash
lerobot-record \
  --robot.type=seeed_b601_rs_follower --robot.port=can0 --robot.id=follower1 --robot.can_adapter=socketcan \
  --dataset.repo_id=${HF_USER}/rebot_vla_pick_cube --dataset.num_episodes=50 \
  --dataset.single_task="把黑色方块放到蓝色托盘里" \
  --dataset.episode_time_s=30 --dataset.reset_time_s=20
```

**方式 B：事后补写 `meta/tasks.jsonl`**——已有 ACT 数据缺少语言时编辑：

```text
{"task_index": 0, "task": "把黑色方块放到蓝色托盘里"}
{"task_index": 1, "task": "把螺丝刀放进工具盒"}
```

**语言标注规范**：① 动词开头（"抓取…""放置…"）；② 物体名具体（"黑色方块"优于"物体"）；③ 句式统一（都用"把 X 放到 Y"）；④ 中英皆可，训练与推理一致；⑤ 避免一条数据多种说法。

### 3.3 🤖 配置 State / Action / Camera Keys
reBot Arm B601 的 7 维向量按以下关节顺序拼接（与 LeRobot 驱动一致）：

| 索引 | 键名（语义） | 含义 |
|------|--------------|------|
| 0 | `shoulder_pan` | 肩部旋转 |
| 1 | `shoulder_lift` | 肩部抬升 |
| 2 | `elbow_flex` | 肘部弯曲 |
| 3 | `wrist_flex` | 腕部弯曲 |
| 4 | `wrist_yaw` | 腕部偏航 |
| 5 | `wrist_roll` | 腕部滚转 |
| 6 | `gripper` | 夹爪开合 |

在 `modality.json` 中拆为 `single_arm`（索引 0–5）与 `gripper`（索引 6）。**相机键**：`observation.images.front` → `front`（全视角）、`observation.images.side` → `side`（腕部近景）；`original_key` 必须与数据集实际键名一致；单相机可训练，双相机通常更好；分辨率建议统一 640×480。查找本机相机索引：`lerobot-find-cameras opencv`。

### 3.4 🤖 创建 `meta/modality.json` 与设置 Embodiment Tag
在数据集 `meta/` 下创建 `modality.json`（reBot Arm B601 单臂 7 维关节空间，RS / DM 相同；切片左闭右开，`"end": 6` 取到索引 5，`"start": 6, "end": 7` 取索引 6）：

```json
{
  "state": { "single_arm": { "start": 0, "end": 6 }, "gripper": { "start": 6, "end": 7 } },
  "action": { "single_arm": { "start": 0, "end": 6 }, "gripper": { "start": 6, "end": 7 } },
  "video": { "front": { "original_key": "observation.images.front" }, "side": { "original_key": "observation.images.side" } },
  "annotation": { "human.task_description": { "original_key": "task_index" } }
}
```

| 字段 | 作用 |
|------|------|
| `state` / `action` | 定义拼接向量中各子段的索引范围 |
| `video` | 将 LeRobot 视频键映射为 GR00T 标准相机名 |
| `annotation` | 将 `task_index` 关联到 `tasks.jsonl`。reBot 用 `human.task_description`；LIBERO / SimplerEnv 用 `human.action.task_description` |

**Embodiment Tag**：reBot Arm 这类自定义机器人，训练和推理统一使用 `--policy.embodiment_tag=new_embodiment`——告知 GR00T 使用**新本体投影层**（Category-Specific MLP），不复用预训练人形的 state/action 维度；微调后 checkpoint 会保存对应 modality 配置，推理时自动加载。**不要在 reBot 数据上使用** `LIBERO_PANDA`、`DROID`、`SIMPLER_ENV_GOOGLE` 等预训练标签，也不存在 `libero_sim` 这个官方标签。

### 3.5 🤖 检查关节顺序和数据维度
这是最容易导致"训练 loss 下降但真机完全不动"的问题，逐项核对：

```python
import json, numpy as np
from pathlib import Path
from lerobot.datasets.lerobot_dataset import LeRobotDataset

meta_dir = Path.home() / ".cache/huggingface/lerobot/seeed_rebot_b601_rs/pick_cube/meta"
print(json.dumps(json.loads((meta_dir / "info.json").read_text()), indent=2)); mod = json.loads((meta_dir / "modality.json").read_text())
ds = LeRobotDataset("seeed_rebot_b601_rs/pick_cube")
s = ds[0]["observation.state"].numpy()
arm = s[mod["state"]["single_arm"]["start"]:mod["state"]["single_arm"]["end"]]
grip = s[mod["state"]["gripper"]["start"]:mod["state"]["gripper"]["end"]]
print("single_arm:", arm.shape, "gripper:", grip.shape)  # 期望 (6,) (1,)
print(ds.meta.stats["observation.state"]); print(ds.meta.stats["action"])
```

用 `lerobot-dataset-viz --repo_id=seeed_rebot_b601_rs/pick_cube --episode-index=0` 可视化：图像与关节运动同步、夹爪开合时 `gripper` 变化、语言与画面一致。若某维度 `min == max`（无变化），说明该关节未运动，可考虑排除或重新采集。

### 3.6 👤 多任务组织与数据量建议
- **方式 A（推荐）**：同一 `repo_id`，多 `task_index`——录制时轮换 `--dataset.single_task`，或分批次录制后合并（方式 B 为多数据集合并，视 LeRobot 版本而定）。

| 场景 | 建议 |
|------|------|
| 单任务入门 | 50 episodes |
| 单任务稳定 | 100–200 episodes |
| 多任务（3 种） | 每种 ≥ 30 episodes |
| 位置泛化 | 每种位置变体 ≥ 10 episodes |

### 3.7 👤 数据质量检查清单（上传 Hub 或训练前）
- [ ] `observation.state` 和 `action` 均为 7 维 float32
- [ ] `meta/modality.json` 存在且索引切片正确
- [ ] `meta/tasks.jsonl` 中每个 task_index 有非空描述
- [ ] 相机键名在 `modality.json` 与数据集中一致；无全零 / 静止不动的废 episode；角度单位统一（reBot 底层电机 API 用度，LeRobot 驱动内部已转为弧度）
- [ ] `embodiment_tag` 计划使用 `new_embodiment`

## 4. 🤖 使用 Isaac GR00T 微调

### 4.1 🤖 单 GPU 微调
本地数据集（未上传 Hub）`repo_id` 须与录制时一致，自动从 `~/.cache/huggingface/lerobot/` 加载。以下命令针对 reBot Arm 单臂、`new_embodiment`；仅本地保存时改 `--policy.push_to_hub=false`：

```bash
export HF_USER="your_hf_username"
export DATASET_REPO_ID="seeed_rebot_b601_rs/pick_cube"   # DM 改 b601_dm
export REPO_ID="${HF_USER}/rebot_groot17_pick_cube"      # 微调后模型上传名
export OUTPUT_DIR="outputs/train/${REPO_ID}"

lerobot-train \
  --dataset.repo_id=${DATASET_REPO_ID} \
  --dataset.image_transforms.enable=true \
  --policy.type=groot \
  --policy.device=cuda \
  --policy.base_model_path=nvidia/GR00T-N1.7-3B \
  --policy.embodiment_tag=new_embodiment \
  --policy.chunk_size=40 \
  --policy.n_action_steps=40 \
  --policy.use_relative_actions=true \
  --policy.relative_exclude_joints='["gripper"]' \
  --policy.use_bf16=true \
  --policy.push_to_hub=true \
  --policy.repo_id=${REPO_ID} \
  --seed=42 --batch_size=32 --steps=20000 --save_checkpoint=true --save_freq=5000 \
  --use_policy_training_preset=true --env_eval_freq=0 --eval_steps=0 --log_freq=10 \
  --output_dir=${OUTPUT_DIR} --job_name=rebot_groot_finetune --wandb.enable=true --wandb.disable_artifact=true
```

### 4.2 👤 关键参数说明
| 参数 | 值 | 说明 |
|------|-----|------|
| `--policy.type` | `groot` | 使用 GR00T 策略 |
| `--policy.embodiment_tag` | `new_embodiment` | reBot 自定义本体 |
| `--policy.chunk_size` | `40` | 对齐 N1.7 `action_horizon=40`（勿用 16） |
| `--policy.n_action_steps` | `40` | 训练时通常与 chunk 一致；推理可再减小 |
| `--policy.use_relative_actions` | `true` | **LeRobot 关节相对预处理**，不是 Relative EEF |
| `--policy.relative_exclude_joints` | `["gripper"]` | 夹爪保持绝对控制 |
| `--policy.use_bf16` | `true` | 混合精度，节省显存 |
| `--batch_size` | `32`（可调） | 40 GB 卡可试 32；OOM 时降至 8 或 16 |
| `--steps` | `20000` | 微调步数；数据少可降至 10000 |
| `--save_freq` | `5000` | 每 5000 步存一次 checkpoint |

### 4.3 🤖 多 GPU 微调与训练监控
多卡环境使用 `accelerate`（每卡 batch=16 示例；其余参数与单 GPU 相同）：

```bash
export NUM_GPUS=2
export BATCH_SIZE=16        # 每卡 batch，总 batch = 16 × GPU 数
export NUM_STEPS=20000
export SAVE_FREQ=5000
export LOG_FREQ=10

accelerate launch --multi_gpu --num_processes=${NUM_GPUS} $(which lerobot-train) \
  --dataset.repo_id=${DATASET_REPO_ID} --dataset.image_transforms.enable=true \
  --policy.type=groot --policy.device=cuda --policy.base_model_path=nvidia/GR00T-N1.7-3B \
  --policy.embodiment_tag=new_embodiment --policy.chunk_size=40 --policy.n_action_steps=40 \
  --policy.use_relative_actions=true --policy.relative_exclude_joints='["gripper"]' --policy.use_bf16=true \
  --policy.push_to_hub=true --policy.repo_id=${REPO_ID} \
  --output_dir=${OUTPUT_DIR} --save_checkpoint=true \
  --batch_size=${BATCH_SIZE} --steps=${NUM_STEPS} --save_freq=${SAVE_FREQ} --log_freq=${LOG_FREQ} \
  --use_policy_training_preset=true --wandb.enable=true --wandb.disable_artifact=true --job_name=rebot_groot_multi_gpu
```

监控（另开终端）：`watch -n 1 nvidia-smi` 看显存、`tail -f ${OUTPUT_DIR}/logs/*.log` 看日志。OOM 时先确认 GPU ≥ 40 GB，再降低 `--batch_size`、保持 `--policy.use_bf16=true`（24 GB 请改 LoRA/PEFT，不要硬降 batch 做全量微调）；显存有余量可增大 batch 加速。Loss 曲线（W&B 网页端 `train/loss`）前 1000 步快速下降、5000 步后平稳；若不下降，检查 `modality.json`、数据维度、语言标注。

## 5. 🤖 Checkpoint 与真机推理

### 5.1 🤖 保存 Checkpoint 与上传 Hub
checkpoint 保存在 `outputs/train/<REPO_ID>/checkpoints/`（`005000/`、`010000/`、`015000/`、`020000/`、`last/`），**推理用 `last/pretrained_model`**。指定 checkpoint：`--policy.path=outputs/train/${REPO_ID}/checkpoints/010000/pretrained_model`。`--policy.push_to_hub=true` 时训练结束自动上传；手动上传：`huggingface-cli upload ${REPO_ID} outputs/train/${REPO_ID}/checkpoints/last/pretrained_model`。

> 状态记忆：训练完成后更新 memory/local-machine-env.md 的「已训练模型」表（见 AGENTS.md 第 3 节）。

### 5.2 🔀 方式 A：`lerobot-record` 带策略录制（推荐入门）
与 ACT 评估流程相同，换成 GR00T checkpoint。下面以 **B601-RS** 为例；DM 替换 `type` / `port` / `can_adapter`：

```bash
export HF_USER="your_hf_username"
export MODEL_PATH="${HF_USER}/rebot_groot17_pick_cube"   # Hub 或本地路径

# RS CAN
sudo ip link set can0 down 2>/dev/null
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up

lerobot-record \
  --robot.type=seeed_b601_rs_follower --robot.port=can0 --robot.id=follower1 --robot.can_adapter=socketcan \
  --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: \"MJPG\"}, side: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, fourcc: \"MJPG\"}}" \
  --display_data=true \
  --dataset.repo_id=${HF_USER}/eval_groot_rebot --dataset.num_episodes=10 \
  --dataset.single_task="把黑色方块放到蓝色托盘里" \
  --dataset.episode_time_s=30 --dataset.reset_time_s=15 \
  --policy.path=${MODEL_PATH} --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.embodiment_tag=new_embodiment
```

> ⚠️ `--robot.cameras` 中的 `front`、`side` 必须与训练数据集键名一致；`--dataset.single_task` 句式与训练数据一致；**结束用 ESC**，异常随时断电（见 `rebot-arm-safety`）。

### 5.3 🔀 方式 B：`lerobot-rollout` 实时部署（进阶）
适合低延迟闭环控制，支持 RTC（Real-Time Chunking）：

```bash
export MODEL_PATH="${HF_USER}/rebot_groot17_pick_cube"

lerobot-rollout \
  --strategy.type=base \
  --policy.path=${MODEL_PATH} \
  --policy.base_model_path=nvidia/GR00T-N1.7-3B \
  --policy.embodiment_tag=new_embodiment \
  --policy.chunk_size=40 --policy.n_action_steps=20 \
  --policy.use_relative_actions=true --policy.relative_exclude_joints='["gripper"]' \
  --robot.type=seeed_b601_rs_follower --robot.port=can0 --robot.id=follower1 --robot.can_adapter=socketcan \
  --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: \"MJPG\"}, side: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, fourcc: \"MJPG\"}}" \
  --task="把黑色方块放到蓝色托盘里" --duration=60 --device=cuda --display_data=true \
  --inference.type=rtc --inference.rtc.enabled=true --inference.rtc.execution_horizon=20 --inference.queue_threshold=2
```

若 RTC 导致抖动，设 `--inference.rtc.enabled=false`；`queue_threshold` 建议 2–5（设为 0 会频繁触发重推理，易抖动）；`n_action_steps` 须 ≤ 训练时的 `chunk_size`。DM 用户把 `type` / `port` / `can_adapter` 换成 `seeed_b601_dm_follower`、`/dev/ttyACM0`、`damiao`。

## ✅ 验证与预期结果

| 运行 | 期望结果 | 失败处理 |
|------|----------|----------|
| 数据检查（3.1/3.5 的 python 脚本 + `lerobot-dataset-viz`） | `observation.state` 与 `action` 均为 `(7,)`；modality 切片 `single_arm (6,)` + `gripper (1,)`；可视化图像与关节运动同步 | 维度或切片不符：回到 `lerobot-record` 排查录制配置，**不要强行改 modality.json 凑维度** |
| 训练（4.1 `lerobot-train --policy.type=groot`，4.3 `watch -n 1 nvidia-smi` 监控） | 前 1000 步 loss 快速下降、5000 步后平稳；checkpoint 保存在 `outputs/train/<REPO_ID>/checkpoints/last/pretrained_model` | loss 不下降：检查 `modality.json`、数据维度、语言标注；OOM：确认 GPU ≥ 40 GB，降 `--batch_size`、保持 `--policy.use_bf16=true` |
| 真机推理（5.2 `lerobot-record` 带策略 / 5.3 `lerobot-rollout`） | 机械臂按语言指令完成动作；`--task` / `single_task` 句式与训练数据一致 | 真机乱动：查关节顺序、角度单位、相机键名、`embodiment_tag`、相对动作；`mean is infinity`：检查 `--robot.cameras` 键名 |

## 6. 🤖 常见问题排查

| 问题 | 排查 |
|------|------|
| 模型下载失败 | 设镜像或代理后重试：`export HF_ENDPOINT=https://hf-mirror.com`；`huggingface-cli download nvidia/GR00T-N1.7-3B`；`nvidia/Cosmos-Reason2-2B` 是 gated，需先在 HF 接受条款 |
| CUDA / PyTorch 版本不匹配 | `python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda)"` 与 `nvidia-smi`，确保驱动满足 PyTorch CUDA 要求 |
| Flash Attention 安装失败 | ① `nvcc --version` 与 PyTorch CUDA 一致；② 试预编译 wheel：`pip install flash-attn --no-build-isolation`；③ RTX 50 系列可试：`pip install flash_attn==2.8.0.post2 torch==2.7.1 --no-build-isolation`；④ 仍失败查阅 Isaac GR00T 官方文档 |
| `mean is infinity` 报错 | 通常因评估时相机键名与训练不一致，检查 `--robot.cameras` 键名 |

**"训练 loss 正常但真机乱动"排查表**：

| 可能原因 | 排查 |
|----------|------|
| 关节顺序不一致 | 对比数据集 meta 与 `--robot.cameras` / 驱动 |
| 角度单位错误 | 确认度/弧度训练推理一致 |
| 相机键名不匹配 | `front`/`side` 与训练数据对齐 |
| embodiment_tag 错误 | 必须为 `new_embodiment` |
| 语言指令不匹配 | `--task` 句式与训练数据一致 |
| 相对动作未正确还原 | 确认 `use_relative_actions` 训练与推理一致；这是关节相对，不是 Relative EEF |

## 7. 🤖 训练效果优化建议

| 方向 | 建议 |
|------|------|
| 数据量 | 单任务先 50 条跑通，再扩到 100+ |
| 数据多样性 | 物体位置、光照、初始姿态多样化 |
| 增强 | 保持 `--dataset.image_transforms.enable=true` |
| 步数 | 数据少 10k–15k；数据多 20k–30k |
| 推理 | 先试 `n_action_steps=20`（须 ≤ 训练时的 `chunk_size=40`），再调 RTC |
| 迭代 | 失败 case 补采数据 → 合并数据集 → 继续微调 |

## 参考

- 官方 Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/> ｜ reBot LeRobot：<https://wiki.seeedstudio.com/cn/rebot_arm_b601_rs_lerobot/> ｜ <https://wiki.seeedstudio.com/cn/rebot_arm_b601_dm_lerobot/>
- NVIDIA Isaac-GR00T：<https://github.com/NVIDIA/Isaac-GR00T> ｜ GR00T 数据准备：<https://nvidia-isaac-gr00t.mintlify.app/guides/data-preparation>
- Seeed-Projects/lerobot：<https://github.com/Seeed-Projects/lerobot> ｜ LeRobot 安装：<https://huggingface.co/docs/lerobot/main/en/installation>
- 配套教程：本地参考教程（未随本仓库发布）**第四阶段「VLA 与 Isaac GR00T」**（第 18–21 章：VLA 理论、GR00T 系统架构、准备 VLA 数据集、GR00T 微调与真机评估）
- 相关技能：`rebot-arm-safety` ｜ `rebot-arm-data-collection` ｜ `rebot-arm-act-training` ｜ `rebot-arm-troubleshooting`
