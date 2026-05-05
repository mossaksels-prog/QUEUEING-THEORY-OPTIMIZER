"""
Sample CSV data for testing the Streamlit Queueing Theory Dashboard
Run this to generate sample_data.csv, then upload to Page 1
"""

import os
import numpy as np
import pandas as pd

# Create sample data matching the 9-column schema
sample_data = pd.DataFrame({
    "time_interval": [
        "05:00-06:00", "06:00-07:00", "07:00-08:00", "08:00-09:00", "09:00-10:00",
        "10:00-11:00", "11:00-12:00", "12:00-13:00", "13:00-14:00", "14:00-15:00",
        "15:00-16:00", "16:00-17:00", "17:00-18:00"
    ],
    "arrival_rate": [8, 14, 22, 30, 35, 38, 40, 42, 38, 32, 28, 20, 12],
    "service_rate": [15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15],
    "servers": [3, 5, 2, 3, 5, 5, 2, 3, 5, 5, 5, 5, 2],
    "utilization": [0.178, 0.187, 0.733, 0.667, 0.467, 0.507, 1.333, 0.933, 0.507, 0.427, 0.373, 0.267, 0.4],
    "Lq": [0.001, 0.002, 5.429, 0.667, 0.088, 0.145, np.inf, 2.846, 0.088, 0.027, 0.010, 0.002, 0.016],
    "Wq": [0.0001, 0.0002, 0.247, 0.022, 0.003, 0.004, np.nan, 0.068, 0.003, 0.001, 0.0003, 0.0001, 0.001],
    "Ls": [0.533, 0.933, 6.4, 2.667, 2.367, 2.533, 4.0, 4.8, 2.533, 2.133, 1.867, 1.333, 0.8],
    "Ws": [0.067, 0.067, 0.291, 0.089, 0.068, 0.067, 0.1, 0.114, 0.067, 0.067, 0.067, 0.067, 0.067],
})

import os

# Set output directory to converted_daily_data
output_dir = os.path.join(os.path.dirname(__file__), "converted_daily_data")
os.makedirs(output_dir, exist_ok=True)

# Save to CSV
sample_file = os.path.join(output_dir, "sample_data.csv")
sample_data.to_csv(sample_file, index=False)
print(f"✅ Created {sample_file}")
print(sample_data)

# Alternative: Create minimal, clean sample
minimal_sample = pd.DataFrame({
    "time_interval": ["08:00-09:00", "09:00-10:00", "10:00-11:00"],
    "arrival_rate": [30.0, 35.0, 38.0],
    "service_rate": [15.0, 15.0, 15.0],
    "servers": [3, 5, 5],
    "utilization": [0.667, 0.467, 0.507],
    "Lq": [0.5, 0.1, 0.1],
    "Wq": [0.016, 0.003, 0.002],
    "Ls": [2.5, 2.4, 2.6],
    "Ws": [0.083, 0.069, 0.068],
})

minimal_file = os.path.join(output_dir, "minimal_sample.csv")
minimal_sample.to_csv(minimal_file, index=False)
print(f"\n✅ Created {minimal_file}")
print(minimal_sample)
