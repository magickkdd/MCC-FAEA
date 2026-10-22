# FAEA-LIBERO 复现报告 (20261022-0334)

> **铰接观测验证（p5b）汇总**：`goal_0` 56 轮 / 10 tries / 失败；`goal_3` 36 轮 / 10 tries / 失败；`goal_7` 52 轮 / 7 tries 后重启，最终 `infra_env`（无 `episode.py`）。3 个任务合计 0 成功。
>
> 结论：`articulated_joints` 被正确读取和使用，但免费模型仍无法完成抽屉/旋钮的把手抓取；剩余瓶颈是末端可达性与抓取姿态，不是关节状态缺失。该结果不支持把 Goal 增益归因于观测修复。

**模型**: agnes-3.0-flash（非论文 Opus 4.5，数字解读必须带此前提）

**会话数**: 1，其中基建失败 1

## 论文 Table I 同构表（严格口径, %）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p5b_goal_grasp_hint | - | - | 0.0 | - | 0.0 |

## 有效口径（剔除基建失败）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p5b_goal_grasp_hint | - | - | - | - | - |

## 资源表（论文 Table V 同构，均值）

| 条件 | suite | n | tries | turns | tokens_out | time(min) |
|---|---|---|---|---|---|---|
| p5b_goal_grasp_hint | Goal | 1 | 2.0 | 9.0 | 2.6K | 1.2 |


## 偏差与诚实声明

- Agent = MiniClaudeCode（非论文 Claude Agent SDK），模型为免费 flash 档（非 Opus 4.5）
- 成功判定经独立重跑复核；复核不一致单列不计入主成功率
- 全部偏差见 SPEC.md §5.7
