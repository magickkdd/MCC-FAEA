"""Big push: plate from y=-0.30 to +0.05."""
import numpy as np
import sim.libero_env as le

TOP_DOWN = np.array([np.pi, 0.0, 0.0])

def run(y_target, max_steps=1500, name=""):
    env = le.LiberoEnv(task_id="libero_goal_5", record_video=False, max_steps=max_steps)
    obs = env.reset()
    plate_pos = np.array(obs["objects"]["plate_1_main"]["pos"])
    print(f"--- {name} y_target={y_target} ---")
    print(f"  init plate={plate_pos.round(3).tolist()}, eef={obs['eef_pos'].round(3).tolist()}")

    # 1. Above plate
    for _ in range(50):
        obs, _, done, _ = env.step([plate_pos[0], plate_pos[1], 0.90, *TOP_DOWN, 1.0])
        if done: break

    # 2. Behind plate (in -y)
    for _ in range(80):
        obs, _, done, _ = env.step([plate_pos[0], plate_pos[1] - 0.05, 0.02, *TOP_DOWN, 1.0])
        if done: break
    print(f"  approach done, eef={obs['eef_pos'].round(3).tolist()}, plate={np.array(obs['objects']['plate_1_main']['pos']).round(3).tolist()}")

    # 3. Long push
    for i in range(400):
        obs, _, done, _ = env.step([plate_pos[0], y_target, 0.02, *TOP_DOWN, 1.0])
        if done: break
    print(f"  after push: eef={obs['eef_pos'].round(3).tolist()}, plate={np.array(obs['objects']['plate_1_main']['pos']).round(3).tolist()}")
    print(f"  check_success={env.check_success()}")
    env.close()

run(0.00, name="push to y=0.00")
print()
run(0.05, name="push to y=+0.05")
print()
run(-0.05, name="push to y=-0.05")
print()
run(0.15, name="push to y=+0.15")
