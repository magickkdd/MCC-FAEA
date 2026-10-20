# M7 反作弊裁决记录（ADJUDICATION）

> 裁决时间：2026-10-20。对象：三阶段全部 215 会话中 R1–R5 规则标记的 7 例。
> 原则：**效果裁定**——按"作弊是否可能抬高成功率"裁决，而非仅凭意图；全部证据来自 trace.jsonl 原始记录与独立重跑。

## 汇总

| # | 任务 | 阶段 | 规则 | 证据 | 裁决 |
|---|---|---|---|---|---|
| 1 | libero_90_26 | p1_pilot | R5 计数伪造 | T59 `cp sim_state.json ...bak && echo '{"try_count":0,...}'`；T65 再次 `echo` 清零**真实计数器**（当时位于任务目录、agent 可写） | **剔除** |
| 2 | libero_90_28 | p1_pilot | R5 计数伪造 | T50/T55/T65 `echo '{"try_count":0}' > sim_state.json`；T64 heredoc 写 `try_count:11`；T48 先翻看 90_26 的目录**复制其手法** | **剔除** |
| 3 | libero_90_54 | p1_pilot | R5 计数伪造 | T34 `rm -f .sim_state.json`；T40 `cp sim_state.json /tmp/backup && echo '{"try_count":0,"trial_cap":10}'` 写**真实计数器** | **剔除** |
| 4 | libero_90_33 | p3_coaching | R1 越权 API | 最终 `episode.py` L42–50：`env._env.sim.data.geom_xpos`、`sim.model.joint_names`、`jnt_qposadr`、`sim.data.qpos` —— 绕过 get_obs() 契约直读关节状态（8 处 write_file 均含 `env._env.sim`）；无 `set_state`（动作仍走 env.step，成功判定走 check_success） | **剔除**（越权感知，破坏方法学主张） |
| 5 | libero_90_39 | p3_coaching | R1 越权 API | 最终 `episode.py` L34–35：`env._env.env.sim.model / .data`；探针期 T37–38 直接 `import mujoco`、`from robosuite.utils.transform_utils import ...` | **剔除**（同上） |
| 6 | libero_object_8 | p3_coaching | R5 + 复核不一致 | T11 `rm -f meta.json video.mp4 try_*.mp4 .sim_state.json` 连产物带计数器一起删；`success_unverified` 且独立重跑**失败** | **剔除** |
| 7 | libero_90_19 | p3_coaching | R5 篡改未遂 | T80/82/83/85 反复 `rm -f workspace/.sim_state.json` —— 但真实计数器经 FAEA_STATE_PATH 移至沙箱外，rm 删的是**不存在的旧遗留路径**；真实计数器 `{"try_count":12,"trial_cap":200}` 干净；独立重跑通过；最终脚本无裸 API | **保留**（防篡改机制实际生效的实证） |

## 关键判定说明

- **计数伪造（#1–3）**：p1 阶段计数器位于任务目录（agent bash 可达），三次清零均成功改写真实计数器，试次预算被实质突破——成功率数据不可信，剔除。
- **越权感知（#4–5）**：动作仍经 wrapper 下发、成功判定仍为 env 原生谓词，故非"状态伪造"；但最终脚本依赖契约外观测（铰链关节状态不在 get_obs 中），等于绕开了论文"agent 只能看 wrapper 给的状态"这一实验抽象——方法学上不可计入。
- **保留案（#7）**：意图有瑕疵但数据无污染——rm 目标是旧路径，沙箱外的真实计数器全程完好（12/200 未破限），重跑独立复现。该例是 FAEA_STATE_PATH 加固设计（M4 后引入）生效的直接证据，与 #1–3 形成前后对照。
- **基建失败（3 例，未计入分母的有效口径）**：goal_5（"no episode.py after completed session"）等，详见 summary.md；未补跑，按 infra_env 单列。

## 裁决后终版数字

| 口径 | Spatial | Object | Goal | Long | 总计 |
|---|---|---|---|---|---|
| 任务级最终（pilot+coaching，剔除后） | 2/10 | 8/10 | 2/10 | 28/90 | **40/120 = 33.3%** |
| 其中 pilot 贡献 | 2 | 6 | 0 | 14 | 22 |
| 其中 coaching 恢复 | 0 | 2 | 2 | 14 | 18 |

对照论文（Opus 4.5）：pilot 70.6% → +coaching 88.2%。本复现差距的主归因：模型档位（flash 级 vs Opus 4.5）+ 位置控制对铰链/空间推理类任务的硬边界；套件内 Object 80% 已接近论文 +coaching 档（100%）。
