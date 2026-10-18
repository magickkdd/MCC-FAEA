"""Probe env internals for success condition."""
import numpy as np
import sim.libero_env as le

env = le.LiberoEnv(task_id="libero_goal_5", record_video=False, max_steps=200)
obs = env.reset()
print("env type:", type(env._env).__name__)
print("env parent class mro:")
for cls in type(env._env).__mro__:
    print(f"  {cls.__module__}.{cls.__name__}")
print()
print("dir(_env):", sorted([x for x in dir(env._env) if not x.startswith('_')]))

# Check task_description
for attr in ['task_description', 'task_instruction', 'instruction', '_task', 'task', 'task_description_']:
    if hasattr(env._env, attr):
        print(f"{attr}: {getattr(env._env, attr)}")

# Get initial state
print()
plate = obs["objects"]["plate_1_main"]
print("plate:", plate)

env.close()
