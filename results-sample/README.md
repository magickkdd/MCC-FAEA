# 代表性实验样本（M4 全量 120 任务中精选 6 例）

完整产物（全部 120 任务的视频/trace）未入库，本目录为人工挑选的代表性案例。
每个案例目录含：`prompt.txt`（实际发送的 FAEA prompt）、`run.json`（判定与指标）、
`trace.jsonl`（MCC 会话全轨迹）、`workspace/`（agent 沙箱：episode.py、meta.json、
try_NNN.mp4 逐次录像）、`video.mp4`（成功尝试的最终录像）、`verify/`（独立重跑复核副本）。

| 案例 | 讲什么 |
|---|---|
| p0_prompt_dev/libero_object_0__r7_ok28turns_1try | task 0 引导成功（P0 阶段），其 episode.py 被固化为全量实验的 few-shot example |
| p1_pilot/libero_object_0 | pilot 1-try 秒杀：few-shot example 注入后的标准成功形态（14 轮） |
| p1_pilot/libero_spatial_3 | Spatial 套件唯一成功（该套件 20%），典型试错型成功（多 try） |
| p1_pilot/libero_90_36 | Long 套件最快成功：23 轮 / 5 try / 9.4 分钟 |
| p1_pilot/libero_goal_0 | 诚实失败样本：86 轮烧尽 10-try cap 后终止，Goal 套件 0% 的代表 |
| p1_pilot/libero_goal_5 | **作弊实证（R5）**：agent 第 33 轮 `rm` 计数文件逃逸 10-try cap，后跑 38+ tries；对应论文 §V-d 护栏讨论 |

背景：MCC（自研 agent，MiniClaudeCode）+ 免费档国产模型（sensenova-6.8-flash-lite /
agnes-3.0-flash），复现 FAEA（arXiv 2601.20334，Claude Agent SDK + Opus 4.5，
LIBERO pilot 70.6%）。本复现 pilot 20.8%，难度梯度与资源曲线和论文同构。
详见根目录 SPEC.md 与 reports/。
