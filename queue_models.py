"""Core M/M/1, M/M/c, M/G/c, M/M/c/K, and M/G/c/K queueing formulas."""

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
    **extra,
):
    """Return a consistent result structure for all queue model calculations."""
    result = {
        "rho": rho,
        "L": L,
        "Lq": Lq,
        "W": W,
        "Wq": Wq,
        "stable": stable,
        "error": error,
    }
    result.update(extra)
    return result


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


def mgc(lambda_, mu, c, service_variance):
    """Approximate steady-state metrics for an M/G/c queue.

    The approximation uses Allen-Cunneen scaling over the M/M/c waiting time:
    Wq(M/G/c) ~= ((Ca^2 + Cs^2) / 2) * Wq(M/M/c), with Poisson arrivals
    so Ca^2 = 1. For exponential service, Cs^2 = 1 and the result matches
    M/M/c.
    """
    if (
        not _is_valid_rate(lambda_)
        or not _is_valid_rate(mu)
        or not _is_valid_rate(service_variance)
    ):
        return _result(
            error="Invalid input: lambda, mu, and service_variance must be finite numbers."
        )

    if not isinstance(c, Integral):
        return _result(error="Invalid input: c must be a positive integer.")

    lambda_ = float(lambda_)
    mu = float(mu)
    c = int(c)
    service_variance = float(service_variance)

    if lambda_ < 0 or mu <= 0 or c <= 0 or service_variance < 0:
        return _result(
            error=(
                "Invalid input: lambda must be >= 0, mu > 0, c > 0, "
                "and service_variance must be >= 0."
            )
        )

    base = mmc(lambda_, mu, c)
    rho = base.get("rho")

    if not base.get("stable", False):
        return _result(
            rho=rho,
            stable=False,
            error="Unstable system: lambda must be less than c * mu for M/G/c.",
        )

    try:
        squared_coefficient_of_service_variation = service_variance * (mu ** 2)
        variability_factor = (1.0 + squared_coefficient_of_service_variation) / 2.0
        Wq = base["Wq"] * variability_factor
        Lq = lambda_ * Wq
        W = Wq + (1.0 / mu)
        L = lambda_ * W
        return _result(rho=rho, L=L, Lq=Lq, W=W, Wq=Wq, stable=True)
    except (OverflowError, ZeroDivisionError, ValueError):
        return _result(
            rho=rho,
            stable=False,
            error="M/G/c calculation failed due to numerical instability.",
        )


def _is_valid_capacity(value) -> bool:
    """Check that a capacity input is a positive integer."""
    return isinstance(value, Integral)


def mmck(lambda_, mu, c, K):
    """Compute exact steady-state metrics for an M/M/c/K finite-capacity queue.

    K is total system capacity: customers in service plus customers waiting.
    Arrivals that find K customers in the system are blocked.
    """
    if not _is_valid_rate(lambda_) or not _is_valid_rate(mu):
        return _result(error="Invalid input: lambda and mu must be finite numbers.")

    if not isinstance(c, Integral):
        return _result(error="Invalid input: c must be a positive integer.")

    if not _is_valid_capacity(K):
        return _result(error="Invalid input: K must be a positive integer.")

    lambda_ = float(lambda_)
    mu = float(mu)
    c = int(c)
    K = int(K)

    if lambda_ < 0 or mu <= 0 or c <= 0 or K <= 0 or K < c:
        return _result(
            error=(
                "Invalid input: lambda must be >= 0, mu > 0, c > 0, "
                "and K must be >= c."
            )
        )

    try:
        offered_load = lambda_ / mu
        weights = []
        for n in range(K + 1):
            if n <= c:
                weight = (offered_load ** n) / math.factorial(n)
            else:
                weight = (offered_load ** n) / (
                    math.factorial(c) * (c ** (n - c))
                )
            weights.append(weight)

        p0 = 1.0 / sum(weights)
        probabilities = [p0 * weight for weight in weights]
        blocking_probability = probabilities[K]
        effective_lambda = lambda_ * (1.0 - blocking_probability)

        L = sum(n * probabilities[n] for n in range(K + 1))
        Lq = sum(max(n - c, 0) * probabilities[n] for n in range(K + 1))
        W = 0.0 if effective_lambda == 0 else L / effective_lambda
        Wq = 0.0 if effective_lambda == 0 else Lq / effective_lambda
        rho = sum(min(n, c) * probabilities[n] for n in range(K + 1)) / c

        return _result(
            rho=rho,
            L=L,
            Lq=Lq,
            W=W,
            Wq=Wq,
            stable=True,
            blocking_probability=blocking_probability,
            effective_lambda=effective_lambda,
            K=K,
        )
    except (OverflowError, ZeroDivisionError, ValueError):
        return _result(
            stable=False,
            error="M/M/c/K calculation failed due to numerical instability.",
            K=K,
        )


def mgck(lambda_, mu, c, service_variance, K):
    """Approximate steady-state metrics for an M/G/c/K finite-capacity queue.

    The finite-capacity blocking probability comes from M/M/c/K. Waiting time
    is adjusted by the same variability factor used for M/G/c.
    """
    if not _is_valid_rate(service_variance):
        return _result(error="Invalid input: service_variance must be finite.")

    service_variance = float(service_variance)
    if service_variance < 0:
        return _result(error="Invalid input: service_variance must be >= 0.")

    base = mmck(lambda_, mu, c, K)
    if not base.get("stable", False):
        return base

    try:
        mu = float(mu)
        effective_lambda = base.get("effective_lambda", 0.0)
        squared_coefficient_of_service_variation = service_variance * (mu ** 2)
        variability_factor = (1.0 + squared_coefficient_of_service_variation) / 2.0
        Wq = base["Wq"] * variability_factor
        Lq = effective_lambda * Wq
        W = Wq + (1.0 / mu)
        L = effective_lambda * W

        return _result(
            rho=base["rho"],
            L=L,
            Lq=Lq,
            W=W,
            Wq=Wq,
            stable=True,
            blocking_probability=base.get("blocking_probability"),
            effective_lambda=effective_lambda,
            K=base.get("K"),
            approximation="Allen-Cunneen adjustment over M/M/c/K",
        )
    except (OverflowError, ZeroDivisionError, ValueError):
        return _result(
            rho=base.get("rho"),
            stable=False,
            error="M/G/c/K calculation failed due to numerical instability.",
            K=base.get("K"),
        )
