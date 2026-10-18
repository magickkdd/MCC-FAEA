"""LIBERO libero_90_36: put the white bowl on the plate.

Single-episode, deterministic script. Uses only env.check_success() as the
success metric.
"""
import json
import shutil
import numpy as np
from sim.libero_env import LiberoEnv

TASK_ID = "libero_90_36"
BOWL = "white_bowl_1_main"
PLATE = "plate_1_main"

# Gripper pointing straight down (axis-angle: pi about x-axis).
TOP_DOWN = np.array([np.pi, 0.0, 0.0])


def make_env():
    return LiberoEnv(task_id=TASK_ID, record_video=True, max_steps=1500)


def move_to(env, pos, gripper=1.0, steps=40, ori=TOP_DOWN):
    """Drive the end-effector to an absolute target pose."""
    pos = np.asarray(pos, dtype=float)
    for _ in range(steps):
        obs, _, done, _ = env.step([*pos.tolist(), *ori.tolist(), gripper])
        if done:
            break
    return obs


def hold_gripper(env, gripper, steps=15):
    """Keep current position, drive gripper open (+1) / closed (-1)."""
    eef = env.get_obs()["eef_pos"]
    for _ in range(steps):
        env.step([*eef, *TOP_DOWN.tolist(), gripper])


def main():
    env = make_env()
    obs = env.reset()

    # Let the scene settle (objects may still be falling).
    for _ in range(10):
        obs, _, done, _ = env.step([*obs["eef_pos"], *TOP_DOWN.tolist(), 1.0])

    bowl_pos = np.array(obs["objects"][BOWL]["pos"])
    plate_pos = np.array(obs["objects"][PLATE]["pos"])

    # 1) Approach: hover above the bowl.
    move_to(env, [bowl_pos[0], bowl_pos[1], bowl_pos[2] + 0.08], gripper=1.0, steps=40)
    # 2) Descend to grasp height (bowl rim level).
    move_to(env, [bowl_pos[0], bowl_pos[1], bowl_pos[2] + 0.01], gripper=1.0, steps=50)
    # 3) Close the gripper around the bowl.
    hold_gripper(env, gripper=-1.0, steps=20)

    bowl_pos = np.array(env.get_obs()["objects"][BOWL]["pos"])

    # 4) Lift the bowl clear.
    move_to(env, [bowl_pos[0], bowl_pos[1], bowl_pos[2] + 0.15], gripper=-1.0, steps=40)
    # 5) Translate over the plate.
    plate_pos = np.array(env.get_obs()["objects"][PLATE]["pos"])
    move_to(env, [plate_pos[0], plate_pos[1], plate_pos[2] + 0.15], gripper=-1.0, steps=50)
    # 6) Lower the bowl onto the plate.
    move_to(env, [plate_pos[0], plate_pos[1], plate_pos[2] + 0.02], gripper=-1.0, steps=50)
    # 7) Open the gripper to release.
    hold_gripper(env, gripper=1.0, steps=20)

    success = env.check_success()
    video_path = env.save_video()
    env.close()

    # Rename the per-try video to video.mp4 for a stable output filename.
    if video_path:
        try:
            shutil.copyfile(video_path, "video.mp4")
        except OSError:
            pass

    # This script performs exactly one try.
    json.dump(
        {"success": bool(success), "num_tries": 1, "final_try": 1},
        open("meta.json", "w"),
    )
    return success


if __name__ == "__main__":
    ok = main()
    print(f"SUCCESS: {ok}")
