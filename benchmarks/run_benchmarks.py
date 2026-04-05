# benchmarks/run_benchmarks.py

import asyncio
import aiohttp
import json
import os
import time
import argparse
import sys
import psutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmarks.load_generator import run_load, send_request, PROMPTS

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

BASE_URL = "http://localhost:8000"


def get_memory_metrics():
    """Capture CPU and memory utilization."""
    process = psutil.Process()
    mem = process.memory_info()
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_rss_mb": round(mem.rss / 1024 / 1024, 2),
        "memory_vms_mb": round(mem.vms / 1024 / 1024, 2),
        "system_memory_percent": psutil.virtual_memory().percent,
    }


async def clear_cache():
    async with aiohttp.ClientSession() as session:
        await session.post(f"{BASE_URL}/cache/clear")


async def get_stats():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/stats") as r:
            return await r.json()


async def benchmark_single_vs_batched():
    """Compare latency: sequential single requests vs concurrent (batched)."""
    print("\n=== Benchmark 1: Single vs Batched Latency ===")
    await clear_cache()

    mem_before = get_memory_metrics()

    async with aiohttp.ClientSession() as session:
        # Single requests — one at a time
        single_latencies = []
        for i in range(10):
            prompt = f"Single request number {i} about science"
            results = []
            sem = asyncio.Semaphore(1)
            await send_request(session, prompt, results, sem)
            single_latencies.append(results[0]["latency_ms"])
            await asyncio.sleep(0.5)

        # Batched — fire many at once
        await clear_cache()
        batched_results = []
        sem = asyncio.Semaphore(50)
        tasks = [
            send_request(session,
                         f"Batched request number {i} about technology",
                         batched_results, sem)
            for i in range(10)
        ]
        await asyncio.gather(*tasks)
        batched_latencies = [r["latency_ms"] for r in batched_results
                             if r["success"]]

    mem_after = get_memory_metrics()

    result = {
        "single_avg_ms": sum(single_latencies) / len(single_latencies),
        "batched_avg_ms": sum(batched_latencies) / len(batched_latencies),
        "single_latencies": single_latencies,
        "batched_latencies": batched_latencies,
        "memory_before": mem_before,
        "memory_after": mem_after,
    }
    print(f"Single avg: {result['single_avg_ms']:.1f}ms")
    print(f"Batched avg: {result['batched_avg_ms']:.1f}ms")
    print(f"Memory RSS: {mem_after['memory_rss_mb']}MB | CPU: {mem_after['cpu_percent']}%")
    return result


async def benchmark_cold_vs_warm_cache():
    """Compare cold cache (first request) vs warm cache (cached response)."""
    print("\n=== Benchmark 2: Cold vs Warm Cache ===")
    await clear_cache()
    cold_latencies = []
    warm_latencies = []

    async with aiohttp.ClientSession() as session:
        sem = asyncio.Semaphore(1)
        for prompt in PROMPTS:
            results = []
            await send_request(session, prompt, results, sem)
            cold_latencies.append(results[0]["latency_ms"])

            results2 = []
            await send_request(session, prompt, results2, sem)
            warm_latencies.append(results2[0]["latency_ms"])

    mem = get_memory_metrics()

    result = {
        "cold_avg_ms": sum(cold_latencies) / len(cold_latencies),
        "warm_avg_ms": sum(warm_latencies) / len(warm_latencies),
        "cold_latencies": cold_latencies,
        "warm_latencies": warm_latencies,
        "speedup_factor": (sum(cold_latencies) / sum(warm_latencies)),
        "memory_metrics": mem,
    }
    print(f"Cold avg: {result['cold_avg_ms']:.1f}ms")
    print(f"Warm avg: {result['warm_avg_ms']:.1f}ms")
    print(f"Speedup: {result['speedup_factor']:.1f}x")
    print(f"Memory RSS: {mem['memory_rss_mb']}MB | CPU: {mem['cpu_percent']}%")
    return result


async def benchmark_throughput():
    """Test throughput at multiple load levels including high load."""
    print("\n=== Benchmark 3: Throughput at Multiple Load Levels ===")
    load_levels = [10, 50, 100]  # low, medium, high
    results = {}

    for rps in load_levels:
        print(f"\nTesting {rps} req/s for 20 seconds...")
        await clear_cache()
        mem_before = get_memory_metrics()
        data = await run_load(rps, duration_seconds=20, repeat_ratio=0.3)
        mem_after = get_memory_metrics()
        successes = [r for r in data if r["success"]]
        if successes:
            latencies = [r["latency_ms"] for r in successes]
            results[rps] = {
                "target_rps": rps,
                "actual_requests": len(data),
                "successful": len(successes),
                "avg_latency_ms": sum(latencies) / len(latencies),
                "p95_latency_ms": sorted(latencies)[int(0.95 * len(latencies))],
                "cache_hit_rate": sum(1 for r in successes if r["cached"]) / len(successes),
                "memory_rss_mb": mem_after["memory_rss_mb"],
                "cpu_percent": mem_after["cpu_percent"],
                "system_memory_percent": mem_after["system_memory_percent"],
            }
            print(f"  Avg latency: {results[rps]['avg_latency_ms']:.1f}ms | "
                  f"P95: {results[rps]['p95_latency_ms']:.1f}ms | "
                  f"Hit rate: {results[rps]['cache_hit_rate']:.1%} | "
                  f"Memory: {results[rps]['memory_rss_mb']}MB | "
                  f"CPU: {results[rps]['cpu_percent']}%")

    return results


async def run_all():
    results = {}
    results["single_vs_batched"] = await benchmark_single_vs_batched()
    results["cold_vs_warm"] = await benchmark_cold_vs_warm_cache()
    results["throughput"] = await benchmark_throughput()

    out_path = os.path.join(RESULTS_DIR, "benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to {out_path}")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run Milestone 5 benchmarks against a running server."
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = f"http://{args.host}:{args.port}"
    asyncio.run(run_all())


if __name__ == "__main__":
    main()