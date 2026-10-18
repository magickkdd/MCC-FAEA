"""Multi-stroke push: plate starts at y~-0.30, stove front at y~+0.35.
Need to push plate ~0.65m total. Do multiple push strokes."""
import numpy as np
import sim.libero_env as le

TOP_DOWN = np.array([np.pi, 0.0, 0.0])

def move(env, pos, steps):
    for _ in range(steps):
        obs, _, done, _ = env.step(list(pos) + list(TOP_DOWN) + [1.0])
        if done: break
    return obs

env = le.LiberoEnv(task_id="libero_goal_5", record_video=False, max_steps=3000)
obs = env.reset()
plate_pos = np.array(obs["objects"]["plate_1_main"]["pos"])
print(f"init plate={plate0:=plate_pos.round(3).tolist() if False else plate_pos.round(3).tolist()}, eef={obs['eef_pos'].round(3).tolist()}")

# Strategy: multiple strokes
# Stroke 1: push from y=-0.30 to y=-0.05
# Reset eef position between strokes.
plate_x = plate_pos[0]
plate_y = plate_pos[1]

for stroke, y_target in enumerate([-0.15, 0.0, 0.15, 0.30, 0.40]):
    print(f"\n--- stroke {stroke}: target y={y_target} ---")
    # 1. Hover above
    obs = move(env, [plate_x, plate_y, 0.20], 30)
    # 2. Go behind plate (plate_y in obs)
    obs = move(env, [plate_x, plate_y - 0.05, 0.03], 40)
    print(f"  approach: eef={obs['eef_pos'].round(3).tolist()}, plate={np.array(obs['objects']['plate_1_main']['pos']).round(3).tolist()}")
    # 3. Push forward
    obs = move(env, [plate_x, y_target, 0.03], 400)
    print(f"  after push: eef={obs['eef_pos'].round(3).tolist()}, plate={np.array(obs['objects']['plate_1_main']['pos']).round(3).tolist()}")
    plate_pos = np.array(obs['objects']['plate_1_main']['pos'])
    plate_x = plate_pos[0]
    plate_y = plate_pos[1]
    if env.check_success():
        print("SUCCESS!")
        break

print(f"\nFINAL: check_success={env.check_success()}")
env.close()
