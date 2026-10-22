# Workspace Guide

You are working on a robotic manipulation task in the LIBERO simulation benchmark.
Read this file first, then read `docs/api.md` for the full simulation API.

## Your assignment

TASK_ID: {{TASK_ID}}
INSTRUCTION: {{INSTRUCTION}}

Create the simulation environment for exactly this task:

```python
from sim.libero_env import LiberoEnv
env = LiberoEnv(task_id="{{TASK_ID}}")
```

(The full task list is available via `sim.libero_env.list_tasks()` if you need it.)

## Interpreter (IMPORTANT)

- Run ALL simulation scripts with the fixed interpreter: `{{LIBERO_PYTHON}}`
- Example: `{{LIBERO_PYTHON}} episode.py`
- The environment is pre-configured and read-only. Do NOT install, upgrade, or
  uninstall any package. Do NOT modify anything outside this workspace.

## Required outputs (in this workspace)

1. `episode.py` — the final, simple, single-episode script that reaches success.
   It must be re-runnable: `{{LIBERO_PYTHON}} episode.py` from this directory
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
- A trial counter tracks your simulation attempts. The authoritative values are
  `obs["task_info"]["try_count"]` and `obs["task_info"]["trial_cap"]`; the
  counter file may live outside this workspace. Do NOT search for or modify it.
- **Every `reset()` counts as a try, including probes.** Before spending a try,
  check `obs["task_info"]["try_count"]`, keep enough tries for the final
  `episode.py`, and stop in time to write `meta.json` with your best result.
- **Do NOT write `meta.json` with `"success": false` while tries remain.** If an
  attempt fails, revise `episode.py` and run it again. The session must use all
  available tries before reporting failure. Early failure is a protocol
  violation and will be rejected. `success` must come from
  `env.check_success()`, not from your own judgement.
