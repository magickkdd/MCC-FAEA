#!/usr/bin/env python3
"""轮换 LLM provider：把激活的 provider 写进 MCC .env 的三行 LLM_*。

用法:
  python3 rotate_key.py            # 切到下一个 provider
  python3 rotate_key.py agnes      # 切到指定 provider
  python3 rotate_key.py sensenova
"""
import json
import sys
from pathlib import Path

FAEA = Path(__file__).resolve().parent
SECRETS = FAEA / "secrets.local.json"
CONFIG = FAEA / "config.json"
MCC_ENV = Path("/home/czx/MiniClaudeCode/.env")
LLM_KEYS = {"LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"}


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    s = json.loads(SECRETS.read_text())
    provs = s["providers"]
    if target:
        idx = next((i for i, p in enumerate(provs) if p["name"] == target), None)
        if idx is None:
            sys.exit(f"未知 provider: {target}（可选: {', '.join(p['name'] for p in provs)}）")
    else:
        idx = (s.get("active", 0) + 1) % len(provs)
    p = provs[idx]
    model = json.loads(CONFIG.read_text())["llm"]["models"][p["name"]]

    lines = MCC_ENV.read_text().splitlines() if MCC_ENV.exists() else []
    out = [ln for ln in lines if ln.split("=", 1)[0].strip() not in LLM_KEYS]
    out += [
        f"LLM_BASE_URL={p['base_url']}",
        f"LLM_API_KEY={p['api_key']}",
        f"LLM_MODEL={model}",
    ]
    MCC_ENV.write_text("\n".join(out) + "\n")

    s["active"] = idx
    SECRETS.write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n")

    masked = p["api_key"][:8] + "..." + p["api_key"][-4:]
    print(f"active -> {p['name']} ({model}, key {masked}) @ {p['base_url']}")


if __name__ == "__main__":
    main()
