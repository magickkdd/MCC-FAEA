# FAEA-LIBERO 复现报告 (20261022-2353)

**模型**: deepseek-v4.1-flash-1017（非论文 Opus 4.5，数字解读必须带此前提）

**会话数**: 13，其中基建失败 1

> **口径警告（必读）**：本阶段只尝试了 13/72 个任务，其中有效会话 9 个。**不要把下表百分比当作 72 任务恢复率引用。**
>
> - 有效口径（剔除 `llm_failure` / `infra_timeout`）：6/9 = 66.7%
> - 分套件：Spatial 5/7 = 71.4%，Object 1/1，Goal 0/1，Long 0 个有效会话
> - 无效会话：`spatial_7`（llm_failure）、`90_25`（120 分钟 wall timeout）、`90_80` / `90_64`（429 首请求即失败）；`90_42` 被手动终止，未落 run.json
> - 下表 Spatial 62.5% 的分母包含 `spatial_7` 的 llm_failure，只是原始汇总，不能与有效口径混用
> - 停机原因：端点自约 19:00 起持续返回 `429 Channel rate limit reached`，小请求偶尔通过、3K 级请求全被拒；用户于 23:53 指示停止

## 论文 Table I 同构表（严格口径, %）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p4_v41_recovery | 62.5 | 100.0 | 0.0 | 0.0 | 46.2 |

## 有效口径（剔除基建失败）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p4_v41_recovery | 62.5 | 100.0 | 0.0 | 0.0 | 50.0 |

## 资源表（论文 Table V 同构，均值）

| 条件 | suite | n | tries | turns | tokens_out | time(min) |
|---|---|---|---|---|---|---|
| p4_v41_recovery | Spatial | 8 | 5.0 | 32.5 | 22.5K | 23.8 |
| p4_v41_recovery | Object | 1 | 7.0 | 29.0 | 24.6K | 13.7 |
| p4_v41_recovery | Goal | 1 | 9.0 | 100.0 | 45.2K | 22.1 |
| p4_v41_recovery | Long | 3 | 1.7 | 18.0 | 20.9K | 40.0 |


## 偏差与诚实声明

- Agent = MiniClaudeCode（非论文 Claude Agent SDK），模型为免费 flash 档（非 Opus 4.5）
- 成功判定经独立重跑复核；复核不一致单列不计入主成功率
- 全部偏差见 SPEC.md §5.7
