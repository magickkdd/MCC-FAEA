"""Calibrate: repeated same action, measure per-step displacement."""
import numpy as np
import sim.libero_env as le

TOP_DOWN = np.array([np.pi, 0.0, 0.0])

# Test different per-step actions with same hold count.
for ax, ay, az in [(0.02, 0, 0.1), (-0.02, 0, 0.1), (0, 0.02, 0.1),
                   (0, -0.02, 0.1), (0.01, 0, 0.1), (0.005, 0, 0.1),
                   (-0.005, 0, 0.1), (0.03, 0, 0.1)]:
    env = le.LiberoEnv(task_id="libero_goal_5", record_video=False, max_steps=200)
    obs = env.reset()
    home = obs['eef_pos'].copy()
    for _ in range(50):
        obs, _, done, _ = env.step([ax, ay, az, *TOP_DOWN, 1.0])
    disp = obs['eef_pos'] - home
    print(f"action=({ax:+.3f},{ay:+.3f}) -> per-step disp xy=({disp[0]/50:+.5f},{disp[1]/50:+.5f}), total=({disp[0]:+.3f},{disp[1]:+.3f})")
    env.close()
