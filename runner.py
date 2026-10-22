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
import hashlib
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

_BUDGET_LOCK = threading.Lock()
_BUDGET_LIMIT = 0
_BUDGET_SPENT = 0
_BUDGET_PATH: Path | None = None


def budget_init(stage_cfg: dict) -> None:
    global _BUDGET_LIMIT, _BUDGET_SPENT, _BUDGET_PATH
    limit = int(stage_cfg.get("stage_token_budget") or 0)
    if limit <= 0:
        return
    _BUDGET_LIMIT = limit
    _BUDGET_PATH = RESULTS / "p4_v41_recovery" / "_budget.json"
    if _BUDGET_PATH.exists():
        try:
            _BUDGET_SPENT = int(json.loads(_BUDGET_PATH.read_text()).get("spent", 0))
        except Exception:
            _BUDGET_SPENT = 0
    print(f"[budget] limit={_BUDGET_LIMIT:,} spent={_BUDGET_SPENT:,}")


def budget_can_start() -> bool:
    if _BUDGET_LIMIT <= 0:
        return True
    with _BUDGET_LOCK:
        return _BUDGET_SPENT < _BUDGET_LIMIT


def budget_add(tokens: int) -> None:
    global _BUDGET_SPENT
    if _BUDGET_LIMIT <= 0:
        return
    with _BUDGET_LOCK:
        _BUDGET_SPENT += max(0, int(tokens))
        if _BUDGET_PATH is not None:
            _BUDGET_PATH.parent.mkdir(parents=True, exist_ok=True)
            _BUDGET_PATH.write_text(
                json.dumps({"spent": _BUDGET_SPENT, "limit": _BUDGET_LIMIT})
            )

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

TRIAL_BUDGET_BLOCK = """
## Trial Budget (IMPORTANT)
- You have {cap} tries. Each `env.reset()` consumes one try.
- The first attempt is expected to fail. Do NOT stop after one failure.
- You MUST NOT write `meta.json` with `"success": false` while tries remain.
- If an attempt fails, inspect `open_fraction` / object poses, revise `episode.py`,
  and run it again. Only stop early when `env.check_success()` returns true;
  otherwise use every available try.
- Write and run `episode.py` by turn 12. Do NOT spend more than 10 turns on
  probe scripts. Iterate on `episode.py`, not on probes.
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


def active_provider(name: str | None = None) -> dict:
    secrets = load_json(ROOT / "secrets.local.json", {})
    provs = secrets.get("providers", [])
    if not provs:
        sys.exit("secrets.local.json 缺少 providers")
    if name:
        match = [p for p in provs if p.get("name") == name]
        if not match:
            sys.exit(f"secrets.local.json 里没有 provider: {name}")
        p = dict(match[0])
        p["index"] = provs.index(match[0])
    else:
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
    if stage in ("p5_goal_obs_pilot", "p5b_goal_grasp_hint"):
        picked = [t for t in tasks if t["suite"] == "libero_goal"]
        if args.task:
            want = set(args.task.split(","))
            picked = [t for t in picked if t["task_id"] in want]
        return picked
    if stage == "p4_v41_recovery":
        order_file = load_config()["stages"][stage].get(
            "order_file", "results/p4_v41_recovery/ORDER.json"
        )
        order_path = ROOT / order_file
        if not order_path.exists():
            sys.exit(f"缺少预注册顺序文件 {order_path}；先跑 --freeze-order")
        order = json.loads(order_path.read_text()).get("order", [])
        by_id = {t["task_id"]: t for t in tasks}
        picked = [by_id[tid] for tid in order if tid in by_id]
        if args.task:
            want = set(args.task.split(","))
            picked = [t for t in picked if t["task_id"] in want]
        print(f"[order] {len(picked)} 个任务（冻结顺序）")
        return picked
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
    if stage.startswith(("p1", "p2", "p3", "p4", "p5")):
        example_file = ROOT / "template" / "example_episode.py"
        if example_file.exists():
            prompt += EXAMPLE_BLOCK.format(example=example_file.read_text().strip())
    if stage.startswith("p3") or stage == "p4_v41_recovery":
        prompt += COACHING_BLOCK
    if stage == "p4_v41_recovery":
        prompt += TRIAL_BUDGET_BLOCK.format(
            cap=cfg["stages"][stage].get("trial_cap", 10)
        )
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


def run_mcc(
    tdir: Path,
    prompt: str,
    cfg: dict,
    provider: dict,
    stage_cfg: dict,
    max_turns_override: int | None = None,
    trace_name: str = "trace.jsonl",
) -> dict:
    ws = tdir / "workspace"
    timeout_min = int(stage_cfg.get("task_walltime_min") or cfg.get("task_walltime_min", 120))
    session_budget = int(
        stage_cfg.get("session_token_budget") or cfg.get("max_total_tokens", 1500000)
    )
    env = os_environ_with(
        LLM_BASE_URL=provider["base_url"],
        LLM_API_KEY=provider["api_key"],
        LLM_MODEL=provider["model"],
        MAX_TURNS=str(max_turns_override or stage_cfg["max_turns"]),
        MAX_TOKENS=str(stage_cfg.get("max_output_tokens", 4096)),
        LLM_REQUEST_TIMEOUT=str(stage_cfg.get("request_timeout_s", 120)),
        MAX_TOTAL_TOKENS=str(session_budget),
        TRACE_PATH=str(tdir / trace_name),
        FAEA_STATE_PATH=str(tdir / "sim_state.json"),
    )
    wait_for_ram()
    cmd = [
        cfg["mcc_python"], "main.py", "--task", prompt, "-y", "--root", str(ws)
    ]
    t0 = time.time()
    proc = subprocess.Popen(
        cmd, cwd=cfg["mcc_dir"], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_min * 60)
        return {
            "exit_code": proc.returncode,
            "stdout_tail": (stdout or "")[-4000:],
            "stderr_tail": (stderr or "")[-4000:],
            "wall_time_s": time.time() - t0,
            "timeout": False,
        }
    except subprocess.TimeoutExpired:
        # 杀整个进程组，防 episode.py / probe 的仿真子进程残留
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            stdout, stderr = proc.communicate(timeout=60)
        except Exception:
            stdout, stderr = "", ""
        return {
            "exit_code": -9,
            "stdout_tail": (stdout or "")[-4000:],
            "stderr_tail": "TIMEOUT\n" + (stderr or "")[-4000:],
            "wall_time_s": time.time() - t0,
            "timeout": True,
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
    if stage == "p4_v41_recovery" and not budget_can_start():
        skip = {
            "stage": stage, "suite": task["suite"], "task_id": task["task_id"],
            "language": task["language"], "model": provider["model"],
            "provider": provider["name"], "outcome": "deadline_skipped",
            "detail": {"reason": "stage token budget exhausted"},
            "turns": 0, "tokens_in": 0, "tokens_out": 0, "tries": 0,
            "flagged": [], "ts": time.strftime("%F %T"),
        }
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "run.json").write_text(json.dumps(skip, indent=1, ensure_ascii=False))
        print(f"[budget] skip {task['task_id']} (token budget exhausted)")
        return skip
    cap = stage_cfg.get("trial_cap")
    tdir, prompt = prep_workspace(task, stage, cfg, cap)
    print(f"[run] {stage}/{task['task_id']} provider={provider['name']} cap={cap}")

    run = run_mcc(tdir, prompt, cfg, provider, stage_cfg)
    trace_text, metrics = collect_trace(tdir / "workspace", tdir)
    (tdir / "trace.jsonl").write_text(trace_text or "")

    run.update(metrics)
    budget_add(metrics.get("tokens_in", 0) + metrics.get("tokens_out", 0))
    outcome, detail = classify(tdir / "workspace", run, metrics)

    # llm_failure（突发限流/瞬断）：严格模式不换模型，冷却后原 provider 重试；
    # 已跑超过 5 分钟则不重启，避免把预算烧在从头再来上。
    strict = bool(stage_cfg.get("strict_provider"))
    attempts = 0
    while outcome == "llm_failure" and attempts < 5:
        if strict and run.get("wall_time_s", 0) > 600:
            print(f"[defer] {task['task_id']} llm_failure after {run['wall_time_s']:.0f}s; not restarting")
            break
        attempts += 1
        cooldown = min(30 * (2 ** (attempts - 1)), 300)
        if strict:
            print(f"[retry {attempts}/5] {task['task_id']} same provider {provider['name']} after {cooldown}s")
        else:
            provider = rotate_provider()
            print(f"[retry {attempts}/5] {task['task_id']} with {provider['name']} after {cooldown}s")
        time.sleep(cooldown)
        tdir, prompt = prep_workspace(task, stage, cfg, cap)
        run = run_mcc(tdir, prompt, cfg, provider, stage_cfg)
        trace_text, metrics = collect_trace(tdir / "workspace", tdir)
        (tdir / "trace.jsonl").write_text(trace_text or "")
        run.update(metrics)
        budget_add(metrics.get("tokens_in", 0) + metrics.get("tokens_out", 0))
        outcome, detail = classify(tdir / "workspace", run, metrics)

    # 早退兜底：meta success=false 且 tries 未用完，在同一 workspace 继续会话，
    # 不重置 try 计数，总 turn 预算仍为 stage_cfg["max_turns"]。
    cont_rounds = 0
    if stage == "p4_v41_recovery" and cap:
        while (
            outcome == "task_failed"
            and (detail.get("meta") or {}).get("success") is False
            and int((load_json(tdir / "sim_state.json", {}) or {}).get("try_count", 0)) < int(cap)
            and cont_rounds < 2
        ):
            remaining_turns = int(stage_cfg["max_turns"]) - int(metrics.get("turns", 0))
            if remaining_turns < 20:
                break
            tries_now = int((load_json(tdir / "sim_state.json", {}) or {}).get("try_count", 0))
            meta_path = tdir / "workspace" / "meta.json"
            if meta_path.exists():
                meta_path.unlink()
            if (tdir / "trace.jsonl").exists():
                shutil.copy(tdir / "trace.jsonl", tdir / f"trace_attempt{cont_rounds + 1}.jsonl")
            cont_prompt = (
                "# Continue the task\n"
                f"The task is: {task['language']}\n"
                f"Your previous attempt ended with success=false after {tries_now} tries. "
                f"You have {int(cap) - tries_now} tries left.\n"
                "Do NOT write meta.json with success=false while tries remain. Read your "
                "existing episode.py and probe files, diagnose the failure, revise episode.py, "
                "and run it again. Use all remaining tries.\n"
            )
            print(f"[continue {cont_rounds + 1}/2] {task['task_id']} tries={tries_now}/{cap}")
            cont = run_mcc(
                tdir, cont_prompt, cfg, provider, stage_cfg,
                max_turns_override=remaining_turns,
            )
            cont_trace, cont_metrics = collect_trace(tdir / "workspace", tdir)
            (tdir / "trace.jsonl").write_text(cont_trace or "")
            run["exit_code"] = cont.get("exit_code", run.get("exit_code"))
            run["wall_time_s"] = run.get("wall_time_s", 0) + cont.get("wall_time_s", 0)
            run["timeout"] = bool(cont.get("timeout", False))
            for k in ("turns", "tokens_in", "tokens_out"):
                metrics[k] = int(metrics.get(k, 0)) + int(cont_metrics.get(k, 0))
            tc = dict(metrics.get("tool_calls") or {})
            for k, v in (cont_metrics.get("tool_calls") or {}).items():
                tc[k] = tc.get(k, 0) + v
            metrics["tool_calls"] = tc
            metrics["mcc_termination"] = cont_metrics.get("mcc_termination")
            budget_add(cont_metrics.get("tokens_in", 0) + cont_metrics.get("tokens_out", 0))
            outcome, detail = classify(tdir / "workspace", run, metrics)
            cont_rounds += 1

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
        "strict_provider": strict,
        "timeout": bool(run.get("timeout", False)),
        "restarts": attempts,
        "ts": time.strftime("%F %T"),
    }
    (tdir / "run.json").write_text(json.dumps(run_json, indent=1, ensure_ascii=False))
    print(f"[done] {task['task_id']} -> {outcome}")
    return run_json


EXCLUDED_FINAL_FAILURES = {
    "libero_90_26", "libero_90_28", "libero_90_54",
    "libero_90_33", "libero_90_39", "libero_object_8",
    "libero_goal_5", "libero_90_69",
}


def eligible_final_failures(tasks: list[dict]) -> list[dict]:
    """旧 pilot + coaching 都没有干净成功的任务（72 个）。"""
    out = []
    for t in tasks:
        tid = t["task_id"]
        if tid in EXCLUDED_FINAL_FAILURES:
            continue
        r1 = load_json(RESULTS / "p1_pilot" / tid / "run.json", {})
        r3 = load_json(RESULTS / "p3_coaching_retry" / tid / "run.json", {})
        ok1 = str((r1 or {}).get("outcome", "")).startswith("success")
        ok3 = str((r3 or {}).get("outcome", "")).startswith("success")
        if not ok1 and not ok3:
            out.append(t)
    return out


def freeze_order(cfg: dict, seed: int) -> None:
    tasks = get_tasks()
    eligible = eligible_final_failures(tasks)
    suites = ("libero_object", "libero_spatial", "libero_goal", "libero_90")
    buckets = {s: [t for t in eligible if t["suite"] == s] for s in suites}
    rng = random.Random(seed)
    for s in suites:
        rng.shuffle(buckets[s])
    order = []
    while any(buckets.values()):
        for s in suites:
            if buckets[s]:
                order.append(buckets[s].pop(0))
    ids = [t["task_id"] for t in order]
    payload = {
        "seed": seed,
        "generated_at": time.strftime("%F %T"),
        "count": len(ids),
        "eligible": sorted(t["task_id"] for t in eligible),
        "excluded": sorted(EXCLUDED_FINAL_FAILURES),
        "order": ids,
    }
    payload["sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    rel = cfg["stages"]["p4_v41_recovery"].get(
        "order_file", "results/p4_v41_recovery/ORDER.json"
    )
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    from collections import Counter
    print(f"[order] frozen {len(ids)} tasks -> {path}")
    print(f"[order] suites {dict(Counter(t['suite'] for t in order))}")
    print(f"[order] sha256 {payload['sha256']}")


# ---- main -----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["p0_prompt_dev", "p1_pilot", "p2_baseline_retry", "p3_coaching_retry", "p4_v41_recovery", "p5_goal_obs_pilot", "p5b_goal_grasp_hint"])
    ap.add_argument("--task", help="逗号分隔 task_id 或 p0 默认")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--sample", type=int, help="分层试点规模(10)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--parallel", type=int, default=1, help="并发会话数（默认1=串行）")
    ap.add_argument("--refresh-tasks", action="store_true")
    ap.add_argument("--provider", help="按名字选择 provider（如 intern）")
    ap.add_argument("--freeze-order", action="store_true", help="冻结 M8 72 任务顺序")
    ap.add_argument("--seed", type=int, default=20261021)
    args = ap.parse_args()

    cfg = load_config()
    if args.refresh_tasks:
        tasks = refresh_tasks()
        n = {}
        for t in tasks:
            n[t["suite"]] = n.get(t["suite"], 0) + 1
        print(f"[tasks] {n}")
        return
    if args.freeze_order:
        freeze_order(cfg, args.seed)
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
    provider = active_provider(args.provider)
    stage_cfg = cfg["stages"][args.stage]
    strict_stage = bool(stage_cfg.get("strict_provider"))
    budget_init(stage_cfg)
    print(f"[provider] {provider['name']} model={provider['model']} strict={strict_stage}")
    ok = 0
    n_par = max(1, int(args.parallel))
    if n_par == 1:
        for t in stage_tasks:
            r = run_one(t, args.stage, cfg, provider, args.force)
            if str(r.get("outcome", "")).startswith("success"):
                ok += 1
            if not strict_stage:
                provider = active_provider()
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        lock = threading.Lock()

        def worker(t):
            if strict_stage:
                prov = provider
            else:
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
