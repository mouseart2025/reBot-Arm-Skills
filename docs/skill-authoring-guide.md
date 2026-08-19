# Skill 编写规范（Skill Authoring Guide）

本仓库所有技能遵循 **Agent Skills 开放规范**。本文档说明技能的结构、frontmatter 字段、正文组织方式与质量要求，供技能作者与 AI 协作编写时遵守。

## 1. 目录结构

每个技能是一个独立目录，放在仓库根 `skills/` 下：

```
skills/<skill-id>/
├── SKILL.md          # 必填：技能主体（frontmatter + Markdown）
├── references/       # 可选：补充参考资料（按需加载，不进主上下文）
└── assets/           # 可选：图片等资源
```

- 目录名（skill-id）使用 kebab-case，如 `rebot-arm-ros2`。
- **每个技能必须自包含**：`SKILL.md` 内联关键命令/表格；大段参考资料放入本技能自己的 `references/`，或用外部链接（官方 Wiki、GitHub）替代，避免跨技能目录的相对路径引用。

## 2. SKILL.md frontmatter（必填）

文件开头必须是一个 YAML frontmatter（前后各一条 `---`），至少包含：

```yaml
---
name: rebot-arm-ros2
description: 当用户需要配置或使用 reBot Arm 的 ROS2 接口（launch 启动、Topic/Service/Action 控制、状态机与故障码排查）时使用本技能。适用于 B601-DM 与 B601-RS。
---
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | kebab-case 技能名，与目录名一致，简短 |
| `description` | 是 | **AI 路由的关键**：一句话说明"用户想做什么时加载本技能"，包含触发关键词（如 reBot Arm、型号、LeRobot、ACT、ROS2 等），3 句以内 |

> 建议：description 用中文编写（面向中文用户），但保留英文技术关键词以便多语言 Agent 路由。

## 3. 正文组织

`SKILL.md` 正文按以下结构组织（可依技能内容增减小节）：

1. **简介**：一两句话说明本技能做什么、适用场景。
2. **何时使用**：明确触发条件。
3. **前置条件**：硬件/软件/权限前提，必要时引用 `rebot-arm-environment-setup`。
4. **安全要点**：真机操作类技能必须给出安全提醒，并提示先读 `rebot-arm-safety`。
5. **步骤**：分步骤、可执行的指引；命令用代码块；参数用表格说明。
6. **DM 与 RS 差异**：两个型号命令不同处分别给出（如 `--robot.type=seeed_b601_dm_follower` vs `seeed_b601_rs_follower`）。
7. **✅ 验证与预期结果**：每个实操技能必须包含，说明"运行什么 → 期望看到什么 → 失败怎么办"（1~3 条）。
8. **常见问题 / 排错**：指向 `rebot-arm-troubleshooting` 或内联 FAQ。
9. **参考**：官方 Wiki、GitHub、教程章节链接。

### 3.1 执行分工标记（AI 使用本技能时如何分工）

每个技能必须让 AI 明确"哪一步它能自己跑、哪一步必须交给用户"。在**步骤标题或步骤正文**前使用以下前缀标记，并在"简介"后加一行图例：

- `🤖 AI 执行` — 可在终端直接运行/自动化的命令（非交互、不需要密码）。例：`sudo chmod 666 /dev/ttyACM*` 之外的非交互命令、`pip install`、`lerobot-find-cameras opencv`。
- `👤 用户执行` — 必须用户手动完成：GUI/网页操作（DM_Tools、MotorBridge Studio、RViz 拖动）、按键控制（`lerobot-record` 的方向键/ESC、校准按 Enter）、插拔线缆、物理搬动机械臂、观察指示灯。
- `🔀 人机协作` — AI 执行命令但需要用户配合：需要输入 sudo 密码的命令、需要用户确认硬件状态/安全的操作、交互式 CLI 提示（`lerobot-calibrate` 按 C/Enter）。

> 规则：**凡涉及 `sudo` 或修改系统配置（如 `sudo apt remove brltty`）标 `🔀` 或 `👤`**；凡涉及网页/GUI/按键/物理操作一律标 `👤`。

### 3.2 环境状态记忆（memory）

每个会改变机器状态的技能（环境搭建、电机配置、数据采集等）在执行关键步骤后，应提示 AI 更新 `memory/local-machine-env.md`（如安装完成、标定完成、数据集创建），并在"前置条件"中提示先读该文件判断是否需要重做。见 `AGENTS.md` 的"环境状态记忆"一节。

## 4. 写作与格式要求

- **语言**：中文正文 + 英文命令/术语。代码注释保留原文或加中文注释均可。
- **准确性**：命令、参数、端口、包名必须与官方 Wiki / 官方仓库一致；不确定时标注"以官方文档为准"，不得编造。
- **代码块**：命令使用 ```bash / ```text，Python 使用 ```python。
- **表格**：参数说明、型号对比使用 Markdown 表格。
- **安全强调**：高风险操作使用 `> ⚠️` 或 `> 🔴` 引用块。
- **链接**：官方资源优先使用官方链接：
  - Wiki：<https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/>、<https://wiki.seeedstudio.com/rebot_b601_rs_getting_started/>
  - GitHub：<https://github.com/Seeed-Projects/reBot-DevArm>、<https://github.com/Seeed-Projects/lerobot>、<https://github.com/Seeed-Projects/reBotArm_control_py>、<https://github.com/Seeed-Projects/reBot-DevArm-Grasp>、<https://github.com/motorbridge/motorbridge>

## 5. 质量标准（Checklist）

- [ ] frontmatter 含 `name` 与 `description`，且 `name` 与目录名一致
- [ ] 正文包含可执行步骤与命令，命令可复制
- [ ] DM/RS 差异已覆盖（若适用）
- [ ] 真机操作技能包含安全要点
- [ ] 无编造的命令、参数或版本号
- [ ] 关键内容不超过约 400 行（避免上下文过载）；大段资料放 references/
- [ ] 在仓库根 `README.md` 技能清单中登记
