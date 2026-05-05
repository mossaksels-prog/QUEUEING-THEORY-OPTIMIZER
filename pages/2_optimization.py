"""
Page 2 — Optimization Engine
✅ Load current_data from session state
✅ Algorithm: for each row, while utilization >= 0.70, increment servers
✅ Recompute ALL metrics  
✅ Store in st.session_state["recommended_data"]
✅ Display cost analysis (Cₛ, Cw, Ca)
✅ Export to Excel
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys

# Import utils safely
sys.path.insert(0, ".")
from utils import compute_costs
from queue_models import mmc

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

UTILIZATION_TARGET = 0.70
PEAK_UTILIZATION_THRESHOLD = 0.80
MAX_SERVERS = 20  # Safety limit


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
# Helper: Compute M/M/c metrics
# ─────────────────────────────────────────────────────────────────────────────


def compute_mmc_metrics(lambda_: float, mu: float, c: int) -> dict:
    """Compute M/M/c queue metrics using correct formula."""
    if lambda_ < 0 or mu <= 0 or c <= 0:
        return {
            "utilization": np.nan,
            "Lq": np.nan,
            "Wq": np.nan,
            "Ls": np.nan,
            "Ws": np.nan,
        }
    
    # Use queue_models.mmc() for correct M/M/c calculation
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
# OPTIMIZATION ALGORITHM
# ─────────────────────────────────────────────────────────────────────────────

def optimize_row(row: pd.Series) -> pd.Series:
    """
    Optimize a single row: increment servers until utilization < UTILIZATION_TARGET.
    
    RULES:
    - Do NOT change arrival_rate or service_rate
    - Only modify servers
    - Recompute ALL metrics
    - Safety: max 20 servers
    """
    optimized = row.copy()
    
    lambda_ = row["arrival_rate"]
    mu = row["service_rate"]
    servers = int(row["servers"])
    
    # Safety validation
    if pd.isna(lambda_) or pd.isna(mu) or pd.isna(servers):
        return optimized
    
    # Increment servers until target utilization reached
    iteration = 0
    while servers < MAX_SERVERS:
        metrics = compute_mmc_metrics(lambda_, mu, servers)
        current_util = metrics["utilization"]
        
        if pd.isna(current_util) or current_util < UTILIZATION_TARGET:
            break
        
        servers += 1
        iteration += 1
        
        if iteration > 50:  # Safety break
            st.warning(f"⚠️ Optimization loop limit hit for {row.get('time_interval')}")
            break
    
    # Final computation
    final_metrics = compute_mmc_metrics(lambda_, mu, servers)
    
    # Update row
    optimized["servers"] = servers
    for key in ["utilization", "Lq", "Wq", "Ls", "Ws"]:
        optimized[key] = final_metrics[key]
    
    return optimized


# ─────────────────────────────────────────────────────────────────────────────
# Main UI
# ─────────────────────────────────────────────────────────────────────────────

st.title("⚙️ Page 2: Optimization Engine")
st.markdown("""
**Objective:** Reduce utilization to target ρ < 0.70
- 🔒 Do NOT change: arrival_rate, service_rate
- ✏️ Only modify: servers (increment until target reached)
- 🔄 Recompute: all metrics (utilization, Lq, Wq, Ls, Ws)
""")

# ─────────────────────────────────────────────────────────────────────────────
# Pre-check: Current data must exist
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.get("current_data") is None:
    st.error("❌ Current data not found!")
    st.info("👉 Please complete **Page 1** first to upload and validate data.")
    st.stop()

current_data = st.session_state["current_data"].copy()

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("⚙️ Configuration & Costing")

# Configuration tabs
config_tab1, config_tab2 = st.tabs(["Optimization Settings", "Costing Settings"])

with config_tab1:
    col1, col2, col3 = st.columns(3)

    with col1:
        target_util = st.slider(
            "Target Utilization (ρ)",
            min_value=0.50,
            max_value=0.90,
            value=UTILIZATION_TARGET,
            step=0.05,
            help="Stop incrementing servers when utilization falls below this"
        )

    with col2:
        st.metric("Peak Threshold", f"{PEAK_UTILIZATION_THRESHOLD:.0%}")

    with col3:
        st.metric("Max Servers", MAX_SERVERS)

with config_tab2:
    st.markdown("**Adjust costing parameters for this analysis:**")
    
    col_c1, col_c2, col_c3 = st.columns(3)
    
    with col_c1:
        cost_per_server_hr = st.number_input(
            "💼 Cost per Cashier (₱/hr)",
            min_value=10.0,
            max_value=500.0,
            value=st.session_state.get("cost_per_server_hr", 87.0),
            step=1.0,
            help="Hourly wage for one cashier/server",
            key="cost_server_p2"
        )
        st.session_state["cost_per_server_hr"] = cost_per_server_hr
    
    with col_c2:
        cost_per_wait_hr = st.number_input(
            "⏳ Cost of Customer Wait (₱/hr)",
            min_value=10.0,
            max_value=500.0,
            value=st.session_state.get("cost_per_wait_hr", 100.0),
            step=1.0,
            help="Opportunity cost of customer time",
            key="cost_wait_p2"
        )
        st.session_state["cost_per_wait_hr"] = cost_per_wait_hr
    
    with col_c3:
        cost_per_abandonment = st.number_input(
            "❌ Cost per Abandon (₱)",
            min_value=10.0,
            max_value=500.0,
            value=st.session_state.get("cost_per_abandonment", 60.0),
            step=1.0,
            help="Cost of lost customer",
            key="cost_abandon_p2"
        )
        st.session_state["cost_per_abandonment"] = cost_per_abandonment
    
    # Show current cost summary from settings
    st.markdown("---")
    st.markdown("**Current Costing Model:**")
    summary_col1, summary_col2, summary_col3 = st.columns(3)
    
    with summary_col1:
        st.metric("Cₛ (Cashier)", f"₱{cost_per_server_hr:.0f}/hr", "per server/hr")
    
    with summary_col2:
        st.metric("Cw (Wait)", f"₱{cost_per_wait_hr:.0f}/hr", "per hour waiting")
    
    with summary_col3:
        st.metric("Ca (Abandon)", f"₱{cost_per_abandonment:.0f}", "per customer lost")

# ─────────────────────────────────────────────────────────────────────────────
# Run Optimization
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")

if st.button("🚀 Run Optimization", key="run_optimization"):
    st.info("⏳ Optimizing...")
    
    recommended_data = current_data.copy()
    progress_bar = st.progress(0)
    
    for idx, row in recommended_data.iterrows():
        optimized_row = optimize_row(row)
        recommended_data.iloc[idx] = optimized_row
        progress_bar.progress((idx + 1) / len(recommended_data))
    
    st.session_state["recommended_data"] = recommended_data
    st.success("✅ Optimization complete!")

# ─────────────────────────────────────────────────────────────────────────────
# Display Recommendations
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.get("recommended_data") is not None:
    st.markdown("---")
    st.subheader("📊 Recommended Configuration")
    
    rec_data = st.session_state["recommended_data"]
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_util = rec_data["utilization"].mean()
        st.metric("Avg Utilization", f"{avg_util:.1%}")
    
    with col2:
        max_util = rec_data["utilization"].max()
        st.metric("Max Utilization", f"{max_util:.1%}")
    
    with col3:
        total_servers = rec_data["servers"].sum()
        current_servers = current_data["servers"].sum()
        delta = total_servers - current_servers
        st.metric("Total Servers (Δ)", f"{total_servers} ({delta:+d})")
    
    with col4:
        rows_improved = (rec_data["utilization"] < current_data["utilization"]).sum()
        st.metric("Rows Improved", f"{rows_improved}/{len(rec_data)}")
    
    # Comparison table
    comparison = pd.DataFrame({
        "time_interval": rec_data["time_interval"],
        "Current Servers": current_data["servers"],
        "Recommended Servers": rec_data["servers"],
        "Server Delta": rec_data["servers"] - current_data["servers"],
        "Current ρ": current_data["utilization"].round(3),
        "Recommended ρ": rec_data["utilization"].round(3),
        "ρ Delta": (rec_data["utilization"] - current_data["utilization"]).round(3),
    })
    
    # Style comparison table - highlight changes
    def highlight_changes(row):
        colors = [''] * len(row)
        server_delta = row["Server Delta"]
        rho_delta = row["ρ Delta"]
        
        if server_delta != 0:
            # Highlight Server Delta and Recommended Servers columns in yellow
            colors[3] = 'background-color: #FFF4A3'
            colors[2] = 'background-color: #FFF4A3'
        
        if abs(rho_delta) > 0.01:
            # Highlight ρ Delta and Recommended ρ columns in light blue
            colors[6] = 'background-color: #B3E5FC'
            colors[5] = 'background-color: #B3E5FC'
        
        return colors
    
    # Format numeric columns to remove trailing zeros, then apply styling
    styled_comparison = (comparison.style
        .apply(highlight_changes, axis=1)
        .format({'Current ρ': lambda x: format_number(x, 3),
                 'Recommended ρ': lambda x: format_number(x, 3),
                 'ρ Delta': lambda x: format_number(x, 3)})
    )
    st.dataframe(styled_comparison, use_container_width=True)
    
    # Full data view (debug only - collapsed by default)
    with st.expander("🔧 Debug: Full Recommended Data", expanded=False):
        st.caption("Detailed raw data for troubleshooting only")
        st.dataframe(rec_data, use_container_width=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # COST ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────────
    
    st.markdown("---")
    st.subheader("💰 Cost Analysis")
    st.markdown("""
    **Costing Model (NOVAMART):**
    - **Cₛ = ₱87/hr** — Cashier salary (flat wage)
    - **Cw = ₱100/hr** — Customer wait opportunity cost
    - **Ca = ₱60/customer** — Abandonment cost (10% × ₱600 basket)
    """)
    
    # Get costing parameters from session state
    cost_per_server_hr = st.session_state.get("cost_per_server_hr", 87.0)
    cost_per_wait_hr = st.session_state.get("cost_per_wait_hr", 100.0)
    cost_per_abandonment = st.session_state.get("cost_per_abandonment", 60.0)
    
    # Compute costs for current and recommended
    current_costs = []
    recommended_costs = []
    
    for idx, row in current_data.iterrows():
        cost_row = compute_costs(
            row,
            cost_per_server_hr=cost_per_server_hr,
            cost_per_wait_hr=cost_per_wait_hr,
            cost_per_abandonment=cost_per_abandonment
        )
        current_costs.append(cost_row)
    
    for idx, row in rec_data.iterrows():
        cost_row = compute_costs(
            row,
            cost_per_server_hr=cost_per_server_hr,
            cost_per_wait_hr=cost_per_wait_hr,
            cost_per_abandonment=cost_per_abandonment
        )
        recommended_costs.append(cost_row)
    
    current_df = pd.DataFrame(current_costs)
    recommended_df = pd.DataFrame(recommended_costs)
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        current_total = current_df["total_cost"].sum()
        st.metric("Current Total Cost", f"₱{current_total:,.2f}")
    
    with col2:
        recommended_total = recommended_df["total_cost"].sum()
        st.metric("Recommended Total Cost", f"₱{recommended_total:,.2f}")
    
    with col3:
        savings_total = current_total - recommended_total
        savings_pct = (savings_total / current_total * 100) if current_total > 0 else 0
        delta_color = "🟢" if savings_total > 0 else "🔴"
        st.metric("Total Savings", f"{delta_color} ₱{savings_total:,.2f}", f"{savings_pct:.1f}%")
    
    with col4:
        monthly_savings = savings_total * 30
        st.metric("Monthly Savings (30d)", f"₱{monthly_savings:,.2f}")
    
    # Cost breakdown
    st.markdown("#### Cost Breakdown by Component")
    
    cost_comparison = pd.DataFrame({
        "time_interval": rec_data["time_interval"],
        "Current Servers": current_data["servers"],
        "Current Server Cost": current_df["server_cost"].round(2),
        "Current Wait Cost": current_df["wait_cost"].round(2),
        "Current Abandon Cost": current_df["abandonment_cost"].round(2),
        "Current Total": current_df["total_cost"].round(2),
        "Recommended Servers": rec_data["servers"],
        "Recommended Server Cost": recommended_df["server_cost"].round(2),
        "Recommended Wait Cost": recommended_df["wait_cost"].round(2),
        "Recommended Abandon Cost": recommended_df["abandonment_cost"].round(2),
        "Recommended Total": recommended_df["total_cost"].round(2),
        "Cost Savings": (current_df["total_cost"] - recommended_df["total_cost"]).round(2),
    })
    
    # Style cost comparison table - highlight significant savings
    def highlight_cost_savings(row):
        colors = [''] * len(row)
        cost_savings = row["Cost Savings"]
        
        # Green highlight for cost savings > 100
        if cost_savings > 100:
            colors[-1] = 'background-color: #C8E6C9'  # Light green
            colors[-2] = 'background-color: #C8E6C9'  # Recommended Total
        # Yellow highlight for moderate savings 10-100
        elif cost_savings > 10:
            colors[-1] = 'background-color: #FFF9C4'  # Light yellow
            colors[-2] = 'background-color: #FFF9C4'  # Recommended Total
        
        return colors
    
    # Format numeric columns to remove trailing zeros, then apply styling
    # Format numeric columns with 2 decimal places
    cost_columns_to_format = {
        'Current Server Cost': '{:.2f}',
        'Current Wait Cost': '{:.2f}',
        'Current Abandon Cost': '{:.2f}',
        'Current Total': '{:.2f}',
        'Recommended Server Cost': '{:.2f}',
        'Recommended Wait Cost': '{:.2f}',
        'Recommended Abandon Cost': '{:.2f}',
        'Recommended Total': '{:.2f}',
        'Cost Savings': '{:.2f}',
    }
    
    styled_cost = (cost_comparison.style
        .apply(highlight_cost_savings, axis=1)
        .format(cost_columns_to_format)
    )
    st.dataframe(styled_cost, use_container_width=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Export to Excel
    # ─────────────────────────────────────────────────────────────────────────────
    
    st.markdown("---")
    st.subheader("💾 Export Recommendations")
    
    # Prepare costing breakdown DataFrame
    try:
        costing_df = pd.DataFrame({
            "time_interval": rec_data["time_interval"],
            "arrival_rate": rec_data["arrival_rate"],
            "service_rate": rec_data["service_rate"],
            "servers": rec_data["servers"],
            "utilization": rec_data["utilization"],
            "Wq (hours)": rec_data["Wq"],
            "server_cost_₱": rec_data.get("servers", 0) * 87.0,
            "waiting_cost_₱": rec_data.get("Wq", 0) * rec_data.get("arrival_rate", 0) * 100.0,
            "abandonment_cost_₱": rec_data.get("arrival_rate", 0) * 0.10 * 60.0,
        })
        costing_df["total_cost_₱"] = (costing_df["server_cost_₱"] + 
                                       costing_df["waiting_cost_₱"] + 
                                       costing_df["abandonment_cost_₱"])
    except Exception as e:
        st.warning(f"⚠️ Costing calculation: {e}")
        costing_df = rec_data
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        csv_bytes = rec_data.to_csv(index=False).encode()
        st.download_button(
            "📥 Download CSV",
            csv_bytes,
            "recommended_data.csv",
            "text/csv",
        )
    
    with col2:
        # Create Excel file for recommendations
        try:
            import io
            excel_buffer = io.BytesIO()
            excel_writer = pd.ExcelWriter(excel_buffer, engine='openpyxl')
            rec_data.to_excel(excel_writer, index=False, sheet_name="Recommended")
            excel_writer.close()
            excel_buffer.seek(0)
            
            st.download_button(
                "📊 Download Excel (Optimization)",
                excel_buffer.getvalue(),
                "recommended_optimized_data.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.warning(f"⚠️ Excel export: {e}")
    
    with col3:
        # Create Excel file for costing breakdown
        try:
            import io
            costing_buffer = io.BytesIO()
            costing_writer = pd.ExcelWriter(costing_buffer, engine='openpyxl')
            
            # Sheet 1: Detailed costing
            costing_df.to_excel(costing_writer, index=False, sheet_name="Costing Detail")
            
            # Sheet 2: Costing summary
            summary_data = {
                "Metric": [
                    "Total Server Cost",
                    "Total Waiting Cost",
                    "Total Abandonment Cost",
                    "TOTAL DAILY COST"
                ],
                "Amount (₱)": [
                    costing_df["server_cost_₱"].sum(),
                    costing_df["waiting_cost_₱"].sum(),
                    costing_df["abandonment_cost_₱"].sum(),
                    costing_df["total_cost_₱"].sum()
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(costing_writer, index=False, sheet_name="Summary")
            
            costing_writer.close()
            costing_buffer.seek(0)
            
            st.download_button(
                "💰 Download Excel (Costing)",
                costing_buffer.getvalue(),
                "costing_analysis.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.warning(f"⚠️ Costing export: {e}")
    
    with col4:
        st.info("✅ Ready for Page 3")
