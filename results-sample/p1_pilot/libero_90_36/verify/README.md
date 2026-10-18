# Workspace Guide

You are working on a robotic manipulation task in the LIBERO simulation benchmark.
Read this file first, then read `docs/api.md` for the full simulation API.

## Your assignment

TASK_ID: libero_90_36
INSTRUCTION: put the white bowl on the plate

Create the simulation environment for exactly this task:

```python
from sim.libero_env import LiberoEnv
env = LiberoEnv(task_id="libero_90_36")
```

(The full task list is available via `sim.libero_env.list_tasks()` if you need it.)

## Interpreter (IMPORTANT)

- Run ALL simulation scripts with the fixed interpreter: `/home/czx/miniforge3/envs/libero/bin/python`
- Example: `/home/czx/miniforge3/envs/libero/bin/python episode.py`
- The environment is pre-configured and read-only. Do NOT install, upgrade, or
  uninstall any package. Do NOT modify anything outside this workspace.

## Required outputs (in this workspace)

1. `episode.py` — the final, simple, single-episode script that reaches success.
   It must be re-runnable: `/home/czx/miniforge3/envs/libero/bin/python episode.py` from this directory
   must reach success again (use deterministic behavior).
2. `meta.json` — written by `episode.py`, exactly:
   `{"success": true, "num_tries": <int>, "final_try": <int>}`
3. Video recording is automatic (one `try_NNN.mp4` per simulation attempt via
   `env.save_video()`; call it at the end of each attempt).

## Rules

- All simulation interaction goes through `sim.libero_env.LiberoEnv` as
  documented in `docs/api.md`. Do not access LIBERO/robosuite/mujoco internals,
  do not modify simulation state directly, and do not call any success
  predicate other than `env.check_success()`.
- The final `episode.py` must use `env.check_success()` as the success metric.
- Do not cheat or reference other tasks.
- A trial counter file (`.sim_state.json`) tracks your simulation attempts.
  If a preset trial cap exists, exceeding it raises an error — stop and write
  `meta.json` with your best result.
