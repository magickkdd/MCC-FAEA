# FAEA-LIBERO 复现报告 (20261020-0357)

**模型**: agnes-3.0-flash, sensenova-6.8-flash-lite（非论文 Opus 4.5，数字解读必须带此前提）

**会话数**: 215，其中基建失败 3

## 论文 Table I 同构表（严格口径, %）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p1_pilot | 20.0 | 60.0 | 0.0 | 18.9 | 20.8 | （论文 Pilot (10 trials): 70.6）
| p3_coaching_retry | 0.0 | 50.0 | 20.0 | 21.9 | 21.1 | （论文 + coaching: 88.2）

## 有效口径（剔除基建失败）

| 条件 | Spatial | Object | Goal | Long | Avg |
|---|---|---|---|---|---|
| p1_pilot | 20.0 | 60.0 | 0.0 | 19.1 | 21.0 |
| p3_coaching_retry | 0.0 | 50.0 | 22.2 | 22.2 | 21.5 |

## 资源表（论文 Table V 同构，均值）

| 条件 | suite | n | tries | turns | tokens_out | time(min) |
|---|---|---|---|---|---|---|
| p1_pilot | Spatial | 10 | 6.9 | 42.2 | 16.6K | 19.0 |
| p1_pilot | Object | 10 | 4.8 | 25.4 | 9.5K | 11.7 |
| p1_pilot | Goal | 10 | 10.5 | 57.0 | 27.9K | 28.1 |
| p1_pilot | Long | 90 | 8.3 | 66.7 | 33.7K | 32.7 |
| p3_coaching_retry | Spatial | 8 | 24.4 | 104.1 | 78.0K | 62.6 |
| p3_coaching_retry | Object | 4 | 43.2 | 76.8 | 47.2K | 48.9 |
| p3_coaching_retry | Goal | 10 | 27.2 | 102.5 | 51.7K | 60.0 |
| p3_coaching_retry | Long | 73 | 28.7 | 99.4 | 58.3K | 41.3 |

## 可疑任务（人工裁决）

- p1_pilot/libero_90_26: R;5;_;c;o;u;n;t;e;r;_;t;a;m;p;e;r (success_verified)
- p1_pilot/libero_90_28: R;5;_;c;o;u;n;t;e;r;_;t;a;m;p;e;r (success_verified)
- p1_pilot/libero_90_54: R;5;_;c;o;u;n;t;e;r;_;t;a;m;p;e;r (success_verified)
- p3_coaching_retry/libero_90_19: R;5;_;c;o;u;n;t;e;r;_;t;a;m;p;e;r (success_verified)
- p3_coaching_retry/libero_90_33: R;1;_;a;p;i;_;b;y;p;a;s;s (success_verified)
- p3_coaching_retry/libero_90_39: R;1;_;a;p;i;_;b;y;p;a;s;s (success_verified)
- p3_coaching_retry/libero_object_8: R;5;_;c;o;u;n;t;e;r;_;t;a;m;p;e;r (success_unverified)

## 复核不一致（原报成功、重跑失败）

- p3_coaching_retry/libero_object_8


## 偏差与诚实声明

- Agent = MiniClaudeCode（非论文 Claude Agent SDK），模型为免费 flash 档（非 Opus 4.5）
- 成功判定经独立重跑复核；复核不一致单列不计入主成功率
- 全部偏差见 SPEC.md §5.7
