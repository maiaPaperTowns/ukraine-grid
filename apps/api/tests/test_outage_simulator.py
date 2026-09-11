"""
Unit coverage for the outage simulator's self-balancing bias logic - the part
of Phase 3 that doesn't need a DB. Full tick()-against-Postgres integration
(the "does routing actually see the new blocked state on the next request"
gate from the plan) is exercised once Docker/Postgres is available; tick()
issues real SQLAlchemy queries against RoadEdge/Facility (PostGIS geometry
columns), which SQLite can't stand in for without the spatialite extension.
"""

from __future__ import annotations

import random

from app.services.outage_simulator import decide_new_state


def test_biases_toward_true_when_below_target():
    rng = random.Random(42)
    results = [decide_new_state(current_ratio=0.0, target_ratio=0.2, rng=rng) for _ in range(2000)]
    true_fraction = sum(results) / len(results)
    assert 0.65 < true_fraction < 0.85  # should cluster around the 0.75 bias


def test_biases_toward_false_when_above_target():
    rng = random.Random(42)
    results = [decide_new_state(current_ratio=0.9, target_ratio=0.2, rng=rng) for _ in range(2000)]
    true_fraction = sum(results) / len(results)
    assert 0.15 < true_fraction < 0.35  # should cluster around the 0.25 bias


def test_self_balances_around_target_ratio_over_many_rounds():
    """Simulate many toggle rounds on a fixed-size pool and confirm the ratio
    of "on" items converges near the target instead of drifting to 0 or 1."""
    rng = random.Random(7)
    pool_size = 200
    target_ratio = 0.15
    state = [False] * pool_size

    for _ in range(3000):
        current_ratio = sum(state) / pool_size
        idx = rng.randrange(pool_size)
        state[idx] = decide_new_state(current_ratio, target_ratio, rng)

    final_ratio = sum(state) / pool_size
    assert abs(final_ratio - target_ratio) < 0.12
