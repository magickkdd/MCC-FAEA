# MCC 环境（py3.11+）

```bash
conda create -n mcc python=3.11 -y
conda run -n mcc pip install -e /home/czx/MiniClaudeCode
```

- LLM 端点不进 .env：runner 启动子进程时经环境变量注入
  （LLM_BASE_URL / LLM_API_KEY / LLM_MODEL，来源 secrets.local.json + config.json）
- 手动 REPL 用法：`python3 /home/czx/FAEA/rotate_key.py sensenova` 后
  `conda run -n mcc python /home/czx/MiniClaudeCode/main.py`
