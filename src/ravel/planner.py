"""Budget-aware deterministic policy and opt-in learned action selector."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

FEATURES = ["identifier", "query_length", "lexical_coverage", "cache_coverage", "latency", "token_budget"]
ACTIONS = ["lexical", "hybrid", "semantic"]


def features(query, coverage, cache_coverage, latency_ms, token_budget):
    identifier = bool(re.search(r"[_./]|[a-z][A-Z]", query)) or (len(query.split()) == 1)
    return [float(identifier), min(len(query.split()) / 20, 1), coverage, cache_coverage,
            min(latency_ms / 1000, 1), min(token_budget / 4096, 1)]


def choose(query, *, semantic, coverage, cache_coverage, latency_ms, token_budget,
           chunks, memory_kib=2048, mode="auto", policy=None, embed_ms=12):
    if mode not in {"auto", *ACTIONS}:
        raise ValueError("mode must be auto, lexical, hybrid, or semantic")
    for name, value in (("latency_ms", latency_ms), ("memory_kib", memory_kib), ("token_budget", token_budget)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 1:
            raise ValueError(f"{name} must be finite and positive")
    x = features(query, coverage, cache_coverage, latency_ms, token_budget)
    reason = "explicit strategy"
    strategy = mode
    if mode == "auto":
        if not semantic:
            strategy, reason = "lexical", "local embedding model is not enabled"
        elif x[0] and coverage >= 0.6:
            strategy, reason = "lexical", "exact identifier with lexical evidence"
        elif latency_ms < max(25, embed_ms * 2):
            strategy, reason = "lexical", "latency target leaves no embedding allowance"
        elif coverage < 0.3:
            strategy, reason = "semantic", "low lexical overlap; spend compute on semantic evidence"
        else:
            strategy, reason = "hybrid", "lexical candidates benefit from local semantic reranking"
        if policy is not None and semantic:
            model = json.loads(Path(policy).read_text())
            if model.get("features") != FEATURES or model.get("actions") != ACTIONS:
                raise ValueError("incompatible learned policy")
            weights = model.get("weights")
            if not isinstance(weights, list) or len(weights) != len(ACTIONS) or any(
                not isinstance(row, list) or len(row) != len(FEATURES) + 1 or
                any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in row) for row in weights
            ):
                raise ValueError("invalid learned policy weights")
            scores = [sum(a*b for a, b in zip(w, [1.0] + x)) for w in weights]
            strategy = ACTIONS[max(range(3), key=lambda i: scores[i])]
            reason = "opt-in learned policy; budget safeguards still apply"
    if strategy != "lexical" and not semantic:
        raise ValueError("Enable a local model with ravel index --semantic --download-model first")
    # Candidate working set only, not a total-process memory guarantee.
    depth = max(1, min(256, chunks, memory_kib // 8, max(8, token_budget // 64)))
    if strategy != "lexical":
        miss_rate = max(0.05, 1 - cache_coverage)
        depth = min(depth, max(1, int(latency_ms / max(1, embed_ms * miss_rate))))
    if mode == "auto" and strategy == "semantic" and coverage > 0 and cache_coverage < 0.5 and chunks > depth:
        strategy = "hybrid"
        reason = "cold semantic coverage would be partial; preserve lexical evidence"
    return {"strategy": strategy, "reason": reason, "depth": depth, "features": dict(zip(FEATURES, x)),
            "latency_target_ms": latency_ms, "working_memory_kib": memory_kib,
            "token_budget": token_budget, "policy": "learned" if policy else "heuristic"}


def train(rows, *, epochs=700):
    """Fit a tiny softmax linear selector to independently measured action labels.

    rows: [{features: six bounded floats, action: lexical|hybrid|semantic}].
    No online training and no source text or queries in saved policy.
    """
    if not rows:
        raise ValueError("training data is empty")
    weights = [[0.0] * (len(FEATURES) + 1) for _ in ACTIONS]
    for _ in range(epochs):
        grad = [[0.0] * 7 for _ in ACTIONS]
        for row in rows:
            x = [1.0] + row["features"]
            if len(x) != 7 or row["action"] not in ACTIONS:
                raise ValueError("invalid training row")
            scores = [sum(a*b for a, b in zip(w, x)) for w in weights]
            prob = [math.exp(v - max(scores)) for v in scores]
            total = sum(prob)
            for k in range(3):
                err = prob[k] / total - (ACTIONS[k] == row["action"])
                for j in range(7):
                    grad[k][j] += err * x[j]
        for k in range(3):
            for j in range(7):
                weights[k][j] -= 0.2 * (grad[k][j] / len(rows) + 0.002 * weights[k][j])
    return {"version": 1, "features": FEATURES, "actions": ACTIONS, "weights": weights,
            "training_rows": len(rows)}
