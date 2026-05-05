"""
Data Converter: Daily CSV Files → Streamlit Dashboard Format (9 Columns)

Converts data from "Daily data mmc" folder from 4-column format to 9-column schema
Required by the Streamlit Queueing Theory Dashboard.

INPUT FORMAT:  time, lambda, mu, c
OUTPUT FORMAT: time_interval, arrival_rate, service_rate, servers, utilization, Lq, Wq, Ls, Ws

Usage:
  python convert_daily_data.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# ─────────────────────────────────────────────────────────────────────────────
# M/M/c Metrics Computation (from utils.py)
# ─────────────────────────────────────────────────────────────────────────────

def compute_mmc_metrics(lambda_: float, mu: float, c: int) -> dict:
    """Compute M/M/c queue steady-state metrics using Erlang-C formula."""
    
    # Input validation
    if lambda_ < 0 or mu <= 0 or c <= 0:
        return {
            "utilization": np.nan,
            "Lq": np.nan,
            "Wq": np.nan,
            "Ls": np.nan,
            "Ws": np.nan,
        }
    
    ρ = lambda_ / (c * mu)  # utilization
    
    # System unstable if ρ >= 1
    if ρ >= 1.0:
        return {
            "utilization": ρ,
            "Lq": np.inf,
            "Wq": np.inf,
            "Ls": np.inf,
            "Ws": np.inf,
        }
    
    try:
        # Erlang-C formula for M/M/c
        # Step 1: Compute numerator
        erlang_num = (lambda_ / mu) ** c
        for i in range(1, c + 1):
            erlang_num /= i
        
        # Step 2: Compute denominator
        erlang_denom = 0
        for i in range(c + 1):
            term = (lambda_ / mu) ** i
            for j in range(1, i + 1):
                term /= j
            erlang_denom += term
        
        # Erlang-C (probability of waiting)
        pw = erlang_num / (erlang_denom + erlang_num * (1 - ρ) / (1 - ρ))
        pw = max(0, min(1, pw))  # Clamp to [0, 1]
        
        # Queue metrics
        Lq = (pw * ρ) / (c * (1 - ρ))
        Wq = Lq / lambda_ if lambda_ > 0 else 0
        Ls = Lq + lambda_ / mu
        Ws = Wq + 1 / mu
        
        return {
            "utilization": round(ρ, 4),
            "Lq": round(Lq, 4),
            "Wq": round(Wq, 4),
            "Ls": round(Ls, 4),
            "Ws": round(Ws, 4),
        }
    except Exception as e:
        print(f"⚠️  Computation error: {e}")
        return {
            "utilization": np.nan,
            "Lq": np.nan,
            "Wq": np.nan,
            "Ls": np.nan,
            "Ws": np.nan,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Main Conversion Function
# ─────────────────────────────────────────────────────────────────────────────

def convert_daily_file(input_path: Path) -> pd.DataFrame:
    """
    Convert a single daily CSV file from 4-column to 9-column format.
    
    Args:
        input_path: Path to the CSV file (e.g., "day 1.csv")
        
    Returns:
        DataFrame with 9 columns in the required format
    """
    
    # Read the input file
    df_input = pd.read_csv(input_path)
    
    # Validate input columns
    required_cols = {"time", "lambda", "mu", "c"}
    if not required_cols.issubset(set(df_input.columns)):
        raise ValueError(f"Missing columns. Expected: {required_cols}, Got: {set(df_input.columns)}")
    
    # Create output dataframe
    df_output = pd.DataFrame()
    
    # Rename columns
    df_output["time_interval"] = df_input["time"]
    df_output["arrival_rate"] = df_input["lambda"]
    df_output["service_rate"] = df_input["mu"]
    df_output["servers"] = df_input["c"].astype(int)
    
    # Compute metrics for each row
    metrics_list = []
    for idx, row in df_output.iterrows():
        metrics = compute_mmc_metrics(
            row["arrival_rate"],
            row["service_rate"],
            row["servers"]
        )
        metrics_list.append(metrics)
    
    # Add computed columns
    metrics_df = pd.DataFrame(metrics_list)
    df_output = pd.concat([df_output, metrics_df], axis=1)
    
    # Ensure column order
    df_output = df_output[[
        "time_interval", "arrival_rate", "service_rate", "servers",
        "utilization", "Lq", "Wq", "Ls", "Ws"
    ]]
    
    return df_output


def convert_all_daily_files(input_dir: Path, output_dir: Path):
    """
    Convert all daily CSV files in input_dir to 9-column format and save to output_dir.
    
    Args:
        input_dir: Directory containing daily CSV files (e.g., "Daily data mmc")
        output_dir: Directory to save converted files
    """
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all CSV files
    csv_files = sorted(input_dir.glob("day *.csv"))
    
    if not csv_files:
        print(f"❌ No CSV files found in {input_dir}")
        return
    
    print(f"📁 Found {len(csv_files)} files to convert")
    print()
    
    converted_files = []
    
    for csv_file in csv_files:
        try:
            print(f"🔄 Converting: {csv_file.name}...", end=" ")
            
            # Convert file
            df_converted = convert_daily_file(csv_file)
            
            # Save converted file
            output_file = output_dir / csv_file.name
            df_converted.to_csv(output_file, index=False)
            
            print(f"✅ Done ({len(df_converted)} rows)")
            converted_files.append(output_file)
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print()
    print(f"✅ Conversion complete! {len(converted_files)} files saved to: {output_dir}")
    
    return converted_files


def merge_all_daily_files(input_files, output_file: Path):
    """
    Merge all converted daily files into a single consolidated CSV.
    
    Args:
        input_files: List of converted CSV file paths
        output_file: Path for the merged output file
    """
    
    all_dfs = []
    
    for file in input_files:
        df = pd.read_csv(file)
        all_dfs.append(df)
    
    # Concatenate all dataframes, removing duplicates by time_interval
    merged_df = pd.concat(all_dfs, ignore_index=True)
    
    # Group by time_interval and take the mean (in case there are variations across days)
    merged_df = merged_df.groupby("time_interval", as_index=False).mean(numeric_only=True)
    
    # Reorder columns
    merged_df = merged_df[[
        "time_interval", "arrival_rate", "service_rate", "servers",
        "utilization", "Lq", "Wq", "Ls", "Ws"
    ]]
    
    # Sort by time_interval
    time_order = [
        "05:00-06:00", "06:00-07:00", "07:00-08:00", "08:00-09:00", "09:00-10:00",
        "10:00-11:00", "11:00-12:00", "12:00-13:00", "13:00-14:00", "14:00-15:00",
        "15:00-16:00", "16:00-17:00", "17:00-18:00"
    ]
    merged_df["time_interval"] = pd.Categorical(merged_df["time_interval"], categories=time_order, ordered=True)
    merged_df = merged_df.sort_values("time_interval")
    merged_df["time_interval"] = merged_df["time_interval"].astype(str)
    
    merged_df.to_csv(output_file, index=False)
    print(f"✅ Merged file: {output_file} ({len(merged_df)} unique intervals)")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    
    # Define paths
    project_root = Path(__file__).parent
    input_dir = Path("c:/Users/krizel/Desktop/O.R AKSELS/QUEUING_THEORY_NOVAMART-main/Daily data mmc")
    output_dir = project_root / "converted_daily_data"
    merged_file = project_root / "merged_daily_data.csv"
    
    print("╔═══════════════════════════════════════════════════════════════════════╗")
    print("║  📊 Daily Data Converter → Streamlit Dashboard Format                ║")
    print("╚═══════════════════════════════════════════════════════════════════════╝")
    print()
    print(f"Input directory:  {input_dir}")
    print(f"Output directory: {output_dir}")
    print()
    
    # Step 1: Convert all files
    print("STEP 1: Converting daily files...")
    print("─" * 70)
    converted_files = convert_all_daily_files(input_dir, output_dir)
    
    # Step 2: Merge all converted files
    if converted_files:
        print()
        print("STEP 2: Merging all daily files...")
        print("─" * 70)
        merge_all_daily_files(converted_files, merged_file)
        
        print()
        print("╔═══════════════════════════════════════════════════════════════════════╗")
        print("║  ✅ CONVERSION COMPLETE                                              ║")
        print("╚═══════════════════════════════════════════════════════════════════════╝")
        print()
        print("📂 Output Files:")
        print(f"   1. Individual files: {output_dir}/day 1.csv, day 2.csv, ... day 14.csv")
        print(f"   2. Merged file:      {merged_file}")
        print()
        print("📌 Next Steps:")
        print("   1. Open Streamlit dashboard: streamlit run streamlit_app.py")
        print("   2. Go to Page 1: Upload & Compute")
        print("   3. Upload: merged_daily_data.csv")
        print("   4. Follow workflow through Pages 2-4")
