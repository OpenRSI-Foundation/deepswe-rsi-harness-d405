#!/usr/bin/env python3
"""Project the full Judge round time and apply the two step-5 judgments.

Inputs come from the smoke Judge (unit cost, overhead), the task declarations
(timeouts, GPU counts), and the measured baseline. Output: J, R, the judgment
results, and which levers apply. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import sys

ROUNDS_PER_DAY_MIN = 6   # measured cadence, not the proposal admission check
TOTAL_LOOPS_MIN = 10
HEADROOM_MIN = 0.20      # judgment B, fraction of the metric ceiling
DAY = 86400.0
NORMAL_BUDGET_MAX = 2 * DAY


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--unit-seconds", type=float, required=True,
                        help="smoke-measured seconds per workload unit (epoch, step, sample)")
    parser.add_argument("--full-units", type=float, required=True,
                        help="workload units in the full fixed protocol")
    parser.add_argument("--overhead-seconds", type=float, default=0.0,
                        help="per-round fixed cost: evaluator startup, snapshot, evaluation")
    parser.add_argument("--work-seconds", type=float, default=0.0,
                        help="minimum Work time to produce one candidate (0 for data/config-only)")
    parser.add_argument("--agent-timeout", type=float, required=True, help="[agent] timeout_sec")
    parser.add_argument("--verifier-timeout", type=float, required=True, help="[verifier] timeout_sec")
    parser.add_argument("--work-gpus", type=int, default=0)
    parser.add_argument("--judge-gpus", type=int, default=0)
    parser.add_argument("--disjoint", action="store_true",
                        help="label separate Work/Judge GPUs (Work still pauses during Judge)")
    parser.add_argument("--candidates-per-round", type=int, default=1,
                        help="candidates the evaluator scores in parallel per round")
    parser.add_argument("--over-budget", action="store_true",
                        help="confirmed task OVER_BUDGET.flag: except daily cadence and 48h ceiling only")
    parser.add_argument("--baseline", type=float, help="baseline score measured by the full Judge")
    parser.add_argument("--score-max", type=float,
                        help="metric ceiling for bounded metrics (1.0 for a rate); omit for unbounded")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    return parser.parse_args()


def hours(seconds: float) -> str:
    return f"{seconds / 3600:.2f} h"


def main() -> int:
    a = parse_args()
    try:
        for name in (
            "unit_seconds", "full_units", "overhead_seconds", "work_seconds",
            "agent_timeout", "verifier_timeout", "score_max", "baseline",
        ):
            value = getattr(a, name)
            if value is not None and not math.isfinite(value):
                raise ValueError(f"--{name.replace('_', '-')} must be finite")
        for name in ("unit_seconds", "overhead_seconds", "work_seconds", "work_gpus", "judge_gpus"):
            if getattr(a, name) < 0:
                raise ValueError(f"--{name.replace('_', '-')} must be non-negative")
        for name in ("full_units", "agent_timeout", "verifier_timeout", "score_max"):
            value = getattr(a, name)
            if value is not None and value <= 0:
                raise ValueError(f"--{name.replace('_', '-')} must be positive")
        if a.candidates_per_round < 1:
            raise ValueError("--candidates-per-round must be at least 1")

        J = a.unit_seconds * a.full_units + a.overhead_seconds
        T = a.agent_timeout
        # GPU allocation controls residency, not concurrent Work/Judge execution.
        cycle = J + a.work_seconds
        for name, value in (("projected Judge time J", J), ("projected cycle", cycle)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        R = T / cycle
        R24 = min(T, DAY) / cycle
        minimum_total = TOTAL_LOOPS_MIN * cycle
        experiments = R * a.candidates_per_round
        for name, value in (("projected rounds", R), ("daily rounds", R24),
                            ("minimum total budget", minimum_total),
                            ("projected experiments", experiments)):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        headroom = None
        if a.score_max is not None and a.baseline is not None:
            headroom = 1 - a.baseline / a.score_max
            if not math.isfinite(headroom):
                raise ValueError("headroom from --baseline and --score-max must be finite")
    except (ValueError, OverflowError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    judgments: dict[str, dict[str, object]] = {}
    judgments["A_iteration_budget"] = {
        "rounds_24h": round(R24, 1), "required": ROUNDS_PER_DAY_MIN,
        "pass": R24 >= ROUNDS_PER_DAY_MIN,
    }
    judgments["A_total_loops"] = {
        "rounds": round(R, 1), "required": TOTAL_LOOPS_MIN, "pass": R >= TOTAL_LOOPS_MIN,
    }
    judgments["budget_limit"] = {
        "budget_seconds": T, "normal_max_seconds": NORMAL_BUDGET_MAX,
        "pass": T <= NORMAL_BUDGET_MAX,
    }
    for name in ("A_iteration_budget", "budget_limit"):
        judgments[name]["excepted"] = a.over_budget and not judgments[name]["pass"]
    if headroom is not None:
        judgments["B_headroom"] = {
            "headroom_fraction": round(headroom, 3), "required": HEADROOM_MIN,
            # Accept roundoff at the inclusive boundary, not a meaningful shortfall.
            "pass": headroom >= HEADROOM_MIN or math.isclose(
                headroom, HEADROOM_MIN, rel_tol=1e-12, abs_tol=0.0,
            ),
        }
    elif a.score_max is not None:
        judgments["B_headroom"] = {"pass": None, "note": "needs --baseline from the full Judge"}
    else:
        judgments["B_headroom"] = {"pass": None, "note": "unbounded metric; skipped"}
    judgments["verifier_timeout"] = {
        "J_seconds": round(J), "timeout": a.verifier_timeout, "pass": J <= a.verifier_timeout,
    }

    levers: list[str] = []
    if not judgments["A_iteration_budget"]["pass"] and not a.over_budget:
        levers.append("remove repeated per-round fixed costs (re-measured baselines, cold caches)")
        levers.append("contract: reduce evaluation size, then the fixed training/computation budget")
    if not judgments["A_total_loops"]["pass"]:
        if minimum_total <= NORMAL_BUDGET_MAX or a.over_budget:
            levers.append(f"extend the approved total budget above {hours(minimum_total)} "
                          "plus research/operational margin; recompile and reproject")
        else:
            levers.append("ten full loops exceed 48 h: reduce cycle cost or obtain a contributor budget exception")
    if not judgments["budget_limit"]["pass"] and not a.over_budget:
        levers.append("use a normal total budget of at most 48 h; an exception requires contributor confirmation")
    if judgments["B_headroom"].get("pass") is False:
        levers.append("contract: reduce the fixed budget or raise environment difficulty constants until the baseline leaves headroom")
    if not judgments["verifier_timeout"]["pass"]:
        levers.append(f"raise [verifier] timeout_sec above {round(J)} s (non-contract)")

    pending_baseline = a.score_max is not None and a.baseline is None
    if any(v["pass"] is False and not v.get("excepted", False) for v in judgments.values()):
        status = "repair_required"
    elif pending_baseline:
        status = "pending"
    else:
        status = "pass"
    result = {
        "J_seconds": round(J), "J": hours(J), "T": hours(T), "cycle": hours(cycle),
        "mode": "disjoint" if a.disjoint else "release-all",
        "rounds_24h": round(R24, 1), "minimum_total_seconds": minimum_total,
        "over_budget": a.over_budget,
        "rounds_R": round(R, 1), "experiments_per_budget": round(experiments, 1),
        "judgments": judgments, "levers": levers,
        "overall": status == "pass", "status": status,
    }
    if a.json:
        print(json.dumps(result, indent=2, allow_nan=False))
    else:
        print(f"J (one full Judge round) = {result['J']} ({round(J)} s); mode {result['mode']}; "
              f"cycle {result['cycle']}; T = {result['T']}")
        print(f"R24 (rounds in first 24 h) = {result['rounds_24h']}; "
              f"R (loops per total budget) = {result['rounds_R']}; "
              f"candidate evaluations = {result['experiments_per_budget']}")
        for name, v in judgments.items():
            state = {True: "PASS", False: "FAIL", None: "skip"}[v.get("pass")]
            if v.get("excepted"):
                state = "EXCEPTION"
            if name == "B_headroom" and pending_baseline:
                state = "PENDING"
            detail = {k: val for k, val in v.items() if k != "pass"}
            print(f"  {name}: {state} {detail}")
        if levers:
            print("levers, in order:")
            for lever in levers:
                print(f"  - {lever}")
        print("overall:", {"pass": "PASS", "pending": "PENDING", "repair_required": "REPAIR REQUIRED"}[status])
    return 0 if result["overall"] else 1


if __name__ == "__main__":
    sys.exit(main())
