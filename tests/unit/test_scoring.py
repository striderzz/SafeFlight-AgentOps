"""Scoring math against hand-computed values, including INFO.md's worked example."""

import numpy as np
import pytest
from scipy import stats

from safeflight.scoring.bayes import (
    Event,
    Prior,
    ScoringConfig,
    decay,
    fit_prior_ml,
    fit_prior_moments,
    score,
    weighted_events,
    weighted_exposure,
)

CFG = ScoringConfig()
PRIOR = Prior(alpha=2.0, beta=4.0, method="given")  # industry rate m = 0.5


def test_decay_halves_every_half_life():
    assert decay(0, 5) == 1.0
    assert decay(5, 5) == pytest.approx(0.5)
    assert decay(10, 5) == pytest.approx(0.25)


def test_event_weights_combine_severity_and_recency():
    events = [Event(0, "fatal"), Event(5, "serious"), Event(10, "minor")]
    # 1.0*1 + 0.5*0.5 + 0.2*0.25
    assert weighted_events(events, CFG) == pytest.approx(1.0 + 0.25 + 0.05)


def test_exposure_is_recency_weighted_in_millions():
    assert weighted_exposure({0: 1_000_000, 5: 2_000_000}, CFG) == pytest.approx(1.0 + 1.0)


@pytest.mark.parametrize(
    ("y", "e", "post_mean", "shrink"),
    [(0, 0.2, 2 / 4.2, 0.2 / 4.2), (6, 20, 8 / 24, 20 / 24), (1, 0.02, 3 / 4.02, 0.02 / 4.02)],
)
def test_worked_example_from_info_md(y, e, post_mean, shrink):
    s = score("X", y, e, PRIOR, CFG)
    assert s.post_mean == pytest.approx(post_mean)
    assert s.shrinkage == pytest.approx(shrink)


def test_interval_is_the_gamma_posterior_quantiles():
    s = score("B", 6, 20, PRIOR, CFG)
    lo, hi = stats.gamma.ppf([0.05, 0.95], 8, scale=1 / 24)
    assert (s.ci_low, s.ci_high) == pytest.approx((lo, hi))


def test_bands():
    assert score("A", 0, 0.2, PRIOR, CFG).band == "limited"  # below the exposure threshold
    assert score("Z", 0, 0.0, PRIOR, CFG).band == "limited"  # no exposure at all
    assert score("good", 2, 40, PRIOR, CFG).band == "strong"  # whole interval below m = 0.5
    assert score("bad", 60, 40, PRIOR, CFG).band == "higher"  # whole interval above m
    assert score("mid", 18, 40, PRIOR, CFG).band == "typical"  # interval spans m


def test_prior_fits_recover_a_known_rate():
    rng = np.random.default_rng(7)
    true_alpha, true_beta = 4.0, 8.0  # mean 0.5
    e = rng.uniform(1, 30, 400)
    lam = rng.gamma(true_alpha, 1 / true_beta, 400)
    y = rng.poisson(lam * e).astype(float)
    mom = fit_prior_moments(y, e, CFG)
    ml = fit_prior_ml(y, e, CFG)
    assert mom.mean == pytest.approx(0.5, rel=0.1)
    assert ml.mean == pytest.approx(0.5, rel=0.1)
    assert ml.alpha == pytest.approx(true_alpha, rel=0.5)


def test_prior_needs_enough_carriers():
    with pytest.raises(ValueError):
        fit_prior_moments(np.array([1.0]), np.array([10.0]), CFG)


def test_homogeneous_carriers_hit_the_variance_floor():
    """When carriers differ no more than chance, the moments fit floors the variance and says so."""
    rng = np.random.default_rng(3)
    e = rng.uniform(1, 10, 60)
    y = rng.poisson(1.2 * e).astype(float)  # same true rate for everyone
    prior = fit_prior_moments(y, e, CFG)
    assert prior.method == "moments_floored"
    assert prior.alpha == pytest.approx(1 / CFG.variance_floor_cv**2)
