"""Robustness check: replay *perturbed* copies of the incident tapes over several seeds.

The grader uses hidden tapes ("shifted in time, different intensity") and several seeds, so passing the public
tapes on one seed is not enough. This script shifts every incident in time and scales its intensity, then
reports, per tape, how many (variant x seed) runs pass and which checks fail.

    python scripts/stress_tapes.py                       # 6 Game Day tapes, resilient client
    python scripts/stress_tapes.py --cache               # tape C1, cached client
    python scripts/stress_tapes.py --seeds 1,2,3 --shifts -60,0,60
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # run without pip install

import argparse
import dataclasses
from collections import Counter

from gameday_lab.factory import build_client
from gameday_lab.sim.config import Effect, LabConfig, Scenario, TimedValue, Window, load_config
from gameday_lab.sim.engine import evaluate_checks, run_scenario


def _shift_window(w: Window, dt: float) -> Window:
    return dataclasses.replace(w, start=w.start + dt, end=w.end + dt)


def _scale_effect(e: Effect, k: float) -> Effect:
    """k > 1 = a harsher incident, k < 1 = a milder one."""
    changes: dict[str, object] = {}
    if e.capacity_factor < 1.0:
        changes["capacity_factor"] = min(1.0, max(0.05, e.capacity_factor / k))
    if e.extra_latency_s:
        changes["extra_latency_s"] = e.extra_latency_s * k
    if e.error_rate:
        changes["error_rate"] = min(0.95, e.error_rate * k)
    if e.rate_limit_rps is not None:
        changes["rate_limit_rps"] = max(1.0, round(e.rate_limit_rps / k))
    return dataclasses.replace(e, **changes)


def perturb(sc: Scenario, dt: float, k: float) -> Scenario:
    effects = tuple(_scale_effect(dataclasses.replace(e, start=max(0.0, e.start + dt), end=e.end + dt), k)
                    if e.start > 0 else _scale_effect(dataclasses.replace(e, end=e.end + dt), k)
                    for e in sc.effects)
    traffic = tuple(dataclasses.replace(_shift_window(w, dt), value=1.0 + (w.value - 1.0) * k) for w in sc.traffic)
    # the malformed share is not scaled: above ~60% no client can reach the G5 availability bar (see README FAQ)
    malformed = tuple(_shift_window(w, dt) for w in sc.malformed)
    return dataclasses.replace(
        sc,
        duration_s=sc.duration_s + max(0.0, dt),  # keep the post-incident measurement window inside the tape
        effects=effects,
        traffic=traffic,
        malformed=malformed,
        primary_only=tuple(_shift_window(w, dt) for w in sc.primary_only),
        restore_at=None if sc.restore_at is None else sc.restore_at + dt,
        content_updates=tuple(TimedValue(u.t + dt, u.value) for u in sc.content_updates),
        silent_updates=tuple(TimedValue(u.t + dt, u.value) for u in sc.silent_updates),
        prompt_deploys=tuple(TimedValue(u.t + dt, u.value) for u in sc.prompt_deploys),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/gameday.yaml")
    ap.add_argument("--cache", action="store_true", help="tape C1 with the cached client")
    ap.add_argument("--seeds", default="25,26,27,1,2")
    ap.add_argument("--shifts", default="-60,-30,0,30,60")
    ap.add_argument("--intensities", default="0.8,1.0,1.25")
    args = ap.parse_args()
    scen = "configs/scenarios_cache.yaml" if args.cache else "configs/scenarios.yaml"
    client = "cached" if args.cache else "resilient"
    cfg: LabConfig = load_config(args.config, scen)
    seeds = [int(s) for s in args.seeds.split(",")]
    shifts = [float(s) for s in args.shifts.split(",")]
    ks = [float(k) for k in args.intensities.split(",")]
    for key, base in cfg.scenarios.items():
        if args.cache != (base.faq is not None):
            continue
        passed = total = 0
        failed: Counter[str] = Counter()
        worst: dict[str, float] = {}
        for dt in shifts:
            for k in ks:
                sc = perturb(base, dt, k)
                variant = dataclasses.replace(cfg, scenarios={key: sc})
                for seed in seeds:
                    m = run_scenario(variant, key, build_client(client, variant), seed).metrics()
                    checks = evaluate_checks(m, sc.checks)
                    total += 1
                    passed += all(checks.values())
                    for name, ok in checks.items():
                        if not ok:
                            failed[f"{name}@dt={dt:+.0f},k={k}"] += 1
                    for name in sc.checks:
                        metric = name.rpartition("_")[0]
                        v = m.get(metric)
                        if isinstance(v, (int, float)):
                            worst[name] = min(worst.get(name, v), v) if name.endswith("_min") else max(
                                worst.get(name, v), v)
        print(f"{key:28s} {passed}/{total} runs pass")
        print(f"{'':28s} worst: " + ", ".join(f"{n}={v:g}" for n, v in worst.items()))
        for name, n in failed.most_common(8):
            print(f"{'':28s} FAIL {name} x{n}")


if __name__ == "__main__":
    main()
