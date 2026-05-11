"""
Shared utility functions for the Queueing Theory Dashboard system.

Provides modular functions for:
- compute_metrics() — Calculate M/M/c queue metrics
- optimize_servers() — Optimize server count
- run_simulation() — Execute Monte Carlo simulation
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Union
from queue_models import mgc, mgck, mmc, mmck

# ─────────────────────────────────────────────────────────────────────────────
# REQUIRED_COLUMNS — Data Contract (STRICT)
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_COLUMNS = [
    "time_interval",
    "arrival_rate",
    "service_rate",
    "servers",
    "utilization",
    "Lq",
    "Wq",
    "Ls",
    "Ws"
]

NUMERIC_COLUMNS = [
    "arrival_rate",
    "service_rate",
    "servers",
    "utilization",
    "Lq",
    "Wq",
    "Ls",
    "Ws"
]

# ─────────────────────────────────────────────────────────────────────────────
# compute_metrics() — Calculate M/M/c queue metrics
# ─────────────────────────────────────────────────────────────────────────────

def compute_mmc_metrics(lambda_: float, mu: float, c: int, variance=None, K=None) -> Dict[str, float]:
    """
    Compute M/M/c or M/G/c queue steady-state metrics.
    
    Args:
        lambda_ (float): Arrival rate (customers/hour)
        mu (float): Service rate per server (customers/hour)
        c (int): Number of servers
        
    Returns:
        dict with keys: utilization, Lq, Wq, Ls, Ws
        
    Handle edge cases:
        - Unstable systems (ρ ≥ 1): return inf metrics
        - Invalid inputs: return NaN metrics
    """
    
    # Input validation
    if lambda_ < 0 or mu <= 0 or c <= 0:
        return {
            "utilization": np.nan,
            "Lq": np.nan,
            "Wq": np.nan,
            "Ls": np.nan,
            "Ws": np.nan,
        }
    
    if K is not None and not pd.isna(K) and variance is not None and not pd.isna(variance):
        result = mgck(lambda_, mu, c, variance, int(K))
    elif K is not None and not pd.isna(K):
        result = mmck(lambda_, mu, c, int(K))
    elif variance is not None and not pd.isna(variance):
        result = mgc(lambda_, mu, c, variance)
    else:
        result = mmc(lambda_, mu, c)
    
    if not result.get("stable", False):
        return {
            "utilization": result.get("rho", np.nan),
            "Lq": np.inf,
            "Wq": np.inf,
            "Ls": np.inf,
            "Ws": np.inf,
        }
    
    return {
        "utilization": round(result["rho"], 4),
        "Lq": round(result["Lq"], 4),
        "Wq": round(result["Wq"], 4),
        "Ls": round(result["L"], 4),
        "Ws": round(result["W"], 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# optimize_servers() — Increment servers until target utilization
# ─────────────────────────────────────────────────────────────────────────────

def optimize_servers(
    row: pd.Series,
    target_utilization: float = 0.70,
    max_servers: int = 20
) -> pd.Series:
    """
    Optimize server count for a single row.
    
    Algorithm (STRICT):
    - While utilization >= target:
        - servers += 1
        - Recompute ALL metrics
    - Do NOT change arrival_rate or service_rate
    
    Args:
        row (pd.Series): Row with arrival_rate, service_rate, servers
        target_utilization (float): Stop when ρ < this value
        max_servers (int): Safety limit
        
    Returns:
        pd.Series with updated servers and all metrics
    """
    
    optimized = row.copy()
    
    lambda_ = row["arrival_rate"]
    mu = row["service_rate"]
    servers = int(row["servers"])
    variance = row.get("variance")
    capacity = row.get("K")
    max_search_servers = min(max_servers, int(capacity)) if capacity is not None and not pd.isna(capacity) else max_servers
    
    # Validation
    if pd.isna(lambda_) or pd.isna(mu) or pd.isna(servers):
        return optimized
    
    # Increment servers until target reached
    iteration = 0
    while servers < max_search_servers:
        metrics = compute_mmc_metrics(lambda_, mu, servers, variance, capacity)
        current_util = metrics["utilization"]
        
        if pd.isna(current_util) or current_util < target_utilization:
            break
        
        servers += 1
        iteration += 1
        
        if iteration > 50:  # Safety break
            break
    
    # Final computation
    final_metrics = compute_mmc_metrics(lambda_, mu, servers, variance, capacity)
    
    # Update row
    optimized["servers"] = servers
    for key in ["utilization", "Lq", "Wq", "Ls", "Ws"]:
        optimized[key] = final_metrics[key]
    
    return optimized


# ─────────────────────────────────────────────────────────────────────────────
# run_simulation() — Monte Carlo simulation
# ─────────────────────────────────────────────────────────────────────────────

def run_simulation(
    row: pd.Series,
    num_simulations: int = 100,
    failure_threshold: float = 0.75
) -> Dict[str, Union[float, int, str]]:
    """
    Run Monte Carlo simulation for a single row.
    
    Introduces randomness:
    - Arrival: ±20% (0.80–1.20)
    - Service: ±10% (0.90–1.10)
    
    Returns:
    - avg_utilization: Mean of all ρ values
    - max_utilization: Max of all ρ values
    - failure_rate: Fraction where ρ > failure_threshold
    
    Args:
        row (pd.Series): Row with arrival_rate, service_rate, servers
        num_simulations (int): Number of trials per row
        failure_threshold (float): ρ value that counts as failure
        
    Returns:
        dict with avg_util, max_util, failure_count, failure_rate, status
    """
    
    lambda_base = row["arrival_rate"]
    mu_base = row["service_rate"]
    c = int(row["servers"])
    
    # Validation
    if pd.isna(lambda_base) or pd.isna(mu_base) or pd.isna(c) or c <= 0:
        return {
            "avg_utilization": np.nan,
            "max_utilization": np.nan,
            "failure_count": 0,
            "failure_rate": np.nan,
            "status": "INVALID",
        }  # type: ignore
    
    utilizations = []
    failures = 0
    
    np.random.seed(42)  # Reproducibility
    
    for _ in range(num_simulations):
        # Add randomness
        arrival_factor = np.random.uniform(0.80, 1.20)
        service_factor = np.random.uniform(0.90, 1.10)
        
        lambda_sim = lambda_base * arrival_factor
        mu_sim = mu_base * service_factor
        
        # Compute utilization
        denominator = c * mu_sim
        if denominator == 0:
            utilization = np.inf
        else:
            utilization = lambda_sim / denominator
        
        utilizations.append(utilization)
        
        # Count failures
        if utilization > failure_threshold:
            failures += 1
    
    avg_util = np.mean(utilizations)
    max_util = np.max(utilizations)
    failure_rate = failures / num_simulations
    
    return {
        "avg_utilization": round(avg_util, 4),
        "max_utilization": round(max_util, 4),
        "failure_count": failures,
        "failure_rate": round(failure_rate, 4),
        "status": "✅ PASS" if failure_rate <= 0.10 else "❌ FAIL",
    }


# ─────────────────────────────────────────────────────────────────────────────
# compute_costs() — Calculate total operational costs
# ─────────────────────────────────────────────────────────────────────────────

def compute_costs(
    row: pd.Series,
    cost_per_server_hr: float = 87.0,
    cost_per_wait_hr: float = 100.0,
    cost_per_abandonment: float = 60.0,
    hours_per_interval: float = 1.0
) -> Dict[str, float]:
    """
    Compute total cost for a single time interval.
    
    Cost Formula:
    - Server Cost = servers × cost_per_server_hr × hours_per_interval
    - Wait Cost = Wq (hours) × arrival_rate × cost_per_wait_hr
    - Abandonment Cost = arrival_rate × 0.10 × cost_per_abandonment
    - Total Cost = Server Cost + Wait Cost + Abandonment Cost
    
    Args:
        row (pd.Series): Row with servers, Wq, arrival_rate
        cost_per_server_hr (float): Hourly cost per cashier (₱87/hr)
        cost_per_wait_hr (float): Hourly value of customer time (₱100/hr)
        cost_per_abandonment (float): Cost per abandoned customer (₱60)
        hours_per_interval (float): Hours in this interval (default 1.0)
        
    Returns:
        dict with server_cost, wait_cost, abandonment_cost, total_cost
    """
    try:
        servers = int(row.get("servers", 0))
        wq = float(row.get("Wq", 0))
        arrival_rate = float(row.get("arrival_rate", 0))
        
        # Handle invalid values
        if pd.isna(servers) or pd.isna(wq) or pd.isna(arrival_rate):
            return {
                "server_cost": np.nan,
                "wait_cost": np.nan,
                "abandonment_cost": np.nan,
                "total_cost": np.nan,
            }
        
        # Prevent negative/infinite values
        if np.isinf(wq) or wq < 0:
            wq = 999999  # Large penalty for unstable systems
        
        # Cost calculations
        server_cost = servers * cost_per_server_hr * hours_per_interval
        wait_cost = wq * arrival_rate * cost_per_wait_hr
        abandonment_cost = arrival_rate * 0.10 * cost_per_abandonment
        total_cost = server_cost + wait_cost + abandonment_cost
        
        return {
            "server_cost": round(server_cost, 2),
            "wait_cost": round(wait_cost, 2),
            "abandonment_cost": round(abandonment_cost, 2),
            "total_cost": round(total_cost, 2),
        }
    except Exception:
        return {
            "server_cost": np.nan,
            "wait_cost": np.nan,
            "abandonment_cost": np.nan,
            "total_cost": np.nan,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────────────────────────────────────

def validate_schema(df: pd.DataFrame) -> Tuple[bool, str]:
    """Check that all REQUIRED_COLUMNS exist."""
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        return False, f"Missing columns: {', '.join(missing)}"
    return True, "Schema valid"


def validate_and_convert_numeric(df: pd.DataFrame) -> Tuple[bool, str, pd.DataFrame]:
    """Validate and convert numeric columns."""
    df_copy = df.copy()
    
    for col in NUMERIC_COLUMNS:
        if col not in df_copy.columns:
            return False, f"Missing column: {col}", df_copy
        
        try:
            df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
            
            nan_count = df_copy[col].isna().sum()
            if nan_count > 0:
                return False, f"Column '{col}' has {nan_count} invalid values", df_copy
                
        except Exception as e:
            return False, f"Error converting '{col}': {str(e)}", df_copy
    
    return True, "All numeric columns validated", df_copy
