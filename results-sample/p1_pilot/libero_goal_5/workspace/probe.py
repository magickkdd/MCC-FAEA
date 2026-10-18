"""Push experiments: try different z heights to actually contact the plate side."""
import numpy as np
import sim.libero_env as le

TOP_DOWN = np.array([np.pi, 0.0, 0.0])


def try_push(z_target, y_target, name="", max_push_steps=200):
    env = le.LiberoEnv(task_id="libero_goal_5", record_video=False, max_steps=500)
    obs = env.reset()
    plate0 = np.array(obs["objects"]["plate_1_main"]["pos"])
    print(f"\n=== {name} ===")
    print(f"  plate0={plate0.tolist()}")

    # Go high above plate first
    for _ in range(30):
        env.step([plate0[0], plate0[1], 0.55, *TOP_DOWN, 1.0])
    print(f"  eef after raise: {env.get_obs()['eef_pos']}")

    # Descend to push height
    for _ in range(50):
        env.step([plate0[0], plate0[1], z_target, *TOP_DOWN, 1.0])
    print(f"  eef after descend to z={z_target}: {env.get_obs()['eef_pos']}")

    # Push in y-direction
    traj = []
    for i in range(max_push_steps):
        obs, _, done, _ = env.step([plate0[0], y_target, z_target, *TOP_DOWN, 1.0])
        if i % 40 == 0:
            traj.append((i, np.round(env.get_obs()["eef_pos"],3).tolist(),
                         np.round(env.get_obs()["objects"]["plate_1_main"]["pos"],3).tolist()))
        if done:
            break
    plate_f = np.array(env.get_obs()["objects"]["plate_1_main"]["pos"])
    ok = env.check_success()
    print(f"  plate y: {plate0[1]:.4f} -> {plate_f[1]:.4f}, x: {plate0[0]:.4f} -> {plate_f[0]:.4f}")
    print(f"  SUCCESS={ok}")
    env.save_video()
    env.close()
    return ok


if __name__ == "__main__":
    # Try z heights that actually touch the plate
    for z in [0.96, 0.95, 0.94]:
        try_push(z_target=z, y_target=-0.30, name=f"z={z}")
