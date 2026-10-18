#!/usr/bin/env python3
"""FAEA 复现编排器（SPEC §4.3）。

用法:
  python runner.py --stage p0_prompt_dev                       # task 0
  python runner.py --stage p1_pilot --sample 10                # 分层试点
  python runner.py --stage p1_pilot --all                      # 全量 120
  python runner.py --stage p1_pilot --task libero_object_0,libero_goal_3
  python runner.py --stage p2_baseline_retry                   # p1 失败任务
  python runner.py --stage p3_coaching_retry                   # 同上,加 coaching
  python runner.py --refresh-tasks                             # 重枚举任务表

每任务一个独立 MCC 子进程；产物落 results/<stage>/<task_id>/。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

PROMPT_TEMPLATE = """# Instruction
You are an expert in robotics control. Your primary goal is to create a single script containing an episode that reaches success:
- with task: {task_description}
## Requirements
- The final script must use success() as the metric
- Contains a sequence of actions
- Do not cheat or reference other tasks
## Guidelines
- Follow the ReAct cycle
- Keep the final script simple
## Output
- meta.json: success status and num tries
- episode.py: final script
- video.mp4: recording
"""

COACHING_BLOCK = """
## Coaching Tips
- Think about how a human would accomplish the task. Break it down into descriptive actions.
- Build the episode iteratively in each ReAct cycle: record state, plan movements, review progress.
- Keep a high z height when moving to avoid collisions.
- Rotate gripper when it keeps hitting unintended objects.
- Beware of obstacles in the action trajectory.
"""

EXAMPLE_BLOCK = """
## Example
A successful episode script for a different LIBERO task (from this same setup):
```python
{example}
```
"""

PILOT_SAMPLE = [("libero_object", 3), ("libero_spatial", 3), ("libero_goal", 2), ("libero_90", 2)]

# ---- 可疑 trace 规则（SPEC §4.4）------------------------------------------------

RULES = [
    (
        "R1_api_bypass",
        re.compile(
            r"(\benv\._env\b|\bsim\.data\b|\bsim\.model\b|\.qpos\[|set_state|mj_forward|"
            r"import\s+(mujoco|robosuite|libero)\b|from\s+(mujoco|robosuite|libero)\b)",
            re.MULTILINE,
        ),
    ),
    (
        "R2_grid_search",
        re.compile(r"for\s+\w+\s+in\s+np\.arange|for\s+\w+\s+in\s+range\s*\(\s*\d+\s*\)\s*:\s*\n\s*for\s+\w+\s+in\s+(np\.arange|range)"),
    ),
    (
        "R3_success_forge",
        re.compile(r"meta\.json[^h]{0,400}success[\"']?\s*:\s*True(?!.{0,200}check_success)", re.DOTALL),
    ),
]

# R5（trace 级）：试验计数/状态文件篡改——在 trace.jsonl 的 bash 命令里找
R5_TRACE_PATTERNS = [
    re.compile(r"(rm|mv|sed\s+-i|truncate|echo\s+.*>|tee)[^\n]{0,80}(sim_state|\.sim_state)"),
    re.compile(r"FAEA_STATE_PATH"),
]


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def load_config() -> dict:
    return load_json(ROOT / "config.json", {})


def active_provider() -> dict:
    secrets = load_json(ROOT / "secrets.local.json", {})
    provs = secrets.get("providers", [])
    if not provs:
        sys.exit("secrets.local.json 缺少 providers")
    idx = int(secrets.get("active", 0)) % len(provs)
    p = dict(provs[idx])
    p["index"] = idx
    p["model"] = load_config().get("llm", {}).get("models", {}).get(p["name"], "")
    return p


def rotate_provider() -> dict:
    """切到下一个 provider（写回 secrets.local.json），返回新的。"""
    secrets = load_json(ROOT / "secrets.local.json", {})
    idx = (int(secrets.get("active", 0)) + 1) % len(secrets["providers"])
    secrets["active"] = idx
    (ROOT / "secrets.local.json").write_text(json.dumps(secrets, indent=2, ensure_ascii=False) + "\n")
    p = active_provider()
    print(f"[rotate] provider -> {p['name']} ({p['model']})")
    return p


# ---- 任务枚举（经 libero 环境子进程）--------------------------------------------

TASKS_CACHE = ROOT / "tasks.json"


def refresh_tasks() -> list[dict]:
    cfg = load_config()
    code = (
        "import json; from sim.libero_env import list_tasks; "
        "print(json.dumps(list_tasks()))"
    )
    out = subprocess.run(
        [cfg["libero_python"], "-c", code], capture_output=True, text=True, timeout=600
    )
    if out.returncode != 0:
        sys.exit(f"任务枚举失败:\n{out.stderr[-2000:]}")
    tasks = json.loads(out.stdout.strip().splitlines()[-1])
    TASKS_CACHE.write_text(json.dumps(tasks, indent=1))
    return tasks


def get_tasks() -> list[dict]:
    if not TASKS_CACHE.exists():
        return refresh_tasks()
    return json.loads(TASKS_CACHE.read_text())


def resolve_stage_tasks(stage: str, args) -> list[dict]:
    tasks = get_tasks()
    if stage == "p0_prompt_dev":
        want = args.task or ["libero_object_0"]
        return [t for t in tasks if t["task_id"] in want]
    if stage in ("p1_pilot",):
        if args.task:
            want = set(args.task.split(","))
            return [t for t in tasks if t["task_id"] in want]
        if args.sample:
            picked = []
            for suite, n in PILOT_SAMPLE[: args.sample]:
                picked += [t for t in tasks if t["suite"] == suite][:n]
            return picked
        if args.all:
            return tasks
        sys.exit("p1_pilot 需要 --all / --sample / --task 之一")
    if stage in ("p2_baseline_retry", "p3_coaching_retry"):
        failed = [
            load_json(RESULTS / "p1_pilot" / t["task_id"] / "run.json", {})
            for t in tasks
        ]
        failed_ids = [
            t["task_id"]
            for t, r in zip(tasks, failed)
            if not r or not str(r.get("outcome", "")).startswith("success")
        ]
        if args.task:
            want = set(args.task.split(","))
            failed_ids = [i for i in failed_ids if i in want]
        print(f"[stage] {len(failed_ids)} 个 p1 失败任务待重试")
        return [t for t in tasks if t["task_id"] in failed_ids]
    sys.exit(f"未知 stage: {stage}")


# ---- prompt / 工作区 ------------------------------------------------------------

def build_prompt(task: dict, stage: str, cfg: dict) -> str:
    prompt = PROMPT_TEMPLATE.format(task_description=task["language"])
    if stage.startswith("p1") or stage.startswith("p2") or stage.startswith("p3"):
        example_file = ROOT / "template" / "example_episode.py"
        if example_file.exists():
            prompt += EXAMPLE_BLOCK.format(example=example_file.read_text().strip())
    if stage.startswith("p3"):
        prompt += COACHING_BLOCK
    return prompt


def prep_workspace(task: dict, stage: str, cfg: dict, cap) -> tuple[Path, str]:
    tdir = RESULTS / stage / task["task_id"]
    if tdir.exists():
        shutil.rmtree(tdir)
    tdir.mkdir(parents=True)
    ws = tdir / "workspace"
    shutil.copytree(ROOT / "template", ws)

    readme = (ws / "README.md").read_text()
    readme = readme.replace("{{TASK_ID}}", task["task_id"]).replace(
        "{{INSTRUCTION}}", task["language"]
    ).replace("{{LIBERO_PYTHON}}", cfg["libero_python"])
    (ws / "README.md").write_text(readme)

    (tdir / "sim_state.json").write_text(
        json.dumps({"try_count": 0, "trial_cap": cap})
    )
    prompt = build_prompt(task, stage, cfg)
    (tdir / "prompt.txt").write_text(prompt)
    return tdir, prompt


# ---- MCC 会话 -------------------------------------------------------------------

def wait_for_ram(min_avail_mb: int = 2200) -> None:
    """并发背压：可用内存不足时等待，防 OOM。"""
    for _ in range(60):
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemAvailable"):
                        avail = int(line.split()[1]) // 1024
                        if avail >= min_avail_mb:
                            return
                        break
        except Exception:
            return
        time.sleep(30)


def run_mcc(tdir: Path, prompt: str, cfg: dict, provider: dict, stage_cfg: dict) -> dict:
    ws = tdir / "workspace"
    env = os_environ_with(
        LLM_BASE_URL=provider["base_url"],
        LLM_API_KEY=provider["api_key"],
        LLM_MODEL=provider["model"],
        MAX_TURNS=str(stage_cfg["max_turns"]),
        MAX_TOTAL_TOKENS=str(cfg.get("max_total_tokens", 1500000)),
        TRACE_PATH=str(tdir / "trace.jsonl"),
        FAEA_STATE_PATH=str(tdir / "sim_state.json"),
    )
    wait_for_ram()
    cmd = [
        cfg["mcc_python"], "main.py", "--task", prompt, "-y", "--root", str(ws)
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=cfg["mcc_dir"], env=env,
            timeout=cfg.get("task_walltime_min", 120) * 60,
            capture_output=True, text=True, start_new_session=True,
        )
        return {
            "exit_code": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
            "wall_time_s": time.time() - t0,
            "timeout": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -9, "stdout_tail": "", "stderr_tail": "TIMEOUT",
            "wall_time_s": time.time() - t0, "timeout": True,
        }


def os_environ_with(**kv) -> dict:
    import os

    env = os.environ.copy()
    env.update({k: v for k, v in kv.items()})
    return env


# ---- trace 解析 ------------------------------------------------------------------

def collect_trace(ws: Path, tdir: Path | None = None) -> tuple[str, dict]:
    """返回 (trace文本或空, metrics dict)。优先 tdir/trace.jsonl（TRACE_PATH 注入）。"""
    direct = (tdir / "trace.jsonl") if tdir else None
    candidates = []
    if direct and direct.exists():
        candidates = [direct]
    else:
        candidates = sorted((ws / ".mcc").rglob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            return "", {}
    trace_path = candidates[-1]
    records = []
    for line in trace_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    metrics = {
        "turns": sum(1 for r in records if r.get("kind") == "turn_start"),
        "tokens_in": sum((r.get("usage") or {}).get("prompt", 0) for r in records if r.get("kind") == "llm_response"),
        "tokens_out": sum((r.get("usage") or {}).get("completion", 0) for r in records if r.get("kind") == "llm_response"),
        "tool_calls": dict(Counter(r.get("name") for r in records if r.get("kind") == "tool_call")),
        "mcc_termination": next(
            (r.get("termination") for r in reversed(records) if r.get("kind") == "run_end"),
            "unknown",
        ),
    }
    return trace_path.read_text(errors="replace"), metrics


# ---- 失败分类 / 复核 / 规则 --------------------------------------------------------

TERMINATION_MAP = {
    "completed": None,
    "max_turns": "max_turns",
    "stalled": "stalled",
    "llm_failure": "llm_failure",
    "context_overflow": "budget",
    "cancelled": "cancelled",
    "user_rejected": "user_rejected",
    "internal_error": "internal_error",
}


def classify(ws: Path, run: dict, metrics: dict) -> tuple[str, dict]:
    meta = load_json(ws / "meta.json")
    episode = ws / "episode.py"
    if run["timeout"]:
        return "infra_timeout", {"reason": "wall clock timeout"}
    if meta and meta.get("success") is True:
        return "provisional_success", {"meta": meta}
    if meta and meta.get("success") is False:
        return "task_failed", {"meta": meta}
    term = metrics.get("mcc_termination", "unknown")
    mapped = TERMINATION_MAP.get(term, term if term != "completed" else None)
    if mapped:
        return mapped, {"termination": term}
    # completed 但无 meta.json
    if not episode.exists():
        return "infra_env", {"reason": "no episode.py after completed session"}
    return "task_failed", {"reason": "completed without meta.json"}


def verify_success(tdir: Path, cfg: dict) -> dict:
    """独立重跑 episode.py（SPEC §4.4 D12）。"""
    ws = tdir / "workspace"
    vdir = tdir / "verify"
    if vdir.exists():
        shutil.rmtree(vdir)
    shutil.copytree(ws, vdir)
    (vdir / ".sim_state.json").write_text(json.dumps({"try_count": 0, "trial_cap": None}))
    try:
        subprocess.run(
            [cfg["libero_python"], "episode.py"],
            cwd=vdir, capture_output=True, text=True, timeout=900,
            start_new_session=True,
        )
        meta = load_json(vdir / "meta.json") or {}
        return {"rerun_success": bool(meta.get("success")), "meta": meta}
    except subprocess.TimeoutExpired:
        return {"rerun_success": False, "meta": {}, "error": "verify timeout"}
    except Exception as e:  # noqa: BLE001
        return {"rerun_success": False, "meta": {}, "error": str(e)}


def scan_rules(ws: Path, tdir: Path | None = None) -> list[str]:
    ep = ws / "episode.py"
    text = ep.read_text(errors="replace") if ep.exists() else ""
    hits = [name for name, rx in RULES if rx.search(text)]
    # R5: trace 级计数篡改检测
    if tdir is not None:
        trace = tdir / "trace.jsonl"
        if trace.exists():
            tt = trace.read_text(errors="replace")
            if any(rx.search(tt) for rx in R5_TRACE_PATTERNS):
                hits.append("R5_counter_tamper")
    return hits


def pick_video(tdir: Path, meta: dict) -> str | None:
    ws = tdir / "workspace"
    if not ws.exists():
        return None
    want = None
    if meta and meta.get("final_try"):
        want = ws / f"try_{int(meta['final_try']):03d}.mp4"
        if want.exists():
            shutil.copy(want, tdir / "video.mp4")
            return "final_try"
    videos = sorted(ws.glob("try_*.mp4"))
    if videos:
        shutil.copy(videos[-1], tdir / "video.mp4")
        return "latest"
    return None


# ---- 单任务全流程 ------------------------------------------------------------------

def run_one(task: dict, stage: str, cfg: dict, provider: dict, force: bool) -> dict:
    tdir = RESULTS / stage / task["task_id"]
    if (tdir / "run.json").exists() and not force:
        print(f"[skip] {stage}/{task['task_id']} 已有 run.json")
        return load_json(tdir / "run.json")

    stage_cfg = cfg["stages"][stage]
    cap = stage_cfg.get("trial_cap")
    tdir, prompt = prep_workspace(task, stage, cfg, cap)
    print(f"[run] {stage}/{task['task_id']} provider={provider['name']} cap={cap}")

    run = run_mcc(tdir, prompt, cfg, provider, stage_cfg)
    trace_text, metrics = collect_trace(tdir / "workspace", tdir)
    (tdir / "trace.jsonl").write_text(trace_text or "")

    run.update(metrics)
    outcome, detail = classify(tdir / "workspace", run, metrics)

    # llm_failure（突发限流/瞬断）：轮换 provider 最多再试 2 次，每次前冷却 60s
    attempts = 0
    while outcome == "llm_failure" and attempts < 2:
        attempts += 1
        provider = rotate_provider()
        print(f"[retry {attempts}/2] {task['task_id']} with {provider['name']} after cooldown")
        time.sleep(60)
        tdir, prompt = prep_workspace(task, stage, cfg, cap)
        run = run_mcc(tdir, prompt, cfg, provider, stage_cfg)
        trace_text, metrics = collect_trace(tdir / "workspace", tdir)
        (tdir / "trace.jsonl").write_text(trace_text or "")
        run.update(metrics)
        outcome, detail = classify(tdir / "workspace", run, metrics)

    verified = None
    flagged = []
    if outcome == "provisional_success":
        vres = verify_success(tdir, cfg)
        verified = vres
        outcome = "success_verified" if vres["rerun_success"] else "success_unverified"
        flagged = scan_rules(tdir / "workspace", tdir)
    # p0 成功即固化 example（M2：example = 最近一次成功 episode）
    if outcome == "success_verified" and stage == "p0_prompt_dev":
        ex = ROOT / "template" / "example_episode.py"
        shutil.copy(tdir / "workspace" / "episode.py", ex)
        print("[example] frozen to template/example_episode.py")

    video_src = pick_video(tdir, detail.get("meta") or {})

    run_json = {
        "stage": stage,
        "suite": task["suite"],
        "task_id": task["task_id"],
        "language": task["language"],
        "model": provider["model"],
        "provider": provider["name"],
        "mcc_exit_code": run["exit_code"],
        "outcome": outcome,
        "flagged": flagged,
        "verified": verified,
        "video_source": video_src,
        "detail": detail,
        "wall_time_s": round(run.get("wall_time_s", 0), 1),
        "turns": metrics.get("turns", 0),
        "tokens_in": metrics.get("tokens_in", 0),
        "tokens_out": metrics.get("tokens_out", 0),
        "tool_calls": metrics.get("tool_calls", {}),
        "tries": load_json(tdir / "sim_state.json", {}).get("try_count",
                 (detail.get("meta") or {}).get("num_tries", 0)),
        "ts": time.strftime("%F %T"),
    }
    (tdir / "run.json").write_text(json.dumps(run_json, indent=1, ensure_ascii=False))
    print(f"[done] {task['task_id']} -> {outcome}")
    return run_json


# ---- main -----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["p0_prompt_dev", "p1_pilot", "p2_baseline_retry", "p3_coaching_retry"])
    ap.add_argument("--task", help="逗号分隔 task_id 或 p0 默认")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--sample", type=int, help="分层试点规模(10)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--parallel", type=int, default=1, help="并发会话数（默认1=串行）")
    ap.add_argument("--refresh-tasks", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    if args.refresh_tasks:
        tasks = refresh_tasks()
        n = {}
        for t in tasks:
            n[t["suite"]] = n.get(t["suite"], 0) + 1
        print(f"[tasks] {n}")
        return
    if not args.stage:
        ap.error("--stage 必填（或用 --refresh-tasks）")
    if not TASKS_CACHE.exists():
        tasks = refresh_tasks()
        n = {}
        for t in tasks:
            n[t["suite"]] = n.get(t["suite"], 0) + 1
        print(f"[tasks] {n}")
        if args.refresh_tasks:
            return
    else:
        tasks = get_tasks()

    stage_tasks = resolve_stage_tasks(args.stage, args)
    provider = active_provider()
    ok = 0
    n_par = max(1, int(args.parallel))
    if n_par == 1:
        for t in stage_tasks:
            r = run_one(t, args.stage, cfg, provider, args.force)
            if str(r.get("outcome", "")).startswith("success"):
                ok += 1
            provider = active_provider()
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        lock = threading.Lock()

        def worker(t):
            with lock:
                prov = active_provider()
            return run_one(t, args.stage, cfg, prov, args.force)

        with ThreadPoolExecutor(max_workers=n_par) as ex:
            futs = [ex.submit(worker, t) for t in stage_tasks]
            for fu in as_completed(futs):
                try:
                    r = fu.result()
                    if str(r.get("outcome", "")).startswith("success"):
                        ok += 1
                except Exception as e:  # noqa: BLE001
                    print("[worker-error]", e)
    print(f"[stage done] {args.stage}: {ok}/{len(stage_tasks)} success")


if __name__ == "__main__":
    main()
