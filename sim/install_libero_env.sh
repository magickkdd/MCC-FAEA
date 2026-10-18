#!/bin/bash
# 把 FAEA/sim 注册进 libero 环境（.pth = 永久 PYTHONPATH），并验证导入
set -e
LIBERO_PY="$(conda info --base)/envs/libero/bin/python"
SP=$("$LIBERO_PY" -c "import site; print(site.getsitepackages()[0])")
echo "/home/czx/FAEA" > "$SP/faea.pth"
"$LIBERO_PY" -c "import sim.libero_env as m; print('sim import OK:', m.__file__)"
