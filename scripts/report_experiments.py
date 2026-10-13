"""Experiments behind reports/REPORT.md (sections 2, 3 and 8). Writes reports/experiments.json.

    python scripts/report_experiments.py            # seed 25, the public tapes

Every row changes ONE setting of configs/gameday.yaml (or the client code, for experiment 3) and replays the
tapes that setting is meant to protect.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # run without pip install

import argparse
import copy
import dataclasses
import json
import random
from typing import Any

from gameday_lab.client import ResilientClient
from gameday_lab.factory import build_client
from gameday_lab.sim.config import LabConfig, load_config
from gameday_lab.sim.engine import evaluate_checks, run_scenario
from gameday_lab.workflows.executor import WorkflowExecutor
from gameday_lab.workflows.runner import STEPS, RefundRequest, run_workflows

KEYS = ["availability", "latency_p95_s", "amplification", "retry_ratio", "cost_per_good_turn", "recovery_s",
        "primary_share_after_restore", "give_up_reasons", "incompatible_routes"]
CACHE_KEYS = ["availability", "faq_availability", "cache_hit_ratio", "stale_served", "wrong_answers",
              "wrong_answers_by_reason", "outdated_answers", "cost_per_good_turn"]


class NoToolFilterClient(ResilientClient):
    """Experiment 3 only: the ladder ignores tool-calling capability."""

    def ladder(self, task: str) -> list[str]:
        return list(self.order)


class KeysOnlyExecutor(WorkflowExecutor):
    """Section 4: stable idempotency keys, but no checkpoints (every restart redoes every step)."""

    def run(self, req: RefundRequest) -> dict[str, Any]:
        state: dict[str, Any] = {}
        for step in STEPS:
            state[step] = self._step(req, state, step)
        return {"status": "done", **state}


class CheckpointsOnlyExecutor(WorkflowExecutor):
    """Section 4: checkpoints, but a fresh random idempotency key per attempt."""

    def _step(self, req: RefundRequest, state: dict[str, Any], step: str) -> Any:
        if step == "issue_refund":
            return self._retry(lambda: self.s.payments.refund(req.order_id, req.amount_cents,
                                                              idempotency_key=f"rnd-{random.random()}"))
        if step == "send_email":
            data = {"refund_id": state["issue_refund"]["refund_id"]}
            return self._retry(lambda: self.s.email.send(req.customer_email, "refund_done", data,
                                                         idempotency_key=f"rnd-{random.random()}"))
        return super()._step(req, state, step)


def _with_client(cfg: LabConfig, changes: dict[str, Any]) -> LabConfig:
    client = copy.deepcopy(cfg.client)
    for key, value in changes.items():
        if key.startswith("breaker."):
            client["breaker"][key.split(".", 1)[1]] = value
        else:
            client[key] = value
    return dataclasses.replace(cfg, client=client)


def _with_cache(cfg: LabConfig, changes: dict[str, Any]) -> LabConfig:
    return dataclasses.replace(cfg, cache={**cfg.cache, **changes})


def run(cfg: LabConfig, tape: str, seed: int, client: str = "resilient", keys: list[str] = KEYS,
        cls: type | None = None) -> dict[str, Any]:
    if cls is not None:
        c = cls(cfg.provider_infos(), cfg.fallback_order, cfg.client, seed=1)
    else:
        c = build_client(client, cfg)
    m = run_scenario(cfg, tape, c, seed).metrics()
    checks = evaluate_checks(m, cfg.scenarios[tape].checks)
    return {**{k: m.get(k) for k in keys}, "pass": all(checks.values()),
            "failed": [k for k, ok in checks.items() if not ok]}


SWEEPS: list[tuple[str, list[Any], list[str]]] = [
    ("attempt_timeout_s", [4.0, 8.0, 30.0], ["G4_slow_region", "G6_provider_outage"]),
    ("max_attempts_per_provider", [1, 2, 4], ["G2_overload_storm", "G3_brownout"]),
    ("backoff_base_s", [0.05, 0.25, 2.0], ["G2_overload_storm", "G3_brownout"]),
    ("retry_budget_ratio", [0.02, 0.1, 1.0], ["G3_brownout"]),
    ("breaker.min_calls", [3, 10, 40], ["G2_overload_storm", "G3_brownout", "G6_provider_outage"]),
    ("breaker.failure_rate_threshold", [0.2, 0.5, 0.9], ["G2_overload_storm", "G3_brownout"]),
    ("breaker.slow_call_s", [3.0, 5.0, 12.0], ["G2_overload_storm", "G4_slow_region"]),
    ("breaker.open_duration_s", [2.0, 10.0, 60.0], ["G2_overload_storm", "G4_slow_region"]),
    ("breaker.half_open_max_probes", [1, 2, 20], ["G2_overload_storm"]),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=25)
    ap.add_argument("--out", default="reports/experiments.json")
    args = ap.parse_args()
    seed = args.seed
    cfg = load_config("configs/gameday.yaml", "configs/scenarios.yaml")
    cache_cfg = load_config("configs/gameday.yaml", "configs/scenarios_cache.yaml")
    out: dict[str, Any] = {"seed": seed, "client_config": cfg.client, "cache_config": cfg.cache}

    out["sweeps"] = {}
    for key, values, tapes in SWEEPS:
        out["sweeps"][key] = {str(v): {t: run(_with_client(cfg, {key: v}), t, seed) for t in tapes} for v in values}

    # Experiment 1: retry budget as the last line of defence (breaker misconfigured, 5 attempts per provider)
    broken = {"breaker.min_calls": 1_000_000_000, "max_attempts_per_provider": 5}
    no_budget = {"retry_budget_ratio": 100, "retry_budget_max_tokens": 1.0e9, "retry_budget_min_per_s": 1.0e6}
    out["exp1_retry_budget"] = {
        name: {t: run(_with_client(cfg, changes), t, seed) for t in ("G2_overload_storm", "G3_brownout")}
        for name, changes in {
            "breaker_ok_budget_on": {},
            "breaker_ok_budget_off": no_budget,
            "breaker_broken_budget_on": broken,
            "breaker_broken_budget_off": {**broken, **no_budget},
        }.items()
    }
    # Experiment 2: attempt_timeout_s = 30 on G6 (and G4 as a control)
    out["exp2_timeout"] = {str(v): {t: run(_with_client(cfg, {"attempt_timeout_s": v}), t, seed)
                                    for t in ("G6_provider_outage", "G4_slow_region")} for v in (8.0, 30.0)}
    # Experiment 3: no tool-calling filter in ladder()
    out["exp3_no_tool_filter"] = {
        "with_filter": run(cfg, "G6_provider_outage", seed),
        "without_filter": run(cfg, "G6_provider_outage", seed, cls=NoToolFilterClient),
    }

    # Section 4: why both idempotency keys and checkpoints
    wf_keys = ["completion_rate", "worker_crashes", "duplicate_refunds", "duplicate_emails", "lost_refunds",
               "overpaid_cents", "wasted_llm_per_crash"]
    out["workflow_variants"] = {}
    for name, cls_ in {"yours": WorkflowExecutor, "keys_only": KeysOnlyExecutor,
                       "checkpoints_only": CheckpointsOnlyExecutor}.items():
        random.seed(seed)
        m = run_workflows(cls_, n=500, seed=seed)
        out["workflow_variants"][name] = {k: m.get(k) for k in wf_keys}

    # Part G
    c1 = "C1_faq_outage"
    out["cache"] = {
        "no_cache": run(cache_cfg, c1, seed, "resilient", CACHE_KEYS),
        "cached": run(cache_cfg, c1, seed, "cached", CACHE_KEYS),
        "starter_values": run(_with_cache(cache_cfg, {"similarity_threshold": 0.80, "ttl_s": 600, "max_stale_s": 0}),
                              c1, seed, "cached", CACHE_KEYS),
        "threshold": {str(v): run(_with_cache(cache_cfg, {"similarity_threshold": v}), c1, seed, "cached", CACHE_KEYS)
                      for v in (0.80, 0.86, 0.90, cache_cfg.cache["similarity_threshold"], 0.97)},
        "ttl_s": {str(v): run(_with_cache(cache_cfg, {"ttl_s": v}), c1, seed, "cached", CACHE_KEYS)
                  for v in (30, 60, 300)},
        "max_stale_s": {str(v): run(_with_cache(cache_cfg, {"max_stale_s": v}), c1, seed, "cached", CACHE_KEYS)
                        for v in (0, 60, cache_cfg.cache["max_stale_s"])},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
