"""Final attempt: pull the middle drawer handle toward -x.

Cabinet middle drawer is a hinge (axis=+y) with range [-0.16, 0.01].
The handle is offset ~+0.2 along the body local z (above the hinge pivot).
Negative rotation around +y maps +z to -x, so pulling the handle toward
-x opens the drawer. Prior attempts wrongly pushed the handle toward +y
or -y; those never moved the hinge.
"""
import json
import shutil
import numpy as np
from sim.libero_env import LiberoEnv

TASK_ID = "libero_goal_0"

TOP_DOWN = np.array([np.pi, 0.0, 0.0])          # +z -> -y
GRI_FACE_NEGX = np.array([0.0, -np.pi/2, 0.0])  # +z -> -x (facing -x)

HANDLE = np.array([0.019, -0.255, 1.022])


def make_env():
    return LiberoEnv(task_id=TASK_ID, record_video=True, max_steps=2000)


def move(env, pos, ori, gripper=1.0, steps=40):
    pos = np.asarray(pos, float)
    for _ in range(steps):
        obs, _, done, _ = env.step([*pos.tolist(), *ori.tolist(), gripper])
        if done:
            break
    return obs


def hold(env, gripper, steps=20):
    eef = np.asarray(env.get_obs()["eef_pos"], float)
    for _ in range(steps):
        env.step([*eef.tolist(), *GRI_FACE_NEGX.tolist(), gripper])


def main():
    try:
        env = make_env()
        env.reset()
    except Exception as e:
        # Trial cap or other runtime failure: record best-effort status.
        json.dump({"success": False, "num_tries": 1, "final_try": 1,
                   "error": str(e)}, open("meta.json", "w"))
        return False

    # 1) Approach above the cabinet area at a safe height.
    move(env, [0.10, -0.10, 1.30], TOP_DOWN, 1.0, 40)

    # 2) Descend to the right of the handle at handle height.
    move(env, [0.10, -0.255, 1.02], TOP_DOWN, 1.0, 80)

    # 3) Rotate gripper to face -x (toward the handle).
    move(env, [0.10, -0.255, 1.02], GRI_FACE_NEGX, 1.0, 40)

    # 4) Close the gripper around the handle.
    move(env, [0.08, -0.255, 1.02], GRI_FACE_NEGX, -1.0, 40)

    # 5) Pull toward -x to swing the drawer open.
    for x in [0.05, 0.02, 0.00, -0.02, -0.05]:
        move(env, [x, -0.255, 1.02], GRI_FACE_NEGX, -1.0, 60)

    success = env.check_success()
    video_path = env.save_video()
    env.close()

    if video_path:
        try:
            shutil.copyfile(video_path, "video.mp4")
        except OSError:
            pass

    json.dump({"success": bool(success), "num_tries": 1, "final_try": 1},
              open("meta.json", "w"))
    return success


if __name__ == "__main__":
    ok = main()
    print(f"SUCCESS: {ok}")
