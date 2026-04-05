import json
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import os

RESULTS = "benchmarks/results/benchmark_results.json"
OUT = "analysis/visualizations"
os.makedirs(OUT, exist_ok=True)

with open(RESULTS) as f:
    data = json.load(f)

# Chart 1: Single vs Batched latency
fig, ax = plt.subplots(figsize=(8, 5))
svb = data["single_vs_batched"]
ax.bar(["Single Requests\n(sequential)", "Concurrent Requests\n(batched)"],
       [svb["single_avg_ms"], svb["batched_avg_ms"]],
       color=["#d62728", "#2ca02c"])
ax.set_ylabel("Average Latency (ms)")
ax.set_title("Single vs Batched Request Latency")
for i, v in enumerate([svb["single_avg_ms"], svb["batched_avg_ms"]]):
    ax.text(i, v + 1, f"{v:.1f}ms", ha="center", fontweight="bold")
plt.tight_layout()
plt.savefig(f"{OUT}/single_vs_batched.png", dpi=150)
print("✓ Chart 1 saved")

# Chart 2: Cold vs Warm cache
fig, ax = plt.subplots(figsize=(8, 5))
cvw = data["cold_vs_warm"]
ax.bar(["Cold Cache\n(first request)", "Warm Cache\n(cached response)"],
       [cvw["cold_avg_ms"], cvw["warm_avg_ms"]],
       color=["#1f77b4", "#ff7f0e"])
ax.set_ylabel("Average Latency (ms)")
ax.set_title(f"Cold vs Warm Cache Latency (Speedup: {cvw['speedup_factor']:.1f}x)")
for i, v in enumerate([cvw["cold_avg_ms"], cvw["warm_avg_ms"]]):
    ax.text(i, v + 0.5, f"{v:.1f}ms", ha="center", fontweight="bold")
plt.tight_layout()
plt.savefig(f"{OUT}/cold_vs_warm_cache.png", dpi=150)
print("✓ Chart 2 saved")

# Chart 3: Latency vs Load
fig, ax = plt.subplots(figsize=(9, 5))
tp = data["throughput"]
rps_vals = [str(k) for k in sorted(tp.keys(), key=int)]
avg_lats = [tp[r]["avg_latency_ms"] for r in rps_vals]
p95_lats = [tp[r]["p95_latency_ms"] for r in rps_vals]
ax.plot(rps_vals, avg_lats, "o-", color="#1f77b4", label="Avg Latency")
ax.plot(rps_vals, p95_lats, "s--", color="#d62728", label="P95 Latency")
ax.set_xlabel("Load (requests/second)")
ax.set_ylabel("Latency (ms)")
ax.set_title("Latency vs Load Level")
ax.legend()
plt.tight_layout()
plt.savefig(f"{OUT}/throughput_latency.png", dpi=150)
print("✓ Chart 3 saved")

# Chart 4: Cache hit rate
fig, ax = plt.subplots(figsize=(8, 5))
hit_rates = [tp[r]["cache_hit_rate"] * 100 for r in rps_vals]
ax.bar(rps_vals, hit_rates, color="#9467bd")
ax.set_xlabel("Load (requests/second)")
ax.set_ylabel("Cache Hit Rate (%)")
ax.set_title("Cache Hit Rate by Load Level")
ax.set_ylim(0, 100)
plt.tight_layout()
plt.savefig(f"{OUT}/cache_hit_rate.png", dpi=150)
print("✓ Chart 4 saved")