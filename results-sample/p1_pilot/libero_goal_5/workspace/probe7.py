"""Test pushing plate forward in multiple tries."""
import numpy as np
import sim.libero_env as le

TOP_DOWN = np.array([np.pi, 0.0, 0.0])

def make_env():
    return le.LiberoEnv(task_id="libero_goal_5", record_video=False, max_steps=500)

def move(env, target, steps=30):
    for _ in range(steps):
        obs, _, done, _ = env.step(list(target) + list(TOP_DOWN) + [1.0])
        if done: break
    return obs

# Reset positions per env
for trial in range(2):
    env = make_env()
    obs = env.reset()
    plate_pos = np.array(obs["objects"]["plate_1_main"]["pos"])
    print(f"=== trial {trial} plate@{plate_pos.round(3).tolist()}, eef@{obs['eef_pos'].round(3).tolist()} ===")

    px, py, pz = plate_pos

    # 1. Hover above plate
    obs = move(env, [px, py, 0.20], 30)
    # 2. Lower to just behind plate (behind means -y, and plate has ~6cm radius). Pusher eef goes below plate bottom
    #    plate z=0.03, plate thickness ~2cm. So plate bottom ~0.02. Push eef at z=0.02 (right at table).
    obs = move(env, [px, py - 0.05, 0.02], 40)
    print(f"  after approach: eef={obs['eef_pos'].round(3).tolist()}")
    # 3. Push plate toward stove (stove is at +y, roughly y ~0)
    target_y = py + 0.28  # push plate to y~0.0 (just in front of stove)
    obs = move(env, [px, target_y, 0.02], 200)
    print(f"  after push: eef={obs['eef_pos'].round(3).tolist()}, plate={np.array(obs['objects']['plate_1_main']['pos']).round(3).tolist()}")
    print(f"  success={env.check_success()}")
    env.close()
