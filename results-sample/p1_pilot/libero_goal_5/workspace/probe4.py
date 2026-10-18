"""Fine delta test."""
import numpy as np
import sim.libero_env as le

TOP_DOWN = np.array([np.pi, 0.0, 0.0])

# Test small deltas to understand kinematic mapping.
# Home eef: (0.0022, -0.0014, 0.9715)
# Test: send small +x action and see eef displacement
deltas = [(0.01, 0), (0.02, 0), (0.05, 0), (0.1, 0), (0.15, 0),
          (-0.01, 0), (-0.02, 0), (-0.05, 0),
          (0, 0.05), (0, -0.05), (0, 0.1), (0, -0.1)]

# Note: from action=(-0.05, 0) eef went to (-0.07, -0.10, 1.00) - BIG y shift!
# That's suspicious. Maybe actions are joint targets not eef.

# Actually check what happens if we hold same target for longer
for hold in [5, 20, 60]:
    env = le.LiberoEnv(task_id="libero_goal_5", record_video=False, max_steps=100)
    env.reset()
    eefs = []
    for _ in range(hold):
        obs, _, done, _ = env.step([-0.05, 0, 0.97, *TOP_DOWN, 1.0])
        eefs.append(obs['eef_pos'].copy())
    print(f"hold {hold}: last 3 eef: {[f'{e.round(3).tolist()}' for e in eefs[-3:]]}")
    env.close()
