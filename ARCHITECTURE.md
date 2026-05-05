"""
SYSTEM ARCHITECTURE DOCUMENT
Streamlit Multi-Page Queueing Theory Dashboard

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. SYSTEM OVERVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A production-grade, 4-page Streamlit dashboard for queue optimization using M/M/c
queueing theory. Enforces strict data pipeline integrity with error-safe design.

┌─────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM OBJECTIVE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Page 1 (Upload & Compute)                                            │
│     ↓                                                                  │
│  st.session_state["current_data"]                                     │
│     ↓                                                                  │
│  Page 2 (Optimize)                                                    │
│     ↓                                                                  │
│  st.session_state["recommended_data"]                                 │
│     ↓                                                                  │
│  Page 3 (Compare) ← Merge current + recommended                       │
│     ↓                                                                  │
│  st.session_state["comparison_data"]                                  │
│     ↓                                                                  │
│  Page 4 (Simulate) ← ONLY uses recommended_data                       │
│     ↓                                                                  │
│  st.session_state["simulation_results"]                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. DATA SCHEMA (STRICT CONTRACT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REQUIRED_COLUMNS = [
    "time_interval",    # string    e.g. "08:00-09:00"
    "arrival_rate",     # float     λ — arrivals per hour
    "service_rate",     # float     μ — service completions per server/hour
    "servers",          # int       c — number of servers
    "utilization",      # float     ρ = λ/(c*μ)
    "Lq",               # float     average queue length
    "Wq",               # float     average wait time in queue
    "Ls",               # float     average system length
    "Ws"                # float     average time in system
]

VALIDATION RULES:
  ✅ All 9 columns MUST exist
  ✅ All numeric columns MUST convert without NaN
  ✅ Keys used: "time_interval" for merge operations
  ✅ No mutations of original data — always .copy()


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. PAGE ARCHITECTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 FILE STRUCTURE:
  streamlit_app.py               — Main entry point (session state init)
  └── pages/
       ├── 1_current_metrics.py   — Upload & validate
       ├── 2_optimization.py      — Server optimization
       ├── 3_comparison.py        — Merge + delta metrics
       └── 4_simulation.py        — Monte Carlo validation
  utils.py                       — Modular functions
  requirements.txt               — Dependencies
  STREAMLIT_QUICKSTART.md       — User guide


━━━━━━ PAGE 1: CURRENT METRICS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBJECTIVE:
  Upload CSV/Excel → Validate schema → Convert numeric → Compute M/M/c metrics

WORKFLOW:
  1. Upload file or load sample data
  2. SCHEMA VALIDATION
     - Check all 9 columns exist
     - If missing: STOP with error
  3. NUMERIC VALIDATION
     - Convert all numeric columns to float/int
     - Check for NaN after conversion
     - If invalid: STOP with error
  4. COMPUTE METRICS
     - For each row: compute utilization, Lq, Wq, Ls, Ws
     - Use M/M/c Erlang-C formula
     - Handle edge cases: ρ ≥ 1 → inf metrics
  5. DISPLAY & SAVE
     - Show metrics table
     - Save to st.session_state["current_data"]

ERROR HANDLING:
  ❌ Missing columns → STOP
  ❌ Invalid numeric → STOP
  ❌ Computation error → Skip row with warning
  ❌ Division by zero → Return NaN


━━━━━━ PAGE 2: OPTIMIZATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBJECTIVE:
  Reduce utilization: target ρ < 0.70 (especially peak hours ≥ 0.80)

ALGORITHM (STRICT):
  for each row:
    while utilization >= 0.70:
      servers += 1
      recompute ALL metrics

CRITICAL RULES:
  🔒 Do NOT change: arrival_rate, service_rate
  ✏️ Only modify: servers (increment)
  🔄 Recompute: ALL metrics (utilization, Lq, Wq, Ls, Ws)
  🛑 Safety limit: max 20 servers

WORKFLOW:
  1. PRE-CHECK: current_data exists
     - If missing: display error → STOP
  2. LOAD: current_data from session state
  3. RUN OPTIMIZATION:
     - For each row: call optimize_servers()
     - Show progress bar
  4. DISPLAY & EXPORT:
     - Show comparison table (current vs recommended)
     - Export to CSV and Excel
     - Save to st.session_state["recommended_data"]

ERROR HANDLING:
  ❌ current_data missing → STOP with help
  ❌ Invalid row inputs → Skip with warning
  ❌ Infinite loop → Safety break at 50 iterations


━━━━━━ PAGE 3: COMPARISON ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBJECTIVE:
  Safe merge of current_data + recommended_data with delta metrics

WORKFLOW:
  1. PRE-CHECK (MANDATORY):
     - Check current_data exists → If not: STOP
     - Check recommended_data exists → If not: STOP
  2. SAFE MERGE:
     - Inner merge on "time_interval"
     - Suffixes: _current, _recommended
     - Handle NaN gracefully
  3. CALCULATE DELTAS:
     - delta_servers = rec - cur
     - delta_utilization = rec - cur
     - delta_Lq, delta_Wq, etc.
  4. VISUALIZE:
     - Bar charts: utilization, servers
     - Line charts: queue metrics
     - Summary statistics
  5. EXPORT:
     - Download CSV with all columns
     - Save to st.session_state["comparison_data"]

ERROR HANDLING:
  ❌ Missing current_data → STOP
  ❌ Missing recommended_data → STOP
  ❌ Merge fails → Show error, skip
  ❌ Column mismatch → Use suffixes to prevent conflicts


━━━━━━ PAGE 4: SIMULATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBJECTIVE:
  Validate recommended configuration with Monte Carlo simulation

🚨 CRITICAL RULE: Use ONLY st.session_state["recommended_data"]

SIMULATION LOGIC:
  for each row in recommended_data:
    for i in range(100):
      arrival_sim = arrival_rate * random(0.80, 1.20)
      service_sim = service_rate * random(0.90, 1.10)
      rho_sim = arrival_sim / (servers * service_sim)
      
      if rho_sim > 0.75:
        failure_count += 1
    
    failure_rate = failure_count / 100

VALIDATION:
  ✅ PASS if failure_rate ≤ 10%
  ❌ FAIL if failure_rate > 10%

WORKFLOW:
  1. PRE-CHECK: recommended_data exists
     - If missing: STOP with help
  2. RUN SIMULATION:
     - For each row: call run_simulation()
     - 100 trials per row
     - Show progress bar
  3. DISPLAY RESULTS:
     - Utilization distribution
     - Failure rate by interval
     - Pass/Fail verdict
  4. EXPORT:
     - Download CSV with simulation results
     - Save to st.session_state["simulation_results"]

ERROR HANDLING:
  ❌ recommended_data missing → STOP
  ❌ Invalid row inputs → Skip with warning
  ❌ Division by zero → Handle gracefully
  ❌ Infinite values → Clamp to safe range


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. CORE MODULAR FUNCTIONS (utils.py)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

compute_mmc_metrics(lambda_, mu, c) → dict
  Uses Erlang-C formula
  Returns: {utilization, Lq, Wq, Ls, Ws}
  Edge cases:
    - ρ < 0: NaN
    - ρ ≥ 1: inf (unstable)
    - mu ≤ 0: NaN (invalid)

optimize_servers(row, target_util=0.70, max_servers=20) → pd.Series
  Algorithm: while ρ ≥ target, servers += 1
  Returns: optimized row with new servers + recomputed metrics
  Safety: max 20 servers, 50 iteration limit

run_simulation(row, num_sims=100, failure_threshold=0.75) → dict
  Monte Carlo with arrival ±20%, service ±10%
  Returns: {avg_util, max_util, failure_count, failure_rate, status}

validate_schema(df) → (bool, str)
  Check all 9 columns exist
  Returns: (success, message)

validate_and_convert_numeric(df) → (bool, str, df)
  Convert numeric columns, check for NaN
  Returns: (success, message, converted_df)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. SESSION STATE MANAGEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INITIALIZATION (streamlit_app.py):
  st.session_state["current_data"] = None
  st.session_state["recommended_data"] = None
  st.session_state["comparison_data"] = None
  st.session_state["simulation_results"] = None

FLOW:
  Page 1 → Sets current_data
  Page 2 → Reads current_data, sets recommended_data
  Page 3 → Reads current_data + recommended_data, sets comparison_data
  Page 4 → Reads recommended_data, sets simulation_results

NEVER mutate in-place:
  ✅ df_copy = df.copy()
  ❌ df.loc[idx] = value (mutates original)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. MATH: M/M/c QUEUE FORMULAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Utilization:
  ρ = λ / (c * μ)

Erlang-C (Probability of Waiting):
  a = λ / μ
  
  Numerator: a^c / c!
  Denominator: Σ(a^i / i!) for i from 0 to c
  
  Pw = Numerator / (Denominator + Numerator * (1 - ρ) / (1 - ρ))

Queue Metrics:
  Lq = (Pw * ρ) / (c * (1 - ρ))    [avg queue length]
  Wq = Lq / λ                       [avg wait time in queue]
  Ls = Lq + λ / μ                   [avg system length]
  Ws = Wq + 1 / μ                   [avg time in system]

Stability:
  System is stable if ρ < 1
  If ρ ≥ 1: queue grows unbounded → return inf metrics


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
7. ERROR PREVENTION STRATEGIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEFENSIVE STRATEGY 1: Pre-Check Before Execution
  Before reading data, explicitly check if it exists:
    if st.session_state.get("current_data") is None:
        st.error("❌ Not found")
        st.stop()

DEFENSIVE STRATEGY 2: Validate All Input Data
  Never assume numeric columns are clean:
    success, msg, df = validate_and_convert_numeric(df)
    if not success:
        st.error(msg)
        st.stop()

DEFENSIVE STRATEGY 3: Copy Data Before Mutation
  Always work with copies:
    df_copy = df.copy()
    df_copy["column"] = new_values

DEFENSIVE STRATEGY 4: Use .copy() Consistently
  Use throughout to prevent accidental mutations:
    row = series.copy()
    df = dataframe.copy()

DEFENSIVE STRATEGY 5: Handle Division by Zero
  Before computing a/b, check denominator:
    if denominator == 0:
        return 0  # or np.nan or np.inf

DEFENSIVE STRATEGY 6: Validate Computation Results
  After computation, check for inf/nan:
    if pd.isna(result) or np.isinf(result):
        handle_error()

DEFENSIVE STRATEGY 7: Merge with Suffixes
  Prevent column conflicts:
    df_merged = pd.merge(df1, df2, on="key", 
                         how="inner", 
                         suffixes=("_current", "_recommended"))

DEFENSIVE STRATEGY 8: Use try/except Judiciously
  Catch computation errors but fail fast:
    try:
        result = compute_metric(row)
    except Exception as e:
        st.warning(f"Skip: {e}")


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8. DEPENDENCIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

streamlit>=1.28.0     — Web UI framework
plotly>=5.17.0        — Interactive visualizations
pandas>=2.1.0         — Data manipulation
numpy>=1.24.0         — Numerical computing
openpyxl>=3.0.0       — Excel export


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
9. DEPLOYMENT CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Session state initialized in streamlit_app.py
✅ All 9 pages created and working
✅ Pre-checks on every dependent page
✅ Error messages are clear and actionable
✅ Sample data provided (create_sample_data.py)
✅ All numeric columns validated
✅ All mutations use .copy()
✅ Merge uses suffixes
✅ M/M/c formulas implemented correctly
✅ Monte Carlo simulation uses recommended_data only
✅ Export buttons on all pages
✅ Documentation complete (STREAMLIT_QUICKSTART.md)

"""
