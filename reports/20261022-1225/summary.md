# FAEA-LIBERO 复现报告 (20261022-1225)

> **只完成 6/72，勿直接引用 33.3%**：M8 在旧 key 完成 4 个任务后额度耗尽；新 key 又完成/尝试了 `spatial_8`（10 tries 用满仍失败）、`spatial_1`（ReadTimeout，`llm_failure`），并中止了 `spatial_4`、未启动 `spatial_0`。
>
> 有效结果：`libero_object_1`、`libero_spatial_2` 为 `success_verified`（旧模型在这两个任务上均为失败）；`libero_goal_1` 为 `max_turns`，`libero_spatial_6`、`libero_spatial_8` 为 `task_failed`，`libero_spatial_1` 为 `llm_failure`。
>
> 已完成子集恢复率 2/6 = 33.3%，其中 Spatial 1/4、Object 1/1、Goal 0/1。样本极小，不能当作 72 任务恢复率，也不能外推。
>
> 新 key 可正常处理 22K prompt + 4096 输出，但 DeepSeek 单任务常需 30–60 分钟且会写失败后继续耗轮数；在剩余额度下继续跑 60+ 任务不划算，故停在 6 个有效会话。

**模型**: deepseek-v4.1-flash-1017（非论文 Opus 4.5，数字解读必须带此前提）

**会话数**: 6，其中基建失败 0

## 论文 Table I 同构表（严格口径, %）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p4_v41_recovery | 25.0 | 100.0 | 0.0 | - | 33.3 |

## 有效口径（剔除基建失败）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p4_v41_recovery | 25.0 | 100.0 | 0.0 | - | 33.3 |

## 资源表（论文 Table V 同构，均值）

| 条件 | suite | n | tries | turns | tokens_out | time(min) |
|---|---|---|---|---|---|---|
| p4_v41_recovery | Spatial | 4 | 4.5 | 31.0 | 18.9K | 11.1 |
| p4_v41_recovery | Object | 1 | 7.0 | 29.0 | 24.6K | 13.7 |
| p4_v41_recovery | Goal | 1 | 9.0 | 100.0 | 45.2K | 22.1 |


## 偏差与诚实声明

- Agent = MiniClaudeCode（非论文 Claude Agent SDK），模型为免费 flash 档（非 Opus 4.5）
- 成功判定经独立重跑复核；复核不一致单列不计入主成功率
- 全部偏差见 SPEC.md §5.7
