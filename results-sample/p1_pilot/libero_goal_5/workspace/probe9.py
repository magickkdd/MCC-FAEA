"""Bigger delta actions and check if there's a limit."""
import numpy as np
import sim.libero_env as le

TOP_DOWN = np.array([np.pi, 0.0, 0.0])

# Try various -y target values (delta) with long hold
for ax, ay in [(-0.2, 0), (-0.15, 0), (-0.1, 0), (-0.05, 0),
               (-0.2, 0.05), (-0.15, -0.05), (-0.1, 0.05)]:
    env = le.LiberoEnv(task_id="libero_goal_5", record_video=False, max_steps=200)
    obs = env.reset()
    for _ in range(150):
        obs, _, done, _ = env.step([ax, ay, 0.1, *TOP_DOWN, 1.0])
        if done: break
    print(f"action=({ax:+.2f},{ay:+.2f}) -> eef={obs['eef_pos'].round(3).tolist()}")
    env.close()
