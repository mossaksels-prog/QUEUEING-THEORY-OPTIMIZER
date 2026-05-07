"""
Page 6 — Adjustment Testing Simulator
🧪 Manual parameter adjustment testing WITHOUT file uploads
✅ Same simulation engine as Page 3
✅ Test custom adjustments for all models (M/M/1, M/M/c, M/G/1)
✅ No dependencies on recommended_data
✅ Output: failure_rate (util > 0.75), avg_utilization, max_utilization
✅ PASS if failure_rate ≤ 10%

Supported Models:
- M/M/1: Single server parameter testing
- M/M/c: Multi-server parameter testing
- M/G/1: General service time parameter testing
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─────────────────────────────────────────────────────────────────────────────
# Helper: Format numbers with trailing zeros removed
# ─────────────────────────────────────────────────────────────────────────────

def format_number(val, decimals=2):
    """Format a number, removing trailing zeros."""
    if pd.isna(val):
        return ""
    formatted = f"{val:.{decimals}f}"
    # Remove trailing zeros but keep at least one decimal place
    formatted = formatted.rstrip('0')
    if formatted.endswith('.'):
        formatted += '0'
    return formatted


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

NUM_SIMULATIONS = 100  # per scenario
ARRIVAL_VARIANCE_RANGE = (0.80, 1.20)  # ±20%
SERVICE_VARIANCE_RANGE = (0.90, 1.10)  # ±10%
FAILURE_THRESHOLD_UTIL = 0.75  # failure if ρ > this
ACCEPTABLE_FAILURE_RATE = 0.10  # 10%


# ─────────────────────────────────────────────────────────────────────────────
# Monte Carlo Simulation Function
# ─────────────────────────────────────────────────────────────────────────────

def simulate_scenario_mg1(arrival_rate: float, service_rate: float, servers: int,
                         service_variance: float, num_simulations: int = 100, 
                         scenario_name: str = "") -> dict:
    """
    Run NUM_SIMULATIONS Monte Carlo trials for M/G/1 scenario.
    
    Input: arrival_rate, service_rate, servers, service_variance
    Output: dict with avg/max utilization, failure_rate, and avg_wq
    
    RULES (M/G/1 with general service variance):
    - Introduce randomness:
      - Arrival: ±10-20% (0.80 - 1.20)
      - Service variance factor: ±20% applied to variance parameter
    - Compute: ρ = λ / (c * μ)
    - Estimate Wq using M/G/1 formula: Wq = (λ * (σ² + (1/μ)²)) / (2 * (1 - ρ))
    - Count failures: ρ > 0.75
    - failure_rate = failures / num_simulations
    """
    
    lambda_base = arrival_rate
    mu_base = service_rate
    c = int(servers)
    variance_base = service_variance
    
    # Validation
    if pd.isna(lambda_base) or pd.isna(mu_base) or pd.isna(c) or c <= 0 or pd.isna(variance_base):
        return {
            "scenario_name": scenario_name,
            "arrival_rate": lambda_base,
            "service_rate": mu_base,
            "servers": c,
            "service_variance": variance_base,
            "baseline_utilization": np.nan,
            "avg_utilization": np.nan,
            "max_utilization": np.nan,
            "failure_count": 0,
            "failure_rate": np.nan,
            "avg_wq": np.nan,
            "status": "INVALID (M/G/1)",
        }
    
    # Calculate baseline utilization
    baseline_utilization = lambda_base / (c * mu_base) if (c * mu_base) > 0 else np.inf
    
    utilizations = []
    wq_values = []
    failures = 0
    
    np.random.seed(42)  # Reproducibility
    
    for _ in range(num_simulations):
        # Add randomness
        arrival_factor = np.random.uniform(*ARRIVAL_VARIANCE_RANGE)
        variance_factor = np.random.uniform(0.80, 1.20)  # ±20% on variance
        
        lambda_sim = lambda_base * arrival_factor
        variance_sim = variance_base * variance_factor
        
        # Compute utilization (ρ = λ / (c * μ))
        denominator = c * mu_base
        
        if denominator == 0:
            utilization = np.inf
            wq = np.inf
        else:
            utilization = lambda_sim / denominator
            
            # M/G/1 formula for Wq (adapted for multiple servers as approximation)
            # Wq ≈ (λ * (σ² + (1/μ)²)) / (2 * (1 - ρ)) for stability
            if utilization < 1.0:
                E_S = 1 / mu_base
                E_S2 = variance_sim + E_S**2
                wq = (lambda_sim * E_S2) / (2 * (1 - utilization)) if (1 - utilization) > 0 else 0
            else:
                wq = np.inf
        
        utilizations.append(utilization)
        if not np.isinf(wq):
            wq_values.append(wq)
        
        # Check if failure (utilization > threshold)
        if utilization > FAILURE_THRESHOLD_UTIL:
            failures += 1
    
    avg_util = np.mean(utilizations)
    max_util = np.max(utilizations)
    failure_rate = failures / num_simulations
    avg_wq = np.mean(wq_values) if wq_values else 0
    
    # Status
    if failure_rate <= ACCEPTABLE_FAILURE_RATE:
        status = "✅ PASS (M/G/1)"
    else:
        status = "❌ FAIL (M/G/1)"
    
    return {
        "scenario_name": scenario_name,
        "arrival_rate": lambda_base,
        "service_rate": mu_base,
        "servers": c,
        "service_variance": variance_base,
        "baseline_utilization": round(baseline_utilization, 4),
        "avg_utilization": round(avg_util, 4),
        "max_utilization": round(max_util, 4),
        "failure_count": failures,
        "failure_rate": round(failure_rate, 4),
        "avg_wq": round(avg_wq, 4),
        "status": status,
    }


def simulate_scenario(arrival_rate: float, service_rate: float, servers: int, 
                     num_simulations: int = 100, scenario_name: str = "") -> dict:
    """
    Run NUM_SIMULATIONS Monte Carlo trials for a single scenario.
    
    Input: arrival_rate, service_rate, servers
    Output: dict with avg/max utilization, failure_rate, and avg_wq
    
    RULES:
    - Introduce randomness:
      - Arrival: ±10-20% (0.80 - 1.20)
      - Service: ±10% (0.90 - 1.10)
    - Compute: ρ = λ / (c * μ)
    - Count failures: ρ > 0.75
    - failure_rate = failures / num_simulations
    - Estimate Wq based on arrival and service rates
    """
    
    lambda_base = arrival_rate
    mu_base = service_rate
    c = int(servers)
    
    # Validation
    if pd.isna(lambda_base) or pd.isna(mu_base) or pd.isna(c) or c <= 0:
        return {
            "scenario_name": scenario_name,
            "arrival_rate": lambda_base,
            "service_rate": mu_base,
            "servers": c,
            "baseline_utilization": np.nan,
            "avg_utilization": np.nan,
            "max_utilization": np.nan,
            "failure_count": 0,
            "failure_rate": np.nan,
            "avg_wq": np.nan,
            "status": "INVALID",
        }
    
    # Calculate baseline utilization
    baseline_utilization = lambda_base / (c * mu_base) if (c * mu_base) > 0 else np.inf
    
    utilizations = []
    wq_values = []
    failures = 0
    
    np.random.seed(42)  # Reproducibility
    
    for _ in range(num_simulations):
        # Add randomness
        arrival_factor = np.random.uniform(*ARRIVAL_VARIANCE_RANGE)
        service_factor = np.random.uniform(*SERVICE_VARIANCE_RANGE)
        
        lambda_sim = lambda_base * arrival_factor
        mu_sim = mu_base * service_factor
        
        # Compute utilization
        denominator = c * mu_sim
        
        if denominator == 0:
            utilization = np.inf
            wq = np.inf
        else:
            utilization = lambda_sim / denominator
            # Estimate Wq: λ / (c * μ * (c - λ/μ))
            # Simplified: Wq ≈ λ / (μ * c^2) for stable systems
            if utilization < 1.0:
                wq = lambda_sim / (mu_sim * c * (1 - utilization)) if (1 - utilization) > 0 else 0
            else:
                wq = np.inf
        
        utilizations.append(utilization)
        if not np.isinf(wq):
            wq_values.append(wq)
        
        # Check if failure (utilization > threshold)
        if utilization > FAILURE_THRESHOLD_UTIL:
            failures += 1
    
    avg_util = np.mean(utilizations)
    max_util = np.max(utilizations)
    failure_rate = failures / num_simulations
    avg_wq = np.mean(wq_values) if wq_values else 0
    
    # Status
    if failure_rate <= ACCEPTABLE_FAILURE_RATE:
        status = "✅ PASS"
    else:
        status = "❌ FAIL"
    
    return {
        "scenario_name": scenario_name,
        "arrival_rate": lambda_base,
        "service_rate": mu_base,
        "servers": c,
        "baseline_utilization": round(baseline_utilization, 4),
        "avg_utilization": round(avg_util, 4),
        "max_utilization": round(max_util, 4),
        "failure_count": failures,
        "failure_rate": round(failure_rate, 4),
        "avg_wq": round(avg_wq, 4),
        "status": status,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main UI
# ─────────────────────────────────────────────────────────────────────────────

st.title("🧪 Page 6: Adjustment Testing Simulator")
st.markdown("""
**Test custom adjustments without file uploads**
- 🎲 Introduce variability: arrival ±20%, service ±10%
- 📊 Output: failure_rate (util > 0.75), avg/max utilization  
- ✅ PASS if failure_rate ≤ 10%
- 🔧 Manually input parameters to test different scenarios
""")

# ─────────────────────────────────────────────────────────────────────────────
# Helper: Generate 13 hourly segments
# ─────────────────────────────────────────────────────────────────────────────

def generate_hourly_segments(start_hour: int, end_hour: int) -> list:
    """
    Generate 13 hourly time intervals.
    
    Args:
        start_hour: Start hour (0-23)
        end_hour: End hour (0-23)
    
    Returns:
        List of 13 time interval labels
    """
    segments = []
    current_hour = start_hour
    
    for i in range(13):
        next_hour = (current_hour + 1) % 24
        segments.append(f"{current_hour:02d}:00-{next_hour:02d}:00")
        current_hour = next_hour
    
    return segments


# ─────────────────────────────────────────────────────────────────────────────
# Input Mode Selection
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📋 Input Mode")

input_mode = st.radio(
    "Choose input method:",
    ["Quick Single Test", "13-Hour Daily Segments", "Segmental Hourly M/G/1", "Batch Comparison"],
    horizontal=True,
    key="input_mode_selector"
)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# QUICK SINGLE TEST
# ─────────────────────────────────────────────────────────────────────────────

if input_mode == "Quick Single Test":
    st.subheader("🔧 Single Scenario Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        scenario_name = st.text_input(
            "Scenario Name",
            value="Test Adjustment",
            key="scenario_name_single"
        )
    
    with col2:
        arrival_rate = st.number_input(
            "Arrival Rate (λ)",
            min_value=0.1,
            max_value=100.0,
            value=5.0,
            step=0.1,
            key="arrival_single"
        )
    
    with col3:
        service_rate = st.number_input(
            "Service Rate (μ)",
            min_value=0.1,
            max_value=100.0,
            value=2.0,
            step=0.1,
            key="service_single"
        )
    
    col4, col5, col6 = st.columns(3)
    
    with col4:
        servers = st.number_input(
            "Number of Servers (c)",
            min_value=1,
            max_value=20,
            value=3,
            step=1,
            key="servers_single"
        )
    
    with col5:
        num_sims = st.slider(
            "Simulations per scenario",
            min_value=10,
            max_value=1000,
            value=NUM_SIMULATIONS,
            step=10,
            key="num_sims_single"
        )
    
    with col6:
        st.metric("Failure Threshold (ρ)", FAILURE_THRESHOLD_UTIL)
    
    # Run single test
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 2])
    
    with col_btn1:
        run_single = st.button("🚀 Run Single Test", key="btn_single_test")
    
    if run_single:
        st.info(f"⏳ Running {num_sims} simulations...")
        
        result = simulate_scenario(
            arrival_rate=arrival_rate,
            service_rate=service_rate,
            servers=servers,
            num_simulations=num_sims,
            scenario_name=scenario_name
        )
        
        st.session_state["single_test_result"] = result
        st.success("✅ Test complete!")
    
    # Display single test results
    if st.session_state.get("single_test_result") is not None:
        st.markdown("---")
        st.subheader("📊 Single Test Results")
        
        result = st.session_state["single_test_result"]
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Baseline ρ", f"{result['baseline_utilization']:.2%}")
        
        with col2:
            st.metric("Avg ρ (Sim)", f"{result['avg_utilization']:.2%}")
        
        with col3:
            st.metric("Max ρ (Sim)", f"{result['max_utilization']:.2%}")
        
        with col4:
            failure_color = "🔴" if result['failure_rate'] > ACCEPTABLE_FAILURE_RATE else "🟢"
            st.metric(
                f"{failure_color} Failure Rate", 
                f"{result['failure_rate']:.2%}",
                result['status']
            )
        
        # Results details
        st.markdown("---")
        st.subheader("📈 Detailed Metrics")
        
        results_df = pd.DataFrame([result])
        results_styled = results_df.style.format({
            "arrival_rate": lambda x: format_number(x, 2),
            "service_rate": lambda x: format_number(x, 2),
            "baseline_utilization": lambda x: format_number(x, 4),
            "avg_utilization": lambda x: format_number(x, 4),
            "max_utilization": lambda x: format_number(x, 4),
            "failure_rate": lambda x: format_number(x, 4),
            "avg_wq": lambda x: format_number(x, 4),
        })
        st.dataframe(results_styled, use_container_width=True)
        
        # Costing analysis for single scenario
        st.markdown("---")
        st.subheader("💰 Costing Analysis (Hourly)")
        
        server_cost = result['servers'] * 87.0
        waiting_cost = result['avg_wq'] * result['arrival_rate'] * 100.0
        abandonment_cost = result['arrival_rate'] * 0.10 * 60.0
        total_cost = server_cost + waiting_cost + abandonment_cost
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Server Cost", f"₱{server_cost:,.0f}")
        
        with col2:
            st.metric("Waiting Cost", f"₱{waiting_cost:,.0f}")
        
        with col3:
            st.metric("Abandonment Cost", f"₱{abandonment_cost:,.0f}")
        
        with col4:
            st.metric("TOTAL HOURLY COST", f"₱{total_cost:,.0f}")
        
        # Costing pie chart
        fig_cost = go.Figure(data=[
            go.Pie(
                labels=["Server", "Waiting", "Abandonment"],
                values=[server_cost, waiting_cost, abandonment_cost],
                marker=dict(colors=["rgba(59, 130, 246, 0.7)", "rgba(244, 63, 94, 0.7)", "rgba(251, 191, 36, 0.7)"])
            )
        ])
        
        fig_cost.update_layout(
            title="Cost Breakdown",
            height=400,
        )
        
        st.plotly_chart(fig_cost, use_container_width=True)
        
        # Verdict
        st.markdown("---")
        st.subheader("🎯 Verdict")
        
        if result['failure_rate'] <= ACCEPTABLE_FAILURE_RATE:
            st.success(f"""
            ✅ **TEST PASSED**
            
            Failure rate: **{result['failure_rate']:.2%}** (target: ≤ {ACCEPTABLE_FAILURE_RATE:.0%})
            
            ✨ This adjustment is robust!
            """)
        else:
            st.error(f"""
            ❌ **TEST FAILED**
            
            Failure rate: **{result['failure_rate']:.2%}** (target: ≤ {ACCEPTABLE_FAILURE_RATE:.0%})
            
            ⚠️ Try adjusting servers or other parameters.
            """)

# ─────────────────────────────────────────────────────────────────────────────
# 13-HOUR DAILY SEGMENTS
# ─────────────────────────────────────────────────────────────────────────────

elif input_mode == "13-Hour Daily Segments":
    st.subheader("⏰ 13-Hour Daily Segments (Start → End Time)")
    
    st.info("Specify start and end times, then input parameters for each hourly segment")
    
    col_time1, col_time2 = st.columns(2)
    
    with col_time1:
        start_hour = st.selectbox(
            "Start Hour",
            options=list(range(24)),
            format_func=lambda x: f"{x:02d}:00",
            index=6,
            key="daily_start_hour"
        )
    
    with col_time2:
        end_hour = st.selectbox(
            "End Hour (Start + 13 hours)",
            options=list(range(24)),
            format_func=lambda x: f"{x:02d}:00",
            index=19,
            key="daily_end_hour"
        )
    
    # Generate time segments
    hourly_segments = generate_hourly_segments(start_hour, end_hour)
    
    st.markdown("---")
    st.subheader("📊 Input Parameters for Each Hour")
    
    # Initialize session state for daily segments
    if "daily_segment_data" not in st.session_state:
        st.session_state.daily_segment_data = None
    
    # Create editable dataframe for hourly parameters
    default_daily_data = pd.DataFrame({
        "time_interval": hourly_segments,
        "arrival_rate": [5.0] * 13,
        "service_rate": [2.0] * 13,
        "servers": [3] * 13,
    })
    
    edited_daily_df = st.data_editor(
        default_daily_data,
        use_container_width=True,
        key="daily_params_editor",
        num_rows="fixed",
        column_config={
            "time_interval": st.column_config.TextColumn("Hour Range", disabled=True),
            "arrival_rate": st.column_config.NumberColumn("λ (Arrival Rate)", min_value=0.1, step=0.1),
            "service_rate": st.column_config.NumberColumn("μ (Service Rate)", min_value=0.1, step=0.1),
            "servers": st.column_config.NumberColumn("Servers", min_value=1, step=1),
        }
    )
    
    st.session_state.daily_segment_data = edited_daily_df
    
    # Run button
    st.markdown("---")
    col_daily_btn1, col_daily_btn2 = st.columns(2)
    
    with col_daily_btn1:
        num_daily_sims = st.slider(
            "Simulations per hour",
            min_value=10,
            max_value=1000,
            value=NUM_SIMULATIONS,
            step=10,
            key="daily_num_sims"
        )
    
    with col_daily_btn2:
        run_daily = st.button("🚀 Run 13-Hour Simulation", key="btn_run_daily")
    
    if run_daily:
        st.info(f"⏳ Running {len(edited_daily_df)} hours × {num_daily_sims} sims...")
        
        daily_results = []
        progress_bar = st.progress(0)
        
        for idx, row in edited_daily_df.iterrows():
            result = simulate_scenario(
                arrival_rate=row['arrival_rate'],
                service_rate=row['service_rate'],
                servers=int(row['servers']),
                num_simulations=num_daily_sims,
                scenario_name=row['time_interval']
            )
            daily_results.append(result)
            progress_bar.progress((idx + 1) / len(edited_daily_df))
        
        st.session_state["daily_results"] = pd.DataFrame(daily_results)
        st.success(f"✅ 13-Hour simulation complete!")
    
    # Display daily results
    if st.session_state.get("daily_results") is not None:
        st.markdown("---")
        st.subheader("📊 13-Hour Simulation Results")
        
        daily_df = st.session_state["daily_results"]
        
        # Summary statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_util = daily_df["avg_utilization"].mean()
            st.metric("Avg Utilization (13h)", f"{avg_util:.1%}")
        
        with col2:
            avg_failure = daily_df["failure_rate"].mean()
            status_badge = "✅ PASS" if avg_failure <= ACCEPTABLE_FAILURE_RATE else "❌ FAIL"
            st.metric("Avg Failure Rate", f"{avg_failure:.1%}", status_badge)
        
        with col3:
            max_util = daily_df["max_utilization"].max()
            st.metric("Peak Utilization", f"{max_util:.1%}")
        
        with col4:
            passed_hours = (daily_df["failure_rate"] <= ACCEPTABLE_FAILURE_RATE).sum()
            pct_pass = (passed_hours / len(daily_df) * 100)
            st.metric("Hours Passed", f"{passed_hours}/{len(daily_df)} ({pct_pass:.0f}%)")
        
        # Results table
        daily_styled = daily_df.style.format({
            "arrival_rate": lambda x: format_number(x, 2),
            "service_rate": lambda x: format_number(x, 2),
            "baseline_utilization": lambda x: format_number(x, 4),
            "avg_utilization": lambda x: format_number(x, 4),
            "max_utilization": lambda x: format_number(x, 4),
            "failure_rate": lambda x: format_number(x, 4),
            "avg_wq": lambda x: format_number(x, 4),
        })
        st.dataframe(daily_styled, use_container_width=True)
        
        # Visualizations
        st.markdown("---")
        st.subheader("📉 13-Hour Analysis")
        
        # Chart 1: Utilization timeline
        fig1 = make_subplots(
            rows=1, cols=2,
            subplot_titles=("Utilization by Hour", "Failure Rate Timeline")
        )
        
        fig1.add_trace(
            go.Scatter(x=daily_df["scenario_name"], y=daily_df["baseline_utilization"],
                      name="Baseline ρ", mode="lines+markers", line=dict(color="orange")),
            row=1, col=1
        )
        
        fig1.add_trace(
            go.Scatter(x=daily_df["scenario_name"], y=daily_df["avg_utilization"],
                      name="Avg ρ", mode="lines+markers", line=dict(color="blue")),
            row=1, col=1
        )
        
        fig1.add_hline(y=FAILURE_THRESHOLD_UTIL, line_dash="dash", line_color="red",
                      annotation_text="Threshold", row=1, col=1)
        
        fig1.add_trace(
            go.Bar(x=daily_df["scenario_name"], y=daily_df["failure_rate"],
                  marker_color=["red" if x > ACCEPTABLE_FAILURE_RATE else "green" 
                               for x in daily_df["failure_rate"]],
                  name="Failure Rate"),
            row=1, col=2
        )
        
        fig1.add_hline(y=ACCEPTABLE_FAILURE_RATE, line_dash="dash", line_color="orange",
                      annotation_text="Acceptable", row=1, col=2)
        
        fig1.update_yaxes(title_text="Utilization (ρ)", row=1, col=1)
        fig1.update_yaxes(title_text="Failure Rate", row=1, col=2)
        fig1.update_layout(height=400, hovermode="x unified")
        
        st.plotly_chart(fig1, use_container_width=True)
        
        # Chart 2: Servers needed per hour
        fig2 = go.Figure()
        
        fig2.add_trace(go.Bar(
            x=daily_df["scenario_name"],
            y=daily_df["servers"],
            name="Servers",
            marker_color="rgba(59, 130, 246, 0.7)",
            text=daily_df["servers"],
            textposition="outside",
        ))
        
        fig2.update_layout(
            title="Staffing Requirements by Hour",
            xaxis_title="Hour",
            yaxis_title="Number of Servers",
            height=400,
        )
        
        st.plotly_chart(fig2, use_container_width=True)
        
        # Chart 3: Daily costing analysis
        st.markdown("---")
        st.subheader("💰 Daily Cost Analysis")
        
        costing_daily_df = pd.DataFrame({
            "hour": daily_df["scenario_name"],
            "server_cost_₱": daily_df["servers"] * 87.0,
            "waiting_cost_₱": daily_df["avg_wq"] * daily_df["arrival_rate"] * 100.0,
            "abandonment_cost_₱": daily_df["arrival_rate"] * 0.10 * 60.0,
        })
        
        costing_daily_df["total_cost_₱"] = (costing_daily_df["server_cost_₱"] + 
                                            costing_daily_df["waiting_cost_₱"] + 
                                            costing_daily_df["abandonment_cost_₱"])
        
        # Costing stacked bar chart
        fig3 = go.Figure()
        
        fig3.add_trace(go.Bar(
            x=costing_daily_df["hour"],
            y=costing_daily_df["server_cost_₱"],
            name="Server Cost",
            marker_color="rgba(59, 130, 246, 0.7)",
        ))
        
        fig3.add_trace(go.Bar(
            x=costing_daily_df["hour"],
            y=costing_daily_df["waiting_cost_₱"],
            name="Waiting Cost",
            marker_color="rgba(244, 63, 94, 0.7)",
        ))
        
        fig3.add_trace(go.Bar(
            x=costing_daily_df["hour"],
            y=costing_daily_df["abandonment_cost_₱"],
            name="Abandonment Cost",
            marker_color="rgba(251, 191, 36, 0.7)",
        ))
        
        fig3.update_layout(
            title="Hourly Cost Breakdown (13h Total)",
            xaxis_title="Hour",
            yaxis_title="Cost (₱)",
            barmode="stack",
            height=400,
            hovermode="x unified",
        )
        
        st.plotly_chart(fig3, use_container_width=True)
        
        # Daily totals
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_server = costing_daily_df["server_cost_₱"].sum()
            st.metric("Total Server Cost (13h)", f"₱{total_server:,.0f}")
        
        with col2:
            total_waiting = costing_daily_df["waiting_cost_₱"].sum()
            st.metric("Total Waiting Cost (13h)", f"₱{total_waiting:,.0f}")
        
        with col3:
            total_abandon = costing_daily_df["abandonment_cost_₱"].sum()
            st.metric("Total Abandonment Cost (13h)", f"₱{total_abandon:,.0f}")
        
        with col4:
            total_daily = costing_daily_df["total_cost_₱"].sum()
            st.metric("TOTAL DAILY COST (13h)", f"₱{total_daily:,.0f}")
        
        # Overall verdict
        st.markdown("---")
        st.subheader("🎯 13-Hour Verdict")
        
        overall_failure = daily_df["failure_rate"].mean()
        
        if overall_failure <= ACCEPTABLE_FAILURE_RATE:
            st.success(f"""
            ✅ **PASSED**
            
            Average failure rate over 13 hours: **{overall_failure:.2%}** (target: ≤ {ACCEPTABLE_FAILURE_RATE:.0%})
            
            ✨ Configuration is robust across the day!
            """)
        else:
            st.warning(f"""
            ⚠️ **NEEDS ADJUSTMENT**
            
            Average failure rate: **{overall_failure:.2%}** (target: ≤ {ACCEPTABLE_FAILURE_RATE:.0%})
            
            💡 Review peak hours and adjust staffing as needed.
            """)
        
        # Export daily results
        st.markdown("---")
        st.subheader("💾 Export 13-Hour Results")
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv_bytes = daily_df.to_csv(index=False).encode()
            st.download_button(
                "📥 Download CSV (Simulation)",
                csv_bytes,
                "13hour_simulation.csv",
                "text/csv",
            )
        
        with col2:
            try:
                import io
                excel_buffer = io.BytesIO()
                excel_writer = pd.ExcelWriter(excel_buffer, engine='openpyxl')
                daily_df.to_excel(excel_writer, index=False, sheet_name="Results")
                costing_daily_df.to_excel(excel_writer, index=False, sheet_name="Costing")
                excel_writer.close()
                excel_buffer.seek(0)
                
                st.download_button(
                    "📊 Download Excel (Complete)",
                    excel_buffer.getvalue(),
                    "13hour_analysis.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            except Exception as e:
                st.warning(f"Excel export: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# SEGMENTAL HOURLY M/G/1
# ─────────────────────────────────────────────────────────────────────────────

elif input_mode == "Segmental Hourly M/G/1":
    st.subheader("🔬 Segmental Hourly M/G/1 Simulation")
    st.markdown("""
    Simulate **M/G/1 queues** with **general service time distributions**.
    Each hour segment includes arrival rate, service rate, servers, and **service variance**.
    """)
    
    st.info("M/G/1 accounts for variability in service times — essential for unpredictable workflows")
    
    col_mg1_time1, col_mg1_time2 = st.columns(2)
    
    with col_mg1_time1:
        mg1_start_hour = st.selectbox(
            "Start Hour",
            options=list(range(24)),
            format_func=lambda x: f"{x:02d}:00",
            index=6,
            key="mg1_start_hour"
        )
    
    with col_mg1_time2:
        mg1_end_hour = st.selectbox(
            "End Hour (Start + 13 hours)",
            options=list(range(24)),
            format_func=lambda x: f"{x:02d}:00",
            index=19,
            key="mg1_end_hour"
        )
    
    # Generate time segments
    mg1_hourly_segments = generate_hourly_segments(mg1_start_hour, mg1_end_hour)
    
    st.markdown("---")
    st.subheader("📊 M/G/1 Parameters for Each Hour")
    st.markdown("**Note:** Variance represents the variability of service times. Higher variance = more unpredictable service.")
    
    # Initialize session state for M/G/1 segments
    if "mg1_segment_data" not in st.session_state:
        st.session_state.mg1_segment_data = None
    
    # Create editable dataframe for M/G/1 hourly parameters
    default_mg1_data = pd.DataFrame({
        "time_interval": mg1_hourly_segments,
        "arrival_rate": [5.0] * 13,
        "service_rate": [2.0] * 13,
        "servers": [3] * 13,
        "service_variance": [0.04] * 13,  # Default variance
    })
    
    edited_mg1_df = st.data_editor(
        default_mg1_data,
        use_container_width=True,
        key="mg1_params_editor",
        num_rows="fixed",
        column_config={
            "time_interval": st.column_config.TextColumn("Hour Range", disabled=True),
            "arrival_rate": st.column_config.NumberColumn("λ (Arrival Rate)", min_value=0.1, step=0.1),
            "service_rate": st.column_config.NumberColumn("μ (Service Rate)", min_value=0.1, step=0.1),
            "servers": st.column_config.NumberColumn("Servers", min_value=1, step=1),
            "service_variance": st.column_config.NumberColumn("Variance (σ²)", min_value=0.001, step=0.01),
        }
    )
    
    st.session_state.mg1_segment_data = edited_mg1_df
    
    # Run button
    st.markdown("---")
    col_mg1_btn1, col_mg1_btn2 = st.columns(2)
    
    with col_mg1_btn1:
        num_mg1_sims = st.slider(
            "Simulations per hour (M/G/1) — Higher iterations = more accurate",
            min_value=100000,
            max_value=500000,
            value=100000,
            step=10000,
            key="mg1_num_sims",
            format="%d"
        )
    
    with col_mg1_btn2:
        run_mg1 = st.button("🚀 Run M/G/1 Simulation", key="btn_run_mg1")
    
    if run_mg1:
        st.info(f"⏳ Running {len(edited_mg1_df)} hours × {num_mg1_sims} M/G/1 sims...")
        
        mg1_results = []
        progress_bar = st.progress(0)
        
        for idx, row in edited_mg1_df.iterrows():
            result = simulate_scenario_mg1(
                arrival_rate=row['arrival_rate'],
                service_rate=row['service_rate'],
                servers=int(row['servers']),
                service_variance=row['service_variance'],
                num_simulations=num_mg1_sims,
                scenario_name=row['time_interval']
            )
            mg1_results.append(result)
            progress_bar.progress((idx + 1) / len(edited_mg1_df))
        
        st.session_state["mg1_results"] = pd.DataFrame(mg1_results)
        st.success(f"✅ M/G/1 simulation complete!")
    
    # Display M/G/1 results
    if st.session_state.get("mg1_results") is not None:
        st.markdown("---")
        st.subheader("📊 M/G/1 Simulation Results (13-Hour)")
        
        mg1_df = st.session_state["mg1_results"]
        
        # Summary statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_util_mg1 = mg1_df["avg_utilization"].mean()
            st.metric("Avg Utilization (13h)", f"{avg_util_mg1:.1%}")
        
        with col2:
            avg_failure_mg1 = mg1_df["failure_rate"].mean()
            status_badge_mg1 = "✅ PASS" if avg_failure_mg1 <= ACCEPTABLE_FAILURE_RATE else "❌ FAIL"
            st.metric("Avg Failure Rate", f"{avg_failure_mg1:.1%}", status_badge_mg1)
        
        with col3:
            max_util_mg1 = mg1_df["max_utilization"].max()
            st.metric("Peak Utilization", f"{max_util_mg1:.1%}")
        
        with col4:
            passed_hours_mg1 = (mg1_df["failure_rate"] <= ACCEPTABLE_FAILURE_RATE).sum()
            pct_pass_mg1 = (passed_hours_mg1 / len(mg1_df) * 100)
            st.metric("Hours Passed", f"{passed_hours_mg1}/{len(mg1_df)} ({pct_pass_mg1:.0f}%)")
        
        # Results table
        mg1_styled = mg1_df.style.format({
            "arrival_rate": lambda x: format_number(x, 2),
            "service_rate": lambda x: format_number(x, 2),
            "service_variance": lambda x: format_number(x, 4),
            "baseline_utilization": lambda x: format_number(x, 4),
            "avg_utilization": lambda x: format_number(x, 4),
            "max_utilization": lambda x: format_number(x, 4),
            "failure_rate": lambda x: format_number(x, 4),
            "avg_wq": lambda x: format_number(x, 4),
        })
        st.dataframe(mg1_styled, use_container_width=True)
        
        # Visualizations
        st.markdown("---")
        st.subheader("📉 M/G/1 13-Hour Analysis")
        
        # Chart 1: M/G/1 Utilization and Variance Impact
        fig_mg1_1 = make_subplots(
            rows=1, cols=2,
            subplot_titles=("M/G/1 Utilization by Hour", "Service Variance Impact")
        )
        
        fig_mg1_1.add_trace(
            go.Scatter(x=mg1_df["scenario_name"], y=mg1_df["baseline_utilization"],
                      name="Baseline ρ", mode="lines+markers", line=dict(color="orange")),
            row=1, col=1
        )
        
        fig_mg1_1.add_trace(
            go.Scatter(x=mg1_df["scenario_name"], y=mg1_df["avg_utilization"],
                      name="Avg ρ (M/G/1)", mode="lines+markers", line=dict(color="blue")),
            row=1, col=1
        )
        
        fig_mg1_1.add_hline(y=FAILURE_THRESHOLD_UTIL, line_dash="dash", line_color="red",
                           annotation_text="Threshold", row=1, col=1)
        
        fig_mg1_1.add_trace(
            go.Scatter(x=mg1_df["scenario_name"], y=mg1_df["service_variance"],
                      name="Service Variance", mode="lines+markers", line=dict(color="purple")),
            row=1, col=2
        )
        
        fig_mg1_1.update_yaxes(title_text="Utilization (ρ)", row=1, col=1)
        fig_mg1_1.update_yaxes(title_text="Variance (σ²)", row=1, col=2)
        fig_mg1_1.update_layout(height=400, hovermode="x unified")
        
        st.plotly_chart(fig_mg1_1, use_container_width=True)
        
        # Chart 2: M/G/1 Wait Time Analysis
        fig_mg1_2 = go.Figure()
        
        fig_mg1_2.add_trace(go.Bar(
            x=mg1_df["scenario_name"],
            y=mg1_df["avg_wq"],
            name="Avg Wait Time (Wq)",
            marker_color="rgba(168, 85, 247, 0.7)",
            text=mg1_df["avg_wq"].round(2),
            textposition="outside",
        ))
        
        fig_mg1_2.update_layout(
            title="M/G/1 Average Wait Time by Hour",
            xaxis_title="Hour",
            yaxis_title="Wait Time (Wq)",
            height=400,
        )
        
        st.plotly_chart(fig_mg1_2, use_container_width=True)
        
        # Chart 3: M/G/1 Failure Rate Timeline
        fig_mg1_3 = go.Figure()
        
        colors_mg1 = ["red" if x > ACCEPTABLE_FAILURE_RATE else "green" for x in mg1_df["failure_rate"]]
        
        fig_mg1_3.add_trace(go.Bar(
            x=mg1_df["scenario_name"],
            y=mg1_df["failure_rate"],
            marker_color=colors_mg1,
            name="Failure Rate",
            text=mg1_df["failure_rate"].round(2),
            textposition="outside",
        ))
        
        fig_mg1_3.add_hline(y=ACCEPTABLE_FAILURE_RATE, line_dash="dash", line_color="orange",
                           annotation_text="Acceptable Threshold")
        
        fig_mg1_3.update_layout(
            title="M/G/1 Failure Rate (ρ > 0.75) by Hour",
            xaxis_title="Hour",
            yaxis_title="Failure Rate",
            height=400,
        )
        
        st.plotly_chart(fig_mg1_3, use_container_width=True)
        
        # M/G/1 Costing Analysis
        st.markdown("---")
        st.subheader("💰 M/G/1 Daily Cost Analysis")
        
        costing_mg1_df = pd.DataFrame({
            "hour": mg1_df["scenario_name"],
            "server_cost_₱": mg1_df["servers"] * 87.0,
            "waiting_cost_₱": mg1_df["avg_wq"] * mg1_df["arrival_rate"] * 100.0,
            "abandonment_cost_₱": mg1_df["arrival_rate"] * 0.10 * 60.0,
        })
        
        costing_mg1_df["total_cost_₱"] = (costing_mg1_df["server_cost_₱"] + 
                                          costing_mg1_df["waiting_cost_₱"] + 
                                          costing_mg1_df["abandonment_cost_₱"])
        
        # M/G/1 Costing stacked bar chart
        fig_mg1_cost = go.Figure()
        
        fig_mg1_cost.add_trace(go.Bar(
            x=costing_mg1_df["hour"],
            y=costing_mg1_df["server_cost_₱"],
            name="Server Cost",
            marker_color="rgba(59, 130, 246, 0.7)",
        ))
        
        fig_mg1_cost.add_trace(go.Bar(
            x=costing_mg1_df["hour"],
            y=costing_mg1_df["waiting_cost_₱"],
            name="Waiting Cost",
            marker_color="rgba(244, 63, 94, 0.7)",
        ))
        
        fig_mg1_cost.add_trace(go.Bar(
            x=costing_mg1_df["hour"],
            y=costing_mg1_df["abandonment_cost_₱"],
            name="Abandonment Cost",
            marker_color="rgba(251, 191, 36, 0.7)",
        ))
        
        fig_mg1_cost.update_layout(
            title="M/G/1 Hourly Cost Breakdown (13h Total)",
            xaxis_title="Hour",
            yaxis_title="Cost (₱)",
            barmode="stack",
            height=400,
            hovermode="x unified",
        )
        
        st.plotly_chart(fig_mg1_cost, use_container_width=True)
        
        # M/G/1 Daily totals
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_server_mg1 = costing_mg1_df["server_cost_₱"].sum()
            st.metric("Total Server Cost (13h)", f"₱{total_server_mg1:,.0f}")
        
        with col2:
            total_waiting_mg1 = costing_mg1_df["waiting_cost_₱"].sum()
            st.metric("Total Waiting Cost (13h)", f"₱{total_waiting_mg1:,.0f}")
        
        with col3:
            total_abandon_mg1 = costing_mg1_df["abandonment_cost_₱"].sum()
            st.metric("Total Abandonment Cost (13h)", f"₱{total_abandon_mg1:,.0f}")
        
        with col4:
            total_daily_mg1 = costing_mg1_df["total_cost_₱"].sum()
            st.metric("TOTAL DAILY COST (13h)", f"₱{total_daily_mg1:,.0f}")
        
        # M/G/1 Verdict
        st.markdown("---")
        st.subheader("🎯 M/G/1 13-Hour Verdict")
        
        overall_failure_mg1 = mg1_df["failure_rate"].mean()
        avg_variance_mg1 = mg1_df["service_variance"].mean()
        avg_wq_mg1 = mg1_df["avg_wq"].mean()
        
        if overall_failure_mg1 <= ACCEPTABLE_FAILURE_RATE:
            st.success(f"""
            ✅ **M/G/1 PASSED**
            
            Average failure rate: **{overall_failure_mg1:.2%}** (target: ≤ {ACCEPTABLE_FAILURE_RATE:.0%})
            Average service variance: **{avg_variance_mg1:.4f}**
            Average wait time (Wq): **{avg_wq_mg1:.4f}** minutes
            
            ✨ M/G/1 configuration is robust across the day!
            """)
        else:
            st.warning(f"""
            ⚠️ **M/G/1 NEEDS ADJUSTMENT**
            
            Average failure rate: **{overall_failure_mg1:.2%}** (target: ≤ {ACCEPTABLE_FAILURE_RATE:.0%})
            Average service variance: **{avg_variance_mg1:.4f}**
            
            💡 Consider increasing servers during high-variance periods.
            """)
        
        # M/G/1 Export results
        st.markdown("---")
        st.subheader("💾 Export M/G/1 Results")
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv_mg1_bytes = mg1_df.to_csv(index=False).encode()
            st.download_button(
                "📥 Download CSV (M/G/1 Simulation)",
                csv_mg1_bytes,
                "mg1_13hour_simulation.csv",
                "text/csv",
                key="mg1_csv_download"
            )
        
        with col2:
            try:
                import io
                excel_mg1_buffer = io.BytesIO()
                excel_mg1_writer = pd.ExcelWriter(excel_mg1_buffer, engine='openpyxl')
                mg1_df.to_excel(excel_mg1_writer, index=False, sheet_name="M/G/1 Results")
                costing_mg1_df.to_excel(excel_mg1_writer, index=False, sheet_name="Costing")
                excel_mg1_writer.close()
                excel_mg1_buffer.seek(0)
                
                st.download_button(
                    "📊 Download Excel (M/G/1 Complete)",
                    excel_mg1_buffer.getvalue(),
                    "mg1_13hour_analysis.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="mg1_excel_download"
                )
            except Exception as e:
                st.warning(f"Excel export: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# BATCH COMPARISON
# ─────────────────────────────────────────────────────────────────────────────

else:
    st.subheader("🔄 Batch Comparison - Multiple Scenarios")
    
    st.info("Create multiple scenarios to compare different adjustments side-by-side")
    
    # Initialize session state for batch scenarios
    if "batch_scenarios" not in st.session_state:
        st.session_state.batch_scenarios = []
    
    # Input section
    st.markdown("---")
    st.subheader("➕ Add Scenario")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        batch_scenario_name = st.text_input(
            "Scenario Name",
            value=f"Scenario {len(st.session_state.batch_scenarios) + 1}",
            key=f"batch_name_{len(st.session_state.batch_scenarios)}"
        )
    
    with col2:
        batch_arrival = st.number_input(
            "Arrival Rate (λ)",
            min_value=0.1,
            max_value=100.0,
            value=5.0,
            step=0.1,
            key=f"batch_arrival_{len(st.session_state.batch_scenarios)}"
        )
    
    with col3:
        batch_service = st.number_input(
            "Service Rate (μ)",
            min_value=0.1,
            max_value=100.0,
            value=2.0,
            step=0.1,
            key=f"batch_service_{len(st.session_state.batch_scenarios)}"
        )
    
    with col4:
        batch_servers = st.number_input(
            "Number of Servers (c)",
            min_value=1,
            max_value=20,
            value=3,
            step=1,
            key=f"batch_servers_{len(st.session_state.batch_scenarios)}"
        )
    
    col_batch_btn1, col_batch_btn2 = st.columns(2)
    
    with col_batch_btn1:
        if st.button("➕ Add Scenario", key="btn_add_scenario"):
            new_scenario = {
                "name": batch_scenario_name,
                "arrival_rate": batch_arrival,
                "service_rate": batch_service,
                "servers": batch_servers
            }
            st.session_state.batch_scenarios.append(new_scenario)
            st.success(f"✅ Added: {batch_scenario_name}")
            st.rerun()
    
    # Display added scenarios
    if st.session_state.batch_scenarios:
        st.markdown("---")
        st.subheader("📋 Added Scenarios")
        
        for i, scenario in enumerate(st.session_state.batch_scenarios):
            col_disp1, col_disp2, col_disp3, col_disp4, col_disp_del = st.columns([2, 1.5, 1.5, 1.5, 1])
            
            with col_disp1:
                st.write(f"**{scenario['name']}**")
            
            with col_disp2:
                st.write(f"λ={scenario['arrival_rate']}")
            
            with col_disp3:
                st.write(f"μ={scenario['service_rate']}")
            
            with col_disp4:
                st.write(f"c={scenario['servers']}")
            
            with col_disp_del:
                if st.button("🗑️", key=f"del_scenario_{i}"):
                    st.session_state.batch_scenarios.pop(i)
                    st.rerun()
        
        # Run batch comparison
        st.markdown("---")
        col_batch_run, col_batch_sims = st.columns([3, 1])
        
        with col_batch_run:
            run_batch = st.button("🚀 Run All Scenarios", key="btn_run_batch")
        
        with col_batch_sims:
            batch_num_sims = st.slider(
                "Simulations",
                min_value=10,
                max_value=1000,
                value=NUM_SIMULATIONS,
                step=10,
                key="batch_num_sims"
            )
        
        if run_batch:
            st.info(f"⏳ Running {len(st.session_state.batch_scenarios)} scenarios × {batch_num_sims} sims...")
            
            batch_results = []
            progress_bar = st.progress(0)
            
            for idx, scenario in enumerate(st.session_state.batch_scenarios):
                result = simulate_scenario(
                    arrival_rate=scenario['arrival_rate'],
                    service_rate=scenario['service_rate'],
                    servers=scenario['servers'],
                    num_simulations=batch_num_sims,
                    scenario_name=scenario['name']
                )
                batch_results.append(result)
                progress_bar.progress((idx + 1) / len(st.session_state.batch_scenarios))
            
            st.session_state["batch_results"] = pd.DataFrame(batch_results)
            st.success(f"✅ Comparison complete!")
        
        # Display batch results
        if st.session_state.get("batch_results") is not None:
            st.markdown("---")
            st.subheader("📊 Batch Comparison Results")
            
            batch_df = st.session_state["batch_results"]
            
            # Summary statistics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                avg_util = batch_df["avg_utilization"].mean()
                st.metric("Avg Utilization (All)", f"{avg_util:.1%}")
            
            with col2:
                avg_failure = batch_df["failure_rate"].mean()
                status_badge = "✅ PASS" if avg_failure <= ACCEPTABLE_FAILURE_RATE else "❌ FAIL"
                st.metric("Avg Failure Rate", f"{avg_failure:.1%}", status_badge)
            
            with col3:
                max_util = batch_df["max_utilization"].max()
                st.metric("Peak Utilization", f"{max_util:.1%}")
            
            with col4:
                passed_rows = (batch_df["failure_rate"] <= ACCEPTABLE_FAILURE_RATE).sum()
                pct_pass = (passed_rows / len(batch_df) * 100)
                st.metric("Scenarios Passed", f"{passed_rows}/{len(batch_df)} ({pct_pass:.0f}%)")
            
            # Results table
            batch_styled = batch_df.style.format({
                "arrival_rate": lambda x: format_number(x, 2),
                "service_rate": lambda x: format_number(x, 2),
                "baseline_utilization": lambda x: format_number(x, 4),
                "avg_utilization": lambda x: format_number(x, 4),
                "max_utilization": lambda x: format_number(x, 4),
                "failure_rate": lambda x: format_number(x, 4),
                "avg_wq": lambda x: format_number(x, 4),
            })
            st.dataframe(batch_styled, use_container_width=True)
            
            # Visualizations
            st.markdown("---")
            st.subheader("📉 Visualizations")
            
            # Chart 1: Utilization comparison
            fig1 = make_subplots(
                rows=1, cols=2,
                subplot_titles=("Baseline vs Avg Utilization", "Max Utilization Range")
            )
            
            fig1.add_trace(
                go.Bar(x=batch_df["scenario_name"], y=batch_df["baseline_utilization"],
                       name="Baseline ρ", marker_color="rgba(248, 113, 113, 0.7)"),
                row=1, col=1
            )
            
            fig1.add_trace(
                go.Bar(x=batch_df["scenario_name"], y=batch_df["avg_utilization"],
                       name="Avg ρ", marker_color="rgba(52, 211, 153, 0.7)"),
                row=1, col=1
            )
            
            fig1.add_trace(
                go.Bar(x=batch_df["scenario_name"], y=batch_df["max_utilization"],
                       name="Max ρ", marker_color="rgba(250, 158, 5, 0.7)"),
                row=1, col=2
            )
            
            fig1.add_hline(y=FAILURE_THRESHOLD_UTIL, line_dash="dash", line_color="red",
                          annotation_text="Failure Threshold", row=1, col=1)
            fig1.add_hline(y=FAILURE_THRESHOLD_UTIL, line_dash="dash", line_color="red",
                          row=1, col=2)
            
            fig1.update_yaxes(title_text="Utilization (ρ)", row=1, col=1)
            fig1.update_yaxes(title_text="Utilization (ρ)", row=1, col=2)
            fig1.update_layout(height=400)
            
            st.plotly_chart(fig1, use_container_width=True)
            
            # Chart 2: Failure rates
            fig2 = go.Figure()
            
            fig2.add_trace(go.Bar(
                x=batch_df["scenario_name"],
                y=batch_df["failure_rate"],
                marker_color=["red" if x > ACCEPTABLE_FAILURE_RATE else "green" 
                              for x in batch_df["failure_rate"]],
                text=batch_df["failure_rate"].apply(lambda x: f"{x:.1%}"),
                textposition="outside",
            ))
            
            fig2.add_hline(y=ACCEPTABLE_FAILURE_RATE, line_dash="dash", line_color="orange",
                          annotation_text=f"Acceptable ({ACCEPTABLE_FAILURE_RATE:.0%})")
            
            fig2.update_layout(
                title="Failure Rates by Scenario",
                xaxis_title="Scenario",
                yaxis_title="Failure Rate",
                height=400,
            )
            
            st.plotly_chart(fig2, use_container_width=True)
            
            # Chart 3: Costing comparison
            st.markdown("---")
            st.subheader("💰 Costing Comparison (Hourly)")
            
            costing_batch_df = pd.DataFrame({
                "scenario_name": batch_df["scenario_name"],
                "server_cost_₱": batch_df["servers"] * 87.0,
                "waiting_cost_₱": batch_df["avg_wq"] * batch_df["arrival_rate"] * 100.0,
                "abandonment_cost_₱": batch_df["arrival_rate"] * 0.10 * 60.0,
            })
            
            costing_batch_df["total_cost_₱"] = (costing_batch_df["server_cost_₱"] + 
                                               costing_batch_df["waiting_cost_₱"] + 
                                               costing_batch_df["abandonment_cost_₱"])
            
            # Costing stacked bar chart
            fig3 = go.Figure()
            
            fig3.add_trace(go.Bar(
                x=costing_batch_df["scenario_name"],
                y=costing_batch_df["server_cost_₱"],
                name="Server Cost",
                marker_color="rgba(59, 130, 246, 0.7)",
            ))
            
            fig3.add_trace(go.Bar(
                x=costing_batch_df["scenario_name"],
                y=costing_batch_df["waiting_cost_₱"],
                name="Waiting Cost",
                marker_color="rgba(244, 63, 94, 0.7)",
            ))
            
            fig3.add_trace(go.Bar(
                x=costing_batch_df["scenario_name"],
                y=costing_batch_df["abandonment_cost_₱"],
                name="Abandonment Cost",
                marker_color="rgba(251, 191, 36, 0.7)",
            ))
            
            fig3.update_layout(
                title="Cost Breakdown Comparison",
                xaxis_title="Scenario",
                yaxis_title="Cost (₱)",
                barmode="stack",
                height=400,
                hovermode="x unified",
            )
            
            st.plotly_chart(fig3, use_container_width=True)
            
            # Costing summary metrics
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_server = costing_batch_df["server_cost_₱"].sum()
                st.metric("Total Server Cost", f"₱{total_server:,.0f}")
            
            with col2:
                total_waiting = costing_batch_df["waiting_cost_₱"].sum()
                st.metric("Total Waiting Cost", f"₱{total_waiting:,.0f}")
            
            with col3:
                total_abandon = costing_batch_df["abandonment_cost_₱"].sum()
                st.metric("Total Abandonment Cost", f"₱{total_abandon:,.0f}")
            
            with col4:
                total_cost = costing_batch_df["total_cost_₱"].sum()
                st.metric("TOTAL (All Scenarios)", f"₱{total_cost:,.0f}")
            
            # Export batch results
            st.markdown("---")
            st.subheader("💾 Export Results")
            
            col1, col2 = st.columns(2)
            
            with col1:
                csv_bytes = batch_df.to_csv(index=False).encode()
                st.download_button(
                    "📥 Download CSV (Scenarios)",
                    csv_bytes,
                    "adjustment_scenarios.csv",
                    "text/csv",
                )
            
            with col2:
                try:
                    import io
                    excel_buffer = io.BytesIO()
                    excel_writer = pd.ExcelWriter(excel_buffer, engine='openpyxl')
                    batch_df.to_excel(excel_writer, index=False, sheet_name="Scenarios")
                    costing_batch_df.to_excel(excel_writer, index=False, sheet_name="Costing")
                    excel_writer.close()
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        "📊 Download Excel (All Data)",
                        excel_buffer.getvalue(),
                        "adjustment_comparison.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                except Exception as e:
                    st.warning(f"Excel export: {e}")
