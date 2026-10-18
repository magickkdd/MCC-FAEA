#!/usr/bin/env python3
"""M0 冒烟：LIBERO 环境 rollout + 绝对控制 + 特权 obs + 视频 + 120 任务枚举断言。

在 libero 环境运行:  python smoke_m0_libero.py  （工作目录随意，退出码 0 = 通过）
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/czx/FAEA")
import os

Path("/tmp/faea_smoke").mkdir(parents=True, exist_ok=True)  # .sim_state.json 落这里
os.chdir("/tmp/faea_smoke")
(Path("/tmp/faea_smoke") / ".sim_state.json").unlink(missing_ok=True)  # 清场

from sim.libero_env import LiberoEnv, list_tasks  # noqa: E402

fail = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f" | {extra}" if extra else ""))
    if not cond:
        fail.append(name)


# 1) 枚举断言：10/10/10/90
tasks = list_tasks()
n = {}
for t in tasks:
    n[t["suite"]] = n.get(t["suite"], 0) + 1
check("enum_120", len(tasks) == 120 and n == {"libero_spatial": 10, "libero_object": 10, "libero_goal": 10, "libero_90": 90}, str(n))
check("task0_language", tasks and tasks[10]["suite"] == "libero_object" and len(tasks[10]["language"]) > 5, tasks[10]["language"][:60])

# 2) task 0 rollout（绝对控制 + 特权 obs + 成功谓词 + 视频）
env = LiberoEnv(task_id="libero_object_0", record_video=True)
check("language", len(env.language) > 10, env.language)

obs = env.reset()
check("reset_obs_fields", all(k in obs for k in ("eef_pos", "eef_quat", "gripper_open", "objects", "task_info")), f"objects={list(obs['objects'])[:3]}")
check("try_count_1", obs["task_info"]["try_count"] == 1)

# 绝对控制：抓 eef 起点，发一个"移动到起点上方 5cm"的目标，位移应接近目标
p0 = np.array(obs["eef_pos"])
target = p0 + np.array([0.0, 0.0, 0.05])
for _ in range(60):
    obs, r, done, info = env.step([*target, np.pi, 0.0, 0.0, 1.0])  # 上移+张爪
p1 = np.array(obs["eef_pos"])
check("absolute_control", np.linalg.norm(p1 - target) < 0.03, f"delta={np.linalg.norm(p1-target):.4f}")
check("check_success_callable", isinstance(env.check_success(), bool))

v = env.save_video()
check("video_saved", v is not None and Path(v).exists() and Path(v).stat().st_size > 10_000, str(v))
env.close()

# 3) trial cap 硬闸（清场：try_count 跨实例持久化是设计行为）
(Path("/tmp/faea_smoke") / ".sim_state.json").unlink(missing_ok=True)
env2 = LiberoEnv(task_id="libero_object_0", trial_cap=2)
env2.reset()
env2.reset()
try:
    env2.reset()
    check("trial_cap", False, "cap 未生效")
except Exception as e:
    check("trial_cap", "cap" in str(e).lower(), type(e).__name__)
env2.close()

print("RESULT:", "ALL GREEN" if not fail else f"FAILED: {fail}")
sys.exit(0 if not fail else 1)
