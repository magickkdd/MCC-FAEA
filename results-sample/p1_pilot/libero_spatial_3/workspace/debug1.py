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


b = np.array(obs["objects"][BOWL]["pos"])
p = np.array(obs["objects"][PLATE]["pos"])

move_to([b[0], b[1], 1.20], 1.0, 40)
move_to([b[0], b[1], 1.10], 1.0, 40)
hold(-1.0)
print("after grasp:", np.round(env.get_obs()["objects"][BOWL]["pos"], 3),
      "grip_open", env.get_obs()["gripper_open"])
move_to([b[0], b[1], 1.20], -1.0, 40)
print("after lift:", np.round(env.get_obs()["objects"][BOWL]["pos"], 3))
move_to([p[0], p[1], 1.20], -1.0, 50)
print("above plate:", np.round(env.get_obs()["objects"][BOWL]["pos"], 3))
move_to([p[0], p[1], 1.00], -1.0, 40)
print("lowered:", np.round(env.get_obs()["objects"][BOWL]["pos"], 3))
hold(1.0)
print("released:", np.round(env.get_obs()["objects"][BOWL]["pos"], 3), "plate", np.round(p, 3))
print("success:", env.check_success())
env.close()
