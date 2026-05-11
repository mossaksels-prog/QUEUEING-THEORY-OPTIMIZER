"""
Page 1 — Current Data Upload & Validation
✅ Upload CSV/Excel
✅ Validate schema for M/M/1, M/M/c, M/G/c, M/M/c/K, or M/G/c/K
✅ Convert numeric columns
✅ Compute metrics
✅ Store in st.session_state["current_data"]

Supported Models:
- M/M/1: Single server (c=1, no variance needed)
- M/M/c: Multiple servers (c>1, no variance needed)
- M/G/c: General service time (any c, variance column optional)
- M/M/c/K: Finite-capacity queue (K column provided)
- M/G/c/K: Finite-capacity general service queue (variance and K provided)
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from queue_models import mgc, mgck, mmc, mmck

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

REQUIRED_COLUMNS = [
    "time",
    "lambda",
    "mu",
    "c"
]

OPTIONAL_COLUMNS = [
    "variance",  # For M/G/c and M/G/c/K model support
    "K",  # Total finite system capacity for M/M/c/K and M/G/c/K
]

NUMERIC_COLUMNS = [
    "lambda",
    "mu",
    "c"
]

# ─────────────────────────────────────────────────────────────────────────────
# Helper: Validate numeric conversion
# ─────────────────────────────────────────────────────────────────────────────

def validate_and_convert_numeric(df: pd.DataFrame) -> tuple[bool, str, pd.DataFrame]:
    """
    Validate that numeric columns exist and convert to proper types.
    Return: (success: bool, message: str, converted_df: DataFrame)
    """
    df_copy = df.copy()
    
    for col in NUMERIC_COLUMNS:
        if col not in df_copy.columns:
            return False, f"❌ Missing column: {col}", df_copy
        
        try:
            df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
            
            # Check for NaN after conversion
            nan_count = df_copy[col].isna().sum()
            if nan_count > 0:
                return False, f"❌ Column '{col}' has {nan_count} invalid numeric values", df_copy
                
        except Exception as e:
            return False, f"❌ Error converting '{col}': {str(e)}", df_copy
    for col in OPTIONAL_COLUMNS:
        if col in df_copy.columns:
            df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')

    return True, "All numeric columns validated", df_copy


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Validate schema
# ─────────────────────────────────────────────────────────────────────────────

def validate_schema(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Check that all REQUIRED_COLUMNS exist.
    Return: (success: bool, message: str)
    """
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        return False, f"❌ Missing columns: {', '.join(missing)}"
    
    return True, "✅ Schema valid"


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Compute metrics (M/M/c model)
# ─────────────────────────────────────────────────────────────────────────────

def compute_mmc_metrics(row: pd.Series) -> dict:
    """
    Compute M/M/c or M/G/c queue metrics for a single row.

    Rows with K use finite-capacity models. Rows with variance use
    general-service approximations.
    """
    lambda_ = row["arrival_rate"]
    mu = row["service_rate"]
    c = int(row["servers"])

    # Validation
    if lambda_ < 0 or mu <= 0 or c <= 0:
        return {
            "utilization": np.nan,
            "Lq": np.nan,
            "Wq": np.nan,
            "Ls": np.nan,
            "Ws": np.nan,
            "model": "Invalid",
        }

    variance = row.get("variance")
    capacity = row.get("K")
    has_variance = variance is not None and not pd.isna(variance)
    has_capacity = capacity is not None and not pd.isna(capacity)

    if has_capacity and has_variance:
        result = mgck(lambda_, mu, c, variance, int(capacity))
        model_name = "M/G/c/K"
    elif has_capacity:
        result = mmck(lambda_, mu, c, int(capacity))
        model_name = "M/M/c/K"
    elif has_variance:
        result = mgc(lambda_, mu, c, variance)
        model_name = "M/G/c"
    else:
        result = mmc(lambda_, mu, c)
        model_name = "M/M/c"

    if not result.get("stable", False):
        return {
            "utilization": result.get("rho", np.nan),
            "Lq": np.inf,
            "Wq": np.inf,
            "Ls": np.inf,
            "Ws": np.inf,
            "model": model_name,
        }

    return {
        "utilization": round(result["rho"], 4),
        "Lq": round(result["Lq"], 4),
        "Wq": round(result["Wq"], 4),
        "Ls": round(result["L"], 4),
        "Ws": round(result["W"], 4),
        "model": model_name,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main UI
# ─────────────────────────────────────────────────────────────────────────────

st.title("📥 Page 1: Current Metrics")
st.markdown("**Upload CSV/Excel → Validate → Compute metrics → View & Export**")
st.info("💡 **Optional:** You can stop here and just view/download data. Pages 2-5 are for optimization analysis only.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Upload File")
    uploaded_file = st.file_uploader(
        "Choose CSV or Excel file",
        type=["csv", "xlsx", "xls"],
        help="Required: time, lambda, mu, c. Optional: variance, K."
    )

with col2:
    st.subheader("Actions")
    if st.button("🔄 Reset All Data", key="reset_data_btn"):
        # Clear ALL session state
        st.session_state["current_data"] = None
        st.session_state["recommended_data"] = None
        st.session_state["comparison_data"] = None
        st.session_state["simulation_results"] = None
        st.session_state["waste_reduction_data"] = None
        st.session_state.pop("_sample_df", None)
        st.success("✅ All data cleared - upload fresh data on this page")

# ─────────────────────────────────────────────────────────────────────────────
# Process uploaded or sample file
# ─────────────────────────────────────────────────────────────────────────────

df_to_process = None

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_to_process = pd.read_csv(uploaded_file)
        else:
            df_to_process = pd.read_excel(uploaded_file)
        st.success(f"✅ Loaded {len(df_to_process)} rows")
        
        # CRITICAL: Clear all downstream data when new upload happens
        st.session_state["recommended_data"] = None
        st.session_state["comparison_data"] = None
        st.session_state["simulation_results"] = None
        st.session_state["waste_reduction_data"] = None
        st.info("⚠️ Downstream data cleared - re-run Pages 2-5 with fresh data")
        
    except Exception as e:
        st.error(f"❌ Error reading file: {e}")
        df_to_process = None
else:
    st.info("👉 **Start here:** Upload a CSV or Excel file with required columns: time, lambda, mu, c. Optional columns: variance, K.")

# ─────────────────────────────────────────────────────────────────────────────
# Validation Stage
# ─────────────────────────────────────────────────────────────────────────────

if df_to_process is not None:
    st.markdown("---")
    st.subheader("🔍 Validation")
    
    # Schema check
    schema_ok, schema_msg = validate_schema(df_to_process)
    st.info(schema_msg)
    
    if not schema_ok:
        st.stop()
    
    # Numeric check
    numeric_ok, numeric_msg, df_converted = validate_and_convert_numeric(df_to_process)
    st.info(numeric_msg)
    
    if not numeric_ok:
        st.stop()
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Transform columns to internal format
    # ─────────────────────────────────────────────────────────────────────────────
    
    st.markdown("---")
    st.subheader("🔄 Transforming Data")
    
    df_transformed = df_converted.copy()
    
    # Rename columns to internal format
    df_transformed = df_transformed.rename(columns={
        'time': 'time_interval',
        'lambda': 'arrival_rate',
        'mu': 'service_rate',
        'c': 'servers'
    })
    
    # Add placeholder columns for metrics (will be calculated next)
    df_transformed['utilization'] = 0.0
    df_transformed['Lq'] = 0.0
    df_transformed['Wq'] = 0.0
    df_transformed['Ls'] = 0.0
    df_transformed['Ws'] = 0.0
    
    st.success(f"✅ Columns renamed - Ready to compute metrics")
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Compute Metrics
    # ─────────────────────────────────────────────────────────────────────────────
    
    st.markdown("---")
    st.subheader("⚙️ Computing Metrics")
    
    df_result = df_transformed.copy()
    
    progress_bar = st.progress(0)
    for idx, row in df_result.iterrows():
        metrics = compute_mmc_metrics(row)
        for key, value in metrics.items():
            df_result.at[idx, key] = value
        progress_bar.progress((idx + 1) / len(df_result))
    
    st.success(f"✅ Metrics computed for {len(df_result)} intervals")
    
    # ─────────────────────────────────────────────────────────────────────────────
    # AUTO-SAVE to Session State (NO BUTTON CLICK NEEDED!)
    # ─────────────────────────────────────────────────────────────────────────────
    
    st.session_state["current_data"] = df_result.copy()
    st.info(f"✅ **Auto-saved to session state** - Ready for Page 2")
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Display Results
    # ─────────────────────────────────────────────────────────────────────────────
    
    st.markdown("---")
    st.subheader("📊 Current Data")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Rows", len(df_result))
    with col2:
        avg_util = df_result["utilization"].mean()
        st.metric("Avg Utilization", f"{avg_util:.1%}")
    with col3:
        max_util = df_result["utilization"].max()
        st.metric("Max Utilization", f"{max_util:.1%}")
    
    # Show data table
    df_result_styled = df_result.style.format({
        "arrival_rate": lambda x: format_number(x, 2),
        "service_rate": lambda x: format_number(x, 2),
        "utilization": lambda x: format_number(x, 4),
        "Lq": lambda x: format_number(x, 4),
        "Wq": lambda x: format_number(x, 4),
        "Ls": lambda x: format_number(x, 4),
        "Ws": lambda x: format_number(x, 4),
    })
    
    st.dataframe(df_result_styled, use_container_width=True)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # DEBUG: Show what was saved
    # ─────────────────────────────────────────────────────────────────────────────
    
    with st.expander("🔧 Debug: Verify Saved Data", expanded=False):
        st.caption("Check that YOUR data was uploaded correctly")
        debug_col1, debug_col2 = st.columns(2)
        
        with debug_col1:
            st.write("**First 2 Rows:**")
            debug_styled = df_result.head(2).style.format({
                "arrival_rate": lambda x: format_number(x, 2),
                "service_rate": lambda x: format_number(x, 2),
                "utilization": lambda x: format_number(x, 4),
                "Lq": lambda x: format_number(x, 4),
                "Wq": lambda x: format_number(x, 4),
                "Ls": lambda x: format_number(x, 4),
                "Ws": lambda x: format_number(x, 4),
            })
            st.dataframe(debug_styled, use_container_width=True)
        
        with debug_col2:
            st.write("**Data Summary:**")
            st.json({
                "Total Rows": len(df_result),
                "Avg Arrival Rate": round(df_result["arrival_rate"].mean(), 2),
                "Avg Service Rate": round(df_result["service_rate"].mean(), 2),
                "Avg Utilization": f"{df_result['utilization'].mean():.2%}",
                "Max Utilization": f"{df_result['utilization'].max():.2%}",
                "Total Current Servers": int(df_result["servers"].sum()),
            })
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Save to Session State & Export
    # ─────────────────────────────────────────────────────────────────────────────

    st.markdown("---")
    st.info("✅ **Data auto-saved to session state!** Use buttons below to export or reset.")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("🔄 Reset All Data", key="reset_manual"):
            st.session_state["current_data"] = None
            st.session_state["recommended_data"] = None
            st.session_state["comparison_data"] = None
            st.session_state["simulation_results"] = None
            st.session_state["waste_reduction_data"] = None
            st.success("✅ All data cleared - upload new file")
    
    with col2:
        csv_bytes = df_result.to_csv(index=False).encode()
        st.download_button(
            "📥 Download CSV",
            csv_bytes,
            f"current_data.csv",
            "text/csv",
        )
    
    with col3:
        try:
            import io
            excel_buffer = io.BytesIO()
            excel_writer = pd.ExcelWriter(excel_buffer, engine='openpyxl')
            df_result.to_excel(excel_writer, index=False, sheet_name="Current Data")
            excel_writer.close()
            excel_buffer.seek(0)
            
            st.download_button(
                "📊 Download Excel",
                excel_buffer.getvalue(),
                "current_data.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.warning(f"Excel export: {e}")
