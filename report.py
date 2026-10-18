#!/usr/bin/env python3
"""汇总报告（SPEC §4.5）：论文 Table I / Table V 同构表 + 任务级 csv。

用法:
  python report.py                       # 全部 stage
  python report.py --stage p1_pilot
  python report.py --compare-paper       # 附论文原数字列
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"

SUITES = [("libero_spatial", "Spatial"), ("libero_object", "Object"),
          ("libero_goal", "Goal"), ("libero_90", "Long")]

PAPER_TABLE1 = {
    "p1_pilot": {"avg": 70.6, "label": "Pilot (10 trials)"},
    "p2_baseline_retry": {"avg": 84.9, "label": "Baseline (no limit)"},
    "p3_coaching_retry": {"avg": 88.2, "label": "+ coaching"},
}


def load_runs(stage):
    base = RESULTS / stage
    if not base.exists():
        return []
    out = []
    for d in sorted(base.iterdir()):
        if "__" in d.name:  # 归档目录（__r5_failed 等）不计入
            continue
        rj = d / "run.json"
        if rj.exists():
            out.append(json.loads(rj.read_text()))
    return out


def rate(runs, suite=None, effective=False):
    sel = [r for r in runs if suite is None or r["suite"] == suite]
    if effective:
        sel = [r for r in sel if not str(r.get("outcome", "")).startswith("infra")]
    if not sel:
        return None
    succ = sum(1 for r in sel
               if str(r.get("outcome", "")).startswith("success")
               and r.get("outcome") != "success_unverified")
    return round(100 * succ / len(sel), 1)


def fmt(v):
    return "-" if v is None else f"{v}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", action="append")
    ap.add_argument("--compare-paper", action="store_true")
    args = ap.parse_args()
    stages = args.stage or ["p0_prompt_dev", "p1_pilot",
                            "p2_baseline_retry", "p3_coaching_retry"]

    ts = time.strftime("%Y%m%d-%H%M")
    outdir = REPORTS / ts
    outdir.mkdir(parents=True, exist_ok=True)

    rows = []
    for stage in stages:
        for r in load_runs(stage):
            rows.append({
                "stage": stage, "task_id": r["task_id"], "suite": r["suite"],
                "outcome": r["outcome"], "flagged": ";".join(r.get("flagged") or []),
                "tries": r.get("tries"), "turns": r.get("turns"),
                "tokens_in": r.get("tokens_in"), "tokens_out": r.get("tokens_out"),
                "wall_time_s": r.get("wall_time_s"), "model": r.get("model"),
                "provider": r.get("provider"), "language": r.get("language"),
            })
    if rows:
        with open(outdir / "tasks.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    L = []
    L.append("# FAEA-LIBERO 复现报告 (" + ts + ")\n")
    models = sorted({r.get("model", "?") for r in rows}) or ["-"]
    L.append("**模型**: " + ", ".join(models)
             + "（非论文 Opus 4.5，数字解读必须带此前提）\n")
    infra = sum(1 for r in rows if str(r.get("outcome", "")).startswith("infra"))
    L.append("**会话数**: " + str(len(rows)) + "，其中基建失败 " + str(infra) + "\n")

    L.append("## 论文 Table I 同构表（严格口径, %）\n")
    L.append("| 条件 | Spatial | Object | Goal | Long | Avg |")
    L.append("|---|---|---|---|---|---|")
    for stage in stages:
        runs = load_runs(stage)
        if not runs:
            continue
        vals = [rate(runs, s) for s, _ in SUITES]
        row = ("| " + stage + " | " + " | ".join(fmt(v) for v in vals)
               + " | " + fmt(rate(runs)) + " |")
        if args.compare_paper and stage in PAPER_TABLE1:
            p = PAPER_TABLE1[stage]
            row += " （论文 " + p["label"] + ": " + str(p["avg"]) + "）"
        L.append(row)
    L.append("")

    L.append("## 有效口径（剔除基建失败）\n")
    L.append("| 条件 | Spatial | Object | Goal | Long | Avg |")
    L.append("|---|---|---|---|---|---|")
    for stage in stages:
        runs = load_runs(stage)
        if not runs:
            continue
        vals = [rate(runs, s, effective=True) for s, _ in SUITES]
        L.append("| " + stage + " | " + " | ".join(fmt(v) for v in vals)
                 + " | " + fmt(rate(runs, effective=True)) + " |")
    L.append("")

    L.append("## 资源表（论文 Table V 同构，均值）\n")
    L.append("| 条件 | suite | n | tries | turns | tokens_out | time(min) |")
    L.append("|---|---|---|---|---|---|---|")
    for stage in stages:
        runs = load_runs(stage)
        if not runs:
            continue
        for s, label in SUITES:
            sel = [r for r in runs if r["suite"] == s]
            if not sel:
                continue
            n = len(sel)
            avg = lambda k: sum(r.get(k) or 0 for r in sel) / n  # noqa: E731
            L.append(
                "| " + stage + " | " + label + " | " + str(n) + " | "
                + f"{avg('tries'):.1f} | {avg('turns'):.1f} | "
                + f"{avg('tokens_out')/1000:.1f}K | {avg('wall_time_s')/60:.1f} |"
            )
    L.append("")

    tools = defaultdict(int)
    total_tools = 0
    for r in rows:
        for k, v in (r.get("tool_calls") or {}).items():
            tools[k] += v
            total_tools += v
    if total_tools:
        L.append("## 工具分布\n")
        L.append("| 工具 | 次数 | 占比 |")
        L.append("|---|---|---|")
        for k, v in sorted(tools.items(), key=lambda x: -x[1]):
            L.append("| " + k + f" | {v} | {100*v/total_tools:.0f}% |")
        L.append("")

    flagged = [r for r in rows if r.get("flagged")]
    if flagged:
        L.append("## 可疑任务（人工裁决）\n")
        for r in flagged:
            L.append("- " + r["stage"] + "/" + r["task_id"] + ": "
                     + ";".join(r["flagged"]) + " (" + r["outcome"] + ")")
        L.append("")

    unverified = [r for r in rows if r.get("outcome") == "success_unverified"]
    if unverified:
        L.append("## 复核不一致（原报成功、重跑失败）\n")
        for r in unverified:
            L.append("- " + r["stage"] + "/" + r["task_id"])
        L.append("")

    L.append("\n## 偏差与诚实声明\n")
    L.append("- Agent = MiniClaudeCode（非论文 Claude Agent SDK），模型为免费 flash 档（非 Opus 4.5）")
    L.append("- 成功判定经独立重跑复核；复核不一致单列不计入主成功率")
    L.append("- 全部偏差见 SPEC.md §5.7")

    (outdir / "summary.md").write_text("\n".join(L) + "\n")
    print("[report]", outdir / "summary.md", "tasks=" + str(len(rows)))


if __name__ == "__main__":
    main()
