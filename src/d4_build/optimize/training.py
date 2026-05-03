"""Train evaluation weights against Maxroll's published builds.

Methodology:
1. Load Maxroll's recommended plans from N builds (positives — should score high).
2. Generate degenerate baselines (negatives — should score low):
   - Empty plan
   - Random shuffle of clicks
   - Greedy "rank-up only" plan (the failure mode we surfaced earlier)
3. Score each plan with the current weights.
4. Compute the loss: how often is at least one negative scoring above
   Maxroll's positive? Lower is better.
5. Coordinate descent over the weight knobs to minimize loss.

The "training set" is small (5 Warlock leveling builds) so we don't risk
overfitting to a single build pattern. The weights produced should generalize
to the per-archetype pattern Maxroll uses.
"""

from __future__ import annotations

import random
from copy import deepcopy
from itertools import product

from pydantic import BaseModel, ConfigDict

from ..model import Build, SkillPointClick
from .evaluation import EvaluationWeights, _classify_click, evaluate


class TrainingExample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    is_positive: bool
    plan: list[SkillPointClick] = []
    notes: str = ""


class TrainingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weights: EvaluationWeights
    positive_scores: dict[str, float] = {}
    negative_scores: dict[str, float] = {}
    margin: float = 0.0  # min(positive) - max(negative); higher is better
    rank_correctness_pct: float = 0.0  # % of (positive, negative) pairs where positive scores higher
    notes: str = ""


def _generate_negatives(positive_plans: list[list[SkillPointClick]], seed: int = 42) -> list[TrainingExample]:
    """Build the negative training set.

    The evaluator is order-blind (scores final state), so we don't include
    "shuffled" plans — they'd be tied with positives. Instead we generate
    plans that have *different* final states designed to fail.
    """
    random.seed(seed)
    negatives: list[TrainingExample] = []

    # 1. Empty plan
    negatives.append(TrainingExample(
        name="empty_plan",
        is_positive=False,
        plan=[],
        notes="Zero points spent.",
    ))

    if not positive_plans:
        return negatives

    first = positive_plans[0]

    # 2. Spam-rank a single Core node to rank 30 — the degenerate greedy result.
    target = next(
        (c for c in first if c.new_rank > 1 and _classify_click(c)[0] == "Core"),
        None,
    )
    if target:
        degenerate = [
            SkillPointClick(
                level=r + 1, point_number=r,
                node_id=target.node_id, node_label=target.node_label,
                new_rank=r, step_name="degenerate", cumulative_total=r,
            )
            for r in range(1, 31)
        ]
        # Pad with rank-1 nodes of the same cluster only (no Basic, no Defensive).
        seen = {target.node_id}
        i = len(degenerate) + 1
        for c in first:
            if i > 40:
                break
            if c.node_id in seen or _classify_click(c)[0] != "Core":
                continue
            seen.add(c.node_id)
            degenerate.append(SkillPointClick(
                level=i + 1, point_number=i,
                node_id=c.node_id, node_label=c.node_label,
                new_rank=1, step_name="degenerate", cumulative_total=i,
            ))
            i += 1
        negatives.append(TrainingExample(
            name="rank_only_no_basic_no_defensive",
            is_positive=False,
            plan=degenerate,
            notes="No Basic or Defensive — should be heavily penalized.",
        ))

    # 3. All-Defensive plan — survival but no damage skills.
    defensive_clicks = [
        c for c in first if _classify_click(c)[0] == "Defensive"
    ][:40]
    if len(defensive_clicks) >= 8:
        # Pad with rank-1 of any Defensive node
        plan = list(defensive_clicks)
        for i, c in enumerate(plan, start=1):
            c = c.model_copy()
            c.point_number = i
            c.level = i + 1
            plan[i - 1] = c
        negatives.append(TrainingExample(
            name="defensive_only_no_damage",
            is_positive=False,
            plan=plan,
            notes="Only Defensive nodes — no Basic / Core — heavy viability penalty.",
        ))

    # 4. Random-subset plan — 40 random clicks from the union of all positives'
    # nodes, excluding Basic and Core (so it'll fail viability).
    all_clicks = []
    for pos in positive_plans:
        for c in pos:
            cl = _classify_click(c)[0]
            if cl not in ("Basic", "Core"):
                all_clicks.append(c)
    random.shuffle(all_clicks)
    sample = all_clicks[:40]
    for i, c in enumerate(sample, start=1):
        cc = c.model_copy()
        cc.point_number = i
        cc.level = i + 1
        cc.new_rank = 1
        sample[i - 1] = cc
    negatives.append(TrainingExample(
        name="random_no_basic_no_core",
        is_positive=False,
        plan=sample,
        notes="40 random non-Basic non-Core clicks — should fail viability.",
    ))

    return negatives


def evaluate_weights(
    weights: EvaluationWeights,
    positives: list[tuple[str, list[SkillPointClick], Build]],
    negatives: list[tuple[str, list[SkillPointClick], Build]],
) -> TrainingResult:
    """Run all examples through the evaluator with the given weights."""
    pos_scores = {n: evaluate(p, b, weights) for n, p, b in positives}
    neg_scores = {n: evaluate(p, b, weights) for n, p, b in negatives}

    if pos_scores and neg_scores:
        margin = min(pos_scores.values()) - max(neg_scores.values())
    else:
        margin = 0.0

    # Rank correctness: every positive should score higher than every negative.
    correct = 0
    total = 0
    for ps in pos_scores.values():
        for ns in neg_scores.values():
            total += 1
            if ps > ns:
                correct += 1
    rank_pct = (100.0 * correct / total) if total else 0.0

    return TrainingResult(
        weights=weights,
        positive_scores={k: round(v, 2) for k, v in pos_scores.items()},
        negative_scores={k: round(v, 2) for k, v in neg_scores.items()},
        margin=round(margin, 2),
        rank_correctness_pct=round(rank_pct, 1),
    )


def train(
    positives: list[tuple[str, list[SkillPointClick], Build]],
    *,
    grid_steps: int = 3,
) -> TrainingResult:
    """Grid-search over a small space of weight knobs.

    Optimizes for: rank correctness first, margin as tiebreaker.

    For grid_steps=3 we explore 3 values per knob over a few key knobs;
    that's small enough to finish in seconds.
    """
    base_negatives_examples = _generate_negatives([p for _, p, _ in positives])
    # Pair negatives with the first positive's build (only thing the
    # evaluator needs from build is gear, which is shared in our case).
    if not positives:
        return TrainingResult(
            weights=EvaluationWeights(),
            notes="No positives provided.",
        )
    ref_build = positives[0][2]
    negatives = [(n.name, n.plan, ref_build) for n in base_negatives_examples]

    best = evaluate_weights(EvaluationWeights(), positives, negatives)

    # Coordinate-grid search across a few primary knobs.
    knobs = {
        "rank_value_core":      [0.5, 1.0, 1.5, 2.0],
        "spec_value":           [0.2, 0.4, 0.6],
        "no_core_penalty":      [50.0, 100.0, 200.0],
        "excess_rank_penalty":  [2.0, 5.0, 10.0],
    }
    base = EvaluationWeights().model_dump()
    n_evals = 0
    for vals in product(*knobs.values()):
        cfg = dict(base)
        for k, v in zip(knobs.keys(), vals):
            cfg[k] = v
        w = EvaluationWeights(**cfg)
        r = evaluate_weights(w, positives, negatives)
        n_evals += 1
        # Prefer higher rank correctness; tiebreak by margin.
        if (r.rank_correctness_pct, r.margin) > (best.rank_correctness_pct, best.margin):
            best = r

    best.notes = f"Grid-searched {n_evals} weight configs."
    return best
