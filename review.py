#!/usr/bin/env python3
"""独立复核 + 可疑规则扫描（SPEC §4.4）。对已完成 stage 的任务重跑判定。

用法:
  python review.py --stage p1_pilot            # 全量复核该 stage
  python review.py --stage p1_pilot --task libero_object_0
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from runner import (  # noqa: E402
    RESULTS,
    ROOT,
    get_tasks,
    load_config,
    load_json,
    pick_video,
    scan_rules,
    verify_success,
)


def review_task(tdir: Path, cfg: dict) -> dict:
    run = load_json(tdir / "run.json")
    if not run:
        print(f"[skip] {tdir.name}: 无 run.json")
        return {}
    ws = tdir / "workspace"
    meta = load_json(ws / "meta.json")

    if run.get("outcome") in ("provisional_success", "success_verified", "success_unverified"):
        vres = verify_success(tdir, cfg)
        outcome = "success_verified" if vres["rerun_success"] else "success_unverified"
        run["verified"] = vres
        run["outcome"] = outcome
        run["flagged"] = scan_rules(ws, tdir)
        run["video_source"] = pick_video(tdir, meta or {}) or run.get("video_source")
        (tdir / "run.json").write_text(json.dumps(run, indent=1, ensure_ascii=False))
        print(f"[review] {run['task_id']} -> {outcome} flagged={run['flagged']}")
        return run

    print(f"[review] {run['task_id']} outcome={run.get('outcome')}（非成功，不重跑）")
    return run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--task")
    args = ap.parse_args()
    cfg = load_config()
    base = RESULTS / args.stage
    if args.task:
        targets = [base / args.task]
    else:
        targets = sorted(p for p in base.iterdir() if p.is_dir()) if base.exists() else []
    ok = 0
    for tdir in targets:
        r = review_task(tdir, cfg)
        ok += str(r.get("outcome", "")).startswith("success")
    if targets:
        print(f"[review done] {ok}/{len(targets)}")


if __name__ == "__main__":
    main()
