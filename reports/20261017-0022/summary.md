# FAEA-LIBERO 复现报告 (20261017-0022)

**模型**: agnes-3.0-flash, sensenova-6.8-flash-lite（非论文 Opus 4.5，数字解读必须带此前提）

**会话数**: 13，其中基建失败 0

## 论文 Table I 同构表（严格口径, %）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p1_pilot | 16.7 | 66.7 | 0.0 | 0.0 | 23.1 | （论文 Pilot (10 trials): 70.6）

## 有效口径（剔除基建失败）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p1_pilot | 16.7 | 66.7 | 0.0 | 0.0 | 23.1 |

## 资源表（论文 Table V 同构，均值）

| 条件 | suite | n | tries | turns | tokens_out | time(min) |
|---|---|---|---|---|---|---|
| p1_pilot | Spatial | 6 | 5.2 | 38.8 | 9.9K | 12.3 |
| p1_pilot | Object | 3 | 1.0 | 22.7 | 6.3K | 11.8 |
| p1_pilot | Goal | 2 | 9.5 | 73.5 | 33.8K | 44.4 |
| p1_pilot | Long | 2 | 5.5 | 93.0 | 49.9K | 50.0 |


## 偏差与诚实声明

- Agent = MiniClaudeCode（非论文 Claude Agent SDK），模型为免费 flash 档（非 Opus 4.5）
- 成功判定经独立重跑复核；复核不一致单列不计入主成功率
- 全部偏差见 SPEC.md §5.7
