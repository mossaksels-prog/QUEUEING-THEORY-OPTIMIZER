"""
Streamlit Multi-Page Dashboard — 4-Page Queueing Theory System
With strict data pipeline integrity and mandatory error-checking.

🎯 Architecture:
  Page 1 (pages/1_current_metrics.py) — Upload & validate
  Page 2 (pages/2_optimization.py) — Generate recommendations  
  Page 3 (pages/3_comparison.py) — Compare with error-safe merge
  Page 4 (pages/4_simulation.py) — Monte Carlo using ONLY recommended data

🔐 Safety Rules:
  - Session state initialized on startup
  - Schema validation on all data entry points
  - Page 3 & 4 require upstream completion
  - All numeric columns validated before compute
  - No mutations of original data — always .copy()
"""

import streamlit as st
import pandas as pd

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

# ─────────────────────────────────────────────────────────────────────────────
# Session State Initialization (MANDATORY)
# ─────────────────────────────────────────────────────────────────────────────

def init_session_state():
    """Initialize all required session state keys."""
    if "current_data" not in st.session_state:
        st.session_state["current_data"] = None
    if "recommended_data" not in st.session_state:
        st.session_state["recommended_data"] = None
    if "comparison_data" not in st.session_state:
        st.session_state["comparison_data"] = None
    if "simulation_results" not in st.session_state:
        st.session_state["simulation_results"] = None
    if "waste_reduction_data" not in st.session_state:
        st.session_state["waste_reduction_data"] = None
    
    # Costing parameters (NOVAMART defaults)
    if "cost_per_server_hr" not in st.session_state:
        st.session_state["cost_per_server_hr"] = 87.0  # ₱87/hr
    if "cost_per_wait_hr" not in st.session_state:
        st.session_state["cost_per_wait_hr"] = 100.0  # ₱100/hr customer time
    if "cost_per_abandonment" not in st.session_state:
        # Abandonment cost: 10% of ₱600 daily = ₱60 per abandonment
        st.session_state["cost_per_abandonment"] = 60.0  # ₱60/customer (10% × 600)


def main():
    """Initialize app and configure metadata."""
    st.set_page_config(
        page_title="Queueing Theory Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # Apply custom styling with modern design
    st.markdown("""
    <style>
    /* Main styling */
    .welcome-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 3rem 2rem;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .welcome-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: bold;
    }
    
    .welcome-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1.1rem;
        opacity: 0.95;
    }
    
    .card {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
        margin-bottom: 1rem;
    }
    
    .card.success {
        border-left-color: #28a745;
    }
    
    .card.pending {
        border-left-color: #ffc107;
    }
    
    .card h3 {
        margin-top: 0;
        color: #333;
    }
    
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #e9ecef;
    }
    
    .progress-step {
        text-align: center;
        padding: 1rem;
    }
    
    .step-number {
        font-size: 2rem;
        font-weight: bold;
        color: #667eea;
    }
    
    .step-title {
        font-size: 1rem;
        color: #333;
        margin-top: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    init_session_state()
    
    # Welcome Header
    st.markdown("""
    <div class="welcome-header">
        <h1>📊 Queueing Theory Optimizer</h1>
        <p>Optimize your service queues with data-driven recommendations</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Overview Stats
    st.markdown("### 📈 System Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Current Data", "📁" if st.session_state.get("current_data") is not None else "❌")
    with col2:
        st.metric("Optimization", "✅" if st.session_state.get("recommended_data") is not None else "⏳")
    with col3:
        st.metric("Comparison", "✅" if st.session_state.get("comparison_data") is not None else "⏳")
    with col4:
        st.metric("Simulation", "✅" if st.session_state.get("simulation_results") is not None else "⏳")
    
    st.markdown("---")
    
    # Quick Start Guide
    st.markdown("### 🚀 Quick Start Guide")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="card">
            <div class="step-number">1️⃣</div>
            <div class="step-title"><b>Upload Data</b></div>
            <p style="font-size: 0.9rem; color: #666;">Upload your queue metrics CSV file</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="card">
            <div class="step-number">2️⃣</div>
            <div class="step-title"><b>Get Recommendations</b></div>
            <p style="font-size: 0.9rem; color: #666;">Generate optimized server counts</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="card">
            <div class="step-number">3️⃣</div>
            <div class="step-title"><b>Compare Results</b></div>
            <p style="font-size: 0.9rem; color: #666;">View current vs optimized metrics</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="card">
            <div class="step-number">4️⃣</div>
            <div class="step-title"><b>Run Simulation</b></div>
            <p style="font-size: 0.9rem; color: #666;">Monte Carlo validation & analysis</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Sidebar info
    st.sidebar.markdown("### 📊 Queueing Theory Optimizer")
    st.sidebar.markdown("""
    **Multi-Page System**
    - 📥 **Page 1:** Upload & compute current metrics
    - ⚙️ **Page 2:** Generate optimized recommendations
    - 📈 **Page 3:** Compare current vs recommended
    - 🔁 **Page 4:** Run Monte Carlo simulation
    
    **Schema** (9 required columns)
    """)
    
    st.sidebar.markdown(f"""
    ```
    {', '.join(REQUIRED_COLUMNS[:3])}
    {', '.join(REQUIRED_COLUMNS[3:6])}
    {', '.join(REQUIRED_COLUMNS[6:])}
    ```
    """)
    
    # Status indicator
    st.sidebar.markdown("---")
    col1, col2, col3, col4 = st.sidebar.columns(4)
    
    with col1:
        status = "✅" if st.session_state.get("current_data") is not None else "⭕"
        st.metric("Page 1", status)
    
    with col2:
        status = "✅" if st.session_state.get("recommended_data") is not None else "⭕"
        st.metric("Page 2", status)
    
    with col3:
        status = "✅" if st.session_state.get("comparison_data") is not None else "⭕"
        st.metric("Page 3", status)
    
    with col4:
        status = "✅" if st.session_state.get("simulation_results") is not None else "⭕"
        st.metric("Page 4", status)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # COSTING CONFIGURATION (ADJUSTABLE)
    # ─────────────────────────────────────────────────────────────────────────────
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("💰 Costing Parameters")
    st.sidebar.markdown("""
    **Adjust costing for your business model**
    """)
    
    # Input fields for costing parameters
    st.session_state["cost_per_server_hr"] = st.sidebar.number_input(
        "💼 Cost per Cashier (₱/hr)",
        min_value=10.0,
        max_value=500.0,
        value=st.session_state.get("cost_per_server_hr", 87.0),
        step=1.0,
        help="Hourly wage for one cashier/server"
    )
    
    st.session_state["cost_per_wait_hr"] = st.sidebar.number_input(
        "⏳ Cost of Customer Wait (₱/hr)",
        min_value=10.0,
        max_value=500.0,
        value=st.session_state.get("cost_per_wait_hr", 100.0),
        step=1.0,
        help="Opportunity cost of customer time waiting"
    )
    
    st.session_state["cost_per_abandonment"] = st.sidebar.number_input(
        "❌ Cost per Abandonment (₱)",
        min_value=10.0,
        max_value=500.0,
        value=st.session_state.get("cost_per_abandonment", 60.0),
        step=1.0,
        help="Cost of lost customer (avg basket loss)"
    )
    
    # Display current costing summary
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Current Settings")
    col_c1, col_c2 = st.sidebar.columns(2)
    
    with col_c1:
        st.metric("Cₛ (Cashier)", f"₱{st.session_state['cost_per_server_hr']:.0f}/hr")
    
    with col_c2:
        st.metric("Cw (Wait)", f"₱{st.session_state['cost_per_wait_hr']:.0f}/hr")
    
    st.sidebar.metric("Ca (Abandon)", f"₱{st.session_state['cost_per_abandonment']:.0f}")


if __name__ == "__main__":
    main()
