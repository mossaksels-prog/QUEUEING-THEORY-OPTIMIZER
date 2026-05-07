"""
Page 5 — Waste Reduction Optimization
🎯 Alternative optimization strategy using aggressive Wq minimization
✅ Load current_data from session state
✅ Apply waste reduction algorithm for all models (M/M/1, M/M/c, M/G/1)
✅ Compare with standard cost optimization (Page 2)
✅ Display waste reduction impact: Server changes, Wq improvements, cost trade-offs
✅ Help decide: Cost optimization vs Waste reduction

Supported Models:
- M/M/1: Single server waste reduction
- M/M/c: Multi-server waste reduction with aggressive staffing
- M/G/1: General service time waste reduction (uses variance)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import json

# Import utils safely
sys.path.insert(0, ".")
from utils import compute_mmc_metrics, compute_costs
from optimization_waste import optimize_segments_waste, summarize_waste_optimization

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

WASTE_REDUCTION_WAITING_COST = 100.0  # ₱ per customer per hour
MAX_SERVERS = 20
LABOR_COST_PER_SERVER = 87.0  # ₱ per server per hour (regular rate)
COST_PER_WAIT_HR = 100.0  # ₱ per customer/hr waiting
ABANDONMENT_COST = 60.0  # ₱60 = 10% × ₱600 per customer abandoned

# ─────────────────────────────────────────────────────────────────────────────
# Page Title & Description
# ─────────────────────────────────────────────────────────────────────────────

st.title("🎯 Page 5: Waste Reduction Optimization")
st.markdown("""Optimization focused on minimizing waste hours and underutilized staff.""")

# ─────────────────────────────────────────────────────────────────────────────
# PRE-CHECK (MANDATORY)
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.get("current_data") is None:
    st.error("❌ current_data not found")
    st.info("Upload and save current data on Page 1 first")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# COMPUTE WASTE REDUCTION OPTIMIZATION
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("🔄 Computing Waste Reduction Optimization...")

current_data = st.session_state["current_data"].copy()

try:
    # Transform current_data to match optimization format
    segments = []
    for _, row in current_data.iterrows():
        segment = {
            "time": str(row.get("time_interval", "—")),
            "lambda": float(row.get("arrival_rate", 0)),
            "mu": float(row.get("service_rate", 1)),
            "c": int(row.get("servers", 1)),
            "server_cost": LABOR_COST_PER_SERVER,
        }
        segments.append(segment)
    
    # Run waste reduction optimization
    waste_opt_results = optimize_segments_waste(
        time_segments=segments,
        default_server_cost=LABOR_COST_PER_SERVER,
        max_servers=MAX_SERVERS
    )
    
    # Convert results to DataFrame
    waste_df = pd.DataFrame(waste_opt_results)
    
    # Store in session state
    st.session_state["waste_reduction_data"] = waste_df
    
    st.success(f"✅ Computed waste reduction for {len(waste_df)} time intervals")
    
except Exception as e:
    st.error(f"❌ Computation failed: {e}")
    import traceback
    st.write(traceback.format_exc())
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY STATISTICS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📊 Waste Reduction Summary")

if not waste_df.empty:
    # Calculate summaries
    total_current_cost = waste_df["cost_current"].sum()
    total_waste_opt_cost = waste_df["cost_waste_opt"].sum()
    total_savings = total_current_cost - total_waste_opt_cost
    
    avg_current_util = waste_df["rho_current"].mean() * 100
    avg_waste_util = waste_df["rho_waste_opt"].mean() * 100
    util_change = avg_waste_util - avg_current_util
    
    avg_current_wq = waste_df["Wq_current"].mean()
    avg_waste_wq = waste_df["Wq_waste_opt"].mean()
    wq_improvement_pct = ((avg_current_wq - avg_waste_wq) / avg_current_wq * 100) if avg_current_wq > 0 else 0
    
    total_server_change = waste_df["delta_c"].sum()
    
    # Display KPI cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Staffing Change",
            value=f"{int(total_server_change):+d} servers",
            delta=None,
            delta_color="off"
        )
    
    with col2:
        st.metric(
            label="Avg Utilization Change",
            value=f"{util_change:+.1f}%",
            delta=f"From {avg_current_util:.1f}% to {avg_waste_util:.1f}%",
            delta_color="off"
        )
    
    with col3:
        st.metric(
            label="Avg Waiting Time Improvement",
            value=f"{wq_improvement_pct:.1f}%",
            delta=f"{avg_current_wq:.4f}h → {avg_waste_wq:.4f}h",
            delta_color="inverse"
        )
    
    with col4:
        st.metric(
            label="Cost Impact",
            value=f"₱{total_savings:+,.0f}",
            delta="Savings" if total_savings >= 0 else "Additional Cost",
            delta_color="inverse" if total_savings >= 0 else "off"
        )

# ─────────────────────────────────────────────────────────────────────────────
# DETAILED TABLE
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📋 Details by Time Interval")

if not waste_df.empty:
    # Prepare display DataFrame
    display_df = pd.DataFrame({
        "Time": waste_df["time"],
        "λ (arr/hr)": waste_df["lambda"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—"),
        "μ (svc/hr)": waste_df["mu"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—"),
        "Current Servers": waste_df["c_current"].apply(lambda x: f"{int(x)}" if pd.notna(x) else "—"),
        "Waste Opt Servers": waste_df["c_waste_opt"].apply(lambda x: f"{int(x)}" if pd.notna(x) else "—"),
        "Δ Servers": waste_df["delta_c"].apply(lambda x: f"{int(x):+d}" if pd.notna(x) else "—"),
        "Current ρ": waste_df["rho_current"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—"),
        "Waste Opt ρ": waste_df["rho_waste_opt"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "—"),
        "Current Wq (hrs)": waste_df["Wq_current"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "—"),
        "Waste Opt Wq (hrs)": waste_df["Wq_waste_opt"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "—"),
        "Δ Wq": waste_df["delta_Wq"].apply(lambda x: f"{x:+.4f}" if pd.notna(x) else "—"),
        "Cost Change (₱)": waste_df["delta_cost"].apply(lambda x: f"₱{x:+,.0f}" if pd.notna(x) else "—"),
    })
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# VISUALIZATIONS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📈 Visualizations")

if not waste_df.empty:
    # Chart 1: Server Changes
    col1, col2 = st.columns(2)
    
    with col1:
        fig_servers = go.Figure()
        fig_servers.add_trace(go.Bar(
            x=waste_df["time"],
            y=waste_df["c_current"],
            name="Current Servers",
            marker_color="rgba(255, 165, 0, 0.7)",  # Orange
            text=waste_df["c_current"].astype(str),
            textposition="auto",
        ))
        fig_servers.add_trace(go.Bar(
            x=waste_df["time"],
            y=waste_df["c_waste_opt"],
            name="Waste Reduction Servers",
            marker_color="rgba(52, 211, 153, 0.7)",  # Green
            text=waste_df["c_waste_opt"].astype(str),
            textposition="auto",
        ))
        fig_servers.update_layout(
            title="Staffing: Current vs Waste Reduction",
            barmode="group",
            xaxis_title="Time Interval",
            yaxis_title="Number of Servers",
            hovermode="x unified",
            height=400,
        )
        st.plotly_chart(fig_servers, use_container_width=True)
    
    # Chart 2: Waiting Time Improvement
    with col2:
        fig_wq = go.Figure()
        fig_wq.add_trace(go.Scatter(
            x=waste_df["time"],
            y=waste_df["Wq_current"],
            mode="lines+markers",
            name="Current Wq",
            line=dict(color="rgba(255, 165, 0, 1)", width=2),
            marker=dict(size=8),
        ))
        fig_wq.add_trace(go.Scatter(
            x=waste_df["time"],
            y=waste_df["Wq_waste_opt"],
            mode="lines+markers",
            name="Waste Reduction Wq",
            line=dict(color="rgba(52, 211, 153, 1)", width=2, dash="dash"),
            marker=dict(size=8, symbol="diamond"),
        ))
        fig_wq.update_layout(
            title="Waiting Time: Current vs Waste Reduction",
            xaxis_title="Time Interval",
            yaxis_title="Wq (Hours)",
            hovermode="x unified",
            height=400,
        )
        st.plotly_chart(fig_wq, use_container_width=True)
    
    # Chart 3: Utilization Change
    col3, col4 = st.columns(2)
    
    with col3:
        fig_util = go.Figure()
        fig_util.add_trace(go.Bar(
            x=waste_df["time"],
            y=waste_df["rho_current"],
            name="Current ρ",
            marker_color="rgba(255, 165, 0, 0.7)",
            text=[f"{x:.1%}" if pd.notna(x) else "—" for x in waste_df["rho_current"]],
            textposition="auto",
        ))
        fig_util.add_trace(go.Bar(
            x=waste_df["time"],
            y=waste_df["rho_waste_opt"],
            name="Waste Reduction ρ",
            marker_color="rgba(52, 211, 153, 0.7)",
            text=[f"{x:.1%}" if pd.notna(x) else "—" for x in waste_df["rho_waste_opt"]],
            textposition="auto",
        ))
        fig_util.add_hline(y=0.70, line_dash="dash", line_color="rgba(74, 222, 128, 0.5)",
                          annotation_text="70% Target")
        fig_util.update_layout(
            title="Utilization (ρ): Current vs Waste Reduction",
            barmode="group",
            xaxis_title="Time Interval",
            yaxis_title="Utilization (ρ)",
            yaxis=dict(tickformat=".0%"),
            hovermode="x unified",
            height=400,
        )
        st.plotly_chart(fig_util, use_container_width=True)
    
    # Chart 4: Cost Impact
    with col4:
        fig_cost = go.Figure()
        
        # Stack: Current Cost Breakdown
        fig_cost.add_trace(go.Bar(
            x=waste_df["time"],
            y=waste_df["cost_current"],
            name="Current Total Cost",
            marker_color="rgba(255, 165, 0, 0.7)",
            text=[f"₱{x:,.0f}" if pd.notna(x) else "—" for x in waste_df["cost_current"]],
            textposition="auto",
        ))
        fig_cost.add_trace(go.Bar(
            x=waste_df["time"],
            y=waste_df["cost_waste_opt"],
            name="Waste Reduction Cost",
            marker_color="rgba(52, 211, 153, 0.7)",
            text=[f"₱{x:,.0f}" if pd.notna(x) else "—" for x in waste_df["cost_waste_opt"]],
            textposition="auto",
        ))
        
        fig_cost.update_layout(
            title="Total Cost Impact per Interval",
            barmode="group",
            xaxis_title="Time Interval",
            yaxis_title="Cost (₱)",
            hovermode="x unified",
            height=400,
        )
        st.plotly_chart(fig_cost, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# RECOMMENDATIONS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("💡 Recommendations")

if not waste_df.empty:
    high_impact = waste_df[waste_df["delta_c"] < 0].copy()
    
    if not high_impact.empty:
        st.markdown(f"**{len(high_impact)} intervals identified for staff reduction:**")
        
        for _, row in high_impact.iterrows():
            servers_removed = int(abs(row["delta_c"]))
            util = row["rho_current"]
            cost_change = row["delta_cost"]
            
            st.markdown(f"**{row['time']}:** Remove {servers_removed} server(s) • ₱{cost_change:+,.0f}")

# ─────────────────────────────────────────────────────────────────────────────
# EXPORT DATA
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("💾 Export Results")

if not waste_df.empty:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv_data = waste_df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name="waste_reduction_optimization.csv",
            mime="text/csv",
        )
    
    with col2:
        try:
            import io
            excel_buffer = io.BytesIO()
            excel_writer = pd.ExcelWriter(excel_buffer, engine='openpyxl')
            waste_df.to_excel(excel_writer, index=False, sheet_name="Waste Reduction")
            excel_writer.close()
            excel_buffer.seek(0)
            
            st.download_button(
                label="📊 Download Excel (Optimization)",
                data=excel_buffer.getvalue(),
                file_name="waste_reduction_optimization.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.warning(f"Excel export: {e}")
    
    with col3:
        # Create Excel file for costing breakdown with waste reduction
        try:
            import io
            
            # Prepare costing comparison DataFrame with abandonment costs
            costing_waste_df = pd.DataFrame({
                "time_interval": waste_df["time"],
                "arrival_rate": waste_df["lambda"],
                "service_rate": waste_df["mu"],
                "current_servers": waste_df.get("c_current", 0),
                "waste_opt_servers": waste_df.get("c_waste_opt", 0),
                "current_server_cost_₱": (waste_df.get("c_current", 0) * LABOR_COST_PER_SERVER).round(2),
                "current_wait_cost_₱": (waste_df.get("Wq_current", 0) * waste_df.get("lambda", 0) * COST_PER_WAIT_HR).round(2),
                "current_abandon_cost_₱": (waste_df.get("lambda", 0) * 0.10 * ABANDONMENT_COST).round(2),
                "current_total_cost_₱": (waste_df.get("cost_current", 0)).round(2),
                "waste_opt_server_cost_₱": (waste_df.get("c_waste_opt", 0) * LABOR_COST_PER_SERVER).round(2),
                "waste_opt_wait_cost_₱": (waste_df.get("Wq_waste_opt", 0) * waste_df.get("lambda", 0) * COST_PER_WAIT_HR).round(2),
                "waste_opt_abandon_cost_₱": (waste_df.get("lambda", 0) * 0.10 * ABANDONMENT_COST).round(2),
                "waste_opt_total_cost_₱": (waste_df.get("cost_waste_opt", 0)).round(2),
            })
            costing_waste_df["saving_₱"] = (costing_waste_df["current_total_cost_₱"] - costing_waste_df["waste_opt_total_cost_₱"]).round(2)
            
            costing_waste_buffer = io.BytesIO()
            costing_waste_writer = pd.ExcelWriter(costing_waste_buffer, engine='openpyxl')
            
            # Sheet 1: Detailed costing comparison
            costing_waste_df.to_excel(costing_waste_writer, index=False, sheet_name="Costing Comparison")
            
            # Sheet 2: Costing summary
            summary_waste_data = {
                "Metric": [
                    "Total Current Cost",
                    "  - Server Cost",
                    "  - Wait Cost",
                    "  - Abandonment Cost",
                    "Total Waste Reduction Cost",
                    "  - Server Cost",
                    "  - Wait Cost",
                    "  - Abandonment Cost",
                    "TOTAL SAVINGS",
                    "Savings %",
                    "—",
                    "Current Servers Total",
                    "Waste Reduction Servers Total",
                    "Server Reduction"
                ],
                "Amount": [
                    f"₱{costing_waste_df['current_total_cost_₱'].sum():,.2f}",
                    f"₱{costing_waste_df['current_server_cost_₱'].sum():,.2f}",
                    f"₱{costing_waste_df['current_wait_cost_₱'].sum():,.2f}",
                    f"₱{costing_waste_df['current_abandon_cost_₱'].sum():,.2f}",
                    f"₱{costing_waste_df['waste_opt_total_cost_₱'].sum():,.2f}",
                    f"₱{costing_waste_df['waste_opt_server_cost_₱'].sum():,.2f}",
                    f"₱{costing_waste_df['waste_opt_wait_cost_₱'].sum():,.2f}",
                    f"₱{costing_waste_df['waste_opt_abandon_cost_₱'].sum():,.2f}",
                    f"₱{costing_waste_df['saving_₱'].sum():,.2f}",
                    f"{(costing_waste_df['saving_₱'].sum() / costing_waste_df['current_total_cost_₱'].sum() * 100):.1f}%" if costing_waste_df['current_total_cost_₱'].sum() > 0 else "0%",
                    "—",
                    f"{int(costing_waste_df['current_servers'].sum())} servers",
                    f"{int(costing_waste_df['waste_opt_servers'].sum())} servers",
                    f"{int(costing_waste_df['current_servers'].sum() - costing_waste_df['waste_opt_servers'].sum())} servers"
                ]
            }
            summary_waste_df = pd.DataFrame(summary_waste_data)
            summary_waste_df.to_excel(costing_waste_writer, index=False, sheet_name="Summary")
            
            costing_waste_writer.close()
            costing_waste_buffer.seek(0)
            
            st.download_button(
                label="💰 Download Excel (Costing)",
                data=costing_waste_buffer.getvalue(),
                file_name="waste_reduction_costing_analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.warning(f"⚠️ Costing export: {e}")
