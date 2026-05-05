"""Demonstrate lean cost optimization using day 10 data."""

import pandas as pd
from optimization import lean_optimize_segments

# Load day 10 data
day10_data = pd.read_csv("../all data/day10.csv")

# Group by time and compute aggregated lambda and mu for each hour
hourly_agg = day10_data.groupby("Time").agg({
    "lambda": "mean",
    "mu": "mean",
}).reset_index()

# Rename column and add servers
hourly_agg.columns = ["time", "lambda", "mu"]
hourly_agg["c"] = 1  # Currently 1 server per hour
hourly_agg["lambda"] = hourly_agg["lambda"].round(2)
hourly_agg["mu"] = hourly_agg["mu"].round(2)

# Convert to list of dicts for optimization
hourly_segments = hourly_agg.to_dict("records")

# Run lean optimization with target_rho = 0.75
# This means: "Find configurations where ρ ≤ 0.75 while minimizing total cost"
optimized = lean_optimize_segments(
    hourly_segments,
    target_rho=0.75,  # Target utilization (ρ)
    default_server_cost=87.0,  # Cost per server per hour
    max_servers=8,
    check_waste_hours=True  # Enable waste hours condition: remove servers if ρ ≤ 30%
)

# Display results
print("=" * 100)
print("LEAN COST OPTIMIZATION REPORT - DAY 10")
print("=" * 100)
print("\nObjective: Minimize traffic intensity (p/rho) while keeping total cost low")
print("Target p: 0.75 (75% utilization)")
print("Waste Hours Detector: Remove servers when p <= 30% (and p stays <= 70%)\n")

for segment in optimized:
    print(f"\n{segment['time']}")
    print("-" * 100)
    print(f"  Current:  {segment['current_c']} server(s) | "
          f"p = {segment['current_rho']:.3f} | "
          f"Total Cost = P{segment['current_total_cost']:.2f} "
          f"(Server: P{segment['current_server_cost']:.2f} + Wait: P{segment.get('current_waiting_cost', 0):.2f})")
    
    # Highlight waste hours
    waste_marker = ""
    if segment['current_rho'] is not None and segment['current_rho'] <= 0.30:
        waste_marker = " [WASTE DETECTED: p <= 30%]"
    print(f"{waste_marker}")
    
    if segment['min_servers_for_target_rho']:
        print(f"  -> Needs {segment['min_servers_for_target_rho']} server(s) to reach target p <= 0.75")
    
    print(f"  Recommendation: {segment['recommendation']}")
    
    # Show all scenarios (only first few to avoid clutter)
    print("\n  Server Scenarios:")
    print("  " + "-" * 96)
    print("    Servers |  p    | Stable | Wq (hrs) | Server P | Wait P  | Total P  ")
    print("  " + "-" * 96)
    
    for scenario in segment["scenarios"][:5]:  # Show first 5 scenarios
        stable_str = "Yes" if scenario["stable"] else "No"
        wq_str = f"{scenario['Wq']:.4f}" if scenario["Wq"] is not None else "  N/A  "
        wait_cost_str = f"{scenario['waiting_cost']:.2f}" if scenario["waiting_cost"] is not None else "  N/A  "
        rho_str = f"{scenario['rho']:.3f}" if scenario['rho'] is not None else " N/A "
        
        marker = ""
        if scenario["servers"] == segment['current_c']:
            marker = " <- CURRENT"
        if scenario["servers"] == segment['recommended_c']:
            marker = " <- RECOMMENDED *"
        
        print(f"    {scenario['servers']:6d}  | {rho_str:6s} | {stable_str:6s} | "
              f"{wq_str:8s} | {scenario['server_cost']:8.2f} | {wait_cost_str:7s} | "
              f"{scenario['total_cost']:8.2f} {marker}")

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)

total_current_cost = sum(seg["current_total_cost"] for seg in optimized)
total_recommended_cost = sum(seg["recommended_total_cost"] for seg in optimized)
total_servers_current = sum(seg["current_c"] for seg in optimized)
total_servers_recommended = sum(seg["recommended_c"] for seg in optimized)

rho_values = [seg["current_rho"] for seg in optimized if seg["current_rho"] is not None]
avg_rho_current = sum(rho_values) / len(rho_values) if rho_values else 0

rho_values_rec = [seg["recommended_rho"] for seg in optimized if seg["recommended_rho"] is not None]
avg_rho_recommended = sum(rho_values_rec) / len(rho_values_rec) if rho_values_rec else 0

print(f"\nCurrent Configuration:")
print(f"  Total Servers: {total_servers_current}")
print(f"  Average p: {avg_rho_current:.3f}")
print(f"  Total Daily Cost: P{total_current_cost:.2f}")

print(f"\nRecommended Configuration:")
print(f"  Total Servers: {total_servers_recommended}")
print(f"  Average p: {avg_rho_recommended:.3f}")
print(f"  Total Daily Cost: P{total_recommended_cost:.2f}")

cost_difference = total_current_cost - total_recommended_cost
if cost_difference > 0:
    print(f"\n[SUCCESS] Potential SAVINGS: P{cost_difference:.2f} per day")
else:
    print(f"\n[INFO] Additional Cost: P{abs(cost_difference):.2f} per day")

server_difference = total_servers_recommended - total_servers_current
if server_difference > 0:
    print(f"  (Requires adding {server_difference} server(s) across the day)")
elif server_difference < 0:
    print(f"  (Can remove {abs(server_difference)} server(s) across the day)")
else:
    print(f"  (No server count changes needed)")

