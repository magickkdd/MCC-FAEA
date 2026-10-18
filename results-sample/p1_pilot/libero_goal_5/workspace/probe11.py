"""Can we reach y=-0.5? Test very large negative y actions."""
import numpy as np
import sim.libero_env as le

TOP_DOWN = np.array([np.pi, 0.0, 0.0])

for ay in [-0.1, -0.2, -0.3, -0.4, -0.5, -0.6]:
    env = le.LiberoEnv(task_id="libero_goal_5", record_video=False, max_steps=200)
    env.reset()
    for _ in range(200):
        obs, _, done, _ = env.step([0, ay, 0.1, *TOP_DOWN, 1.0])
        if done: break
    print(f"action_y={ay:+.2f} -> eef={obs['eef_pos'].round(3).tolist()}")
    env.close()
