"""Core M/M/1 and M/M/c queueing model formulas."""

from __future__ import annotations

import math
from numbers import Integral, Real


def _result(
    rho=None,
    L=None,
    Lq=None,
    W=None,
    Wq=None,
    stable=False,
    error=None,
):
    """Return a consistent result structure for all queue model calculations."""
    return {
        "rho": rho,
        "L": L,
        "Lq": Lq,
        "W": W,
        "Wq": Wq,
        "stable": stable,
        "error": error,
    }


def _is_valid_rate(value) -> bool:
    """Check that a rate input is numeric and finite."""
    return isinstance(value, Real) and math.isfinite(float(value))


def mm1(lambda_, mu):
    """Compute steady-state metrics for an M/M/1 queue."""
    if not _is_valid_rate(lambda_) or not _is_valid_rate(mu):
        return _result(error="Invalid input: lambda and mu must be finite numbers.")

    lambda_ = float(lambda_)
    mu = float(mu)

    if lambda_ < 0 or mu <= 0:
        return _result(error="Invalid input: lambda must be >= 0 and mu must be > 0.")

    rho = lambda_ / mu

    if lambda_ >= mu:
        return _result(
            rho=rho,
            stable=False,
            error="Unstable system: lambda must be less than mu for M/M/1.",
        )

    try:
        gap = mu - lambda_
        L = lambda_ / gap
        Lq = (lambda_ ** 2) / (mu * gap)
        W = 1.0 / gap
        Wq = lambda_ / (mu * gap)
        return _result(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq, stable=True)
    except ZeroDivisionError:
        return _result(
            rho=rho,
            stable=False,
            error="Calculation failed because the service margin reached zero.",
        )


def mmc(lambda_, mu, c):
    """Compute steady-state metrics for an M/M/c queue."""
    if not _is_valid_rate(lambda_) or not _is_valid_rate(mu):
        return _result(error="Invalid input: lambda and mu must be finite numbers.")

    if not isinstance(c, Integral):
        return _result(error="Invalid input: c must be a positive integer.")

    lambda_ = float(lambda_)
    mu = float(mu)
    c = int(c)

    if lambda_ < 0 or mu <= 0 or c <= 0:
        return _result(
            error="Invalid input: lambda must be >= 0, mu > 0, and c > 0."
        )

    rho = lambda_ / (c * mu)

    if lambda_ >= c * mu:
        return _result(
            rho=rho,
            stable=False,
            error="Unstable system: lambda must be less than c * mu for M/M/c.",
        )

    try:
        offered_load = lambda_ / mu
        tail_term = (offered_load ** c) / (math.factorial(c) * (1.0 - rho))
        p0_denominator = sum(
            (offered_load ** n) / math.factorial(n) for n in range(c)
        ) + tail_term
        p0 = 1.0 / p0_denominator

        Lq = (
            p0
            * (offered_load ** c)
            * rho
            / (math.factorial(c) * ((1.0 - rho) ** 2))
        )
        Wq = 0.0 if lambda_ == 0 else Lq / lambda_
        W = Wq + (1.0 / mu)
        L = lambda_ * W

        return _result(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq, stable=True)
    except (OverflowError, ZeroDivisionError, ValueError):
        return _result(
            rho=rho,
            stable=False,
            error="Calculation failed due to numerical instability.",
        )
