---
name: rebot-arm-data-collection
description: 为 reBot Arm（B601-DM / B601-RS）采集 LeRobot 模仿学习数据集：任务与 Episode 设计、相机配置（俯视/腕部、lerobot-find-cameras）、创建数据集并录制（lerobot-record）、录制控制（暂停/重录/ESC 结束）、数据集结构与质量检查（回放、可视化、删除/补录）。当用户需要录制示范数据、检查数据集质量或"模型学不好需要补数据"时使用本技能。
---

# reBot Arm 数据采集：LeRobot 数据集录制与质量检查

## 简介

本技能覆盖从"任务设计"到"录出合格数据集"的完整流程：先定义任务（起点/结束条件、一致性/多样性、成功标准），再配置相机（单/双相机、索引确认），用 `lerobot-record` 录制 Episode，最后用 `lerobot-dataset-viz` 可视化回放并按四条质量标准检查，必要时删除/补录/整集重录。适用于 B601-DM 与 B601-RS。

## 何时使用

- 用户要录制示范数据（测试 5 条 / 正式 50 条）、检查数据集质量（回放、可视化、结构）
- 用户说"模型学不好 / 成功率低 / 需要补数据"
- 用户问"任务怎么设计 / 相机怎么接 / 数据存在哪 / 怎么删坏数据"

## 前置条件

- **遥操作已跑通**（`lerobot-teleoperate` 主从跟随正常）：见 `rebot-arm-teleoperation`
- **相机已接好**（USB 直插电脑，见"相机配置"）
- **已完成安全检查**：先读 `rebot-arm-safety`（真机运动）
- **已确认型号**：DM（串口 `/dev/ttyACM0`、`damiao`）与 RS（CAN `can0`、`socketcan`）命令分支不同
- 环境已装好 LeRobot 依赖（conda + motorbridge，见 `rebot-arm-environment-setup`）

## 安全要点

> ⚠️ 录制动作为**真实运动**：机械臂会按你的遥操作真实移动，录制前清空运动范围内的人员与障碍物，手边放好电源开关，遇到失控立即断电（`rebot-arm-safety`）。

1. **结束录制用 ESC，不要按 Ctrl+C**：ESC 正常编码视频、计算统计量并保存数据集；Ctrl+C 属异常退出，数据可能不完整。
2. **主从臂电源脱落/接触不良/信号线脱落**：先停止程序 → 机械臂回初始 0 点 → 重新上电 → 再运行（防止数据错乱导致失控）。
3. 停止前把机械臂移回安全位，避免停在半空受力姿态。
4. 录制中目标物、盒子、相机、机械臂位置与光线保持固定——随便动产生的是噪声，不是多样性。

## 1. 任务设计（第 12 章）：先想清楚再开录

### 1.1 什么是 Episode，一条数据里有什么

**Episode 即一次完整的任务示范**：从机械臂处于起点姿态、任务开始，到任务完成，系统连续记录下的全部数据。

一条数据包含：

- **observation**：图像（相机帧）与关节状态
- **action**：**通过 Leader 给出的目标动作**（不是 Follower 事后实际到达的位置）——精确对应行为克隆定义：模型学的是"在这种观测和状态下，人当时想做什么"
- **时间戳**：图像走 USB、关节数据走 CAN，两路到达天然有先后，LeRobot 用时间戳把"同一时刻"的图像、状态、动作对齐成一行

### 1.2 起点条件与结束条件

采集前先用文字把任务定义写清楚，回答两个问题：**从哪开始？到哪算完？**

- **起点条件**：机械臂初始姿态固定——每条 Episode 都从同一个安全姿态出发（如零位附近）。起点五花八门，模型第一步就得学"从任意姿态怎么进入任务"，凭空增加难度。
- **结束条件**：成功结束 = 任务目标达成（如"方块完全进入盒子，夹爪松开，机械臂抬离"）；失败终止 = 出现无法恢复的状况（物体掉落、碰倒容器、进入危险姿态），立即停止本条录制

### 1.3 一致性与多样性：数据设计的核心矛盾

**一致性：教的是一种"做法"**

- 操作风格一致：同一任务所有 Episode 用同一种策略（如都从方块右侧接近、夹取、从上方移入盒子）。一半左抓一半右抓，模型学到的是两种做法的"平均"——往往是哪个都抓不着的诡异路径
- 节奏一致：动作速度、停顿位置大体稳定，设置 20 秒即在 20 秒内完成
- 流程一致：每条都完整走"接近→抓取→搬运→放置→撤离"，不省略步骤
- 场景初始状态可控：目标物放在规定区域内（区域可大、边界要清楚），无关物品清出工作区
- 相机位置固定：采集全程相机不能挪动——相机动 5 厘米等于世界变了

**多样性：见过的"情况"要够多**

- 目标位置多样：方块出现在工作区各个位置（网格化覆盖，而不是随手撒）
- 初始姿态多样：方块的朝向、与障碍的相对关系有变化

**泛化预算论**：数据量有限，变化花在哪个维度，模型就学会哪个维度——花在目标位置上，模型学会抓不同位置的目标；花在相机/光线变化上，模型既要学抓又要学视角差异，需要更多数据且效果差。"什么都随便动"产生的是噪声而非多样性；真要扩边界，走"补数据迭代"有意识地扩展。

### 1.4 成功与失败标准

- **失败片段：本条重录**。不要留下失败数据——模型确实会学，连失败一起学。
- **任务完成必须可客观判定**，而不是"看起来差不多了"。

### 1.5 数据数量与数据质量

经验参考（单一桌面任务、干净环境如数采实验盒内；没有数据采集箱建议增加数据量）：

| 数据量 | 预期效果 |
|---|---|
| **50 条** | 能跑通流程，模型在数据覆盖的区域内开始工作（入门任务起步量级） |
| **50–100 条** | 成功率进入可用区间，大多数单任务实验的甜点区 |
| **100+ 条** | 边际收益递减，除非任务复杂或成功率要求很高 |

- **50 条高质量数据，胜过 200 条敷衍数据。**
- **数据采集有问题，不要犹豫，直接重录这一条。**
- 想要泛化性强，那肯定是成百上千条数据。

### 1.6 单任务与多任务数据集

| 类型 | 说明 | 特点 |
|---|---|---|
| 单任务数据集 | 一个数据集只含一种任务（如"方块入盒"） | 模型目标单一、数据需求小、成功率容易做高；**第一个模型务必从单任务开始** |
| 多任务数据集 | 一个数据集含多种任务（抓方块、开抽屉、方块入抽屉） | 每条 Episode 用 `task_index` 标注任务；数据利用率高，但任务互相挤占模型容量，每个任务需要更多数据 |

### 1.7 数据制作示例：铅笔五点定位法（第 12 章）

**场景设计**：将目标物（教程示例：小龙虾）放入黑色盒子；黑盒底部用双面胶固定防移动；相机、机械臂保持固定，光线不变。

**铅笔五点定位法**（解决"物体怎么摆才算练到位"）：

1. **画点**：在数据采集区域用铅笔点上 **5 个点**，呈**十字架形状**——中心 1 个，上下左右各 1 个
2. **定距**：相邻点相隔 **5~10 cm**，确保五个点都在工作范围内、且在两路相机画面中清晰可见
3. **分配**：**每个点采集 10 组**，5 点 × 10 组 = **50 条**；不要先连续录完一个点再录下一个点，而是**每点 1 条、5 点为一轮，走 10 轮**

**夹取与放置流程**（一条完整示范）：

初始位置 → 移动到目标正上方（每次都到中心、保持相同高度）→ 张开夹爪（保持距离以免碰倒目标）→ 相同力度与速度夹取 → 移到黑色盒子中心正上方 → 匀速张开夹爪并抬起，目标平稳落入盒子 → 机械臂归位。重复 50 次。

### 1.8 数据采集迭代

**先采 50 条 → 训练 → 真机评估 → 针对失败场景补采 → 再训练**。模型大方向对、只是精度差，补数据有用；模型行为完全不对，说明任务或数据设计有问题，补再多也是浪费。

## 2. 相机配置

### 2.1 单相机与双相机方案

| 方案 | 组成 | 用途 |
|---|---|---|
| 单相机 | 只接俯视相机（front） | 第一次跑通流程、验证环境——少一路相机，排查问题少一个变量 |
| 双相机 | 俯视（front）+ 腕部（教程正文亦称 wrist，命令示例键名为 `side`） | **正式采集用（课程主线）**，ACT 模型默认吃两路输入；也可俯视 + 侧视 |

3、4 个相机也能采集训练：ACT 对相机路数无硬性限制（每路图像各自过共享 ResNet18 骨干得 token 再拼接进 Transformer，原版 ALOHA 双臂就是 4 路）。**代价**：每多一路，显存/计算近似线性增加、数据量需求增加、每路都要保证同步与固定机位。

- **俯视相机（front）**：固定支架上俯瞰整个工作区，告诉模型"目标在哪里、机械臂整体处于什么状态"
- **腕部相机**：装在机械臂末端跟着夹爪走，告诉模型"夹爪和目标的相对位置、该不该闭合"

### 2.2 查找相机索引：lerobot-find-cameras

```bash
lerobot-find-cameras opencv
```

输出列出每个相机的名称、ID 和默认分辨率（`Id: 0` 即索引号）。要点：

- 每台相机拍摄的图片可在 `~/rebot_lerobot/outputs/captured_images/` 找到，据此查看机位是否合适
- **笔记本自身摄像头通常索引为 0**，通过拔插 USB 相机找到正确的俯视/腕部索引
- **插拔顺序会改变索引**：今天前置是 0，明天重插可能就变了。**每次开录前重跑一次确认**
- **USB 相机必须直插电脑，不要接扩展坞**：无源 Hub 带宽竞争会表现为读不到图像或掉帧；两路相机最好分插不同 USB 控制器
- `index_or_path` 的值由 `lerobot-find-cameras` 输出的摄像头 ID 决定

### 2.3 相机参数推荐

推荐 **640 × 480 @ 30 fps，`fourcc: "MJPG"`**：

- **分辨率 640×480**：清晰度和实时性的平衡点——分辨率翻倍，USB 带宽和存储开销翻两番，而模型输入端本来就会缩放图像，收益有限
- **帧率 30**：与采集帧率一致（否则记录时反复用旧帧充数）
- **`fourcc: "MJPG"`**：图像压缩后再传输，USB 带宽压力小一个量级；`YUYV` 会导致分辨率/FPS 降低、机械臂运行卡顿。MJPG 下可支持 3 个摄像头 1920×1080 @ 30 FPS

## 3. 创建数据集并录制（lerobot-record）

> 输出命令前应随时准备录制：启动后会有声音提示进入录制阶段，若无声音可看终端提示。

### 3.1 完整录制命令（双相机 front + side，正式采集）

**RS 版本：**

```bash
lerobot-record \
    --robot.type=seeed_b601_rs_follower \
    --robot.port=can0 \
    --robot.id=follower1 \
    --robot.can_adapter=socketcan \
    --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: "MJPG"}, side: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, fourcc: "MJPG"}}" \
    --teleop.type=rebot_arm_102_leader \
    --teleop.port=/dev/ttyUSB0 \
    --teleop.id=rebot_arm_102_leader \
    --display_data=true \
    --dataset.repo_id=seeed_rebot_b601_rs/test \
    --dataset.num_episodes=5 \
    --dataset.single_task="Grab the crayfish into the box" \
    --dataset.push_to_hub=false \
    --dataset.episode_time_s=30 \
    --dataset.reset_time_s=20
```

**DM 版本：**

```bash
lerobot-record \
    --robot.type=seeed_b601_dm_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=follower1 \
    --robot.can_adapter=damiao \
    --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: "MJPG"}, side: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, fourcc: "MJPG"}}" \
    --teleop.type=rebot_arm_102_leader \
    --teleop.port=/dev/ttyUSB0 \
    --teleop.id=rebot_arm_102_leader \
    --display_data=true \
    --dataset.repo_id=seeed_rebot_b601_dm/test \
    --dataset.num_episodes=5 \
    --dataset.single_task="Grab the crayfish into the box" \
    --dataset.push_to_hub=false \
    --dataset.episode_time_s=30 \
    --dataset.reset_time_s=20
```

> 单相机测试：`--robot.cameras` 只保留 `front` 一路即可（格式同上）。

### 3.2 数据集相关参数说明

| 参数 | 含义 | 建议 |
|---|---|---|
| `--dataset.repo_id` | 数据集名，也是本地文件夹名 | 测试集和正式集分开命名，如 `rebot_b601/grab_cube_test` / `rebot_b601/grab_cube_v1` |
| `--dataset.single_task` | 任务描述，存入数据集 | **英文**，符合任务描述，如 `"Grab the crayfish into the box"` |
| `--dataset.num_episodes` | 要录多少条 | 测试 5 条；**正式 50 条（默认值就是 50）** |
| `--dataset.push_to_hub` | 录完是否上传 Hugging Face Hub | `false` 代表不上传（本地保存） |
| `--dataset.episode_time_s=30` | 一条数据的录制时间 | 可根据任务复杂度修改 |
| `--dataset.reset_time_s=20` | 恢复现场、等待下次录制的时间 | 可根据恢复现场的时间修改 |
| `--display_data=true` | 实时显示相机画面 | 建议开启 |

### 3.3 数据保存位置

```text
~/.cache/huggingface/lerobot/<你的 repo_id 路径>
```

例如 `--dataset.repo_id=seeed_rebot_b601_dm/test` 会在 `~/.cache/huggingface/lerobot/` 下创建 `seeed_rebot_b601_dm/test` 文件夹。

### 3.4 录制、暂停和重新录制（键盘控制）

| 按键 | 作用 |
|---|---|
| →（右箭头） | 提前结束当前 Episode，进入复位/下一条 |
| ←（左箭头） | 作废当前 Episode，重新录制本条 |
| ESC | 结束整个采集会话：编码视频、计算统计量、保存数据集 |

- **暂停/结束录制按 ESC，不要按 Ctrl+C**（否则异常退出）。
- 按键没反应是 `pynput` 版本问题，降级即可：`pip install pynput==1.6.8`（Linux 下另检查 `$DISPLAY` 是否已设置）。

### 3.5 测试录制与正式采集

1. **测试**：`num_episodes=5`，先录 5 条验证全流程（相机、同步、回放）。
2. **回放检查**：用第 4 节命令回放测试集，确认没问题。
3. **正式采集**：`repo_id` 换正式名、`num_episodes=50`，按**铅笔五点定位法**执行——每点 1 条、5 点一轮、共 10 轮。

## 4. 可视化与回放

**可视化数据集**（未上传 Hub、本地可视化，`repo_id` 用采集时自定义的名字）：

```bash
# RS
lerobot-dataset-viz \
  --repo-id seeed_rebot_b601_rs/test \
  --episode-index 0 \
  --display-compressed-images=false
```

```bash
# DM
lerobot-dataset-viz \
  --repo-id seeed_rebot_b601_dm/test \
  --episode-index 0 \
  --display-compressed-images=false
```

> 若上传到了 Hub，`repo_id` 换成 `${HF_USER}/rebot_test` 等 Hub 路径。

**真机回放**（教程标记为不稳定，可跳过或尝试；`--dataset.episode=0` 为第一条，可依次类推）。DM 示例：

```bash
lerobot-replay \
    --robot.type=seeed_b601_dm_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.can_adapter=damiao \
    --robot.id=follower1 \
    --dataset.repo_id=seeed_rebot_b601_dm/test \
    --dataset.episode=0
```

> RS 仅替换三个参数：`--robot.type=seeed_b601_rs_follower`、`--robot.port=can0`、`--robot.can_adapter=socketcan`（`repo_id` 相应换为 `seeed_rebot_b601_rs/test`）。此时机器人应做出与遥操作记录时一样的动作。

## 5. 数据集结构与质量检查（第 14 章）

### 5.1 数据集在硬盘上的结构

```text
~/.cache/huggingface/lerobot/seeed_rebot_b601_rs/test/
├── data/chunk-000/file-000.parquet        ← 数值帧（state / action / 时间戳）
├── videos/
│   ├── observation.images.front/chunk-000/file-000.mp4   ← 俯视视频（50 条拼接）
│   └── observation.images.wrist/chunk-000/file-000.mp4   ← 腕部视频（同上）
└── meta/
    ├── info.json                          ← 版本、fps、总帧数、特征定义
    ├── stats.json                         ← 每个特征的均值/方差/极值
    ├── tasks.parquet                      ← 任务描述表
    └── episodes/chunk-000/file-000.parquet ← 每条 Episode 的"档案卡"
```

**三种载体，各存一类数据：**

| 载体 | 存什么 | 为什么用它 |
|---|---|---|
| MP4 视频 | 两路相机的全部图像帧 | 图像占数据集体积九成以上，视频压缩比逐帧存图省一到两个数量级 |
| Parquet 表 | 每帧的数值：state、action、时间戳、索引 | 列式存储，读"第 3 关节的全部取值"不必加载整个文件 |
| meta 元信息 | 结构定义、统计量、任务、episode 索引 | 加载器和训练程序先读它，才知道怎么解释前两者 |

### 5.2 什么样的数据算"好"：四条质量标准

按教程第 14 章回放检查标准，判断数据集能不能进训练看四个维度：

1. **画面完整性**：两路画面都在，没有黑屏、花屏、一路静止不动
2. **清晰度与可见性**：画面清晰、曝光正常，方块和夹爪始终可见
3. **动作与画面同步**：夹爪闭合的瞬间，画面里正是夹爪碰到方块
4. **起止正确性**：开头在标准起始姿态，结尾达成结束条件

（结合第 12 章，数据层面还要满足一致性——同一种做法/节奏/流程；多样性——目标位置与姿态覆盖足够。）

### 5.3 回放与图像检查

可视化用 `lerobot-dataset-viz`，真机回放用 `lerobot-replay`（见第 4 节）。建议至少回放**第 0 条、中间一条、最后一条**：第一条看流程对不对，中间看状态有没有漂移，最后一条最容易暴露疲劳期的质量下滑。

### 5.4 发现问题怎么办：删除、补录还是整集重录

- **个位数坏条**（如第 3、17 条画面糊了）→ 删掉对应 2 条，再补录 2 条
- **成片问题**（一半条数光照变了、整批音画错位）→ 别修，**整集重录**。修出来的数据集七拼八凑，比数据少更伤模型

**删除数据**（`--operation.episode_indices "[0]"` 代表删除第一个数据集，依次类推；删除时需耐心等待；需修改对应的数据集名称）：

```bash
lerobot-edit-dataset \
  --repo_id rebot_b601/grab_cube_v1 \
  --operation.type delete_episodes \
  --operation.episode_indices "[0]"
```

**补录数据**：录制中会自动创建检查点；在原命令基础上加 `--resume=true` 继续补录。**恢复时 `--dataset.num_episodes` 设为要额外录制的数量**（不是数据集目标总数）。

> 删除后工具会自动**重建**数据集——episode 重新连续编号、`stats.json` 重新计算，不必手动修任何东西；无论删还是补，工具都会重新生成一遍 meta。若要从头开始记录，**手动删除数据集目录**即可。

## 6. 常见问题

| 现象 | 原因与处理 |
|---|---|
| 按键（→/←/ESC）没反应 | `pynput` 版本问题 → `pip install pynput==1.6.8`；Linux 检查 `$DISPLAY` 是否设置 |
| 相机读不到 / 掉帧 | USB 相机**直插电脑**（不要接扩展坞）；两路分插不同 USB 控制器；拔插后索引会变，重跑 `lerobot-find-cameras` 确认 |
| 画面里没有目标/夹爪 | 相机安装位置不对 → 查看 `~/rebot_lerobot/outputs/captured_images/` 实拍图调整机位 |
| 录制中途异常退出（Ctrl+C 或断电） | 用 `--resume=true` 补录（`num_episodes` 设为额外条数）；要重头开始就手动删除数据集目录 |
| 图像与动作不同步 | 相机帧率低于 30 会用旧帧充数 → 按推荐参数 640×480@30fps、MJPG 配置 |
| 模型学不好 / 成功率低 | 先回放检查数据（5.3 节）：坏条删除/补录；行为完全不对说明任务或数据设计有问题（第 1 节），补数据无效 |

## 参考

- 官方 Wiki（Dataset Collection / Visualize the Dataset / Replay an Episode 章节）：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/> ｜ <https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
- 官方仓库：<https://github.com/Seeed-Projects/lerobot>
- 配套教程（本仓库同目录）：第 12 章《机器人数据集与任务设计》、第 13 章《相机配置与 LeRobot 数据采集》、第 14 章《数据集结构与质量检查》
- 相关技能：安全 → `rebot-arm-safety`；遥操作 → `rebot-arm-teleoperation`；环境 → `rebot-arm-environment-setup`
- 下一步：训练 ACT 模型 → `rebot-arm-act-training`
