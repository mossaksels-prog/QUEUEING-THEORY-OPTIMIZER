"""Waste Reduction Optimization — Minimize waiting time (Wq) by prioritizing understaffing over costs.

This module implements a separate optimization strategy using a LOW waiting cost penalty (₱50)
to make staff reduction economically viable. This complements the standard cost-optimized
recommendations.

Key Difference from optimize_segment():
  - Standard optimization: Minimize total cost (labor + waiting with ₱100 penalty)
  - Waste reduction: Minimize total cost (labor + waiting with ₱50 penalty)
  - Result: Aggressive staff reduction possible, improving Wq significantly
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from numbers import Integral, Real

from queue_models import mm1, mmc
from optimization import (
    DEFAULT_SERVER_COST,
    DEFAULT_MAX_SERVERS,
    UNSTABLE_FIXED_COST,
    _is_number,
    _segment_server_cost,
    _queue_metrics,
    _safe_diff,
)


# Waste reduction uses lower waiting cost penalty
WASTE_REDUCTION_WAITING_COST = 50.0  # ₱ per customer per hour (50% of the default ₱100)

# Abandonment cost: 10% of ₱600 daily cost per customer = ₱60
ABANDONMENT_COST_BASE = 600.0  # ₱ daily cost per customer
ABANDONMENT_COST_PERCENTAGE = 0.10  # 10%
ABANDONMENT_COST = ABANDONMENT_COST_BASE * ABANDONMENT_COST_PERCENTAGE  # = ₱60


def _compute_waiting_cost_waste(lambda_, wq_value):
    """Compute waiting cost with LOW penalty for waste reduction optimization.
    
    Uses WASTE_REDUCTION_WAITING_COST (₱50) instead of ₱100 to make staff reduction
    economically attractive while maintaining stability.
    """
    if lambda_ is None:
        return None
    
    if wq_value is not None:
        return lambda_ * wq_value * WASTE_REDUCTION_WAITING_COST
    else:
        return UNSTABLE_FIXED_COST


def _compute_total_cost_waste(lambda_, wq_value, c, cost_per_server, abandonment_rate=0.10, abandonment_cost=60.0):
    """Compute TOTAL cost for waste reduction including:
    - Server cost
    - Waiting cost (low penalty ₱50)
    - Abandonment cost (₱60 = 10% × ₱600)
    
    Args:
        lambda_: Arrival rate (customers/hour)
        wq_value: Mean waiting time in queue (hours)
        c: Number of servers
        cost_per_server: Labor cost per server per hour
        abandonment_rate: % of customers that abandon (default 10%)
        abandonment_cost: Cost per abandoned customer (default ₱60)
    
    Returns:
        dict with breakdown and total cost
    """
    if lambda_ is None or c is None or cost_per_server is None:
        return {
            "server_cost": None,
            "waiting_cost": None,
            "abandonment_cost": None,
            "total_cost": None,
        }
    
    # Server cost
    server_cost = c * cost_per_server
    
    # Waiting cost (with low penalty)
    if wq_value is not None:
        waiting_cost = lambda_ * wq_value * WASTE_REDUCTION_WAITING_COST
    else:
        waiting_cost = UNSTABLE_FIXED_COST
    
    # Abandonment cost: arrivals × 10% abandonment rate × ₱60 per abandonment
    abandonment_realized_cost = lambda_ * abandonment_rate * abandonment_cost
    
    # Total
    total_cost = server_cost + waiting_cost + abandonment_realized_cost
    
    return {
        "server_cost": server_cost,
        "waiting_cost": waiting_cost,
        "abandonment_cost": abandonment_realized_cost,
        "total_cost": total_cost,
    }


def optimize_segment_waste(
    segment: Mapping,
    default_server_cost: float = DEFAULT_SERVER_COST,
    max_servers: int = DEFAULT_MAX_SERVERS,
) -> dict:
    """Waste reduction optimization for one time segment.
    
    STRATEGY: Minimize total cost using low waiting cost penalty (₱50).
    This makes staff reduction economically viable when standard optimization won't.
    
    Returns comparison between current and waste-optimized staffing.
    """
    empty_result = {
        "time": "Unknown",
        "lambda": None,
        "mu": None,
        "cost_per_server": None,
        "c_current": None,
        "rho_current": None,
        "Wq_current": None,
        "Lq_current": None,
        "cost_current": None,
        "waiting_cost_current": None,
        "c_waste_opt": None,
        "rho_waste_opt": None,
        "Wq_waste_opt": None,
        "Lq_waste_opt": None,
        "cost_waste_opt": None,
        "waiting_cost_waste_opt": None,
        "delta_c": None,
        "delta_rho": None,
        "delta_Wq": None,
        "delta_Lq": None,
        "delta_cost": None,
        "current_stable": False,
        "waste_opt_stable": False,
        "recommendation": "Unable to optimize invalid segment input.",
        "warning": "Invalid segment format: each segment must be a dictionary.",
    }

    if not isinstance(segment, Mapping):
        return empty_result

    time_label = str(segment.get("time", "Unknown"))
    lambda_ = segment.get("lambda")
    mu = segment.get("mu")
    current_c = segment.get("c", 1)
    variance = segment.get("variance")
    capacity = segment.get("K")
    cost_per_server = _segment_server_cost(segment, default_server_cost)

    if (
        not isinstance(current_c, Integral)
        or int(current_c) <= 0
        or cost_per_server is None
        or not isinstance(max_servers, Integral)
        or int(max_servers) <= 0
    ):
        invalid_result = empty_result.copy()
        invalid_result.update({
            "time": time_label,
            "lambda": lambda_,
            "mu": mu,
            "cost_per_server": cost_per_server,
            "c_current": current_c,
            "recommendation": f"Unable to optimize {time_label}.",
            "warning": "Invalid optimization settings or segment cost.",
        })
        return invalid_result

    current_c = int(current_c)
    max_servers = int(max_servers)

    # Get current scenario metrics (including abandonment cost)
    current_metrics = _queue_metrics(lambda_, mu, current_c, variance, capacity)
    current_costs = _compute_total_cost_waste(
        lambda_=lambda_,
        wq_value=current_metrics.get("Wq"),
        c=current_c,
        cost_per_server=cost_per_server,
        abandonment_rate=0.10,
        abandonment_cost=60.0  # 10% × ₱600
    )
    current_total_cost = current_costs["total_cost"]
    current_rho = current_metrics.get("rho")

    # WASTE REDUCTION: Evaluate ALL server options to find minimum total cost with LOW waiting penalty
    best_waste_cost_scenario = None
    best_waste_total = float('inf')

    for candidate_c in range(1, max_servers + 1):
        candidate_metrics = _queue_metrics(lambda_, mu, candidate_c, variance, capacity)
        if not candidate_metrics.get("stable"):
            continue

        candidate_costs = _compute_total_cost_waste(
            lambda_=lambda_,
            wq_value=candidate_metrics.get("Wq"),
            c=candidate_c,
            cost_per_server=cost_per_server,
            abandonment_rate=0.10,
            abandonment_cost=60.0
        )
        total_cost = candidate_costs["total_cost"]

        if total_cost < best_waste_total:
            best_waste_total = total_cost
            best_waste_cost_scenario = {
                "c": candidate_c,
                "rho": candidate_metrics.get("rho"),
                "Wq": candidate_metrics.get("Wq"),
                "Lq": candidate_metrics.get("Lq"),
                "stable": True,
                "total_cost": total_cost,
                "server_cost": candidate_costs["server_cost"],
                "waiting_cost": candidate_costs["waiting_cost"],
                "abandonment_cost": candidate_costs["abandonment_cost"],
            }

    if best_waste_cost_scenario is None:
        # No stable solution found
        wq_cur = current_metrics.get("Wq")
        current_costs_fallback = _compute_total_cost_waste(
            lambda_=lambda_,
            wq_value=wq_cur,
            c=current_c,
            cost_per_server=cost_per_server,
            abandonment_rate=0.10,
            abandonment_cost=60.0
        )
        return {
            "time": time_label,
            "lambda": lambda_,
            "mu": mu,
            "cost_per_server": cost_per_server,
            "c_current": current_c,
            "rho_current": current_rho,
            "Wq_current": wq_cur,
            "Lq_current": current_metrics.get("Lq"),
            "cost_current": current_costs_fallback["total_cost"],
            "waiting_cost_current": current_costs_fallback["waiting_cost"],
            "c_waste_opt": None,
            "rho_waste_opt": None,
            "Wq_waste_opt": None,
            "Lq_waste_opt": None,
            "cost_waste_opt": None,
            "waiting_cost_waste_opt": None,
            "delta_c": None,
            "delta_rho": None,
            "delta_Wq": None,
            "delta_Lq": None,
            "delta_cost": None,
            "current_stable": bool(current_metrics.get("stable")),
            "waste_opt_stable": False,
            "recommendation": f"Unable to find a stable staffing plan at {time_label}.",
            "warning": "No server level maintained system stability within search range.",
        }

    # Extract waste-optimized values
    waste_opt_c = best_waste_cost_scenario["c"]
    waste_opt_rho = best_waste_cost_scenario["rho"]
    waste_opt_wq = best_waste_cost_scenario["Wq"]
    waste_opt_lq = best_waste_cost_scenario["Lq"]
    waste_opt_cost = best_waste_cost_scenario["total_cost"]  # Full cost including abandonment
    waste_opt_waiting_cost = best_waste_cost_scenario["waiting_cost"]

    # Build recommendation message
    if waste_opt_c > current_c:
        change = waste_opt_c - current_c
        label = "server" if change == 1 else "servers"
        recommendation = f"Add {change} {label} at {time_label}."
    elif waste_opt_c < current_c:
        change = current_c - waste_opt_c
        label = "server" if change == 1 else "servers"
        recommendation = f"Remove {change} {label} at {time_label} (waste reduction with ₱50 cost)."
    else:
        recommendation = f"Maintain current staffing at {time_label}."

    return {
        "time": time_label,
        "lambda": lambda_,
        "mu": mu,
        "cost_per_server": cost_per_server,
        "c_current": current_c,
        "rho_current": current_rho,
        "Wq_current": current_metrics.get("Wq"),
        "Lq_current": current_metrics.get("Lq"),
        "cost_current": current_costs["total_cost"],
        "waiting_cost_current": current_costs["waiting_cost"],
        "c_waste_opt": waste_opt_c,
        "rho_waste_opt": waste_opt_rho,
        "Wq_waste_opt": waste_opt_wq,
        "Lq_waste_opt": waste_opt_lq,
        "cost_waste_opt": waste_opt_cost,
        "waiting_cost_waste_opt": waste_opt_waiting_cost,
        "delta_c": waste_opt_c - current_c,
        "delta_rho": _safe_diff(waste_opt_rho, current_rho),
        "delta_Wq": _safe_diff(waste_opt_wq, current_metrics.get("Wq")),
        "delta_Lq": _safe_diff(waste_opt_lq, current_metrics.get("Lq")),
        "delta_cost": best_waste_cost_scenario["total_cost"] - current_total_cost,
        "current_stable": bool(current_metrics.get("stable")),
        "waste_opt_stable": True,
        "recommendation": recommendation,
        "warning": current_metrics.get("error"),
    }


def optimize_segments_waste(
    time_segments: Iterable[Mapping],
    default_server_cost: float = DEFAULT_SERVER_COST,
    max_servers: int = DEFAULT_MAX_SERVERS,
) -> list[dict]:
    """Optimize a sequence of time segments for WASTE REDUCTION using ₱50 waiting cost."""
    if time_segments is None:
        return []

    return [
        optimize_segment_waste(
            segment=segment,
            default_server_cost=default_server_cost,
            max_servers=max_servers,
        )
        for segment in time_segments
    ]


def summarize_waste_optimization(waste_rows: list[dict]) -> dict:
    """Compute top-level comparison KPIs for waste reduction optimization."""
    if not waste_rows:
        return {
            "total_current_cost": 0.0,
            "total_waste_opt_cost": 0.0,
            "total_savings": 0.0,
            "avg_utilization_current": None,
            "avg_utilization_waste_opt": None,
            "avg_utilization_change": None,
            "total_server_change": 0,
            "avg_waiting_current": None,
            "avg_waiting_waste_opt": None,
            "waiting_time_improvement_pct": None,
        }

    current_cost = sum(
        row["cost_current"] for row in waste_rows if row["cost_current"] is not None
    )
    waste_opt_cost = sum(
        row["cost_waste_opt"] for row in waste_rows if row["cost_waste_opt"] is not None
    )

    utilization_pairs = [
        (row["rho_current"], row["rho_waste_opt"])
        for row in waste_rows
        if row["rho_current"] is not None and row["rho_waste_opt"] is not None
    ]

    waiting_pairs = [
        (row["Wq_current"], row["Wq_waste_opt"])
        for row in waste_rows
        if row["Wq_current"] is not None and row["Wq_waste_opt"] is not None
    ]

    avg_util_current = (
        sum(pair[0] for pair in utilization_pairs) / len(utilization_pairs)
        if utilization_pairs
        else None
    )
    avg_util_waste_opt = (
        sum(pair[1] for pair in utilization_pairs) / len(utilization_pairs)
        if utilization_pairs
        else None
    )

    avg_wait_current = (
        sum(pair[0] for pair in waiting_pairs) / len(waiting_pairs)
        if waiting_pairs
        else None
    )
    avg_wait_waste_opt = (
        sum(pair[1] for pair in waiting_pairs) / len(waiting_pairs)
        if waiting_pairs
        else None
    )

    waiting_improvement_pct = None
    if avg_wait_current not in (None, 0) and avg_wait_waste_opt is not None:
        # Negative = improvement (less waiting)
        waiting_improvement_pct = (
            (avg_wait_current - avg_wait_waste_opt) / avg_wait_current
        ) * 100.0

    return {
        "total_current_cost": current_cost,
        "total_waste_opt_cost": waste_opt_cost,
        "total_savings": current_cost - waste_opt_cost,
        "avg_utilization_current": avg_util_current,
        "avg_utilization_waste_opt": avg_util_waste_opt,
        "avg_utilization_change": (
            avg_util_waste_opt - avg_util_current
            if avg_util_current is not None and avg_util_waste_opt is not None
            else None
        ),
        "total_server_change": sum(
            row["delta_c"] for row in waste_rows if row["delta_c"] is not None
        ),
        "avg_waiting_current": avg_wait_current,
        "avg_waiting_waste_opt": avg_wait_waste_opt,
        "waiting_time_improvement_pct": waiting_improvement_pct,
    }
