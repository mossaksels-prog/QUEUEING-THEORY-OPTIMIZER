"""Data preparation helpers for the queueing dashboard."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import pandas as pd

from optimization import (
    DEFAULT_MAX_SERVERS,
    DEFAULT_SERVER_COST,
    DEFAULT_TARGET_UTILIZATION,
    DEFAULT_CUSTOMER_WAITING_COST,
    UNSTABLE_PENALTY_MULTIPLIER,
    build_recommendations,
    compute_blended_rate,
    optimize_segments,
    summarize_optimization,
)
from queue_models import mgc, mgck, mm1, mmc, mmck


CURRENT_COLUMNS = [
    "time",
    "lambda",
    "mu",
    "c",
    "model",
    "rho",
    "L",
    "Lq",
    "W",
    "Wq",
    "stable",
    "status",
    "warning",
]

COMPARISON_COLUMNS = [
    "time",
    "lambda",
    "mu",
    "cost_per_server",
    "c_current",
    "rho_current",
    "Wq_current",
    "Lq_current",
    "cost_current",
    "waiting_cost_current",
    "c_optimal",
    "rho_optimal",
    "Wq_optimal",
    "Lq_optimal",
    "cost_optimal",
    "waiting_cost_optimal",
    "delta_c",
    "delta_rho",
    "delta_Wq",
    "delta_Lq",
    "delta_cost",
    "current_stable",
    "optimized_stable",
    "recommendation",
    "warning",
]


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    """Return an empty DataFrame with the requested columns."""
    return pd.DataFrame(columns=columns)


def _get_segment_cost(segment: Mapping, default_cost: float = DEFAULT_SERVER_COST) -> float:
    """Extract or compute cost per server from a segment.
    
    Uses blended rate formula if labor hours are provided, otherwise falls back to default.
    """
    reg = segment.get("regular_hours")
    ot = segment.get("ot_hours")
    tot = segment.get("total_hours")
    
    if reg is not None and ot is not None and tot is not None:
        return compute_blended_rate(reg, ot, tot)
    
    explicit_cost = segment.get("server_cost", default_cost)
    if explicit_cost is not None:
        return float(explicit_cost)
    
    return default_cost


def _sanitize_records(dataframe: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to JSON-like records with None instead of NaN."""
    if dataframe is None or dataframe.empty:
        return []
    normalized = dataframe.astype(object).where(pd.notna(dataframe), None)
    return normalized.to_dict("records")


def _classify_utilization_status(rho) -> str:
    """Classify queue utilization status based on rho value.
    
    Categories:
    - Lean: ρ < 60%
    - Normal: 60% ≤ ρ ≤ 79%
    - Peak: 80% < ρ ≤ 89%
    - Critical: ρ > 90%
    - Unstable: ρ > 1 (system unstable)
    """
    if rho is None:
        return "—"
    if rho > 1.0:
        return "Unstable"
    if rho >= 0.90:
        return "Critical"
    if rho > 0.80:
        return "Peak"
    if rho >= 0.60:
        return "Normal"
    return "Lean"


def _current_row(time_label, lambda_, mu, c, model_name, metrics) -> dict:
    """Build one normalized current-system result row."""
    stable = bool(metrics.get("stable"))
    rho = metrics.get("rho")
    status = _classify_utilization_status(rho)
    
    return {
        "time": str(time_label),
        "lambda": lambda_,
        "mu": mu,
        "c": c,
        "model": model_name,
        "rho": rho,
        "L": metrics.get("L"),
        "Lq": metrics.get("Lq"),
        "W": metrics.get("W"),
        "Wq": metrics.get("Wq"),
        "stable": stable,
        "status": status,
        "warning": metrics.get("error"),
    }


def process_segments(time_segments: Iterable[Mapping]) -> pd.DataFrame:
    """Process Page 1 current-system segments into a DataFrame."""
    if time_segments is None:
        return _empty_frame(CURRENT_COLUMNS)

    rows = []
    for index, segment in enumerate(time_segments, start=1):
        if not isinstance(segment, Mapping):
            rows.append(
                _current_row(
                    time_label=f"Segment {index}",
                    lambda_=None,
                    mu=None,
                    c=None,
                    model_name=None,
                    metrics={
                        "rho": None,
                        "L": None,
                        "Lq": None,
                        "W": None,
                        "Wq": None,
                        "stable": False,
                        "error": "Invalid segment format: each segment must be a dictionary.",
                    },
                )
            )
            continue

        time_label = segment.get("time", f"Segment {index}")
        lambda_ = segment.get("lambda")
        mu = segment.get("mu")
        c = segment.get("c", 1)
        variance = segment.get("variance")
        capacity = segment.get("K")

        if capacity is not None and pd.notna(capacity) and variance is not None and pd.notna(variance):
            metrics = mgck(lambda_, mu, c, variance, int(capacity))
            model_name = "M/G/c/K"
            servers = c
        elif capacity is not None and pd.notna(capacity):
            metrics = mmck(lambda_, mu, c, int(capacity))
            model_name = "M/M/c/K"
            servers = c
        elif variance is not None and pd.notna(variance):
            metrics = mgc(lambda_, mu, c, variance)
            model_name = "M/G/c"
            servers = c
        elif c == 1:
            metrics = mm1(lambda_, mu)
            model_name = "M/M/1"
            servers = 1
        else:
            metrics = mmc(lambda_, mu, c)
            model_name = "M/M/c"
            servers = c

        rows.append(_current_row(time_label, lambda_, mu, servers, model_name, metrics))

    return pd.DataFrame(rows, columns=CURRENT_COLUMNS) if rows else _empty_frame(CURRENT_COLUMNS)


def process_comparison_segments(
    time_segments: Iterable[Mapping],
    target_utilization: float = DEFAULT_TARGET_UTILIZATION,
    default_server_cost: float = DEFAULT_SERVER_COST,
    max_servers: int = DEFAULT_MAX_SERVERS,
) -> pd.DataFrame:
    """Process Page 2 optimization comparison segments into a DataFrame."""
    rows = optimize_segments(
        time_segments=time_segments,
        target_utilization=target_utilization,
        default_server_cost=default_server_cost,
        max_servers=max_servers,
    )
    return pd.DataFrame(rows, columns=COMPARISON_COLUMNS) if rows else _empty_frame(COMPARISON_COLUMNS)


def compute_kpis(results_df: pd.DataFrame, time_segments: Iterable[Mapping] = None, customer_waiting_cost: float = None) -> dict:
    """Compute Page 1 KPI summary values including waiting costs.
    
    Waiting Cost calculation:
    - Stable (ρ < 1): cost = Lq × customer_waiting_cost
    - Unstable (ρ ≥ 1): cost = λ × UNSTABLE_PENALTY_MULTIPLIER × customer_waiting_cost
    """
    if customer_waiting_cost is None:
        customer_waiting_cost = DEFAULT_CUSTOMER_WAITING_COST
    
    if results_df is None or results_df.empty:
        return {
            "avg_utilization": None,
            "max_utilization": None,
            "max_utilization_time": None,
            "avg_waiting_time": None,
            "total_waiting_cost": 0.0,
            "avg_waiting_cost": 0.0,
            "stable_count": 0,
            "unstable_count": 0,
        }

    # Calculate waiting costs for ALL rows (stable + unstable)
    total_wait_cost = 0.0
    avg_wait_time = 0.0
    
    for idx, row in results_df.iterrows():
        is_stable = row.get("stable", False)
        rho = row.get("rho")
        
        if is_stable:
            # Stable system: use actual Lq
            lq = row.get("Lq")
            if lq is not None and not pd.isna(lq):
                total_wait_cost += lq * customer_waiting_cost
            
            wq = row.get("Wq")
            if wq is not None and not pd.isna(wq):
                avg_wait_time += wq
        else:
            # Unstable system (ρ ≥ 1): apply penalty multiplier
            lambda_ = row.get("lambda")
            if lambda_ is not None and not pd.isna(lambda_):
                total_wait_cost += lambda_ * UNSTABLE_PENALTY_MULTIPLIER * customer_waiting_cost
    
    count_total = len(results_df)
    count_stable = int(results_df["stable"].sum())
    count_unstable = count_total - count_stable
    avg_cost = total_wait_cost / count_total if count_total > 0 else 0.0
    avg_wait_time = avg_wait_time / count_stable if count_stable > 0 else None
    
    # Find worst utilization (from stable segments only)
    stable_df = results_df[results_df["stable"]].copy()
    if stable_df.empty:
        return {
            "avg_utilization": None,
            "max_utilization": None,
            "max_utilization_time": None,
            "avg_waiting_time": None,
            "total_waiting_cost": total_wait_cost,
            "avg_waiting_cost": avg_cost,
            "stable_count": 0,
            "unstable_count": count_unstable,
        }

    worst_index = stable_df["rho"].idxmax()
    
    return {
        "avg_utilization": results_df["rho"].mean(),
        "max_utilization": stable_df["rho"].max(),
        "max_utilization_time": stable_df.loc[worst_index, "time"],
        "avg_waiting_time": avg_wait_time,
        "total_waiting_cost": total_wait_cost,
        "avg_waiting_cost": avg_cost,
        "stable_count": count_stable,
        "unstable_count": count_unstable,
    }


def compute_comparison_kpis(comparison_df: pd.DataFrame) -> dict:
    """Compute Page 2 optimization summary values."""
    return summarize_optimization(_sanitize_records(comparison_df))


def get_unstable_messages(results_df: pd.DataFrame) -> list[str]:
    """Collect validation messages for unstable current-system segments."""
    if results_df is None or results_df.empty:
        return []

    issue_rows = results_df[~results_df["stable"]]
    messages = []
    for _, row in issue_rows.iterrows():
        details = row["warning"] or "Segment could not be evaluated."
        messages.append(f"{row['time']}: {details}")
    return messages


def get_recommendation_messages(comparison_df: pd.DataFrame) -> list[str]:
    """Collect optimization recommendation messages for Page 2."""
    return build_recommendations(_sanitize_records(comparison_df))
