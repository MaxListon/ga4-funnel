import math

import pytest

from ga4funnel.stats import newcombe_diff, wilson


def test_wilson_zero_successes():
    lo, hi = wilson(0, 10)
    assert lo == 0
    assert hi == pytest.approx(0.2775, abs=1e-4)


def test_wilson_half():
    lo, hi = wilson(5, 10)
    assert (lo, hi) == (pytest.approx(0.2366, abs=1e-4), pytest.approx(0.7634, abs=1e-4))


def test_wilson_empty_is_nan():
    assert all(math.isnan(x) for x in wilson(0, 0))


def test_newcombe_matches_published_example():
    # Newcombe (1998), Stat Med 17:873-890, method 10: 56/70 vs 48/80 -> 0.0524 to 0.3339
    d, lo, hi = newcombe_diff(56, 70, 48, 80)
    assert d == pytest.approx(0.2)
    assert lo == pytest.approx(0.0524, abs=1e-4)
    assert hi == pytest.approx(0.3339, abs=1e-4)
