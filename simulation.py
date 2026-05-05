"""
simulation.py — Discrete-event simulation engine using SimPy.

Simulates M/M/1 and M/M/c queueing systems for time-segmented arrival/service
patterns. Produces empirical metrics that complement the analytical formulas in
queue_models.py.

Metric glossary
───────────────
  rho_sim      : empirical server utilization (fraction of busy time)
  Lq_sim       : time-average queue length  (Little's Law: Lq = λ · Wq)
  Wq_sim       : mean waiting time in queue  (hours)
  max_queue    : maximum observed queue depth during the interval
  status       : NORMAL / BUSY / OVERLOADED based on configurable thresholds
  served       : total customers served in the interval
  dropped      : customers who arrived during an overloaded stretch
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Optional

import simpy

# ──────────────────────────────────────────────────────────────────────────────
# Simulation constants
# ──────────────────────────────────────────────────────────────────────────────

# Simulation constants
# ──────────────────────────────────────────────────────────────────────────────

LEAN_THRESHOLD = 0.60        # ρ < this → Lean
NORMAL_THRESHOLD = 0.80      # 0.60 ≤ ρ < this → Normal
PEAK_THRESHOLD = 0.90        # 0.80 < ρ < this → Peak
CRITICAL_THRESHOLD = 0.90    # ρ ≥ this → Critical
UNSTABLE_THRESHOLD = 1.0     # ρ > this → Unstable
DEFAULT_QUEUE_OVERLOAD = 20  # queue depth that triggers Critical regardless of ρ
SIM_HOURS_PER_SEGMENT = 24.0  # each segment represents 1 simulated hour
RANDOM_SEED = 42             # reproducible runs; override per call for stochastic analysis


# ──────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SegmentResult:
    """Holds simulation output for one time segment."""
    time: str
    lambda_: float
    mu: float
    c: int

    # Empirical metrics
    rho_sim: Optional[float] = None
    Lq_sim: Optional[float] = None
    Wq_sim: Optional[float] = None
    max_queue: int = 0
    served: int = 0
    dropped: int = 0
    status: str = "Lean"
    error: Optional[str] = None

    # Internal accumulators (not exposed to callers)
    _busy_area: float = field(default=0.0, repr=False)
    _queue_area: float = field(default=0.0, repr=False)
    _wait_sum: float = field(default=0.0, repr=False)

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "lambda": self.lambda_,
            "mu": self.mu,
            "c": self.c,
            "rho_sim": self.rho_sim,
            "Lq_sim": self.Lq_sim,
            "Wq_sim": self.Wq_sim,
            "max_queue": self.max_queue,
            "served": self.served,
            "dropped": self.dropped,
            "status": self.status,
            "error": self.error,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _validate_segment(segment: Mapping) -> tuple[Optional[str], Optional[float], Optional[float], int]:
    """Extract and validate segment fields. Returns (error, lambda_, mu, c)."""
    lambda_ = segment.get("lambda")
    mu = segment.get("mu")
    c = segment.get("c", 1)

    if lambda_ is None or mu is None:
        return "Missing lambda or mu.", None, None, 1

    try:
        lambda_ = float(lambda_)
        mu = float(mu)
        c = int(c)
    except (TypeError, ValueError):
        return "lambda, mu, and c must be numeric.", None, None, 1

    if lambda_ < 0:
        return "lambda must be >= 0.", None, None, c
    if mu <= 0:
        return "mu must be > 0.", None, None, c
    if c <= 0:
        return "c must be >= 1.", None, None, c

    return None, lambda_, mu, c


def _classify_status(rho: float, max_queue: int, queue_overload_threshold: int) -> str:
    """Map empirical utilization + queue depth to a status label.
    
    Categories:
    - Lean: ρ < 60%
    - Normal: 60% ≤ ρ < 80%
    - Peak: 80% < ρ < 90%
    - Critical: ρ ≥ 90% or queue depth ≥ threshold
    - Unstable: ρ > 1 (system unstable)
    """
    if rho > UNSTABLE_THRESHOLD:
        return "Unstable"
    if rho >= CRITICAL_THRESHOLD or max_queue >= queue_overload_threshold:
        return "Critical"
    if rho > NORMAL_THRESHOLD:
        return "Peak"
    if rho >= LEAN_THRESHOLD:
        return "Normal"
    return "Lean"


def _exponential(rate: float, rng: random.Random) -> float:
    """Draw an exponential inter-event time; guard against zero rate."""
    if rate <= 0:
        return float("inf")
    return rng.expovariate(rate)


# ──────────────────────────────────────────────────────────────────────────────
# SimPy process definitions
# ──────────────────────────────────────────────────────────────────────────────

class _QueueMonitor:
    """Tracks time-averaged queue length and server busyness via area-under-curve."""

    def __init__(self, env: simpy.Environment, servers: simpy.Resource):
        self.env = env
        self.servers = servers
        self._last_t = 0.0
        self._queue_area = 0.0   # ∫ Lq(t) dt
        self._busy_area = 0.0    # ∫ busy_servers(t) dt

    def _snapshot(self, at: float = None):
        """Accumulate area since the last snapshot, optionally forcing a time."""
        now = at if at is not None else self.env.now
        dt = now - self._last_t
        if dt <= 0:
            return
        q = len(self.servers.queue)           # number waiting
        b = self.servers.count                # number in service
        self._queue_area += q * dt
        self._busy_area  += b * dt
        self._last_t = now

    def record(self):
        """Call this at every state-change point."""
        self._snapshot()

    def finalize(self, end_time: float) -> tuple[float, float]:
        """Flush remaining area exactly up to end_time and return (Lq, busy_fraction).

        Forces the snapshot to end_time so the idle tail after the last event
        is correctly included — otherwise rho_sim is understated.
        """
        self._snapshot(at=end_time)
        duration = end_time  # simulation starts at t=0
        if duration <= 0:
            return 0.0, 0.0
        lq = self._queue_area / duration
        # busy_fraction averages busy_servers / total_servers → utilization per server
        busy_fraction = self._busy_area / (duration * max(self.servers.capacity, 1))
        return lq, busy_fraction


def _customer_process(
    env: simpy.Environment,
    servers: simpy.Resource,
    mu: float,
    result: SegmentResult,
    monitor: _QueueMonitor,
    rng: random.Random,
):
    """SimPy generator: one customer enters queue, waits for a server, gets served."""
    arrival = env.now
    monitor.record()

    with servers.request() as req:
        # Update queue depth tracking before and after acquiring server
        q_depth = len(servers.queue)
        if q_depth > result.max_queue:
            result.max_queue = q_depth

        yield req
        monitor.record()

        wait = env.now - arrival
        result._wait_sum += wait

        service_time = _exponential(mu, rng)
        yield env.timeout(service_time)
        monitor.record()

    result.served += 1


def _arrival_process(
    env: simpy.Environment,
    servers: simpy.Resource,
    lambda_: float,
    mu: float,
    sim_duration: float,
    result: SegmentResult,
    monitor: _QueueMonitor,
    rng: random.Random,
):
    """SimPy generator: generates arrivals for the duration of one segment."""
    while True:
        iat = _exponential(lambda_, rng)
        # Peek ahead: if next arrival falls outside the window, stop
        if env.now + iat >= sim_duration:
            break
        yield env.timeout(iat)

        env.process(
            _customer_process(env, servers, mu, result, monitor, rng)
        )


# ──────────────────────────────────────────────────────────────────────────────
# Public API — single-segment simulation
# ──────────────────────────────────────────────────────────────────────────────

def simulate_segment(
    segment: Mapping,
    sim_hours: float = SIM_HOURS_PER_SEGMENT,
    queue_overload_threshold: int = DEFAULT_QUEUE_OVERLOAD,
    seed: Optional[int] = RANDOM_SEED,
) -> SegmentResult:
    """
    Run a discrete-event simulation for one time segment.

    Parameters
    ----------
    segment : Mapping
        Must contain 'lambda', 'mu', and optionally 'c' (default 1) and 'time'.
    sim_hours : float
        Duration of the simulated interval in hours (default 1.0 per segment).
    queue_overload_threshold : int
        Queue depth that triggers OVERLOADED status regardless of utilization.
    seed : int or None
        Random seed for reproducibility.  Pass None for true stochasticity.

    Returns
    -------
    SegmentResult
        Empirical metrics for the interval.
    """
    time_label = str(segment.get("time", "Unknown"))
    result = SegmentResult(time=time_label, lambda_=0.0, mu=0.0, c=1)

    error, lambda_, mu, c = _validate_segment(segment)
    result.lambda_ = lambda_ or 0.0
    result.mu = mu or 0.0
    result.c = c

    if error:
        result.error = error
        result.status = "ERROR"
        return result

    # Zero-arrival edge case: no queue, servers idle
    if lambda_ == 0:
        result.rho_sim = 0.0
        result.Lq_sim = 0.0
        result.Wq_sim = 0.0
        result.status = "NORMAL"
        return result

    # Detect analytically unstable segments (λ ≥ c·μ).
    # For unstable segments, long simulations just build infinite queues and
    # produce rho_sim >> 1.0, which is meaningless and distorts all averages.
    # Cap sim_duration to 1 hour for unstable segments so the result stays
    # comparable to the analytical tab (which marks them as UNSTABLE/OVERLOADED).
    theoretical_rho = lambda_ / (c * mu)
    is_unstable = theoretical_rho >= 1.0
    effective_sim_hours = 1.0 if is_unstable else sim_hours

    rng = random.Random(seed)
    sim_duration = effective_sim_hours  # environment time unit = hours

    env = simpy.Environment()
    servers = simpy.Resource(env, capacity=c)
    monitor = _QueueMonitor(env, servers)

    env.process(
        _arrival_process(env, servers, lambda_, mu, sim_duration, result, monitor, rng)
    )
    env.run(until=sim_duration)

    # Finalize time-averaged metrics at the true segment boundary
    lq_avg, rho_emp = monitor.finalize(sim_duration)
    # For unstable segments, rho can exceed 1.0 — cap at 0.9999 so KPI cards
    # stay meaningful and consistent with the analytical tab's OVERLOADED label.
    result.rho_sim = round(min(rho_emp, 0.9999) if is_unstable else rho_emp, 6)
    result.Lq_sim = round(lq_avg, 6)

    # Mean waiting time: use Little's Law (Wq = Lq / λ) as primary estimate;
    # fall back to accumulated wait sums when available.
    if result.served > 0:
        result.Wq_sim = round(result._wait_sum / result.served, 6)
    elif lambda_ > 0:
        result.Wq_sim = round(lq_avg / lambda_, 6)
    else:
        result.Wq_sim = 0.0

    result.status = _classify_status(rho_emp, result.max_queue, queue_overload_threshold)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Public API — multi-segment simulation
# ──────────────────────────────────────────────────────────────────────────────

def simulate_segments(
    time_segments: Iterable[Mapping],
    sim_hours: float = SIM_HOURS_PER_SEGMENT,
    queue_overload_threshold: int = DEFAULT_QUEUE_OVERLOAD,
    seed: Optional[int] = RANDOM_SEED,
) -> list[dict]:
    """
    Simulate a sequence of time segments and return a list of result dicts.

    Each segment is simulated independently (no carry-over customers between
    segments).  The seed is incremented per segment so results are reproducible
    but statistically independent.

    Parameters
    ----------
    time_segments : Iterable[Mapping]
        Sequence of segment dicts (keys: time, lambda, mu, c).
    sim_hours : float
        Simulated hours per segment.
    queue_overload_threshold : int
        Queue depth that forces OVERLOADED status.
    seed : int or None
        Base random seed.  Segments use seed, seed+1, seed+2, … when not None.

    Returns
    -------
    list[dict]
        One dict per segment, matching SegmentResult.to_dict() schema.
    """
    if time_segments is None:
        return []

    results = []
    for i, seg in enumerate(time_segments):
        seg_seed = (seed + i) if seed is not None else None
        res = simulate_segment(
            segment=seg,
            sim_hours=sim_hours,
            queue_overload_threshold=queue_overload_threshold,
            seed=seg_seed,
        )
        results.append(res.to_dict())

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Public API — summary KPIs across all segments
# ──────────────────────────────────────────────────────────────────────────────

def summarize_simulation(sim_rows: list[dict]) -> dict:
    """
    Compute dashboard-level KPIs from a list of simulate_segments() outputs.

    Returns
    -------
    dict
        avg_rho, max_rho, max_rho_time, avg_Lq, avg_Wq,
        total_served, total_dropped,
        overloaded_count, busy_count, normal_count,
        avg_max_queue
    """
    if not sim_rows:
        return {
            "avg_rho": None,
            "max_rho": None,
            "max_rho_time": None,
            "avg_Lq": None,
            "avg_Wq": None,
            "total_served": 0,
            "total_dropped": 0,
            "overloaded_count": 0,
            "busy_count": 0,
            "normal_count": 0,
            "avg_max_queue": None,
        }

    valid = [r for r in sim_rows if r.get("rho_sim") is not None]

    if not valid:
        return {
            "avg_rho": None,
            "max_rho": None,
            "max_rho_time": None,
            "avg_Lq": None,
            "avg_Wq": None,
            "total_served": sum(r.get("served", 0) for r in sim_rows),
            "total_dropped": sum(r.get("dropped", 0) for r in sim_rows),
            "critical_count": sum(1 for r in sim_rows if r.get("status") == "Critical"),
            "peak_count": sum(1 for r in sim_rows if r.get("status") == "Peak"),
            "normal_count": sum(1 for r in sim_rows if r.get("status") == "Normal"),
            "lean_count": sum(1 for r in sim_rows if r.get("status") == "Lean"),
            "avg_max_queue": None,
        }

    # Mirror compute_kpis() on Page 1 & 2: exclude unstable segments (λ >= c·μ)
    # from avg_rho and avg_Wq so the simulation KPIs match the analytical tab,
    # which only averages stable segments.
    stable_for_avg = [
        r for r in valid
        if (r.get("lambda") or 0) < (r.get("c", 1) * r.get("mu", 1))
    ] or valid  # fallback to all rows if somehow all are unstable

    rho_vals = [r["rho_sim"] for r in valid]
    lq_vals  = [r["Lq_sim"]  for r in stable_for_avg if r.get("Lq_sim") is not None]
    wq_vals  = [r["Wq_sim"]  for r in stable_for_avg if r.get("Wq_sim") is not None]
    mq_vals  = [r["max_queue"] for r in valid]

    max_rho_row = max(valid, key=lambda r: r["rho_sim"])

    avg_rho = sum(r["rho_sim"] for r in stable_for_avg) / len(stable_for_avg)

    return {
        "avg_rho": avg_rho,
        "max_rho": max(rho_vals),
        "max_rho_time": max_rho_row["time"],
        "avg_Lq": sum(lq_vals) / len(lq_vals) if lq_vals else None,
        "avg_Wq": sum(wq_vals) / len(wq_vals) if wq_vals else None,
        "total_served": sum(r.get("served", 0) for r in sim_rows),
        "total_dropped": sum(r.get("dropped", 0) for r in sim_rows),
        "critical_count": sum(1 for r in sim_rows if r.get("status") == "Critical"),
        "peak_count": sum(1 for r in sim_rows if r.get("status") == "Peak"),
        "normal_count": sum(1 for r in sim_rows if r.get("status") == "Normal"),
        "lean_count": sum(1 for r in sim_rows if r.get("status") == "Lean"),
        "avg_max_queue": sum(mq_vals) / len(mq_vals) if mq_vals else None,
    }
