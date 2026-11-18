"""Bayesian carrier safety score. Plain NumPy and SciPy; no LLM is involved.

Method (INFO.md, Scoring method):
- Event weight   w = severity weight * 0.5 ** (age / half_life)
- Exposure       E = sum over years of departures * 0.5 ** (age / half_life) / 1e6
- Model          y ~ Poisson(lambda * E), lambda ~ Gamma(alpha, beta)
- Posterior      Gamma(alpha + y, beta + E)
- Prior          method of moments over carriers with enough exposure (empirical Bayes),
                 with a maximum-likelihood negative binomial fit as a check
- Bands          Limited data (exposure below a threshold) / Strong record (interval
                 below the industry rate) / Higher rate (interval above) / Typical
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
from scipy import optimize, special, stats


@dataclass(frozen=True)
class ScoringConfig:
    severity_weights: dict[str, float] = field(
        default_factory=lambda: {"fatal": 1.0, "serious": 0.5, "minor": 0.2, "none": 0.2}
    )
    half_life_years: float = 5.0
    min_exposure_for_prior: float = 0.5  # million (weighted) departures
    min_exposure_for_band: float = 1.0  # below this a carrier is "limited data"
    variance_floor_cv: float = 0.10  # floor on between-carrier spread, as a coefficient of variation
    interval: float = 0.90


@dataclass(frozen=True)
class Event:
    year_fraction_age: float  # years between the event and the end of the window
    severity: str  # fatal | serious | minor | none


@dataclass(frozen=True)
class Prior:
    alpha: float
    beta: float
    method: str

    @property
    def mean(self) -> float:
        return self.alpha / self.beta


@dataclass(frozen=True)
class CarrierScore:
    carrier: str
    weighted_events: float
    exposure_millions: float
    raw_rate: float | None
    post_mean: float
    ci_low: float
    ci_high: float
    shrinkage: float
    band: str


def decay(age_years: float, half_life: float) -> float:
    return 0.5 ** (age_years / half_life)


def weighted_events(events: Iterable[Event], cfg: ScoringConfig) -> float:
    return float(
        sum(
            cfg.severity_weights[e.severity] * decay(e.year_fraction_age, cfg.half_life_years) for e in events
        )
    )


def weighted_exposure(departures_by_age: dict[float, float], cfg: ScoringConfig) -> float:
    """departures_by_age maps the age of a year (end of window minus year) to departures."""
    return float(sum(d * decay(age, cfg.half_life_years) for age, d in departures_by_age.items()) / 1_000_000)


def fit_prior_moments(y: np.ndarray, e: np.ndarray, cfg: ScoringConfig) -> Prior:
    """Method of moments over carriers with exposure >= min_exposure_for_prior."""
    keep = e >= cfg.min_exposure_for_prior
    y, e = y[keep], e[keep]
    if len(y) < 3:
        raise ValueError("need at least 3 carriers with enough exposure to fit the prior")
    m = y.sum() / e.sum()
    raw = y / e
    v = raw.var(ddof=1) - m * np.mean(1.0 / e)
    floor = (cfg.variance_floor_cv * m) ** 2
    floored = v < floor
    # v <= floor means the spread between carriers is no bigger than chance alone would
    # produce; the floor keeps the prior proper and is reported, not hidden.
    v = max(v, floor)
    return Prior(alpha=m**2 / v, beta=m / v, method="moments_floored" if floored else "moments")


def fit_prior_ml(y: np.ndarray, e: np.ndarray, cfg: ScoringConfig) -> Prior:
    """Maximum likelihood of the Poisson-Gamma (negative binomial) marginal; a check on the moments fit.

    The likelihood uses the continuous extension (gamma functions), since weighted counts
    are not integers.
    """
    keep = e >= cfg.min_exposure_for_prior
    y, e = y[keep], e[keep]

    def nll(params: np.ndarray) -> float:
        a, b = np.exp(params)
        ll = (
            special.gammaln(a + y)
            - special.gammaln(a)
            - special.gammaln(y + 1)
            + a * np.log(b / (b + e))
            + y * np.log(e / (b + e))
        )
        return -float(ll.sum())

    start = fit_prior_moments(y, e, cfg)
    res = optimize.minimize(nll, x0=np.log([start.alpha, start.beta]), method="Nelder-Mead")
    a, b = np.exp(res.x)
    return Prior(alpha=float(a), beta=float(b), method="ml")


def score(carrier: str, y: float, e: float, prior: Prior, cfg: ScoringConfig) -> CarrierScore:
    a, b = prior.alpha + y, prior.beta + e
    tail = (1 - cfg.interval) / 2
    lo, hi = stats.gamma.ppf([tail, 1 - tail], a, scale=1 / b)
    shrink = e / (prior.beta + e)
    m = prior.mean
    if e < cfg.min_exposure_for_band:
        band = "limited"
    elif hi < m:
        band = "strong"
    elif lo > m:
        band = "higher"
    else:
        band = "typical"
    return CarrierScore(
        carrier=carrier,
        weighted_events=y,
        exposure_millions=e,
        raw_rate=(y / e) if e > 0 else None,
        post_mean=a / b,
        ci_low=float(lo),
        ci_high=float(hi),
        shrinkage=shrink,
        band=band,
    )
