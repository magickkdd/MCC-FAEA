"""Learn action->eef mapping."""
import numpy as np
import sim.libero_env as le

TOP_DOWN = np.array([np.pi, 0.0, 0.0])

for tx in [0, 0.05, -0.05, 0.1, -0.1, 0.0]:
    for ty in [0, -0.05, 0.05]:
        env = le.LiberoEnv(task_id="libero_goal_5", record_video=False, max_steps=100)
        obs = env.reset()
        for _ in range(40):
            obs, _, done, _ = env.step([tx, ty, 0.97, *TOP_DOWN, 1.0])
        print(f"action=({tx:+.2f},{ty:+.2f}) -> eef={np.round(obs['eef_pos'],4).tolist()}")
        env.close()
