"""Page 3 — Monte Carlo Simulation Engine
🚨 CRITICAL: ONLY use st.session_state["recommended_data"]
✅ 50-100 Monte Carlo simulations per row
✅ Arrival variation: ±10-20%
✅ Service variation: ±10%
✅ Output: failure_rate (util > 0.75), avg_utilization, max_utilization
✅ PASS if failure_rate ≤ 10%

Supported Models:
- M/M/1: Single server Monte Carlo
- M/M/c: Multi-server Monte Carlo with utilization tracking
- M/G/c: General service time Monte Carlo (uses variance from data)
- M/M/c/K: Finite-capacity Monte Carlo approximation (uses K)
- M/G/c/K: Finite-capacity general service approximation (uses variance and K)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from queue_models import mgc, mgck, mmck
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

NUM_SIMULATIONS = 100  # per row
ARRIVAL_VARIANCE_RANGE = (0.80, 1.20)  # ±20%
SERVICE_VARIANCE_RANGE = (0.90, 1.10)  # ±10%
FAILURE_THRESHOLD_UTIL = 0.75  # failure if ρ > this
ACCEPTABLE_FAILURE_RATE = 0.10  # 10%


# ─────────────────────────────────────────────────────────────────────────────
# Monte Carlo Simulation Function
# ─────────────────────────────────────────────────────────────────────────────

def simulate_row(row: pd.Series, num_simulations: int = 100) -> dict:
    """
    Run NUM_SIMULATIONS Monte Carlo trials for a single row.
    
    Input: row with arrival_rate, service_rate, servers
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
    
    lambda_base = row["arrival_rate"]
    mu_base = row["service_rate"]
    c = int(row["servers"])
    variance_base = row.get("variance")
    capacity = row.get("K")
    
    # Validation
    if pd.isna(lambda_base) or pd.isna(mu_base) or pd.isna(c) or c <= 0:
        return {
            "avg_utilization": np.nan,
            "max_utilization": np.nan,
            "failure_count": 0,
            "failure_rate": np.nan,
            "avg_wq": np.nan,
            "status": "INVALID",
        }
    
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
            if capacity is not None and not pd.isna(capacity) and variance_base is not None and not pd.isna(variance_base):
                variance_sim = variance_base * service_factor
                metrics = mgck(lambda_sim, mu_sim, c, variance_sim, int(capacity))
                wq = metrics["Wq"] if metrics.get("stable", False) else np.inf
            elif capacity is not None and not pd.isna(capacity):
                metrics = mmck(lambda_sim, mu_sim, c, int(capacity))
                wq = metrics["Wq"] if metrics.get("stable", False) else np.inf
            elif variance_base is not None and not pd.isna(variance_base):
                variance_sim = variance_base * service_factor
                metrics = mgc(lambda_sim, mu_sim, c, variance_sim)
                wq = metrics["Wq"] if metrics.get("stable", False) else np.inf
            elif utilization < 1.0:
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

st.title("🔁 Page 4: Monte Carlo Simulation")
st.markdown("""
**Run 100 Monte Carlo simulations using ONLY recommended_data**
- 🎲 Introduce variability: arrival ±20%, service ±10%
- 📊 Output: failure_rate (util > 0.75), avg/max utilization  
- ✅ PASS if failure_rate ≤ 10%
""")

# ─────────────────────────────────────────────────────────────────────────────
# PRE-CHECK: Recommended data must exist
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("✅ Dependency Check")

if st.session_state.get("recommended_data") is None:
    st.error("❌ recommended_data NOT found!")
    st.info("""
    👉 **Required:**
    - **Page 1:** Upload and save current data
    - **Page 2:** Run optimization and generate recommendations
    """)
    st.stop()

st.success("✅ recommended_data exists")

# ─────────────────────────────────────────────────────────────────────────────
# CRITICAL: Load ONLY recommended_data
# ─────────────────────────────────────────────────────────────────────────────

simulation_input = st.session_state["recommended_data"].copy()

st.info(f"📌 Using {len(simulation_input)} rows from recommended_data")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    num_sims = st.slider(
        "Simulations per row",
        min_value=10,
        max_value=1000,
        value=NUM_SIMULATIONS,
        step=10,
    )

with col2:
    st.metric("Failure Threshold (ρ)", FAILURE_THRESHOLD_UTIL)

with col3:
    st.metric("Acceptable Failure Rate", f"{ACCEPTABLE_FAILURE_RATE:.0%}")

# ─────────────────────────────────────────────────────────────────────────────
# Run Simulation
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")

if st.button("🚀 Run Simulation", key="run_simulation"):
    st.info(f"⏳ Running {num_sims * len(simulation_input)} simulations...")
    
    results = []
    progress_bar = st.progress(0)
    
    for idx, row in simulation_input.iterrows():
        sim_result = simulate_row(row, num_sims)
        
        result_row = {
            "time_interval": row["time_interval"],
            "arrival_rate": row["arrival_rate"],
            "service_rate": row["service_rate"],
            "servers": row["servers"],
            "baseline_utilization": row["utilization"],
            "sim_avg_utilization": sim_result["avg_utilization"],
            "sim_max_utilization": sim_result["max_utilization"],
            "sim_avg_wq": sim_result["avg_wq"],
            "failure_count": sim_result["failure_count"],
            "failure_rate": sim_result["failure_rate"],
            "status": sim_result["status"],
        }
        results.append(result_row)
        progress_bar.progress((idx + 1) / len(simulation_input))
    
    results_df = pd.DataFrame(results)
    st.session_state["simulation_results"] = results_df
    
    st.success(f"✅ Simulation complete! ({num_sims * len(simulation_input)} total)")

# ─────────────────────────────────────────────────────────────────────────────
# Display Results
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.get("simulation_results") is not None:
    st.markdown("---")
    st.subheader("📊 Simulation Results")
    
    results_df = st.session_state["simulation_results"]
    
    # Summary statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_util = results_df["sim_avg_utilization"].mean()
        st.metric("Avg Utilization", f"{avg_util:.1%}")
    
    with col2:
        avg_failure = results_df["failure_rate"].mean()
        status_badge = "✅ PASS" if avg_failure <= ACCEPTABLE_FAILURE_RATE else "❌ FAIL"
        st.metric("Avg Failure Rate", f"{avg_failure:.1%}", status_badge)
    
    with col3:
        max_util = results_df["sim_max_utilization"].max()
        st.metric("Peak Utilization", f"{max_util:.1%}")
    
    with col4:
        passed_rows = (results_df["failure_rate"] <= ACCEPTABLE_FAILURE_RATE).sum()
        pct_pass = (passed_rows / len(results_df) * 100)
        st.metric("Rows Passed", f"{passed_rows}/{len(results_df)} ({pct_pass:.0f}%)")

    st.markdown("---")
    st.subheader("Presentation Dashboard")

    peak_row = results_df.loc[results_df["failure_rate"].idxmax()]
    verdict = "✅ Staffing Validated" if avg_failure <= ACCEPTABLE_FAILURE_RATE else "⚠️ Needs Review"
    message = (
        f"{passed_rows} of {len(results_df)} intervals passed the simulation. "
        f"Highest risk: {peak_row['time_interval']} at {peak_row['failure_rate']:.1%} failure rate."
    )

    dash_col1, dash_col2 = st.columns([1, 2])
    with dash_col1:
        st.metric("Simulation Verdict", verdict)
        st.metric("Highest Risk Interval", str(peak_row["time_interval"]))
        st.metric("Highest Failure Rate", f"{peak_row['failure_rate']:.1%}")
    with dash_col2:
        if avg_failure <= ACCEPTABLE_FAILURE_RATE:
            st.success(message)
        else:
            st.warning(message)
        st.caption("Use this dashboard as the presentation summary for the simulation page.")    
    # ─────────────────────────────────────────────────────────────────────────────
    # Results Table
    # ─────────────────────────────────────────────────────────────────────────────
    
    results_styled = results_df.style.format({
        "arrival_rate": lambda x: format_number(x, 2),
        "service_rate": lambda x: format_number(x, 2),
        "baseline_utilization": lambda x: format_number(x, 4),
        "sim_avg_utilization": lambda x: format_number(x, 4),
        "sim_max_utilization": lambda x: format_number(x, 4),
        "failure_rate": lambda x: format_number(x, 4),
        "sim_avg_wq": lambda x: format_number(x, 4),
    })
    
    st.dataframe(results_styled, use_container_width=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Visualizations
    # ─────────────────────────────────────────────────────────────────────────────
    
    st.markdown("---")
    st.subheader("📉 Visualizations")
    
    # Chart 1: Utilization Distribution
    fig1 = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Baseline vs Sim Avg", "Simulation Range")
    )
    
    fig1.add_trace(
        go.Bar(x=results_df["time_interval"], y=results_df["baseline_utilization"],
               name="Baseline ρ", marker_color="rgba(248, 113, 113, 0.7)"),
        row=1, col=1
    )
    
    fig1.add_trace(
        go.Bar(x=results_df["time_interval"], y=results_df["sim_avg_utilization"],
               name="Sim Avg ρ", marker_color="rgba(52, 211, 153, 0.7)"),
        row=1, col=1
    )
    
    fig1.add_trace(
        go.Scatter(x=results_df["time_interval"], y=results_df["sim_avg_utilization"],
                   name="Avg", mode="lines", line=dict(color="blue")),
        row=1, col=2
    )
    
    fig1.add_trace(
        go.Scatter(x=results_df["time_interval"], y=results_df["sim_max_utilization"],
                   name="Max", mode="lines", line=dict(color="red")),
        row=1, col=2
    )
    
    fig1.add_hline(y=FAILURE_THRESHOLD_UTIL, line_dash="dash", line_color="orange",
                   annotation_text="Failure Threshold", secondary_y=False)
    
    fig1.update_yaxes(title_text="Utilization (ρ)", row=1, col=1)
    fig1.update_yaxes(title_text="Utilization (ρ)", row=1, col=2)
    fig1.update_layout(height=400)
    
    st.plotly_chart(fig1, use_container_width=True)
    
    # Chart 2: Failure Rate
    fig2 = go.Figure()
    
    fig2.add_trace(go.Bar(
        x=results_df["time_interval"],
        y=results_df["failure_rate"],
        marker_color=["red" if x > ACCEPTABLE_FAILURE_RATE else "green" 
                      for x in results_df["failure_rate"]],
        text=results_df["failure_rate"].apply(lambda x: f"{x:.1%}"),
        textposition="outside",
    ))
    
    fig2.add_hline(y=ACCEPTABLE_FAILURE_RATE, line_dash="dash", line_color="orange",
                   annotation_text=f"Acceptable ({ACCEPTABLE_FAILURE_RATE:.0%})")
    
    fig2.update_layout(
        title="Failure Rate by Time Interval",
        xaxis_title="Time Interval",
        yaxis_title="Failure Rate (ρ > 0.75)",
        height=400,
    )
    
    st.plotly_chart(fig2, use_container_width=True)
    
    # Chart 3: Status Summary
    pass_count = (results_df["failure_rate"] <= ACCEPTABLE_FAILURE_RATE).sum()
    fail_count = len(results_df) - pass_count
    
    fig3 = go.Figure(data=[
        go.Pie(labels=["PASS", "FAIL"], values=[pass_count, fail_count],
               marker=dict(colors=["green", "red"]))
    ])
    
    fig3.update_layout(
        title="Overall Simulation Status",
        height=400,
    )
    
    
    st.plotly_chart(fig3, use_container_width=True)
    
    # Chart 4: Costing Analysis
    st.markdown("---")
    st.subheader("💰 Costing Analysis")
    
    # Calculate costing for each interval
    costing_sim_df_chart = pd.DataFrame({
        "time_interval": results_df["time_interval"],
        "server_cost_₱": results_df["servers"] * 87.0,
        "waiting_cost_₱": results_df["sim_avg_wq"] * results_df["arrival_rate"] * 100.0,
        "abandonment_cost_₱": results_df["arrival_rate"] * 0.10 * 60.0,
    })
    
    costing_sim_df_chart["total_cost_₱"] = (costing_sim_df_chart["server_cost_₱"] + 
                                             costing_sim_df_chart["waiting_cost_₱"] + 
                                             costing_sim_df_chart["abandonment_cost_₱"])
    
    # Costing stacked bar chart
    fig4 = go.Figure()
    
    fig4.add_trace(go.Bar(
        x=costing_sim_df_chart["time_interval"],
        y=costing_sim_df_chart["server_cost_₱"],
        name="Server Cost",
        marker_color="rgba(59, 130, 246, 0.7)",
        text=costing_sim_df_chart["server_cost_₱"].apply(lambda x: f"₱{x:.0f}"),
        textposition="inside",
    ))
    
    fig4.add_trace(go.Bar(
        x=costing_sim_df_chart["time_interval"],
        y=costing_sim_df_chart["waiting_cost_₱"],
        name="Waiting Cost",
        marker_color="rgba(244, 63, 94, 0.7)",
        text=costing_sim_df_chart["waiting_cost_₱"].apply(lambda x: f"₱{x:.0f}"),
        textposition="inside",
    ))
    
    fig4.add_trace(go.Bar(
        x=costing_sim_df_chart["time_interval"],
        y=costing_sim_df_chart["abandonment_cost_₱"],
        name="Abandonment Cost",
        marker_color="rgba(251, 191, 36, 0.7)",
        text=costing_sim_df_chart["abandonment_cost_₱"].apply(lambda x: f"₱{x:.0f}"),
        textposition="inside",
    ))
    
    fig4.update_layout(
        title="Cost Breakdown by Time Interval (Hourly)",
        xaxis_title="Time Interval",
        yaxis_title="Cost (₱)",
        barmode="stack",
        height=400,
        hovermode="x unified",
    )
    
    st.plotly_chart(fig4, use_container_width=True)
    
    # Costing summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_server = costing_sim_df_chart["server_cost_₱"].sum()
        st.metric("Total Server Cost", f"₱{total_server:,.0f}")
    
    with col2:
        total_waiting = costing_sim_df_chart["waiting_cost_₱"].sum()
        st.metric("Total Waiting Cost", f"₱{total_waiting:,.0f}")
    
    with col3:
        total_abandon = costing_sim_df_chart["abandonment_cost_₱"].sum()
        st.metric("Total Abandonment Cost", f"₱{total_abandon:,.0f}")
    
    with col4:
        total_cost = costing_sim_df_chart["total_cost_₱"].sum()
        st.metric("TOTAL DAILY COST", f"₱{total_cost:,.0f}")
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Overall Verdict
    # ─────────────────────────────────────────────────────────────────────────────
    
    st.markdown("---")
    st.subheader("🎯 Final Verdict")
    
    overall_failure_rate = results_df["failure_rate"].mean()
    
    if overall_failure_rate <= ACCEPTABLE_FAILURE_RATE:
        st.success(f"""
        ✅ **SIMULATION PASSED**
        
        Overall failure rate: **{overall_failure_rate:.2%}** (target: ≤ {ACCEPTABLE_FAILURE_RATE:.0%})
        
        ✨ The recommended configuration is robust and safe for deployment.
        """)
    else:
        st.error(f"""
        ❌ **SIMULATION FAILED**
        
        Overall failure rate: **{overall_failure_rate:.2%}** (target: ≤ {ACCEPTABLE_FAILURE_RATE:.0%})
        
        ⚠️ Recommend returning to **Page 2** to adjust optimization parameters.
        """)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Export Results
    # ─────────────────────────────────────────────────────────────────────────────
    
    st.markdown("---")
    st.subheader("💾 Export Simulation Results")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv_bytes = results_df.to_csv(index=False).encode()
        st.download_button(
            "📥 Download CSV",
            csv_bytes,
            "simulation_results.csv",
            "text/csv",
        )
    
    with col2:
        try:
            import io
            excel_buffer = io.BytesIO()
            excel_writer = pd.ExcelWriter(excel_buffer, engine='openpyxl')
            results_df.to_excel(excel_writer, index=False, sheet_name="Simulation")
            excel_writer.close()
            excel_buffer.seek(0)
            
            st.download_button(
                "📊 Download Excel (Simulation)",
                excel_buffer.getvalue(),
                "simulation_results.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.warning(f"Excel export: {e}")
    
    with col3:
        # Create Excel file for costing breakdown with simulation
        try:
            import io
            
            # Prepare costing breakdown DataFrame
            # For simulation, we calculate costing based on:
            # - Server cost: servers × ₱87
            # - Waiting cost: sim_avg_wq × λ × ₱100
            # - Abandonment cost: λ × 0.10 × ₱60
            
            costing_sim_df = pd.DataFrame({
                "time_interval": results_df["time_interval"],
                "arrival_rate": results_df["arrival_rate"],
                "service_rate": results_df["service_rate"],
                "servers": results_df["servers"],
                "sim_avg_utilization": results_df["sim_avg_utilization"],
                "sim_avg_wq_hours": results_df["sim_avg_wq"],
                "server_cost_₱": results_df["servers"] * 87.0,
                "waiting_cost_₱": results_df["sim_avg_wq"] * results_df["arrival_rate"] * 100.0,
                "abandonment_cost_₱": results_df["arrival_rate"] * 0.10 * 60.0,
                "failure_rate": results_df["failure_rate"],
                "status": results_df["status"],
            })
            
            costing_sim_df["total_cost_₱"] = (costing_sim_df["server_cost_₱"] + 
                                               costing_sim_df["waiting_cost_₱"] + 
                                               costing_sim_df["abandonment_cost_₱"])
            
            costing_sim_buffer = io.BytesIO()
            costing_sim_writer = pd.ExcelWriter(costing_sim_buffer, engine='openpyxl')
            
            # Sheet 1: Detailed costing with simulation results
            costing_sim_df.to_excel(costing_sim_writer, index=False, sheet_name="Costing Detail")
            
            # Sheet 2: Costing summary
            pass_count = (results_df["status"] == "✅ PASS").sum()
            fail_count = (results_df["status"] == "❌ FAIL").sum()
            
            summary_sim_data = {
                "Metric": [
                    "Total Server Cost",
                    "Total Waiting Cost (from Wq)",
                    "Total Abandonment Cost",
                    "TOTAL DAILY COST",
                    "—",
                    "Pass (≤10% failure)",
                    "Fail (>10% failure)",
                    "Pass Rate"
                ],
                "Amount": [
                    f"₱{costing_sim_df['server_cost_₱'].sum():,.0f}",
                    f"₱{costing_sim_df['waiting_cost_₱'].sum():,.0f}",
                    f"₱{costing_sim_df['abandonment_cost_₱'].sum():,.0f}",
                    f"₱{costing_sim_df['total_cost_₱'].sum():,.0f}",
                    "—",
                    f"{pass_count} intervals",
                    f"{fail_count} intervals",
                    f"{(pass_count / len(results_df) * 100):.1f}%"
                ]
            }
            summary_sim_df = pd.DataFrame(summary_sim_data)
            summary_sim_df.to_excel(costing_sim_writer, index=False, sheet_name="Summary")
            
            costing_sim_writer.close()
            costing_sim_buffer.seek(0)
            
            st.download_button(
                "💰 Download Excel (Costing)",
                costing_sim_buffer.getvalue(),
                "simulation_costing_analysis.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.warning(f"⚠️ Costing export: {e}")
    
    st.info("✅ Simulation analysis complete!")
