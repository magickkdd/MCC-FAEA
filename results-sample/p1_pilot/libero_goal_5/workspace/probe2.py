"""Dump both tasks to compare obs-frame vs world-frame layout."""
import numpy as np, sim.libero_env as le

def dump(tid):
    env = le.LiberoEnv(task_id=tid, record_video=False, max_steps=5)
    obs = env.reset()
    sim = env._env.sim
    model, data = sim.model, sim.data
    print(f"===== {tid} =====")
    print(" objects (obs frame):")
    for k,v in obs['objects'].items():
        print(f"   {k}: pos={np.round(v['pos'],3).tolist()}")
    print(" eef_pos (obs):", np.round(obs['eef_pos'],3).tolist())
    print(" world body positions:")
    for i,n in enumerate([model.body_id2name(j) for j in range(model.nbody)]):
        if n and any(x in n.lower() for x in ['soup','basket','plate','bowl','stove','table_']):
            print(f"   {n}: x={np.round(data.xpos[i],4).tolist()}")
    print(" stove/table sites (world):")
    for i in range(model.nsite):
        n = model.site_id2name(i)
        if n and any(x in n.lower() for x in ['stove','table_','region']):
            print(f"   {n}: x={np.round(data.site_xpos[i],4).tolist()}")
    env.close()

dump('libero_object_0')
dump('libero_goal_5')
