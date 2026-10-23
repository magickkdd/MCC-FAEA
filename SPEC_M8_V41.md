# M8 规格：强模型在旧终版失败集上的恢复实验

> 状态：草案（待执行）
> 目标机器：本机 RTX 3050 4GB / 7GB RAM / 8 核 / miniforge3
> 前序基线：M4–M7，LIBERO-120 终版 40/120 = 33.3%（免费 flash 档，pilot + 增量重试）
> 本阶段定位：辅助实验，不替换 33.3% 主结果

---

## 0. 范围

### 0.1 目标

在旧模型（免费 flash 档）**用尽 pilot + coaching 仍失败**的任务上，换用 `deepseek-v4.1-flash-1017`，用**更少的预算**重跑，测量恢复率。

这样设计的目的：

1. 旧模型在这些任务上是 0 成功，分母干净
2. 新模型预算更紧（10 tries，而旧 coaching 是无上限），若仍能解出，结论是保守的
3. 只跑失败集，token 花在最有信息量的地方

### 0.2 非目标

- 不跑全量 120，不更新 33.3% 主结果
- 不重跑旧模型，不复用旧成功任务
- 不做 baseline 阶段，不做三阶段全量
- 不改仿真接口、动作空间、成功谓词、prompt 正文
- 不做训练、不做视觉输入

### 0.3 前置变更：articulated 观测（V13）

M8 正式跑强模型前，先补一个观测缺口：

- `sim/libero_env.py` 的 `get_obs()` 新增 `articulated_joints`
- 字段：关节类型（slide/hinge）、qpos、range、travel、axis_world、anchor_pos、body_pos/body_quat、handle_pos、handle_mesh、open_fraction、opening_direction、handle_radius
- `template/docs/api.md` 同步契约；`SPEC.md` 登记 V13
- 扫描器仍禁止 `env._env.sim.data` 等直读，合法读取新字段不标记

验证门（M8-pre）：

1. 免费模型（sensenova）跑 Goal 10 pilot，10 tries / 100 turns / 120 min
2. `goal_0` 若能在 <30 轮内成功，且 Goal pilot >0/10，视为 obs 修复有效
3. 若无效，仍如实记录；先不把 Goal 的增益归给强模型

**归因限制**：强模型恢复实验将使用新 obs，因此 72 个终版失败任务的对比是"V4.1 + V13"的系统级对比，不是纯模型档位对比。报告中必须把 Goal/铰链类任务与非铰接任务分开归因。

#### M8-pre 实测结果（2026-10-22）

| 实验 | 模型 | 预算 | 结果 | 说明 |
|---|---|---|---|---|
| p5 goal_0（无抓取提示） | sensenova→agnes | 10 tries / 100 turns | 43 轮 / 10 tries / 0 成功 | 模型正确读取 `articulated_joints`；最终脚本无上限重跑仍失败（open_fraction≈0.049） |
| p5b goal_0（加抓取提示） | 免费模型 | 10 tries / 100 turns | 56 轮 / 10 tries / 0 成功 | 按提示从前侧接近，仍未夹住把手 |
| p5b goal_3（加抓取提示） | 免费模型 | 10 tries / 100 turns | 36 轮 / 10 tries / 0 成功 | 抽屉 + 碗复合任务 |
| DS 冒烟 goal_0 | V4.1-Flash | 10 tries / 100 turns | 4 tries 后写失败；最终脚本无上限重跑仍失败 | 瓶颈是把手可达/抓取姿态，不是观测 |
| p5b goal_7（stove knob） | sensenova→agnes | 10 tries / 100 turns | 52 轮 / 7 tries 后重启，最终 `infra_env`（无 episode.py） | 铰接验证 3 个任务合计 0 成功 |

结论：**观测字段已经被正确消费，但 Goal 的剩余瓶颈是末端可达性与抓取姿态，不是关节状态缺失。** 72 任务主实验继续跑，但 Goal/铰链类任务的成功不能作为"强模型"证据单独使用。

#### 协议修订 A1：反早退（2026-10-22）

首轮 72 任务全量在 `object_1` / `spatial_2` 上发现 DeepSeek 只用了 2 tries / 8–10 轮就写 `meta.json success=false`，远未用完 10 tries。这是协议行为问题，不是模型上限。

修订：

1. `template/README.md` 明确：tries 未耗尽前不得写 `success:false`；失败后必须改 `episode.py` 再跑；`success` 只能来自 `env.check_success()`。
2. `MAX_TOKENS` 4096 → 8192，防止 reasoning 占满输出预算导致工具调用截断。
3. 重新全量前先跑 3 任务 smoke（`object_1` / `spatial_2` / `90_25`），确认 turns ≥ 20 或 tries ≥ 5 才继续。

该修订属于协议约束，不改变任务、动作空间、成功判定或模型。

#### 运行状态与配额阻塞（2026-10-22 02:46）

已完成 4/72：

| 任务 | 结果 | turns | tries | tokens_in |
|---|---|---|---|---|
| `libero_object_1` | `success_verified` | 29 | 7 | 447,820 |
| `libero_spatial_2` | `success_verified` | 23 | 6 | 353,523 |
| `libero_goal_1` | `max_turns` | 100 | 9 | 1,935,737 |
| `libero_spatial_6` | `task_failed` | 15 | 1 | 183,010 |

累计 token：3,785,471。旧模型在这 4 个任务上均为失败，已完成子集恢复率 2/4 = 50%（样本太小，不能当作 72 任务恢复率）。

**阻塞项**：DeepSeek key 在约 3.8M tokens 后开始返回 `429 quota_exceeded`。实测同一 key：232 prompt + 64 max_tokens 仍通过，3K prompt + 512/1024/4096 max_tokens 均被拒；成功会话早期曾使用 22K prompt + 8192 max_tokens。04:01 整点复测仍未恢复。因此不是 50 RPM / 2M TPM 的速率问题，而是 key 的剩余 token 配额已接近耗尽（远小于 150M 预期）。剩余 68 个任务未运行；MCC 首轮约 2.6K prompt，无法压到残余额度内。

**恢复方式**（配额恢复或换新 key 后）：

```bash
# 1) 更新 secrets.local.json 的 intern / intern_proxy key
# 2) 已完成的 run.json 会自动跳过；对 llm_failure 任务先删除 run.json
python3 runner.py --stage p4_v41_recovery --all --provider intern --parallel 2
# 3) 复核 + 报告
python3 review.py --stage p4_v41_recovery
python3 report.py --stage p4_v41_recovery
```

若新 key 仍有单请求上限，先实测 `3K prompt + 4096 max_tokens` 是否 200；不通则降到 2048 或换 key，不要直接全量。

#### 新 key 二次运行（2026-10-22 12:25）

新 key 可正常处理 22K prompt + 4096 输出。二次运行结果：

| 任务 | 结果 | turns | tries | tokens_in |
|---|---|---|---|---|
| `libero_spatial_1` | `llm_failure`（ReadTimeout，1710s） | 38 | 1 | 655,525 |
| `libero_spatial_8` | `task_failed`（10 tries 用满） | 48 | 10 | 842,898 |
| `libero_spatial_4` | 中止（4 tries，未计入） | 31 | 4 | 516,759 |
| `libero_spatial_0` | 未启动 | - | - | - |

**最终有效会话 6 个**：`object_1`、`spatial_2` 为 `success_verified`；`goal_1` 为 `max_turns`；`spatial_6`、`spatial_8` 为 `task_failed`；`spatial_1` 为 `llm_failure`。已完成子集 2/6 = 33.3%，Spatial 1/4、Object 1/1、Goal 0/1。样本极小，不能当作 72 任务恢复率。

新 key 已消耗约 2.12M token（预算计数），剩余约 6M；DeepSeek 单任务常需 30–60 分钟，且在写失败后仍会继续耗轮数，继续跑 60+ 任务的边际收益低，故停止。

### 0.4 口径声明（重要）

本阶段是**条件恢复实验**，不是全量成功率：

- 分母是 72 个旧终版失败任务，不是 120
- 新模型预算 10 tries / 100 turns，旧 coaching 是无上限 / 120 turns
- 因此结果只能表述为“旧模型失败集上的恢复率”，**不能写成新的 120 任务成功率**
- 因为新模型预算更紧，恢复率是保守下界；若恢复率高，说明模型档位差异被低估

---

## 1. 已确认的决策

| ID | 决策 | 取值 | 理由 |
|---|---|---|---|
| D17 | 实验范围 | 旧终版失败集 72 个任务 | token 优先；分母为 0，信号最干净 |
| D18 | 协议 | coaching prompt + few-shot，10 tries / 100 turns / 120 min | 比旧 coaching 更紧，结论保守 |
| D19 | 总 token 预算 | 150M，启动上限 130M，预留 20M | 用户额度；预留重试与收尾 |
| D20 | 单会话 token | 3M | 100 turns × 约 30K 上下文足够；限制超额 |
| D21 | 并发 | 2 | 时间不限，优先稳定与限流安全 |
| D22 | 模型策略 | 严格单模型，禁止轮换/回退 | 结果不混模型 |
| D23 | 任务顺序 | 预注册分层随机，冻结后不可改 | 防结果导向挑任务 |
| D24 | 动态停止 | 累计 token ≥ 130M 停止提交新任务 | 完成集仍是随机前缀，无偏 |
| D25 | 复核 | 独立干净环境重放 + R1–R5 扫描 | 沿用 M4–M7 标准 |
| D26 | M8 前置 | `get_obs()` 增加 `articulated_joints`（V13） | 先补 Goal 的观测缺口，再做模型实验 |
| D27 | 归因 | 强模型结果按"铰接任务 / 非铰接任务"分开报告 | obs 与模型同时变化，不能混算 |

---

## 2. 模型与端点

### 2.1 端点事实（已实测）

| 项 | 值 |
|---|---|
| Base URL | `https://discovery-api.intern-ai.org.cn/v1` |
| Model ID | `deepseek-v4.1-flash-1017` |
| 上下文 | 1,048,576 tokens |
| 工具调用 | 支持 OpenAI `tools` / `tool_calls`，实测 `finish_reason=tool_calls` |
| 基础延迟 | 36K prompt + 1 token 输出约 4.2s |
| 小请求延迟 | 312 token prompt + 工具调用约 2.0s |
| 返回值 | 可能带 `reasoning_content`，当前客户端忽略，不影响正文与工具调用 |

### 2.2 配额

- 生成模型：50 RPM
- 决策模型：200 RPM
- 共享：2.00M TPM

2 并发在真实负载下预计 5–15 RPM，远低于 50 RPM；TPM 也不是瓶颈。

### 2.3 Key 管理

- key 只写入 `secrets.local.json`（`.gitignore` 已忽略）
- 规格、报告、README、trace 中不得出现明文 key
- 实验结束后轮换
- 401/403 立即停止，不重试

---

## 3. 任务集

### 3.1 入选标准（预注册）

旧模型在两个阶段都没有拿到干净的 `success_verified`：

- p1_pilot 未成功，或成功但被裁决剔除
- p3_coaching_retry 未成功，或成功但被裁决剔除

### 3.2 排除项

| 任务 | 原因 |
|---|---|
| `libero_90_26` / `90_28` / `90_54` | R5 计数伪造，裁决剔除 |
| `libero_90_33` / `90_39` | R1 越权 API，裁决剔除 |
| `libero_object_8` | R5 + 复核失败，裁决剔除 |
| `libero_goal_5` / `libero_90_69` | `infra_env`，非模型失败 |
| `libero_90_19` | 裁决保留的成功案例，不属于失败集 |

### 3.3 入选结果

共 **72** 个：

| 套件 | 数量 |
|---|---|
| LIBERO-Long | 56 |
| LIBERO-Spatial | 8 |
| LIBERO-Goal | 7 |
| LIBERO-Object | 1 |

说明：

- Object 只有 1 个，因为旧模型 Object 已 8/10；报告里 Object 不单独下结论
- 包含 1 个 `user_rejected`、1 个 `unknown`、1 个 `stalled`；这三类是旧模型未产出干净成功，不做事后剔除
- 旧模型在这 72 个任务上的历史消耗约 139.8M token（p1/p3 合计口径，部分任务只算了一个阶段）

### 3.4 预注册顺序

首次运行前生成并冻结 `results/p4_v41_recovery/ORDER.json`：

- 固定种子 `20261021`
- 套件内随机打乱，再按套件轮转交错，保证前 20 个覆盖 Long/Spatial/Goal/Object
- 文件包含：种子、入选 72 个 task_id、排除清单、生成时间、SHA-256
- 冻结后任何增删改都视为破坏预注册，实验作废

前 20 个为**优先样本**；其余按冻结顺序继续，直到 token 上限。

---

## 4. 预算

| 项 | 值 |
|---|---|
| tries | 10 |
| turns | 100 |
| wall time | 120 分钟 |
| 单会话 token | 3M |
| 阶段总 token | 150M |
| 启动停止线 | 130M |
| 预留 | 20M（重试、异常、收尾） |

与旧条件对比：

| 条件 | tries | turns | wall | prompt |
|---|---|---|---|---|
| 旧 p3 coaching | 无上限（实际最高 89） | 120 | 120 min | example + coaching |
| M8 Arm A | 10 | 100 | 120 min | example + coaching |

Arm A 预算更紧，所以恢复率是保守估计。

---

## 5. 实验设计

### 5.1 Arm A（主实验）

- 任务：72 个，按冻结顺序
- 预算：10 tries / 100 turns / 120 min
- prompt：与旧 p3 完全一致（模板 + 任务描述 + example + 五条 coaching）
- 成功：四步判定，`success_verified` 才算
- 停止：累计 token ≥ 130M，或 72 个跑完

主指标：

```
恢复率 = success_verified / 已完成任务数
```

同时报告 Wilson 95% 置信区间。旧模型在这 72 个任务上是 0/72，因此任何正数都是提升。

### 5.2 Arm B（可选，token 允许时）

触发条件（预注册，不看结果）：

- Arm A 全部结束后，累计 token < 110M（即剩余 ≥ 40M）

对象：

- 冻结顺序前 20 个任务中，Arm A 失败的任务
- 最多 10 个，按冻结顺序取前 10 个

预算：

- 无 tries 上限 / 120 turns / 120 min
- prompt 不变

用途：

- 与旧 p3 完全同条件（无上限 + coaching），是模型档位最直接的配对对比
- 旧模型在这批任务上仍是 0，新模型解出即强证据

### 5.3 不做的对照

- 不重跑旧模型：旧结果已经存在，重跑纯烧 token
- 不跑旧成功任务：与本阶段问题无关
- 不做 120 全量：token 不允许，且会稀释失败集信号

---

## 6. 指标

### 6.1 主指标

- Arm A 恢复率及 Wilson 95% CI
- 分套件恢复数（Long / Spatial / Goal；Object n=1 仅列事实）
- Arm B 恢复率（若触发）

### 6.2 次指标

- 每个成功任务的 tries、turns、tokens_in/out、wall time
- 每个成功任务的 token 成本
- 结果分布：`success_verified` / `task_failed` / `max_turns` / `budget` / `infra_timeout` / `infra_env` / `llm_failure`
- 旧模型同任务的 turns/tries 对比（看是否更少步数解决）

### 6.3 一致性检查

- 所有 `run.json.model` 必须是 `deepseek-v4.1-flash-1017`
- 出现其他模型即视为污染，该任务不计入分母
- 72 个任务中实际完成数、未完成数、因 token 停止数必须如实列出

---

## 7. 系统改动

### 7.1 `config.json`

新增阶段：

```json
{
  "llm": {
    "models": {
      "intern": "deepseek-v4.1-flash-1017"
    }
  },
  "stages": {
    "p4_v41_recovery": {
      "max_turns": 100,
      "trial_cap": 10,
      "task_walltime_min": 120,
      "session_token_budget": 3000000,
      "stage_token_budget": 130000000,
      "provider": "intern",
      "strict_provider": true,
      "coaching": true,
      "task_set": "final_failures",
      "order_file": "results/p4_v41_recovery/ORDER.json",
      "arm_b": {
        "enabled": true,
        "min_remaining_tokens": 40000000,
        "max_tasks": 10,
        "trial_cap": null,
        "max_turns": 120
      }
    }
  }
}
```

旧阶段配置不变。

### 7.2 `secrets.local.json`

新增 provider `intern`，key 只存此文件。`active` 索引不动，新阶段用 `--provider intern`。

### 7.3 `runner.py`

| 函数 | 改动 |
|---|---|
| `active_provider(name=None)` | 支持按名字选 provider |
| `resolve_stage_tasks` | 新增 `p4_v41_recovery`：读 `ORDER.json`，按冻结顺序返回 72 个；无 ORDER 则拒绝运行 |
| `freeze_order` | 新增子命令：生成 72 个任务的分层随机顺序 + SHA-256，写入 `ORDER.json` |
| `build_prompt` | `p4` 注入 example + coaching |
| `run_mcc` | 阶段级 `task_walltime_min`；`MAX_TOTAL_TOKENS=3000000`；`Popen` + `os.killpg` 超时杀进程组 |
| `run_one` | `strict_provider` 时禁止 `rotate_provider()`；`llm_failure` 冷却 60s 后重试，最多 2 次，且仅当已耗时 < 5 分钟 |
| 全局 token 计数器 | 线程锁 + `stage_token_budget`；提交新任务前检查累计 token；超 130M 不再提交 |
| `run.json` | 新增 `provider`、`model`、`arm`、`order_rank`、`timeout`、`restarts`、`strict_provider` |
| `main` | 新增 `--provider intern`、`--freeze-order`、`--arm a/b`；默认 2 并发；无截止时间 |

### 7.4 复核

- 每个 `provisional_success` 立即复核（内联，沿用旧流程）
- 干净副本，`.sim_state.json` 重置
- 复核超时 600 秒；超时记 `success_unverified`，允许补一次
- R1–R5 扫描不变；命中项人工裁决

### 7.5 不改的部分

- `sim/libero_env.py`、`template/`、动作空间、观测 schema、成功谓词
- 旧 `results/`、旧 `reports/`

---

## 8. 运行计划（时间不限）

| 步骤 | 动作 | 产出 |
|---|---|---|
| 1 | 预检：端点、工具调用、36K 延迟、2 并发压测 | `preflight.json` |
| 2 | 冻结 ORDER，记录 SHA-256 | `ORDER.json` |
| 3 | 单任务冒烟（选一个 Spatial 失败任务） | 四件套齐全 |
| 4 | Arm A：72 个按冻结顺序，2 并发 | `results/p4_v41_recovery/` |
| 5 | 若触发条件满足，跑 Arm B（≤10 个） | `arm_b/` 子目录 |
| 6 | 复核全部成功 | `verify/` |
| 7 | 裁决 + 报告 | `ADJUDICATION.md`、`summary.md`、`tasks.csv` |

预计 wall time：Arm A 约 72 × 25–45 分钟 / 2 并发 ≈ 15–27 小时；token 先到 130M 则提前停止。

### 8.1 预检清单

1. `/models` 返回目标模型且 `is_ready=true`
2. 基础 chat 200
3. 工具调用返回 `finish_reason=tool_calls`
4. 36K prompt 延迟 < 15s
5. 2 并发连续 10 次请求无 429
6. 单任务冒烟产出 `episode.py` / `meta.json` / `try_*.mp4` / `run.json`
7. 进程退出后无残留 `episode.py` 子进程
8. 全局 token 计数器能正确累加

### 8.2 429 与故障

- 客户端 3 次重试 + 指数退避，遵守 `Retry-After`
- 会话级 `llm_failure`：冷却 60 秒重跑，最多 2 次；已跑 >5 分钟则标记 `deferred`，不重跑
- 端点连续 15 分钟不可用：暂停提交
- 端点连续 30 分钟不可用：终止，出部分报告

---

## 9. 产物

```
results/p4_v41_recovery/
├── ORDER.json                  # 预注册顺序 + SHA-256
├── _budget.json                # 累计 token、已完成任务数
├── <task_id>/
│   ├── prompt.txt
│   ├── trace.jsonl
│   ├── workspace/
│   ├── verify/
│   ├── run.json
│   └── video.mp4
└── arm_b/<task_id>/            # 若触发
```

`run.json` 必含：

- `stage`, `task_id`, `suite`, `language`, `arm`, `order_rank`
- `provider`, `model`
- `outcome`
- `tries`, `turns`, `tokens_in`, `tokens_out`, `wall_time_s`
- `tool_calls`
- `timeout`, `restarts`, `strict_provider`
- `flagged`

---

## 10. 报告口径

### 10.1 主表

| 条件 | 任务数 | 模型 | 预算 | 成功 |
|---|---|---|---|---|
| 旧 pilot | 72 | 免费 flash 档 | 10 tries / 100 turns | 0/72 |
| 旧 coaching | 72 | 免费 flash 档 | 无上限 / 120 turns | 0/72 |
| **M8 Arm A** | **N（≤72）** | **V4.1-Flash** | **10 tries / 100 turns** | **k/N** |
| M8 Arm B（若跑） | ≤10 | V4.1-Flash | 无上限 / 120 turns | j/m |

旧模型 0/72 是构造保证，不是统计估计；表下必须写明。

### 10.2 必须写的三句结论

1. 旧模型 0/72 的任务，新模型在更紧预算下恢复 k 个
2. 恢复集中在哪些套件、哪些任务类型
3. 剩余失败的主因：能力、观测缺口、10 tries 截断、还是接口/限流

### 10.3 展示素材

- 3–5 个新模型成功视频（优先选旧模型 100 轮/无上限仍失败的）
- 1–2 个新模型失败视频，说明边界
- 新模型成功任务的 `episode.py` 片段，展示代码即策略

---

## 11. 验收标准

| Gate | 标准 |
|---|---|
| M8.0 | 预检 8 项全过 |
| M8.1 | `ORDER.json` 在任何正式运行前冻结，SHA-256 已记录 |
| M8.2 | Arm A 至少完成 50/72，或 token 达到 130M 停止 |
| M8.3 | 所有 `run.json.model` 为目标模型 |
| M8.4 | 全部 `provisional_success` 已复核；R1–R5 命中已裁决 |
| M8.5 | 报告含恢复率、Wilson CI、分套件、token 成本、口径声明 |
| M8.6 | 总 token ≤ 150M |

---

## 12. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 终版失败集是最难的任务 | 恢复率可能很低，结论不“大” | 这是最保守的设计；低恢复率说明差距不只是模型档位，也是观测/动作接口 |
| 10 tries 比旧 coaching 更紧 | 新模型可能被预算截断 | 报告单列 `max_turns` / 预算耗尽；Arm B 用无上限补测 |
| token 先耗尽 | 只完成随机前缀 | 前缀仍是无偏样本；报告 N 和未完成清单 |
| Object 只有 1 个 | 不能单独下结论 | Object 只列事实，不报比率 |
| 4 并发取消后速度慢 | 总时长 15–27 小时 | 时间不限；2 并发稳定优先 |
| 端点故障 | 中断 | 15 分钟暂停、30 分钟终止；不回退旧模型 |
| 推理 token 挤占输出 | 工具调用被截断 | 监控 `finish_reason=length`；>5% 时把 `MAX_TOKENS` 提到 8192，重跑受影响任务 |
| 进程残留 | 内存耗尽 | 超时杀进程组；预检第 7 项 |

---

## 13. 执行命令

```bash
# 1) 预检
python3 runner.py --stage p4_v41_recovery --preflight --provider intern

# 2) 冻结顺序（只做一次）
python3 runner.py --stage p4_v41_recovery --freeze-order --seed 20261021

# 3) 单任务冒烟
python3 runner.py --stage p4_v41_recovery --task <spatial_failure_id> --provider intern --parallel 1 --force

# 4) Arm A
python3 runner.py --stage p4_v41_recovery --all --provider intern --parallel 2

# 5) Arm B（若剩余 ≥40M）
python3 runner.py --stage p4_v41_recovery --arm b --provider intern --parallel 2

# 6) 复核
python3 review.py --stage p4_v41_recovery

# 7) 报告
python3 report.py --stage p4_v41_recovery
```

---

## 14. 与旧实验的差异登记

| 项 | 旧实验 | M8 | 性质 |
|---|---|---|---|
| 任务集 | 120 全量 | 72 终版失败 | 条件恢复，非全量 |
| 模型 | 两个免费 flash 档轮换 | 单一 V4.1-Flash | 目标变量 |
| 协议 | pilot → 失败重试 | 直接 coaching | 口径变化 |
| tries | pilot 10 / 重试无上限 | 10 | 预算收紧 |
| turns | 100 / 120 | 100 | 基本一致 |
| 并发 | 2 | 2 | 一致 |
| 复核 | 内联 | 内联 | 一致 |
| 主结果 | 40/120 = 33.3% | 不替换 | 辅助实验 |

以上差异在报告中全部披露。

---

## 15. 终止与最终统计（2026-10-22 23:53）

用户于 23:53 指示停止继续测试 DeepSeek，实验在此终止。最终只尝试 13/72，**不构成 72 任务恢复率**。

### 15.1 有效会话（剔除 llm_failure / infra_timeout）

| 套件 | 成功 / 有效 | 任务 |
|---|---|---|
| Spatial | 5/7 | `spatial_0/1/2/4/5` 成功；`spatial_6/8` task_failed |
| Object | 1/1 | `object_1` |
| Goal | 0/1 | `goal_1` max_turns |
| Long | 0/0 | 无有效会话 |
| **合计** | **6/9 = 66.7%** | Wilson 95% CI 约 [35.4%, 87.1%] |

### 15.2 无效会话与停机原因

| 任务 | 结果 | 说明 |
|---|---|---|
| `spatial_7` | llm_failure | 45 轮 / 3 tries 后请求失败 |
| `90_25` | infra_timeout | 跑满 120 分钟 / 51 轮 / 5 tries，842K tokens，未完成 |
| `90_80`、`90_64` | llm_failure | 首请求即 `429 Channel rate limit`，0–3.9K tokens |
| `90_42` | 手动终止 | 限流重试中被停止，未落 run.json |

自约 19:00 起端点持续返回 `429 Channel rate limit reached for model`。实测 5–800 token 的小请求偶尔返回 200，但 3K 级请求全部被拒，故自动续跑多次触发失败。23:53 用户指示停止。

### 15.3 预算

- 预算计数：5,953,126 / 7,900,000（tokens_in + tokens_out）
- 新 key 估算剩余约 2.4M，未继续消耗
- 所有进程已终止，无残留 runner / 探测守护

### 15.4 结论边界

1. 在非铰接的 Spatial/Object 任务上，V4.1-Flash 相对旧免费档有明显恢复：旧模型在 `spatial_0/1/2/4/5`、`object_1` 上均为 0，新模型 6 个全部 `success_verified`。
2. Goal 与 Long 没有形成可比较样本：Goal 已知瓶颈是铰接把手的可达/抓取，Long 本轮被 429 与 120 分钟 wall time 阻断。
3. 因此只能表述为“旧模型失败集上、非铰接子集的恢复信号”，不能外推为 72 任务恢复率，更不能替换主结果 40/120 = 33.3%。
4. 分支与主线：二阶段改动位于 `experiment/m8-v41-recovery`，`main` 保持阶段一终版。

### 15.5 第二轮恢复尝试与最终停止（2026-10-23 00:00–12:26）

第一把 key 之后，先后换用两把新 key（key2、key3），均指向同一个 `intern` 端点。结论：

- 三把 key 在同一时刻返回完全相同的 `429 Channel rate limit reached`，说明限流在共享通道层，不是单 key 额度
- 00:00 与 08:45 探针偶发 200，但真实 3K 请求立即 429；5 token 小请求同样 429，可排除“请求体过大”
- 期间 13 个 Long 任务只落 `llm_failure`（1 轮 / 0 tokens），无新增有效会话
- key2 实际消耗 4,004 tokens；key3 未启用；key1 计数另存 `_budget_key1.json`
- 12:26 用户指示停止自动恢复脚本，评测终止，无残留进程
- 有效结果不变：6/9 = 66.7%（Spatial 5/7、Object 1/1、Goal 0/1、Long 无有效会话）
