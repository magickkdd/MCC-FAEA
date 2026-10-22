# FAEA-LIBERO 复现报告 (20261022-0246)

> **运行中止，勿直接引用 50%**：M8 只完成 4/72 个任务。DeepSeek key 在累计约 3.8M tokens 后开始返回 `429 quota_exceeded`（实测 3K prompt + 512 输出可通过，3K + 4096 被拒）；剩余 68 个任务未运行。
>
> 已完成子集：`libero_object_1`、`libero_spatial_2` 为 `success_verified`；`libero_goal_1` 为 `max_turns`，`libero_spatial_6` 为 `task_failed`。旧模型在这 4 个任务上均为失败，因此已完成子集的恢复率为 2/4 = 50%，样本太小，不能当作 72 任务恢复率。
>
> 主要价值：验证了反早退协议和 DeepSeek 在两个旧失败任务上的可恢复性；配额是当前唯一阻塞项。

**模型**: deepseek-v4.1-flash-1017（非论文 Opus 4.5，数字解读必须带此前提）

**会话数**: 4，其中基建失败 0

## 论文 Table I 同构表（严格口径, %）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p4_v41_recovery | 50.0 | 100.0 | 0.0 | - | 50.0 |

## 有效口径（剔除基建失败）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p4_v41_recovery | 50.0 | 100.0 | 0.0 | - | 50.0 |

## 资源表（论文 Table V 同构，均值）

| 条件 | suite | n | tries | turns | tokens_out | time(min) |
|---|---|---|---|---|---|---|
| p4_v41_recovery | Spatial | 2 | 3.5 | 19.0 | 12.0K | 8.0 |
| p4_v41_recovery | Object | 1 | 7.0 | 29.0 | 24.6K | 13.7 |
| p4_v41_recovery | Goal | 1 | 9.0 | 100.0 | 45.2K | 22.1 |


## 偏差与诚实声明

- Agent = MiniClaudeCode（非论文 Claude Agent SDK），模型为免费 flash 档（非 Opus 4.5）
- 成功判定经独立重跑复核；复核不一致单列不计入主成功率
- 全部偏差见 SPEC.md §5.7
