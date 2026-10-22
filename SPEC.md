# FAEA-LIBERO 复现规格书（SPEC v1.0）

| 项 | 值 |
|---|---|
| 状态 | v1.0（待评审） |
| 日期 | 2026-10-16 |
| 源论文 | Demonstration-Free Robotic Control via LLM Agents（FAEA），arXiv:2601.20334v2 |
| 复现底座 | MiniClaudeCode（用户自研 agent，下称 MCC） |
| 运行机器 | 本机：RTX 3050 4GB / 7GB RAM / 8 核 / miniforge3 |
| 仓库根 | `/home/czx/FAEA` |

---

## 1. 背景与目标

### 1.1 论文要点

FAEA 将未修改的生产级 agent SDK（Claude Agent SDK + Opus 4.5）直接用于仿真机器人操作：agent 通过 Gymnasium 风格接口（`step / reset / check_success / get_obs`）自主写 Python 脚本控制机器人，在**特权状态**（非 RGB）与**笛卡尔末端控制**抽象下，通过 ReAct 循环试错发现任务程序，零示教。LIBERO 120 任务上：pilot（10 次尝试上限）70.6% → baseline（无上限）84.9% → +coaching 88.2%。

关键事实（本复现须对齐的协议细节）：

- 三条件是**增量重试协议**，不是三次独立全量：pilot 失败的 35 个任务在 baseline 条件重试恢复 17/35（累计 102/120）；coaching 对**同一批 35 个失败任务**重试恢复 21/35（累计 106/120）。
- Prompt 开发只用 LIBERO-Object task 0，其成功脚本作为 example 注入后续所有任务的 prompt，实测省约 3× token。
- 每任务产出：`meta.json`（success、num tries）、`episode.py`、`video.mp4`。
- 成功后置 trace 审查：标记硬编码坐标、穷举网格搜索、绕过任务语义的解法，确认后剔除。

### 1.2 复现要检验的命题

对应论文三个 scoped claims 中本阶段可检验的部分：

| 命题 | 本阶段检验方式 |
|---|---|
| C1：单一 agent/模型无需示教即可发现操作程序 | LIBERO 120 任务三阶段协议出数 |
| C3：成功程序可产出仿真轨迹 | 每成功任务产出可独立重放的 episode.py + 轨迹/视频 |
| C2：同一 prompt 与 agent 循环跨仿真器迁移 | **不在 v1 范围**（ManiSkill/MetaWorld 后置） |

### 1.3 非目标（v1 明确不做）

- ManiSkill3 / MetaWorld 基准（留待 v2）
- VLA 基线复跑（SmolVLA 等数字直接引用论文，且论文自述观测模态不同、比较是 context 而非 controlled）
- 真机部署、其他 agent 框架、模型横评
- 轨迹数据训练 VLA 的下游（论文 Future Work）
- 论文 Table I 中 VLA 基线的任何训练

### 1.4 验收哲学（先跑通）

- **硬门槛是基建完整性**：链路无基建性失败（崩溃、超时、产物缺失与任务失败严格区分）。
- **绝对成功率是信息项不是门槛**：模型非 Opus 4.5（D03），数字允许显著偏离论文；解读时如实标注模型差异。
- 所有与论文的偏差必须登记（§5.7），不静默放宽。

---

## 2. 决策记录

| # | 决策 | 理由 |
|---|---|---|
| D01 | 范围 = LIBERO 120 任务全量先行 | 论文主战场；三条件消融都在此；跑通后再扩 |
| D02 | Agent 底座 = MCC，零修改起步 | 论文卖点是"SDK 未修改"；运行参数全走环境变量 |
| D03 | 模型 = OpenAI 兼容端点，配置化可热换 | 不聚焦模型；所有结果标注所用模型与版本 |
| D04 | 集成 = runner 以子进程 per-task 拉起 MCC | 崩溃隔离、与 MCC 解耦、符合极简 |
| D05 | MCC 若确需改代码 → 先登记偏差再改 | 保持"底座未修改"主张可审计 |
| D06 | 本机运行，初版串行；M4 起改为 --parallel 2（修订） | 实测单会话峰值 ~1GB（MCC 31MB + 仿真子进程瞬态），可用 5.4GB，2 并发安全；90 套件 88 任务串行预估 70h+ 不可接受，加 RAM 背压（<2.2GB 等待） |
| D07 | 双 conda 环境：`libero`(py3.10) + `mcc`(py3.11) | LIBERO 依赖 robosuite 1.4.1 适配 py≤3.10；MCC 需 3.11+（StrEnum） |
| D08 | 节奏 = 单任务链路 → 10 任务试点 → 全量 | 稳定底座优先，避免带病全量 |
| D09 | 视频第一版就带（EGL 离屏渲染） | 论文产出含 video.mp4；失败分析依赖视频 |
| D10 | 三阶段全做（pilot → baseline → coaching） | 完整复现论文协议 |
| D11 | few-shot example 忠实复现 | task 0 成功脚本注入后续 prompt（3× token 节省） |
| D12 | 成功判定 = env 原生谓词 + runner 独立重跑复核 | 防 agent 谎报；成本低 |
| D13 | trace 审查 = 规则 + 人工抽查先行，自动审查器后置 | 对齐论文后置审查机制，先简后全 |
| D14 | 动作空间 = 绝对末端位姿控制（7D） | 论文明言三基准共用 absolute EEF 抽象；M0 验证 robosuite OSC absolute 模式可用，不可用则登记偏差并降级 |
| D15 | Prompt 用英文原文（论文 Fig.1 模板） | 忠实复现；任务描述取 LIBERO 官方英文指令 |
| D16 | 模型 = 双平台 flash 档轮换：sensenova-6.8-flash-lite（主）→ agnes-3.0-flash（备） | 免费额度耐用优先；实测两模型 tools 均可用；限额时 `rotate_key.py` 切换，429 由 MCC 自带退避吸收 |
| D26 | M8 前置：`get_obs()` 增加 `articulated_joints`（V13） | Goal 套件旧模型 0% 的直接病灶是看不到抽屉关节状态；先用免费模型在 Goal 10 上做 obs 消融，再决定是否进入强模型实验 |

---

## 3. 系统架构

### 3.1 组件与数据流

```
                    ┌─────────────────────────────────────────────┐
                    │  runner.py（编排，跑在 mcc 环境或系统 python）│
                    └──────┬──────────────────────────┬────────────┘
        1. 准备工作区      │                          │  4. 收集产物
        (template/ + prompt)│                         │  5. 独立复核(review)
                           ▼                          ▼
   ┌────────────────────────────────┐        ┌────────────────────────┐
   │  MCC 子进程（mcc 环境, py3.11） │        │  results/<stage>/...   │
   │  --task "$(cat prompt.txt)" -y │        │  episode.py / meta.json│
   │  --root <task_workspace>       │        │  video.mp4 / trace.jsonl│
   │                                │        │  run.json               │
   │  工具: bash/write/read/...     │        └────────────────────────┘
   │    │ bash 执行 agent 写的脚本  │
   │    ▼                           │        6. report.py 汇总
   │  <libero_python> episode.py    │        7. review.py 可疑规则
   │  （libero 环境, py3.10）       │
   │    └─ sim/ wrapper:            │
   │       reset/step/get_obs/      │
   │       check_success + EGL 视频 │
   └────────────────────────────────┘
```

一次任务会话 = 一个 MCC 子进程 = 一个任务工作区。agent 在工作区内读 `docs/`、写脚本、用 bash 以 libero 解释器执行，产物落工作区；runner 会话结束后收集、复核、归档。

### 3.2 仓库目录结构（极简，5 个可执行单元）

```
/home/czx/FAEA/
├── SPEC.md                  # 本文档
├── config.json              # 全局运行配置（§4.6）
├── envs/
│   ├── libero.yml           # M0 锁定后的环境 spec（含版本钉子）
│   └── mcc.md               # MCC 环境安装说明（pip install -e）
├── sim/
│   ├── libero_env.py        # LIBERO wrapper（§4.1，agent 唯一仿真入口）
│   └── install_libero_env.sh# 可选：把 sim/ 安装进 libero 环境（或 PYTHONPATH 方案）
├── template/
│   ├── README.md            # agent 入口契约：布局、解释器路径、必产出
│   └── docs/
│       ├── api.md           # wrapper API 完整文档
│       └── gymnasium.md    # 标准接口摘要（对应论文 Gymnasium 文档）
├── runner.py                # 编排器（§4.3）
├── review.py                # 独立复核 + 可疑规则（§4.4）
└── report.py                # 汇总报告（§4.5）

运行期生成（gitignore）：
├── results/
│   └── <stage>/<suite>/<task_id>/
│       ├── workspace/       # agent 沙箱（episode.py、meta.json、video、.sim_state）
│       ├── prompt.txt       # 实际发送的 prompt 全文（含 example 与否、coaching 与否）
│       ├── trace.jsonl     # MCC 会话 trace（从 workspace/.mcc 复制）
│       ├── run.json        # runner 元数据（§附录 D）
│       └── verify/         # 独立重跑复核产物
└── reports/                # report.py 输出（markdown + csv）
```

MCC 本体位于 `/home/czx/MiniClaudeCode`（workspace 外，独立管理，不进本仓库）。

### 3.3 双 conda 环境

| 环境 | Python | 内容 | 作用 |
|---|---|---|---|
| `libero` | 3.10 | LIBERO（官方仓库）+ robosuite 1.4.1 + mujoco 2.3.x + imageio[ffmpeg] | 执行 agent 写的 episode.py、跑 wrapper |
| `mcc` | ≥3.11 | `pip install -e /home/czx/MiniClaudeCode` | 执行 MCC 本体 |

- 具体版本钉子在 M0 冒烟通过后写入 `envs/libero.yml` 并冻结；此后不再漂移。
- `libero` 环境只装论文运行所需，不装 torch 等策略训练依赖（若 LIBERO 安装强依赖则按需最小化）。
- LLM 端点配置（`LLM_BASE_URL / LLM_API_KEY / LLM_MODEL`）由 MCC 仓库 `.env` 管理，不进本仓库、不进 git。

### 3.4 进程模型：一次任务会话的生命周期

1. **准备**：runner 为任务 `<stage>/<suite>/<task_id>` 创建工作区（复制 `template/`），填充 `prompt.txt`（模板 + 任务描述 [+ example 脚本] [+ coaching tips]）。
2. **执行**：runner 以子进程拉起 MCC：
   ```
   cd /home/czx/MiniClaudeCode && \
   MAX_TURNS=<per-stage> MAX_TOTAL_TOKENS=<cfg> \
   python main.py --task "$(cat <task_dir>/prompt.txt)" -y --root <task_dir>/workspace
   ```
   退出码 0 = agent COMPLETED（≠任务成功）；非 0 = MCC 侧失败（失败原因从 trace `run_end` 读取）。
3. **墙钟看护**：runner 维持 `task_walltime_min`（默认 120）超时 kill，归类 `infra_timeout`。
4. **收集**：归档 `workspace/{episode.py,meta.json,video 或 try_*.mp4}`、`.sim_state.json`、trace。
5. **复核**（review.py）：在干净副本中用 libero 解释器独立重跑 `episode.py`，比对 success。
6. **归档**：写 `run.json`，含失败分类与全部指标。

---

## 4. 组件规格

### 4.1 `sim/libero_env.py` — LIBERO Wrapper

agent 的唯一仿真入口。**设计约束：API 面向 agent 文档化、语义与论文四接口同构；一切 LIBERO/robosuite 内部细节不外泄。**

#### 4.1.1 公开 API

```python
from sim.libero_env import LiberoEnv

env = LiberoEnv(task_id="libero_object_1",          # 任务枚举见 4.1.6
                seed=0,                              # 确定性初始状态
                record_video=True)                   # 自动逐 try 录制
obs = env.reset()                                    # 1 try 计数在此发生
obs, reward, done, info = env.step(action)           # 绝对末端控制
state = env.get_obs()                                # 特权状态观测（不推进物理）
ok = env.check_success()                            # env 原生成功谓词
```

| 方法 | 语义 |
|---|---|
| `reset()` | 重置到任务初始状态；**每次调用计 1 try**（cap 命中时抛 `TrialCapExceeded`，agent 可在脚本输出里看到） |
| `step(action)` | 推进一个控制步；`done` 仅表示 rollout 结束条件（步数上限），不表示成功 |
| `get_obs()` | 返回特权状态字典（不消耗 try） |
| `check_success()` | 返回 bool；**唯一权威成功信号**，来自 LIBERO 任务原生谓词 |

#### 4.1.2 动作空间（D14）

- `action`：7D = `[x, y, z, roll, pitch, yaw, gripper]`，**绝对**末端位姿目标（robosuite OSC_POSE `input_type='absolute'`），单位米/弧度；gripper ∈ {-1 闭合, +1 张开}。
- M0 验证 absolute 模式在 LIBERO + robosuite 1.4.1 下可用；**若不可用**：登记偏差 V11，降级为 delta 控制（文档同步改写），并复跑 M0/M1。
- 精确语义（坐标系、四元数 vs 欧拉、gripper 符号约定）在 M0 锁定后完整写入 `template/docs/api.md`，agent 只依赖该文档。

#### 4.1.3 特权状态 schema（`get_obs()`）

```json
{
  "eef_pos": [x, y, z],
  "eef_quat": [x, y, z, w],
  "gripper_open": 0.0~1.0,
  "objects": { "<object_name>": {"pos": [x,y,z], "quat": [x,y,z,w]} },
  "articulated_joints": {
    "<joint_name>": {
      "body": "...", "type": "slide|hinge",
      "qpos": 0.0, "range": [min, max], "travel": 0.17,
      "axis_world": [x,y,z], "anchor_pos": [x,y,z],
      "body_pos": [x,y,z], "body_quat": [x,y,z,w],
      "handle_pos": [x,y,z], "handle_mesh": "...",
      "open_fraction": 0.0, "opening_direction": [x,y,z]
    }
  },
  "task_info": { "task_description": "...", "try_count": 4, "trial_cap": 10 }
}
```

对象名与坐标语义以 M0 锁定后的 `docs/api.md` 为准。**不暴露**成功判定内部、目标位姿、BDD 谓词等任务语义信息。

`articulated_joints` 为 M8 前置扩展（V13）：把抽屉/门/旋钮的关节类型、qpos、行程、世界系轴、锚点、把手位置作为**契约内观测**暴露，替代"模型反推 MJCF"。该字段不包含目标位姿或任务谓词。

#### 4.1.4 try 计数与 trial cap

- 计数持久化于 `<workspace>/.sim_state.json`（跨脚本进程存活），由 wrapper 读写。
- pilot 条件 `trial_cap=10`：第 11 次 `reset()` 抛异常，异常文本明示 cap 已到。
- baseline/coaching 条件 `trial_cap=None`：只计数不强制。
- **try 的定义 = 一次 `reset()` 及其后的 rollout**（而非一次脚本执行），可在多 rollout 脚本下正确计量，与论文 "Tries/Task: simulation runs" 对齐。

#### 4.1.5 渲染与视频（D09）

- `MUJOCO_GL=egl` 离屏渲染，分辨率 256×256、20fps（`config.json` 可调；论文未给参数，登记 V10）。
- 每个 try 自动落盘 `workspace/try_<n>.mp4`；runner 按 `meta.json.final_try` 选择对应视频归档为 `video.mp4`（论文产出形态）。
- EGL 失败时回退 OSMesa 软件渲染（慢但 256×256 可接受），回退发生即登记。

#### 4.1.6 任务枚举与 suite 映射

| suite | 任务数 | benchmark key | 论文列名 |
|---|---|---|---|
| libero_object | 10 | `libero_object` | Object |
| libero_spatial | 10 | `libero_spatial` | Spatial |
| libero_goal | 10 | `libero_goal` | Goal |
| libero_90 | 90 | `libero_90` | Long |

（LIBERO 另有 `libero_10`——10 任务长程套件，即 π0.5 报告所用 LIBERO-10——与 `libero_100`，均不在本复现范围。勘正：初版误写 Long=libero_10，据官方源码 `libero_suite_task_map.py` 勘正。）

- 枚举通过 `libero` 官方 benchmark API 获取，suite 内按官方 `libero_task_map` 顺序建立 `<suite>_<idx>`（0 起）稳定索引；**task 0 = libero_object 索引 0**（论文 "task 0 (LIBERO-Object)"）。
- `{{TASK_DESCRIPTION}}` 填 LIBERO 官方英文任务指令，不改写。
- 全量核对：120 个 key 与论文四 suite 计数（10/10/10/90）一致，M0 断言。

### 4.2 `template/` — 任务工作区模板

agent 进入工作区后自主探索（MCC 惯例第一步 `find_files`），模板必须自解释：

```
template/
├── README.md          # 入口契约（agent 读的第一个文件）
└── docs/
    ├── api.md        # wrapper 完整 API：构造、动作语义、obs schema、
    │                  # try/cap 行为、视频落盘、确定性 seed 建议
    └── gymnasium.md  # step/reset 标准语义摘要（对应论文 Gymnasium 文档）
```

`README.md` 必须写明（agent 契约的核心）：

1. 文件布局与产出要求：`episode.py`（最终单集脚本）、`meta.json`（`{"success": bool, "num_tries": int, "final_try": int}`）、视频由 wrapper 自动录制；
2. **仿真脚本解释器**：`<libero_python>` 绝对路径（libero 环境），并声明"环境已固定，不要安装/修改任何包"；
3. `episode.py` 的可复现要求：固定 seed，保证 runner 独立重跑可复现；
4. docs/ 的位置与"所有仿真交互只经 `sim.libero_env` 文档化 API"的边界声明。

**注意**：`docs/example` 只含 API 最小用法片段（构造 env + 一步），**不含任何任务解法**；任务解法 example 只经 prompt 注入（§5.6），两者严格分离。

### 4.3 `runner.py` — 编排器

```bash
python runner.py --stage p0_prompt_dev [--task libero_object_1]
python runner.py --stage p1_pilot   [--all | --sample 10 | --task ID,...]
python runner.py --stage p2_baseline_retry   # 自动只跑 p1 失败任务
python runner.py --stage p3_coaching_retry   # 自动只跑 p1 失败任务
```

职责与规则：

1. **工作区准备**：复制 `template/`，按阶段填 prompt（§5），注入 example（p1 起）。
2. **子进程拉起 MCC**：§3.4 命令模板；`MAX_TURNS` 按阶段取 `config.json`。
3. **看护**：墙钟超时 kill；检测 workspace 残留（无 episode.py / 无 meta.json / 无任何 bash 执行痕迹）→ `infra` 类失败。
4. **产物收集**：episode.py、meta.json（原件保存，复核不覆盖）、选定 try 的 video、trace.jsonl（自 `workspace/.mcc/` 复制）、`.sim_state.json`。
5. **断点续跑**：以 `<task_dir>/run.json` 存在与否为幂等标记；中断后重跑跳过已完成任务。
6. **串行**：`max_parallel=1`（D06），config 不提供并发选项。
7. runner 自身在 mcc 环境下运行（只需标准库）。

### 4.4 `review.py` — 独立复核与可疑审查

**独立复核（每成功任务，D12）**：

1. 复制 `workspace` 到 `verify/` 沙箱，清空 `.sim_state.json` 计数；
2. 以 libero 解释器重跑 `episode.py`（墙钟 15min）；
3. 比对重跑后 `meta.json.success`：
   - 一致成功 → `success_verified`
   - 原报成功、复核失败 → `success_unverified`，**不计入主成功率**，单列并供人工裁决（论文对 MetaWorld 两个作弊任务同样"成功但记失败"）。

**可疑规则（对全部 `success_verified` 任务，D13）**，命中即标记 `flagged`，由人工复核后定 `excluded_cheating`：

| 规则 | 检测方式 |
|---|---|
| R1 绕过 API 直写仿真状态 | episode.py 出现 `env.env`、`env.sim`、`qpos[`、`set_state` 等未文档化访问 |
| R2 穷举搜索 | 嵌套循环遍历候选位姿 / 对动作空间网格扫描 |
| R3 操纵成功信号 | 调用任务内部谓词或直接写 `meta.json` success 而非调用 `check_success()` 的结果 |
| R4 疑似内部坐标硬编码 | 与 reset 前初始状态差异极小却命中的字面常量位姿（弱信号，仅提示人工） |

规则宁漏报不误报（对齐 MCC 的失败模式标注哲学）；自动审查器（论文用 Claude Code 做 post-hoc 审查）后置为 v1.1。

### 4.5 `report.py` — 汇总

```bash
python report.py [--stage p1_pilot,p2_baseline_retry,...] [--compare-paper]
```

产出 `reports/<timestamp>/`：`summary.md` + `tasks.csv`。

- **任务级表**（csv）：stage、suite、task_id、outcome、verified、tries、turns、tokens_in/out、wall_time、tool_calls 分布、模型名、flagged。
- **论文 Table I 同构表**（markdown）：三条件 × 四 suite + Avg。累计口径：baseline = p1 成功 + p2 恢复；coaching = p1 成功 + p3 恢复（对齐论文 85+17 / 85+21 的算法）。
- **资源表**（论文 Table V 同构）：per-suite 平均 turns / tries / tokens / 时间 / 工具分布。
- `--compare-paper` 附论文原数字列与差值，**并强制附注模型差异声明**（D03）。
- 成功率双口径：严格口径（success_verified / 全部 120）与有效口径（剔除 infra 失败的分母），两口径并列，不混用。

### 4.6 `config.json`

```json
{
  "llm": {
    "models": { "sensenova": "sensenova-6.8-flash-lite", "agnes": "agnes-3.0-flash" }
  },
  "model_label": "auto(取 MCC .env 的 LLM_MODEL)",
  "stages": {
    "p0_prompt_dev": { "max_turns": 60, "trial_cap": null },
    "p1_pilot":      { "max_turns": 60, "trial_cap": 10 },
    "p2_baseline_retry": { "max_turns": 80, "trial_cap": null },
    "p3_coaching_retry": { "max_turns": 80, "trial_cap": null }
  },
  "max_total_tokens": 1500000,
  "task_walltime_min": 120,
  "video": { "res": 256, "fps": 20 },
  "seed": 0,
  "mcc_dir": "/home/czx/MiniClaudeCode",
  "libero_python": "/home/czx/miniforge3/envs/libero/bin/python"
}
```

参数依据：论文 Table IV 中 Goal 任务平均 52.3 turns，故 pilot 用 60、重试阶段用 80 留尾部余量；`max_total_tokens` 取论文单任务最大消耗（47.1K 输出 token，Spatial）的充分余量；MCC 默认值（25 / 800K）不满足论文条件，属运行参数覆盖（D02，不改代码）。

---

## 5. 实验协议

### 5.1 总览：增量重试协议

```
P0  task 0 prompt 开发（1 任务，人工迭代）        → 产出 example episode.py
P1  pilot:      120 任务 × trial_cap=10           → S1 = 成功数（论文 85/120, 70.6%）
P2  baseline:   对 P1 失败任务 × 无 cap 重试       → 恢复 R2（论文 17/35）
P3  coaching:   对 P1 失败任务 × 无 cap + tips 重试 → 恢复 R3（论文 21/35）
```

- 累计口径：baseline 成功率 = (S1+R2)/120（论文 84.9%）；coaching = (S1+R3)/120（论文 88.2%）。
- P3 对**全部 P1 失败任务**重试（含 P2 已恢复的，论文口径即 21/35 对同一批 35 任务），保证与论文同构。
- 总会话数 ≈ 120 + 2×|P1 失败集|（论文量级 ≈ 190 次）。
- 每阶段新工作区（`results/<stage>/`），prompt 阶段化但 example 一致。

### 5.2 P0：prompt 开发

1. 对 task 0 反复跑 runner（`--stage p0_prompt_dev`），人工迭代至稳定成功；
2. 稳定判据：**连续 2 次全新会话均 `success_verified`**；
3. 固化该次 `episode.py` 为 example，此后不再改动 prompt 模板（改动即重跑 P0）；
4. 本阶段允许人工调整 prompt 措辞；P1 起冻结。

### 5.3 P1：pilot（120 任务）

- 全部 120 任务、`trial_cap=10`、baseline 模板（无 coaching 段）+ example。
- 先以 `--sample 10`（分层：object 3 / spatial 3 / goal 2 / long 2）跑试点 M3，通过后 `--all`。

### 5.4 P2：baseline 重试

- 输入集 = P1 中 outcome 非成功的任务；`trial_cap=null`；prompt 与 P1 完全一致（同一 example、无 coaching）。
- MCC 侧新会话（不携带 P1 上下文）——论文 "We retry the 35 tasks" 无上下文继承表述，按新会话处理（登记 V12）。

### 5.5 P3：coaching 重试

- 输入集 = 与 P2 相同的 P1 失败任务；prompt 追加论文 Fig.1 蓝色 Coaching Tips 五条原文；
- tips 来源对齐论文：从**本复现 P1 失败视频**人工提炼可确认论文原 tips（论文 tips 即 LIBERO 失败分析所得），**优先逐条使用论文原文**；若需补充新 tip，须在报告登记来源与动机（论文 ManiSkill 负对照表明 tips 是任务域特定的，故补充需谨慎）。

### 5.6 few-shot example 机制（D11）

- 自 P1 起，prompt 在论文模板基础上追加：

  ```
  ## Example
  A successful episode script for a different LIBERO task (from this same setup):
  <task 0 的 episode.py 全文>
  ```

- 注入位置为论文未指定的实现细节，本复现定义如上（登记 V8）。
- 3× token 节省为论文实测值，本复现在 report 中统计实际 token 消耗对照（信息项）。

### 5.7 与论文协议的偏差登记表

| # | 偏差 | 影响 | 处置 |
|---|---|---|---|
| V1 | Agent SDK：Claude Agent SDK → MCC | 论文明确不跨框架宣称；本复现即检验可迁移性（扩展性声明） | 报告显著标注 |
| V2 | 模型：Opus 4.5 → 可配置端点 | 成功率数字不可直接对标 | 双列呈现 + 模型声明 |
| V3 | MCC 无 WebFetch → 文档预置 docs/ | 论文 WebFetch 仅占 2% 调用 | 视为等价机制 |
| V4 | "无上限" → 硬顶（turns 60/80、tokens 1.5M、墙钟 120min） | 极端长尾任务可能被截断，记 `max_turns`/`budget` 类失败 | 数值登记可调 |
| V5 | trace 自动审查 → 规则 + 人工 | 论文自动审查器未开源 | v1.1 再自动化 |
| V6 | trial cap 强制机制论文未述 → wrapper reset 硬计数 | 更严格（论文可能仅 prompt 约束） | 有利方向 |
| V7 | 独立重跑复核为新增 | 论文未见等价机制；可能暴露论文未遇的 flaky | 不利方向，如实报告 |
| V8 | example 注入位置/格式为自定义 | 论文只说"included as an example" | 实现细节 |
| V9 | 视频参数 256×256@20fps | 论文未给 | 可配置 |
| V10 | MCC 上下文压缩机制与 Claude SDK 原生机制不同 | token 曲线不可比 | 指标口径独立统计 |
| V11 | （条件触发）absolute 控制不可用降级 delta | 违背论文抽象声明 | 触发时升级评审 |
| V12 | 重试会话不继承历史上下文 | 论文未述 | 按"全新会话"最简解释 |
| V13 | M8 前置：特权观测增加 `articulated_joints`（关节类型/qpos/行程/轴/锚点/把手） | 超出论文 obs schema；Goal 与铰接 Long 任务不再与论文严格同条件 | 先做 Goal 10 obs 消融；M8 报告单列；旧 40/120 结果不回溯、不混算 |

新增偏差随做随登记，不允许静默偏离。

---

## 6. 成功判定与指标

### 6.1 判定链

```
env.check_success()（原生谓词）
  → episode.py 写 meta.json.success（agent 自报）
    → runner 读 run.json.outcome
      → review.py 独立重跑复核（D12）
        → 可疑规则扫描（D13）
          → 最终 outcome
```

### 6.2 失败分类学（run.json.outcome 枚举）

| outcome | 定义 | 计入成功率 |
|---|---|---|
| `success_verified` | 原生成功 + 复核一致 + 未被剔除 | ✓ |
| `success_unverified` | 原报成功，复核失败 | ✗（单列，人工裁决） |
| `excluded_cheating` | 审查确认作弊 | ✗ |
| `task_failed` | MCC exit 0（agent 自认完成）但 success=0 | ✗ |
| `max_turns` / `budget` / `stalled` / `llm_failure` / `internal_error` | MCC TerminationReason 映射（completed 之外七种） | ✗ |
| `infra_env` | wrapper/env 崩溃、产物缺失 | ✗（另计基建失败率） |
| `infra_timeout` | 墙钟超时被 kill | ✗（另计） |

**基建完整性指标 = (infra_env + infra_timeout) / 总会话数，M3 起必须为 0**；不为 0 时禁止进入下一里程碑。

### 6.3 指标定义（对齐论文 Table IV/V）

| 指标 | 来源 |
|---|---|
| 成功率（严格/有效双口径） | §4.5 |
| Turns/Task（ReAct 轮数） | MCC trace `turn_start` 计数 |
| Tries/Task | wrapper `.sim_state.json` |
| Tokens/Task（in/out 分列） | MCC trace `run_end` |
| Time/Task | runner 墙钟 |
| 工具分布（bash/write/read/…） | MCC trace `tool_call` 按 tool 名聚合 |
| Cost/Task（可选） | tokens × config 价格表；未配置则省略 |

### 6.4 可疑 trace 处置

命中 §4.4 规则 → `flagged` → 人工裁决 → `excluded_cheating`（计入失败）或解除。处置记录（含裁决理由）写入 `reports/`，对齐论文"两处 MetaWorld 剔除"的诚实记账。

---

## 7. 里程碑与验收

| # | 内容 | 验收判据（可证伪） |
|---|---|---|
| M0 底座 | 双 conda 环境 + 锁定 `envs/libero.yml` + 冒烟脚本 | ① `libero` 环境随机动作 rollout task 0：绝对控制 step×20、get_obs 全字段、check_success 可调用、try_1.mp4 非空，退出码 0；② 120 任务枚举计数 = 10/10/10/90 断言通过；③ `mcc` 环境 `--task "创建 hello.py 输出 hello" -y` exit 0 且文件存在 |
| M1 单任务链路 | task 0 全链路（runner 一条命令） | `results/p0_prompt_dev/` 产出四件套 + run.json，outcome ∈ {success_verified, 明确分类} |
| M2 prompt 定稿 | task 0 稳定 | 连续 2 次全新会话 `success_verified`；example 固化 |
| M3 试点 | `--sample 10` 分层试点 | 基建失败 = 0；10/10 会话全部给出分类 outcome；report 可生成 |
| M4 全量 pilot | 120 任务 `--all` | 120/120 分类完成；Table I 同构表 + 资源表产出 |
| M5 baseline 重试 | P2 | 失败任务全部重试完成，恢复数入表 |
| M6 coaching 重试 | P3 | 同上；tips 若有补充已登记 |
| M7 复核与报告 | review + report 全量 | 全部 success 经独立复核；可疑规则全量扫描；终版报告含偏差表与模型声明 |

依赖链：M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7；任何一步判据不过，停在该步修复，不越过。

---

## 8. 风险登记表

| # | 风险 | 概率/影响 | 缓解 |
|---|---|---|---|
| R1 | LIBERO 依赖链（robosuite 1.4.1 / mujoco 2.3.x）在当前 pip 生态安装失败 | 中/高 | M0 唯一焦点；逐版本钉子；实在不行打补丁 fork 并登记 |
| R2 | 非 Opus 模型成功率显著偏低 | 高/中 | 预期内（D03）：验收只卡基建，数字如实报；若试点全线 <20% 再评估模型更换 |
| R3 | EGL 在 RTX 3050 不可用 | 低/中 | 回退 OSMesa（登记） |
| R4 | 7GB RAM 不足（MuJoCo + EGL + MCC 并存） | 低/中 | 串行 + M0 实测；不足则降视频分辨率/关闭渲染调试期视频 |
| R5 | agent 在 bash 里污染 libero 环境（pip install 等） | 中/中 | README 契约声明环境只读；M3 起抽查 `pip freeze` diff（可选） |
| R6 | LIBERO-10（90 长程任务）拉低整体成功率与拉长时间 | 高/低（时间） | 论文 Long 亦最难（83.3% baseline）；墙钟 120min 硬顶兜底 |
| R7 | MCC 路径锁/权限模式拦截 agent 合法操作 | 低/中 | M1 实测；确需改 → D05 流程登记偏差 |
| R8 | 独立重跑不可复现（随机性来源未钉死） | 中/中 | M0 验证 reset(seed) 确定性；不可复现则 success_unverified 单列，不静默 |

---

## 9. 附录

### A. 论文原始数字（对照基准）

Table I（LIBERO，%）：

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| Pilot (10 trials) | 70.0 | 100.0 | 60.0 | 68.9 | 70.6 |
| Baseline (no limit) | 90.0 | 100.0 | 80.0 | 83.3 | 84.9 |
| + coaching | 90.0 | 100.0 | 90.0 | 86.7 | 88.2 |

Table IV（LIBERO 资源，每任务均值）：

| suite | Cost | Tokens(输出) | Turns | Tries | Time(min) |
|---|---|---|---|---|---|
| Object/10 | $0.80 | 9.9K | 17.2 | 2.2 | 3.2 |
| Long/90 | $2.05 | 27.7K | 37.3 | 6.8 | 10.2 |
| Spatial/10 | $3.90 | 47.1K | 37.3 | 9.7 | 16.2 |
| Goal/10 | $4.08 | 36.9K | 52.3 | 7.4 | 12.1 |

（论文墙钟 3.2–16.2 min/任务为 Opus 实测，本复跑仅作容量参考：全协议串行预计数个机器日。）

### B. MCC 集成参考

- 调用：`python main.py --task "<prompt>" -y --root <workspace>`；`-y` = auto 权限（工作区内自动放行，破坏性命令仍拒）。
- 退出码：0 = COMPLETED；非 0 = 失败。**exit 0 ≠ 任务成功**，成功只认判定链（§6.1）。
- 相关环境变量（运行时覆盖，不改代码）：`MAX_TURNS`、`MAX_TOTAL_TOKENS`；LLM 配置在 MCC `.env`（`LLM_BASE_URL/LLM_API_KEY/LLM_MODEL`）。
- trace：JSONL（schema 2.0），位于 `--root` 下的 `.mcc/`；8 种事件，指标抽取点：`turn_start`（轮数）、`tool_call`（工具分布）、`run_end`（token/终止原因）。
- TerminationReason → outcome 映射：completed→按 success 分流；max_turns/stalled/llm_failure/context_overflow/cancelled/internal_error→同名失败类。
- MCC 默认工具集（9 个）覆盖论文主力工具（Bash/Write/Read = MCC 的 bash/write_file/read_file）；`run_tests`/`write_todos` 等 agent 可自主选用，不干预。

### C. FAEA Prompt 模板（论文 Fig.1 原文）

黑色部分 = baseline（P0/P1/P2 用）；加 Coaching Tips 段 = coaching（P3 用）：

```
# Instruction
You are an expert in robotics control. Your primary goal is to create a single
script containing an episode that reaches success:
- with task: {{TASK_DESCRIPTION}}
## Requirements
- The final script must use success() as the metric
- Contains a sequence of actions
- Do not cheat or reference other tasks
## Guidelines
- Follow the ReAct cycle
- Keep the final script simple
## Output
- meta.json: success status and num tries
- episode.py: final script
- video.mp4: recording
## Coaching Tips            [仅 P3 追加]
- Think about how a human would accomplish the task. Break it down into
  descriptive actions.
- Build the episode iteratively in each ReAct cycle: record state, plan
  movements, review progress.
- Keep a high z height when moving to avoid collisions.
- Rotate gripper when it keeps hitting unintended objects.
- Beware of obstacles in the action trajectory.
## Example                  [仅 P1 起追加，V8]
A successful episode script for a different LIBERO task (from this same setup):
{{EXAMPLE_EPISODE_PY}}
```

（视频由 wrapper 自动录制，与模板 "Output: video.mp4" 声明一致，docs 中说明。）

### D. 产物 schema

`meta.json`（agent 的 episode.py 写，runner 只读不覆盖）：

```json
{ "success": true, "num_tries": 4, "final_try": 4 }
```

`run.json`（runner 写）：

```json
{
  "stage": "p1_pilot", "suite": "libero_object", "task_id": "libero_object_1",
  "model": "<LLM_MODEL>", "mcc_exit_code": 0, "mcc_termination": "completed",
  "outcome": "success_verified", "flagged": [],
  "wall_time_s": 412.3, "turns": 21, "tokens_in": 96000, "tokens_out": 8200,
  "tool_calls": { "bash": 12, "write_file": 5, "read_file": 4 },
  "tries": 4, "verified": true
}
```

`.sim_state.json`（wrapper 写）：

```json
{ "try_count": 4, "trial_cap": 10 }
```
