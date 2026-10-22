# LiberoEnv API

The only supported way to interact with the simulation.

```python
from sim.libero_env import LiberoEnv

env = LiberoEnv(task_id="<TASK_ID>")
```

Task ids look like `libero_object_0` (i.e. `<suite>_<index>`). Suites:
`libero_spatial` (10 tasks), `libero_object` (10), `libero_goal` (10),
`libero_90` (90). Index is the 0-based position in the suite's task list.
`sim.libero_env.list_tasks()` returns the full mapping of task ids to natural
language instructions.

## Environment

```python
env = LiberoEnv(
    task_id="libero_object_0",   # required
    record_video=True,           # default True: one try_NNN.mp4 per attempt
    max_steps=1500,              # per-attempt step limit
)
```

The environment uses a **7-DoF absolute end-effector position controller**
(OSC in world frame). Physics runs at 20 Hz.

## reset() -> dict

Resets the scene to the task's fixed initial state and starts a new simulation
attempt. **Each call counts as one try** and is persisted in
`.sim_state.json`. If the workspace has a preset trial cap, the call raises
`sim.libero_env.TrialCapExceeded` once the cap is reached — in that case stop
and write `meta.json` with your best result.

The returned dict is the privileged observation (see below).

## step(action) -> (obs, reward, done, info)

- `action`: sequence of 7 numbers
  `[x, y, z, roll, pitch, yaw, gripper]`
  - `x, y, z`: absolute end-effector target position in the world frame (meters).
    Workspace is a tabletop; safe heights are typically z in [0.7, 1.2].
  - `roll, pitch, yaw`: absolute end-effector target orientation as an
    axis-angle rotation vector (rotation axis = vector direction, angle =
    vector magnitude, radians). A top-down grasp is typically
    `[pi, 0, 0]` (pi radians about the x-axis).
  - `gripper`: +1 = open, -1 = closed.
- Returns `(obs, reward, done, info)`.
  `done` is True when the step limit is reached (NOT when the task succeeds).
  `info["success"]` carries the current success flag for convenience.
- Steps are executed at 20 Hz; each `step` advances physics by 50 ms.

Typical grasp sequence: move above the object at safe height → lower to grasp
height → close gripper (hold for ~10 steps) → lift up → move above the target
location → lower → open gripper.

## get_obs() -> dict

Privileged state observation (does NOT advance physics, does NOT consume a
try). Schema:

```json
{
  "eef_pos": [x, y, z],
  "eef_quat": [qx, qy, qz, qw],
  "gripper_open": 0.0,
  "objects": {
    "<object_name>": {"pos": [x, y, z], "quat": [qx, qy, qz, qw]}
  },
  "articulated_joints": {
    "<joint_name>": {
      "body": "<moving_body_name>",
      "type": "slide",
      "qpos": 0.0,
      "range": [-0.16, 0.01],
      "travel": 0.17,
      "axis_world": [0.0, -1.0, 0.0],
      "anchor_pos": [x, y, z],
      "body_pos": [x, y, z],
      "body_quat": [qx, qy, qz, qw],
      "handle_pos": [x, y, z],
      "handle_mesh": "<mesh_name_or_null>",
      "open_fraction": 0.0588,
      "opening_direction": [0.0, 1.0, 0.0]
    }
  },
  "task_info": {
    "task_id": "...", "language": "...",
    "try_count": 1, "trial_cap": 10, "step_count": 0
  }
}
```

- `gripper_open`: 1.0 fully open, 0.0 fully closed.
- `objects`: every movable object in the scene with its ground-truth pose.
  Use these ground-truth positions to plan grasps and verify progress.
- `articulated_joints`: every non-robot slide/hinge joint in the scene
  (drawers, doors, knobs). Empty object when the scene has none. Use this
  instead of guessing joint kinematics from the task description.

`articulated_joints` fields:

- `body`: name of the moving link.
- `type`: `"slide"` or `"hinge"`.
- `qpos`: current joint value. **slide = meters along the axis; hinge = radians.**
- `range`: `[min, max]` in the same units as `qpos`.
- `travel`: `max - min`.
- `open_fraction` (slide only): 0.0 = closed end, 1.0 = open end.
- `opening_direction` (slide only): unit vector in world frame that the
  handle moves when the joint opens.
- `axis_world`: joint axis in world frame. For hinges, positive rotation
  follows the right-hand rule around this axis.
- `anchor_pos`: joint anchor in world frame.
- `body_pos` / `body_quat`: world pose of the moving link.
- `handle_pos`: estimated grasp/pull point, taken from the object's handle
  mesh when available; otherwise the body's geometry center. Treat it as a
  target estimate, not a ground-truth contact point.
- `handle_mesh`: handle mesh name, or `null` when the fallback was used.
- `handle_radius` (hinge only): distance from the joint axis to the handle.

Typical use:

```python
aj = env.get_obs()["articulated_joints"]
for name, j in aj.items():
    if j["type"] == "slide" and j["open_fraction"] < 0.5:
        grasp = j["handle_pos"]          # where to hook the gripper
        pull = j["opening_direction"]    # direction to pull
```

### Handle grasp recipe (slide joints)

For a drawer or similar slide handle, a reliable sequence is:

1. Move to `handle_pos` plus a small offset **opposite** `opening_direction`,
   so the gripper approaches the handle from its front side.
2. Keep the end-effector z at `handle_pos[2]`. **Do not descend below the
   handle**: the gripper will miss it and only push the drawer body.
3. Orient the gripper so the fingers can straddle the handle bar, then close.
4. Move along `opening_direction` while keeping the gripper closed, and watch
   `open_fraction` rise. Stop when it is close to 1.0 or the task succeeds.

A top-down grasp is usually wrong for a vertical drawer handle: it approaches
from above the bar and cannot hook it. Prefer a horizontal approach along
`-opening_direction`.

The dicts returned by `reset()`, `step()` and `get_obs()` have EXACTLY the
keys shown above — `eef_pos`, `eef_quat`, `gripper_open`, `objects`,
`articulated_joints`, `task_info`. There are no other keys (no `robot0_*`
keys, no image keys). Images are only written to the video files, never
returned in observations.

> Do NOT access `env._env`, `env._env.sim`, `sim.data`, `.qpos[...]`, or
> import `mujoco`/`robosuite` directly. `articulated_joints` is the sanctioned
> interface for joint state; bypassing it is treated as out-of-contract and
> flagged by the audit.

## check_success() -> bool

The authoritative success signal, evaluated by the task's native predicate.
The final script MUST use this as the success metric.

## save_video(path=None) -> str | None

Flushes the current attempt's frames to `try_NNN.mp4` (numbered by try).
Call it at the end of every attempt. Recording starts automatically on
`reset()` and captures one frame per `step()`.

## close()

Saves any pending video and shuts the simulation down.

## Determinism

Every `reset()` restores the same fixed initial state, so scripts are
deterministic. Write `episode.py` as a single-episode script: one reset, one
sequence of actions, check success, write `meta.json`.

## Complete episode skeleton

```python
import json
import numpy as np
from sim.libero_env import LiberoEnv

env = LiberoEnv(task_id="<TASK_ID>")
obs = env.reset()

TOP_DOWN = np.array([np.pi, 0.0, 0.0])   # axis-angle: pi about x-axis = gripper pointing down

def move_to(pos, ori=TOP_DOWN, gripper=1.0, steps=30):
    for _ in range(steps):
        obs, r, done, info = env.step([*pos, *ori, gripper])
        if done:
            break

state = env.get_obs()
obj_name, obj = next(iter(state["objects"].items()))   # pick the object you need
above = np.array(obj["pos"]) + [0, 0, 0.12]            # hover above the object
at = np.array(obj["pos"]) + [0, 0, 0.02]               # grasp height (tune as needed)

move_to(above)                                          # 1. hover above object
move_to(at)                                             # 2. lower to grasp
move_to(at, gripper=-1.0, steps=15)                     # 3. close gripper
move_to(above, gripper=-1.0)                            # 4. lift up
# ... move above the target location, lower, open gripper (gripper=+1)

success = env.check_success()
env.save_video()
env.close()
json.dump({"success": bool(success), "num_tries": 1, "final_try": 1},
          open("meta.json", "w"))
```

IMPORTANT: object names in `state["objects"]` are ground truth. Always
re-read `env.get_obs()` before each motion phase instead of trusting stale
positions — the object may have moved.

## meta.json contract

`episode.py` must end with:

```python
import json
json.dump({"success": bool(...), "num_tries": N, "final_try": K},
          open("meta.json", "w"))
```

## Not allowed

- Importing `libero`, `robosuite`, or `mujoco` directly, or touching
  `env._env` / raw simulation state.
- Any success check other than `env.check_success()`.
- Modifying files outside this workspace or installing packages.
