"""Page 4 — Comparison (Error-Safe Merge)
✅ Pre-check: current_data exists
✅ Pre-check: recommended_data exists  
✅ Safe merge with suffixes
✅ Calculate delta metrics for all models
✅ Cost analysis and comparison
✅ Visualize improvements

Supported Comparisons:
- M/M/1 vs M/M/1: Single server improvements
- M/M/c vs M/M/c: Multi-server optimization results
- M/G/1 vs M/G/1: General service time comparison (with variance)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys

# Import utils safely
sys.path.insert(0, ".")
from utils import compute_costs

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
# Main UI
# ─────────────────────────────────────────────────────────────────────────────

st.title("📈 Page 3: Comparison")
st.markdown("""
**Safe merge of Current vs Recommended data with delta metrics**
- 🔀 Inner merge on time_interval
- 📊 Compare utilization, servers, and queue metrics
- 📉 Visualize improvements
""")

# ─────────────────────────────────────────────────────────────────────────────
# PRE-CHECK (MANDATORY)
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("✅ Dependency Check")

col1, col2 = st.columns(2)

# Check 1: current_data exists
with col1:
    if st.session_state.get("current_data") is None:
        st.error("❌ current_data NOT found")
        current_exists = False
    else:
        st.success("✅ current_data exists")
        current_exists = True

# Check 2: recommended_data exists
with col2:
    if st.session_state.get("recommended_data") is None:
        st.error("❌ recommended_data NOT found")
        recommended_exists = False
    else:
        st.success("✅ recommended_data exists")
        recommended_exists = True

# STOP if dependencies not met
if not (current_exists and recommended_exists):
    st.error("❌ Cannot proceed — missing upstream data!")
    st.info("""
    👉 **Required:**
    - **Page 1:** Upload and save current data
    - **Page 2:** Run optimization and generate recommendations
    """)
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# SAFE MERGE (with suffixes)
# ─────────────────────────────────────────────────────────────────────────────

current_data = st.session_state["current_data"].copy()
recommended_data = st.session_state["recommended_data"].copy()

try:
    # Inner merge on time_interval
    comparison_df = pd.merge(
        current_data,
        recommended_data,
        on="time_interval",
        how="inner",
        suffixes=("_current", "_recommended")
    )
    
    st.success(f"✅ Merged {len(comparison_df)} rows")
    
    # Store in session state
    st.session_state["comparison_data"] = comparison_df
    
except Exception as e:
    st.error(f"❌ Merge failed: {e}")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# CALCULATE DELTA METRICS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📊 Delta Metrics")

# Create summary stats
deltas = pd.DataFrame({
    "Metric": [
        "Servers",
        "Utilization (ρ)",
        "Queue Length (Lq)",
        "Wait Time (Wq)",
        "System Length (Ls)",
        "System Time (Ws)",
    ],
    "Current": [
        comparison_df["servers_current"].mean(),
        comparison_df["utilization_current"].mean(),
        comparison_df["Lq_current"].mean(),
        comparison_df["Wq_current"].mean(),
        comparison_df["Ls_current"].mean(),
        comparison_df["Ws_current"].mean(),
    ],
    "Recommended": [
        comparison_df["servers_recommended"].mean(),
        comparison_df["utilization_recommended"].mean(),
        comparison_df["Lq_recommended"].mean(),
        comparison_df["Wq_recommended"].mean(),
        comparison_df["Ls_recommended"].mean(),
        comparison_df["Ws_recommended"].mean(),
    ]
})

deltas["Δ (Rec - Current)"] = deltas["Recommended"] - deltas["Current"]
deltas["% Change"] = (deltas["Δ (Rec - Current)"] / deltas["Current"] * 100).round(2)

st.dataframe(deltas, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# KEY INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("🎯 Key Insights")

col1, col2, col3, col4 = st.columns(4)

with col1:
    total_servers_current = comparison_df["servers_current"].sum()
    total_servers_recommended = comparison_df["servers_recommended"].sum()
    server_delta = total_servers_recommended - total_servers_current
    st.metric(
        "Server Count (Δ)",
        f"{total_servers_recommended}",
        f"{server_delta:+d}",
        delta_color="inverse"  # Green if negative (cost reduction)
    )

with col2:
    util_current = comparison_df["utilization_current"].mean()
    util_recommended = comparison_df["utilization_recommended"].mean()
    util_delta = util_recommended - util_current
    st.metric(
        "Avg Utilization (Δ)",
        f"{util_recommended:.1%}",
        f"{util_delta:+.1%}",
        delta_color="inverse"  # Green if negative (better)
    )

with col3:
    wq_current = comparison_df["Wq_current"].mean()
    wq_recommended = comparison_df["Wq_recommended"].mean()
    wq_delta = wq_recommended - wq_current
    st.metric(
        "Avg Wait Time (Δ)",
        f"{wq_recommended:.3f}",
        f"{wq_delta:+.3f}",
        delta_color="inverse"  # Green if negative (faster)
    )

with col4:
    rows_improved = (comparison_df["utilization_recommended"] < comparison_df["utilization_current"]).sum()
    pct_improved = (rows_improved / len(comparison_df) * 100)
    st.metric(
        "Intervals Improved",
        f"{rows_improved}/{len(comparison_df)}",
        f"{pct_improved:.0f}%"
    )

# ─────────────────────────────────────────────────────────────────────────────
# COST ANALYSIS (NEW)
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("💰 Cost Analysis & Savings")
st.markdown("""
**Costing Model (NOVAMART):**
- **Cₛ = ₱87/hr** — Cashier salary
- **Cw = ₱100/hr** — Customer wait opportunity cost  
- **Ca = ₱60/customer** — Abandonment cost (10% × ₱600 basket)
""")

# Get costing parameters from session state
cost_per_server_hr = st.session_state.get("cost_per_server_hr", 87.0)
cost_per_wait_hr = st.session_state.get("cost_per_wait_hr", 100.0)
cost_per_abandonment = st.session_state.get("cost_per_abandonment", 60.0)

# Rebuild current_data and recommended_data from comparison_df for cost calculation
current_data_for_cost = current_data.copy()
recommended_data_for_cost = recommended_data.copy()

# Compute costs
current_costs = []
recommended_costs = []

for idx, row in current_data_for_cost.iterrows():
    cost_row = compute_costs(
        row,
        cost_per_server_hr=cost_per_server_hr,
        cost_per_wait_hr=cost_per_wait_hr,
        cost_per_abandonment=cost_per_abandonment
    )
    current_costs.append(cost_row)

for idx, row in recommended_data_for_cost.iterrows():
    cost_row = compute_costs(
        row,
        cost_per_server_hr=cost_per_server_hr,
        cost_per_wait_hr=cost_per_wait_hr,
        cost_per_abandonment=cost_per_abandonment
    )
    recommended_costs.append(cost_row)

current_df = pd.DataFrame(current_costs)
recommended_df = pd.DataFrame(recommended_costs)

# Cost summary metrics
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    current_total = current_df["total_cost"].sum()
    st.metric("Current Total Cost (24h)", f"₱{current_total:,.2f}")

with col2:
    recommended_total = recommended_df["total_cost"].sum()
    st.metric("Recommended Total Cost (24h)", f"₱{recommended_total:,.2f}")

with col3:
    savings_daily = current_total - recommended_total
    savings_pct = (savings_daily / current_total * 100) if current_total > 0 else 0
    delta_color = "🟢" if savings_daily > 0 else "🔴"
    st.metric("Period Savings", f"{delta_color} ₱{savings_daily:,.2f}", f"{savings_pct:.1f}%")

with col4:
    savings_monthly = savings_daily * 30
    st.metric("Monthly Savings (30d)", f"₱{savings_monthly:,.2f}")

with col5:
    savings_annual = savings_daily * 347
    st.metric("Annual Savings (347d)", f"₱{savings_annual:,.2f}")

# Cost breakdown component analysis
st.markdown("#### Cost Component Breakdown")

component_current = {
    "Server Cost": current_df["server_cost"].sum(),
    "Wait Cost": current_df["wait_cost"].sum(),
    "Abandonment Cost": current_df["abandonment_cost"].sum(),
}

component_recommended = {
    "Server Cost": recommended_df["server_cost"].sum(),
    "Wait Cost": recommended_df["wait_cost"].sum(),
    "Abandonment Cost": recommended_df["abandonment_cost"].sum(),
}

component_df = pd.DataFrame({
    "Component": list(component_current.keys()),
    "Current (₱)": list(component_current.values()),
    "Recommended (₱)": list(component_recommended.values()),
    "Savings (₱)": [component_current[k] - component_recommended[k] for k in component_current.keys()],
})

st.dataframe(component_df, use_container_width=True)

# Cost breakdown chart
fig_cost = go.Figure()

fig_cost.add_trace(go.Bar(
    name="Current",
    x=component_df["Component"],
    y=component_df["Current (₱)"],
    marker_color="rgba(248, 113, 113, 0.7)",
))

fig_cost.add_trace(go.Bar(
    name="Recommended",
    x=component_df["Component"],
    y=component_df["Recommended (₱)"],
    marker_color="rgba(52, 211, 153, 0.7)",
))

fig_cost.update_layout(
    title="Cost Breakdown: Current vs Recommended",
    xaxis_title="Cost Component",
    yaxis_title="Cost (₱)",
    barmode="group",
    height=400,
)

st.plotly_chart(fig_cost, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# VISUALIZATIONS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📉 Visualizations")

# Chart 1: Utilization Comparison
fig1 = go.Figure()

fig1.add_trace(go.Bar(
    x=comparison_df["time_interval"],
    y=comparison_df["utilization_current"],
    name="Current ρ",
    marker_color="rgba(248, 113, 113, 0.7)",
))

fig1.add_trace(go.Bar(
    x=comparison_df["time_interval"],
    y=comparison_df["utilization_recommended"],
    name="Recommended ρ",
    marker_color="rgba(52, 211, 153, 0.7)",
))

fig1.add_hline(y=0.70, line_dash="dash", line_color="yellow", annotation_text="Target (0.70)")
fig1.add_hline(y=0.80, line_dash="dash", line_color="red", annotation_text="Peak (0.80)")

fig1.update_layout(
    title="Utilization: Current vs Recommended",
    xaxis_title="Time Interval",
    yaxis_title="Utilization (ρ)",
    barmode="group",
    height=400,
)

st.plotly_chart(fig1, use_container_width=True)

# Chart 2: Server Allocation
fig2 = go.Figure()

fig2.add_trace(go.Bar(
    x=comparison_df["time_interval"],
    y=comparison_df["servers_current"],
    name="Current Servers",
    marker_color="rgba(248, 113, 113, 0.7)",
))

fig2.add_trace(go.Bar(
    x=comparison_df["time_interval"],
    y=comparison_df["servers_recommended"],
    name="Recommended Servers",
    marker_color="rgba(52, 211, 153, 0.7)",
))

fig2.update_layout(
    title="Server Allocation: Current vs Recommended",
    xaxis_title="Time Interval",
    yaxis_title="Number of Servers",
    barmode="group",
    height=400,
)

st.plotly_chart(fig2, use_container_width=True)

# Chart 3: Queue Metrics
fig3 = make_subplots(
    rows=1, cols=2,
    subplot_titles=("Avg Queue Length (Lq)", "Avg Wait Time (Wq)")
)

fig3.add_trace(
    go.Bar(x=comparison_df["time_interval"], y=comparison_df["Lq_current"], 
           name="Current Lq", marker_color="rgba(248, 113, 113, 0.7)"),
    row=1, col=1
)

fig3.add_trace(
    go.Bar(x=comparison_df["time_interval"], y=comparison_df["Lq_recommended"], 
           name="Recommended Lq", marker_color="rgba(52, 211, 153, 0.7)"),
    row=1, col=1
)

fig3.add_trace(
    go.Bar(x=comparison_df["time_interval"], y=comparison_df["Wq_current"], 
           name="Current Wq", marker_color="rgba(248, 113, 113, 0.7)", showlegend=False),
    row=1, col=2
)

fig3.add_trace(
    go.Bar(x=comparison_df["time_interval"], y=comparison_df["Wq_recommended"], 
           name="Recommended Wq", marker_color="rgba(52, 211, 153, 0.7)", showlegend=False),
    row=1, col=2
)

fig3.update_yaxes(title_text="Lq (customers)", row=1, col=1)
fig3.update_yaxes(title_text="Wq (hours)", row=1, col=2)
fig3.update_xaxes(title_text="Time Interval", row=1, col=1)
fig3.update_xaxes(title_text="Time Interval", row=1, col=2)

fig3.update_layout(height=400)

st.plotly_chart(fig3, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# DETAILED COMPARISON TABLE
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📋 Detailed Comparison Table")

detailed = pd.DataFrame({
    "Time": comparison_df["time_interval"],
    "Servers Δ": comparison_df["servers_recommended"] - comparison_df["servers_current"],
    "ρ Current": comparison_df["utilization_current"].round(3),
    "ρ Recommended": comparison_df["utilization_recommended"].round(3),
    "ρ Δ": (comparison_df["utilization_recommended"] - comparison_df["utilization_current"]).round(3),
    "Lq Current": comparison_df["Lq_current"].round(2),
    "Lq Recommended": comparison_df["Lq_recommended"].round(2),
    "Wq Current": comparison_df["Wq_current"].round(3),
    "Wq Recommended": comparison_df["Wq_recommended"].round(3),
})

# Format numeric columns to remove trailing zeros
detailed_styled = detailed.style.format({
    "ρ Current": lambda x: format_number(x, 3),
    "ρ Recommended": lambda x: format_number(x, 3),
    "ρ Δ": lambda x: format_number(x, 3),
    "Lq Current": lambda x: format_number(x, 2),
    "Lq Recommended": lambda x: format_number(x, 2),
    "Wq Current": lambda x: format_number(x, 3),
    "Wq Recommended": lambda x: format_number(x, 3),
})

st.dataframe(detailed_styled, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("💾 Export Comparison")

col1, col2, col3 = st.columns(3)

with col1:
    csv_bytes = comparison_df.to_csv(index=False).encode()
    st.download_button(
        "📥 Download CSV",
        csv_bytes,
        "comparison_data.csv",
        "text/csv",
    )

with col2:
    try:
        import io
        excel_buffer = io.BytesIO()
        excel_writer = pd.ExcelWriter(excel_buffer, engine='openpyxl')
        comparison_df.to_excel(excel_writer, index=False, sheet_name="Comparison")
        excel_writer.close()
        excel_buffer.seek(0)
        
        st.download_button(
            "📊 Download Excel (Comparison)",
            excel_buffer.getvalue(),
            "comparison_data.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        st.warning(f"Excel export: {e}")

with col3:
    # Create Excel file for costing comparison
    try:
        import io
        
        # Prepare costing comparison DataFrame
        costing_cmp_df = pd.DataFrame({
            "time_interval": comparison_df["time_interval"],
            "arrival_rate": comparison_df["arrival_rate"],
            "service_rate": comparison_df["service_rate"],
            "current_servers": comparison_df.get("c_current", 0),
            "recommended_servers": comparison_df.get("c_optimal", 0),
            "current_cost_₱": comparison_df.get("c_current", 0) * 87.0 + comparison_df.get("Wq_current", 0) * comparison_df.get("arrival_rate", 0) * 100.0 + comparison_df.get("arrival_rate", 0) * 0.10 * 60.0,
            "recommended_cost_₱": comparison_df.get("c_optimal", 0) * 87.0 + comparison_df.get("Wq_optimal", 0) * comparison_df.get("arrival_rate", 0) * 100.0 + comparison_df.get("arrival_rate", 0) * 0.10 * 60.0,
        })
        costing_cmp_df["saving_₱"] = costing_cmp_df["current_cost_₱"] - costing_cmp_df["recommended_cost_₱"]
        
        costing_cmp_buffer = io.BytesIO()
        costing_cmp_writer = pd.ExcelWriter(costing_cmp_buffer, engine='openpyxl')
        
        # Sheet 1: Detailed costing comparison
        costing_cmp_df.to_excel(costing_cmp_writer, index=False, sheet_name="Costing Comparison")
        
        # Sheet 2: Costing summary
        summary_cmp_data = {
            "Metric": [
                "Total Current Cost",
                "Total Recommended Cost",
                "TOTAL SAVINGS",
                "Savings %"
            ],
            "Amount (₱)": [
                costing_cmp_df["current_cost_₱"].sum(),
                costing_cmp_df["recommended_cost_₱"].sum(),
                costing_cmp_df["saving_₱"].sum(),
                f"{(costing_cmp_df['saving_₱'].sum() / costing_cmp_df['current_cost_₱'].sum() * 100):.1f}%" if costing_cmp_df["current_cost_₱"].sum() > 0 else "0%"
            ]
        }
        summary_cmp_df = pd.DataFrame(summary_cmp_data)
        summary_cmp_df.to_excel(costing_cmp_writer, index=False, sheet_name="Summary")
        
        costing_cmp_writer.close()
        costing_cmp_buffer.seek(0)
        
        st.download_button(
            "💰 Download Excel (Costing)",
            costing_cmp_buffer.getvalue(),
            "comparison_costing_analysis.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        st.warning(f"⚠️ Costing export: {e}")

st.success("✅ Ready for Page 4: Simulation")
