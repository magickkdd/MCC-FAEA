import numpy as np
from sim.libero_env import LiberoEnv

TOP_DOWN = np.array([np.pi, 0.0, 0.0])
BOWL = "akita_black_bowl_1_main"
PLATE = "plate_1_main"

env = LiberoEnv(task_id="libero_spatial_3", record_video=False, max_steps=1500)
obs = env.reset()


def move_to(pos, gripper=1.0, steps=40):
    pos = np.asarray(pos, dtype=float)
    for _ in range(steps):
        o, r, done, info = env.step([*pos.tolist(), *TOP_DOWN.tolist(), gripper])
        if done:
            break


def hold(g, steps=20):
    eef = env.get_obs()["eef_pos"]
    for _ in range(steps):
        env.step([*eef, *TOP_DOWN.tolist(), g])


def state(tag):
    s = env.get_obs()
    print(tag, "eef", np.round(s["eef_pos"], 3), "bowl",
          np.round(np.array(s["objects"][BOWL]["pos"]), 3), "open", round(s["gripper_open"], 3))


b0 = np.array(obs["objects"][BOWL]["pos"])
p0 = np.array(obs["objects"][PLATE]["pos"])
move_to([b0[0], b0[1], 1.15], 1.0, 40)
move_to([b0[0], b0[1], 1.00], 1.0, 40)
state("descend(z=1.00)")
# test a few z's, descend a little then lift to check
for z in (0.98, 0.95, 0.92):
    move_to([b0[0], b0[1], z], 1.0, 25)
    state(f"descend(z={z})")
hold(-1.0, 20)
state("grasp")
move_to([b0[0], b0[1], 1.20], -1.0, 40)
state("lift")
move_to([p0[0], p0[1], 1.20], -1.0, 60)
state("translate")
move_to([p0[0], p0[1], 1.05], -1.0, 40)
state("lower")
hold(1.0, 15)
state("release")
print("success:", env.check_success())
env.close()
