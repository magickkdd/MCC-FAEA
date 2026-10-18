# FAEA-LIBERO 复现报告 (20261018-0946)

**模型**: agnes-3.0-flash, sensenova-6.8-flash-lite（非论文 Opus 4.5，数字解读必须带此前提）

**会话数**: 120，其中基建失败 1

## 论文 Table I 同构表（严格口径, %）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p1_pilot | 20.0 | 60.0 | 0.0 | 18.9 | 20.8 |

## 有效口径（剔除基建失败）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p1_pilot | 20.0 | 60.0 | 0.0 | 19.1 | 21.0 |

## 资源表（论文 Table V 同构，均值）

| 条件 | suite | n | tries | turns | tokens_out | time(min) |
|---|---|---|---|---|---|---|
| p1_pilot | Spatial | 10 | 6.9 | 42.2 | 16.6K | 19.0 |
| p1_pilot | Object | 10 | 4.8 | 25.4 | 9.5K | 11.7 |
| p1_pilot | Goal | 10 | 10.5 | 57.0 | 27.9K | 28.1 |
| p1_pilot | Long | 90 | 8.3 | 66.7 | 33.7K | 32.7 |

## 可疑任务（人工裁决）

- p1_pilot/libero_90_26: R;5;_;c;o;u;n;t;e;r;_;t;a;m;p;e;r (success_verified)
- p1_pilot/libero_90_28: R;5;_;c;o;u;n;t;e;r;_;t;a;m;p;e;r (success_verified)
- p1_pilot/libero_90_54: R;5;_;c;o;u;n;t;e;r;_;t;a;m;p;e;r (success_verified)


## 偏差与诚实声明

- Agent = MiniClaudeCode（非论文 Claude Agent SDK），模型为免费 flash 档（非 Opus 4.5）
- 成功判定经独立重跑复核；复核不一致单列不计入主成功率
- 全部偏差见 SPEC.md §5.7
