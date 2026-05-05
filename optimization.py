"""Optimization and comparison utilities for the queueing dashboard."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from numbers import Integral, Real

from queue_models import mm1, mmc


DEFAULT_TARGET_UTILIZATION = 0.70
DEFAULT_SERVER_COST = 1.0
DEFAULT_MAX_SERVERS = 24
DEFAULT_CUSTOMER_WAITING_COST = 100.0  # ₱ per customer per hour (NovaMart Grocery)
UNSTABLE_PENALTY_MULTIPLIER = 10.0     # Penalty for unstable systems (ρ ≥ 1) for comparison visibility
UNSTABLE_FIXED_COST = 5000.0            # Fixed cost when system is unstable (ρ ≥ 1)

# Labor rate constants
REGULAR_RATE = 87.0   # cost per regular hour
OT_RATE = 109.0       # cost per overtime hour


def compute_blended_rate(regular_hours, ot_hours, total_hours):
    """Compute blended server cost rate: (reg_hrs*87 + OT_hrs*109) / total_hrs.

    Falls back to DEFAULT_SERVER_COST when any value is missing or invalid.
    """
    try:
        reg = float(regular_hours)
        ot = float(ot_hours)
        tot = float(total_hours)
        if tot <= 0:
            return DEFAULT_SERVER_COST
        return (reg * REGULAR_RATE + ot * OT_RATE) / tot
    except (TypeError, ValueError, ZeroDivisionError):
        return DEFAULT_SERVER_COST


def _is_number(value) -> bool:
    """Return True when a value is a finite real number."""
    return isinstance(value, Real) and math.isfinite(float(value))


def _compute_waiting_cost(lambda_, wq_value):
    """Compute actual waiting cost from Wq, or return fixed cost for unstable systems.
    
    - If Wq is available: cost = λ * Wq * DEFAULT_CUSTOMER_WAITING_COST
    - If Wq is None (unstable): cost = UNSTABLE_FIXED_COST (fixed value, not infinite)
    - For unstable systems (ρ ≥ 1), a fixed cost is assigned instead of penalties.
    """
    if lambda_ is None:
        return None
    
    if wq_value is not None:
        # Calculate actual waiting cost from queue time
        return lambda_ * wq_value * DEFAULT_CUSTOMER_WAITING_COST
    else:
        # System is unstable: assign fixed cost (not infinite, just a fixed penalty value)
        # This provides a reasonable cost estimate for unstable systems
        return UNSTABLE_FIXED_COST


def _compute_waiting_cost_low(lambda_, wq_value, low_cost=50.0):
    """Compute waiting cost using lower penalty (₱50 instead of ₱100) for WASTE REDUCTION optimization.
    
    Used by waste reduction optimization to prioritize staff efficiency over customer service.
    - If Wq is available: cost = λ * Wq * low_cost
    - If Wq is None (unstable): cost = UNSTABLE_FIXED_COST (fixed penalty)
    """
    if lambda_ is None:
        return None
    
    if wq_value is not None:
        return lambda_ * wq_value * low_cost
    else:
        return UNSTABLE_FIXED_COST


def _queue_metrics(lambda_, mu, c):
    """Evaluate a queue segment using the appropriate M/M/1 or M/M/c model."""
    if c == 1:
        return mm1(lambda_, mu)
    return mmc(lambda_, mu, c)


def _safe_diff(new_value, old_value):
    """Return a difference only when both operands are present."""
    if new_value is None or old_value is None:
        return None
    return new_value - old_value


def _segment_server_cost(segment, default_server_cost):
    """Resolve server cost using blended rate formula when labor hours are provided.

    If the segment contains regular_hours, ot_hours, and total_hours, the cost
    is computed as:
        (regular_hours * 87 + ot_hours * 109) / total_hours

    Otherwise falls back to the segment's explicit server_cost or the default.
    """
    reg = segment.get("regular_hours")
    ot = segment.get("ot_hours")
    tot = segment.get("total_hours")

    if reg is not None and ot is not None and tot is not None:
        return compute_blended_rate(reg, ot, tot)

    # Legacy fallback: explicit server_cost or default
    segment_cost = segment.get("server_cost", default_server_cost)
    if not _is_number(segment_cost) or float(segment_cost) < 0:
        return None
    return float(segment_cost)


def _search_limit(lambda_, mu, current_c, target_utilization, max_servers):
    """Estimate a safe upper bound for the server search loop."""
    if not _is_number(lambda_) or not _is_number(mu) or float(mu) <= 0:
        return max(current_c, max_servers)

    required_by_target = math.ceil(float(lambda_) / (float(mu) * target_utilization))
    return max(1, current_c, required_by_target + 2, max_servers)


def _format_recommendation(time_label, current_c, optimal_c):
    """Build a staffing recommendation message."""
    if current_c is None or optimal_c is None:
        return f"Unable to determine server action at {time_label}."

    if optimal_c > current_c:
        change = optimal_c - current_c
        label = "server" if change == 1 else "servers"
        return f"Add {change} {label} at {time_label}."

    if optimal_c < current_c:
        change = current_c - optimal_c
        label = "server" if change == 1 else "servers"
        return f"Remove {change} {label} at {time_label}."

    return f"Maintain current staffing at {time_label}."


def optimize_segment(
    segment: Mapping,
    target_utilization: float = DEFAULT_TARGET_UTILIZATION,
    default_server_cost: float = DEFAULT_SERVER_COST,
    max_servers: int = DEFAULT_MAX_SERVERS,
) -> dict:
    """Compare current and optimized configuration for one time segment.
    
    Uses LEAN COST OPTIMIZATION:
    - Minimizes total cost (server + waiting)
    - Detects waste hours (if ρ ≤ 30%, tries to remove servers)
    - Ensures ρ stays ≤ 70% for stability
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
        "c_optimal": None,
        "rho_optimal": None,
        "Wq_optimal": None,
        "Lq_optimal": None,
        "cost_optimal": None,
        "waiting_cost_optimal": None,
        "delta_c": None,
        "delta_rho": None,
        "delta_Wq": None,
        "delta_Lq": None,
        "delta_cost": None,
        "current_stable": False,
        "optimized_stable": False,
        "recommendation": "Unable to optimize invalid segment input.",
        "warning": "Invalid segment format: each segment must be a dictionary.",
    }

    if not isinstance(segment, Mapping):
        return empty_result

    time_label = str(segment.get("time", "Unknown"))
    lambda_ = segment.get("lambda")
    mu = segment.get("mu")
    current_c = segment.get("c", 1)
    cost_per_server = _segment_server_cost(segment, default_server_cost)

    if (
        not isinstance(current_c, Integral)
        or int(current_c) <= 0
        or not _is_number(target_utilization)
        or not 0 < float(target_utilization) < 1
        or cost_per_server is None
        or not isinstance(max_servers, Integral)
        or int(max_servers) <= 0
    ):
        invalid_result = empty_result.copy()
        invalid_result.update(
            {
                "time": time_label,
                "lambda": lambda_,
                "mu": mu,
                "cost_per_server": cost_per_server,
                "c_current": current_c,
                "recommendation": f"Unable to optimize {time_label}.",
                "warning": "Invalid optimization settings, segment cost, or server count.",
            }
        )
        return invalid_result

    current_c = int(current_c)
    target_utilization = float(target_utilization)
    max_servers = int(max_servers)

    current_metrics = _queue_metrics(lambda_, mu, current_c)
    current_server_cost = current_c * cost_per_server
    current_waiting_cost = _compute_waiting_cost(lambda_, current_metrics.get("Wq"))
    current_total_cost = current_server_cost + (current_waiting_cost if current_waiting_cost is not None else 0)
    current_rho = current_metrics.get("rho")
    
    # LEAN OPTIMIZATION: Evaluate ALL server options to find minimum total cost
    best_cost_scenario = None
    best_cost_total = float('inf')
    
    for candidate_c in range(1, max_servers + 1):
        candidate_metrics = _queue_metrics(lambda_, mu, candidate_c)
        if not candidate_metrics.get("stable"):
            continue
            
        server_cost = candidate_c * cost_per_server
        waiting_cost = _compute_waiting_cost(lambda_, candidate_metrics.get("Wq"))
        total_cost = server_cost + (waiting_cost if waiting_cost is not None else 0)
        
        if total_cost < best_cost_total:
            best_cost_total = total_cost
            best_cost_scenario = {
                "c": candidate_c,
                "rho": candidate_metrics.get("rho"),
                "Wq": candidate_metrics.get("Wq"),
                "Lq": candidate_metrics.get("Lq"),
                "stable": True,
                "total_cost": total_cost,
                "waiting_cost": waiting_cost,
                "server_cost": server_cost,
            }
    
    if best_cost_scenario is None:
        wq_cur = current_metrics.get("Wq")
        waiting_cost_cur = _compute_waiting_cost(lambda_, wq_cur)
        return {
            "time": time_label,
            "lambda": lambda_,
            "mu": mu,
            "cost_per_server": cost_per_server,
            "c_current": current_c,
            "rho_current": current_rho,
            "Wq_current": wq_cur,
            "Lq_current": current_metrics.get("Lq"),
            "cost_current": current_server_cost,
            "waiting_cost_current": waiting_cost_cur,
            "c_optimal": None,
            "rho_optimal": None,
            "Wq_optimal": None,
            "Lq_optimal": None,
            "cost_optimal": None,
            "waiting_cost_optimal": None,
            "delta_c": None,
            "delta_rho": None,
            "delta_Wq": None,
            "delta_Lq": None,
            "delta_cost": None,
            "current_stable": bool(current_metrics.get("stable")),
            "optimized_stable": False,
            "recommendation": f"Unable to find a stable staffing plan at {time_label}.",
            "warning": "No server level maintained system stability within search range.",
        }
    
    optimal_c = best_cost_scenario["c"]
    optimal_rho = best_cost_scenario["rho"]
    optimal_wq = best_cost_scenario["Wq"]
    optimal_lq = best_cost_scenario["Lq"]
    optimal_cost = best_cost_scenario["server_cost"]
    optimal_waiting_cost = best_cost_scenario["waiting_cost"]
    optimal_total_cost = best_cost_scenario["total_cost"]
    
    # Check WASTE HOURS condition: if current ρ ≤ 30% and current_c > 1, try removing a server
    recommendation = _format_recommendation(time_label, current_c, optimal_c)
    final_optimal_c = optimal_c
    final_optimal_rho = optimal_rho
    final_optimal_wq = optimal_wq
    final_optimal_lq = optimal_lq
    final_optimal_cost = optimal_cost
    final_optimal_waiting_cost = optimal_waiting_cost
    final_optimal_total_cost = optimal_total_cost
    
    if current_rho is not None and current_rho <= 0.30 and current_c > 1:
        # Check if we can remove a server while staying stable (ρ ≤ 70%)
        reduced_c = current_c - 1
        reduced_metrics = _queue_metrics(lambda_, mu, reduced_c)
        reduced_rho = reduced_metrics.get("rho")
        
        if reduced_rho is not None and reduced_rho <= 0.70 and reduced_metrics.get("stable", False):
            reduced_server_cost = reduced_c * cost_per_server
            reduced_waiting_cost = _compute_waiting_cost(lambda_, reduced_metrics.get("Wq"))
            reduced_total_cost = reduced_server_cost + (reduced_waiting_cost if reduced_waiting_cost is not None else 0)
            savings = current_total_cost - reduced_total_cost
            
            change = current_c - reduced_c
            label = "server" if change == 1 else "servers"
            recommendation = (
                f"Remove {change} {label} at {time_label} (waste hours: p={current_rho:.3f} <= 30%). "
                f"p becomes {reduced_rho:.3f} (stable) and save P{savings:.2f} in total cost."
            )
            
            final_optimal_c = reduced_c
            final_optimal_rho = reduced_rho
            final_optimal_wq = reduced_metrics.get("Wq")
            final_optimal_lq = reduced_metrics.get("Lq")
            final_optimal_cost = reduced_server_cost
            final_optimal_waiting_cost = reduced_waiting_cost
            final_optimal_total_cost = reduced_total_cost
    
    warning = current_metrics.get("error") or best_cost_scenario.get("error")

    return {
        "time": time_label,
        "lambda": lambda_,
        "mu": mu,
        "cost_per_server": cost_per_server,
        "c_current": current_c,
        "rho_current": current_rho,
        "Wq_current": current_metrics.get("Wq"),
        "Lq_current": current_metrics.get("Lq"),
        "cost_current": current_server_cost,
        "waiting_cost_current": current_waiting_cost,
        "c_optimal": final_optimal_c,
        "rho_optimal": final_optimal_rho,
        "Wq_optimal": final_optimal_wq,
        "Lq_optimal": final_optimal_lq,
        "cost_optimal": final_optimal_cost,
        "waiting_cost_optimal": final_optimal_waiting_cost,
        "delta_c": final_optimal_c - current_c,
        "delta_rho": _safe_diff(final_optimal_rho, current_rho),
        "delta_Wq": _safe_diff(final_optimal_wq, current_metrics.get("Wq")),
        "delta_Lq": _safe_diff(final_optimal_lq, current_metrics.get("Lq")),
        "delta_cost": final_optimal_total_cost - current_total_cost,
        "current_stable": bool(current_metrics.get("stable")),
        "optimized_stable": bool(best_cost_scenario.get("stable")),
        "recommendation": recommendation,
        "warning": warning,
    }


def optimize_segments(
    time_segments: Iterable[Mapping],
    target_utilization: float = DEFAULT_TARGET_UTILIZATION,
    default_server_cost: float = DEFAULT_SERVER_COST,
    max_servers: int = DEFAULT_MAX_SERVERS,
) -> list[dict]:
    """Optimize a sequence of time segments."""
    if time_segments is None:
        return []

    return [
        optimize_segment(
            segment=segment,
            target_utilization=target_utilization,
            default_server_cost=default_server_cost,
            max_servers=max_servers,
        )
        for segment in time_segments
    ]


def summarize_optimization(comparison_rows: list[dict]) -> dict:
    """Compute top-level comparison KPIs from optimized segment rows."""
    if not comparison_rows:
        return {
            "total_current_cost": 0.0,
            "total_optimized_cost": 0.0,
            "total_savings": 0.0,
            "avg_utilization_current": None,
            "avg_utilization_optimized": None,
            "avg_utilization_improvement": None,
            "total_server_change": 0,
            "avg_waiting_current": None,
            "avg_waiting_optimized": None,
            "waiting_time_improvement_pct": None,
        }

    current_cost = sum(
        row["cost_current"] for row in comparison_rows if row["cost_current"] is not None
    )
    optimized_cost = sum(
        row["cost_optimal"] for row in comparison_rows if row["cost_optimal"] is not None
    )
    total_waiting_cost_current = sum(
        row["waiting_cost_current"] for row in comparison_rows if row.get("waiting_cost_current") is not None
    )
    total_waiting_cost_optimal = sum(
        row["waiting_cost_optimal"] for row in comparison_rows if row.get("waiting_cost_optimal") is not None
    )

    utilization_pairs = [
        (row["rho_current"], row["rho_optimal"])
        for row in comparison_rows
        if row["rho_current"] is not None and row["rho_optimal"] is not None
    ]
    waiting_pairs = [
        (row["Wq_current"], row["Wq_optimal"])
        for row in comparison_rows
        if row["Wq_current"] is not None and row["Wq_optimal"] is not None
    ]

    avg_util_current = (
        sum(pair[0] for pair in utilization_pairs) / len(utilization_pairs)
        if utilization_pairs
        else None
    )
    avg_util_optimized = (
        sum(pair[1] for pair in utilization_pairs) / len(utilization_pairs)
        if utilization_pairs
        else None
    )
    avg_wait_current = (
        sum(pair[0] for pair in waiting_pairs) / len(waiting_pairs)
        if waiting_pairs
        else None
    )
    avg_wait_optimized = (
        sum(pair[1] for pair in waiting_pairs) / len(waiting_pairs)
        if waiting_pairs
        else None
    )

    waiting_improvement_pct = None
    if avg_wait_current not in (None, 0) and avg_wait_optimized is not None:
        waiting_improvement_pct = (
            (avg_wait_current - avg_wait_optimized) / avg_wait_current
        ) * 100.0

    return {
        "total_current_cost": current_cost,
        "total_optimized_cost": optimized_cost,
        "total_savings": current_cost - optimized_cost,
        "total_waiting_cost_current": total_waiting_cost_current,
        "total_waiting_cost_optimal": total_waiting_cost_optimal,
        "avg_utilization_current": avg_util_current,
        "avg_utilization_optimized": avg_util_optimized,
        "avg_utilization_improvement": (
            avg_util_current - avg_util_optimized
            if avg_util_current is not None and avg_util_optimized is not None
            else None
        ),
        "total_server_change": sum(
            row["delta_c"] for row in comparison_rows if row["delta_c"] is not None
        ),
        "avg_waiting_current": avg_wait_current,
        "avg_waiting_optimized": avg_wait_optimized,
        "waiting_time_improvement_pct": waiting_improvement_pct,
    }


def build_recommendations(comparison_rows: list[dict]) -> list[str]:
    """Generate recommendation messages from optimized segment rows."""
    summary = summarize_optimization(comparison_rows)

    segment_actions = [
        row["recommendation"]
        for row in comparison_rows
        if row.get("recommendation") and row.get("delta_c") not in (None, 0)
    ]

    if not segment_actions:
        segment_actions = [
            "No staffing changes are required to satisfy the utilization target."
        ]

    messages = list(segment_actions)

    savings = summary["total_savings"]
    if savings is not None:
        if savings >= 0:
            messages.append(f"Estimated total daily savings: {savings:.2f} cost units.")
        else:
            messages.append(
                f"Estimated additional daily cost: {abs(savings):.2f} cost units."
            )

    if summary["waiting_time_improvement_pct"] is not None:
        messages.append(
            f"Average waiting time improvement: {summary['waiting_time_improvement_pct']:.1f}%."
        )

    return messages


def lean_optimize_segment(
    segment: Mapping,
    target_rho: float = 0.75,  # Target utilization (ρ) instead of utilization target
    default_server_cost: float = DEFAULT_SERVER_COST,
    max_servers: int = DEFAULT_MAX_SERVERS,
    check_waste_hours: bool = True,  # If True, remove servers when ρ ≤ 30% and stays stable
) -> dict:
    """Lean cost optimization: minimize ρ while keeping total cost low.
    
    Returns a detailed analysis with multiple server scenarios showing:
    - Current scenario (as-is)
    - Minimum viable (reduces ρ to target with minimum servers)
    - Optimal cost (minimizes total cost: server + waiting)
    
    Waste Hours Logic (when check_waste_hours=True):
    - If current ρ ≤ 30% (underutilized), consider removing servers
    - Only remove if resulting ρ stays ≤ 70% (system remains stable)
    - This reduces idle server time and saves cost
    """
    empty_result = {
        "time": "Unknown",
        "lambda": None,
        "mu": None,
        "cost_per_server": None,
        "scenarios": [],
        "current_c": None,
        "current_rho": None,
        "current_total_cost": None,
        "recommended_c": None,
        "recommended_rho": None,
        "recommended_total_cost": None,
        "recommendation": "Unable to optimize invalid segment input.",
        "warning": "Invalid segment format: each segment must be a dictionary.",
    }

    if not isinstance(segment, Mapping):
        return empty_result

    time_label = str(segment.get("time", "Unknown"))
    lambda_ = segment.get("lambda")
    mu = segment.get("mu")
    current_c = segment.get("c", 1)
    cost_per_server = _segment_server_cost(segment, default_server_cost)

    if (
        not isinstance(current_c, Integral)
        or int(current_c) <= 0
        or cost_per_server is None
        or not isinstance(max_servers, Integral)
        or int(max_servers) <= 0
    ):
        invalid_result = empty_result.copy()
        invalid_result.update(
            {
                "time": time_label,
                "lambda": lambda_,
                "mu": mu,
                "cost_per_server": cost_per_server,
                "current_c": current_c,
                "recommendation": f"Unable to optimize {time_label}.",
                "warning": "Invalid optimization settings or segment cost.",
            }
        )
        return invalid_result

    current_c = int(current_c)
    target_rho = float(target_rho) if 0 < target_rho < 1 else 0.75
    max_servers = int(max_servers)

    # Evaluate all scenarios from 1 to max_servers
    scenarios = []
    best_cost_scenario = None
    best_rho_scenario = None
    min_servers_for_target = None

    for candidate_c in range(1, max_servers + 1):
        candidate_metrics = _queue_metrics(lambda_, mu, candidate_c)
        server_cost = candidate_c * cost_per_server
        waiting_cost = _compute_waiting_cost(lambda_, candidate_metrics.get("Wq"))
        total_cost = server_cost + (waiting_cost if waiting_cost is not None else 0)
        rho = candidate_metrics.get("rho")
        
        scenario = {
            "servers": candidate_c,
            "rho": rho,
            "stable": candidate_metrics.get("stable", False),
            "Wq": candidate_metrics.get("Wq"),
            "Lq": candidate_metrics.get("Lq"),
            "server_cost": server_cost,
            "waiting_cost": waiting_cost,
            "total_cost": total_cost,
        }
        scenarios.append(scenario)

        # Find minimum viable (first scenario that meets target rho)
        if (
            min_servers_for_target is None
            and rho is not None
            and rho <= target_rho
            and candidate_metrics.get("stable", False)
        ):
            min_servers_for_target = candidate_c
            best_rho_scenario = scenario

        # Find lowest total cost scenario
        if (
            total_cost is not None
            and candidate_metrics.get("stable", False)
            and (best_cost_scenario is None or total_cost < best_cost_scenario["total_cost"])
        ):
            best_cost_scenario = scenario

    current_metrics = _queue_metrics(lambda_, mu, current_c)
    current_server_cost = current_c * cost_per_server
    current_waiting_cost = _compute_waiting_cost(lambda_, current_metrics.get("Wq"))
    current_total_cost = current_server_cost + (current_waiting_cost if current_waiting_cost is not None else 0)
    current_rho = current_metrics.get("rho")

    # Recommendation logic: prefer cost optimization over ρ reduction
    # First check: waste hours condition (if ρ ≤ 30%, try to remove servers)
    recommendation = f"Maintain {current_c} server(s) at {time_label}."
    recommended = best_cost_scenario if best_cost_scenario else best_rho_scenario
    
    if check_waste_hours and current_rho is not None and current_rho <= 0.30 and current_c > 1:
        # Check if we can remove a server while staying stable (ρ ≤ 70%)
        reduced_c = current_c - 1
        reduced_metrics = _queue_metrics(lambda_, mu, reduced_c)
        reduced_rho = reduced_metrics.get("rho")
        
        if reduced_rho is not None and reduced_rho <= 0.70 and reduced_metrics.get("stable", False):
            reduced_server_cost = reduced_c * cost_per_server
            reduced_waiting_cost = _compute_waiting_cost(lambda_, reduced_metrics.get("Wq"))
            reduced_total_cost = reduced_server_cost + (reduced_waiting_cost if reduced_waiting_cost is not None else 0)
            savings = current_total_cost - reduced_total_cost
            
            change = current_c - reduced_c
            label = "server" if change == 1 else "servers"
            recommendation = (
                f"Remove {change} {label} at {time_label} (waste hours: ρ={current_rho:.3f} ≤ 30%). "
                f"ρ becomes {reduced_rho:.3f} (≤ 70% safe) and save ₱{savings:.2f} in total cost."
            )
            recommended = {
                "servers": reduced_c,
                "rho": reduced_rho,
                "total_cost": reduced_total_cost,
            }
    elif recommended and recommended["servers"] != current_c:
        if best_cost_scenario and best_cost_scenario["total_cost"] < current_total_cost:
            savings = current_total_cost - best_cost_scenario["total_cost"]
            if best_cost_scenario["servers"] > current_c:
                change = best_cost_scenario["servers"] - current_c
                label = "server" if change == 1 else "servers"
                recommendation = (
                    f"Add {change} {label} at {time_label} to reduce ρ to {best_cost_scenario['rho']:.3f} "
                    f"and save ₱{savings:.2f} in total cost."
                )
            else:
                change = current_c - best_cost_scenario["servers"]
                label = "server" if change == 1 else "servers"
                recommendation = (
                    f"Remove {change} {label} at {time_label} to optimize cost. "
                    f"ρ will be {best_cost_scenario['rho']:.3f}."
                )

    return {
        "time": time_label,
        "lambda": lambda_,
        "mu": mu,
        "cost_per_server": cost_per_server,
        "scenarios": scenarios,
        "current_c": current_c,
        "current_rho": current_rho,
        "current_stable": current_metrics.get("stable", False),
        "current_server_cost": current_server_cost,
        "current_waiting_cost": current_waiting_cost,
        "current_total_cost": current_total_cost,
        "min_servers_for_target_rho": min_servers_for_target,
        "recommended_c": recommended["servers"] if recommended else current_c,
        "recommended_rho": recommended["rho"] if recommended else current_rho,
        "recommended_total_cost": recommended["total_cost"] if recommended else current_total_cost,
        "recommendation": recommendation,
    }


def lean_optimize_segments(
    time_segments: Iterable[Mapping],
    target_rho: float = 0.75,
    default_server_cost: float = DEFAULT_SERVER_COST,
    max_servers: int = DEFAULT_MAX_SERVERS,
    check_waste_hours: bool = True,
) -> list[dict]:
    """Lean optimize a sequence of time segments."""
    if time_segments is None:
        return []

    return [
        lean_optimize_segment(
            segment=segment,
            target_rho=target_rho,
            default_server_cost=default_server_cost,
            max_servers=max_servers,
            check_waste_hours=check_waste_hours,
        )
        for segment in time_segments
    ]
