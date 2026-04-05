# benchmarks/load_generator.py

import asyncio
import aiohttp
import time
import random

PROMPTS = [
    "The future of artificial intelligence is",
    "Machine learning models can be used to",
    "In the context of natural language processing",
    "Deep learning has revolutionized the way",
    "The most important factor in model performance is",
]


async def send_request(session: aiohttp.ClientSession, prompt: str,
                       results: list, semaphore: asyncio.Semaphore):
    async with semaphore:
        start = time.perf_counter()
        try:
            async with session.post(
                "http://localhost:8000/generate",
                json={"prompt": prompt, "max_new_tokens": 20},
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                data = await resp.json()
                elapsed = (time.perf_counter() - start) * 1000
                results.append({
                    "latency_ms": elapsed,
                    "cached": data.get("cached", False),
                    "success": True
                })
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            results.append({"latency_ms": elapsed, "cached": False,
                            "success": False, "error": str(e)})


async def run_load(requests_per_second: int, duration_seconds: int,
                   repeat_ratio: float = 0.3):
    """
    repeat_ratio: fraction of requests that reuse prompts (tests cache hits).
    """
    results = []
    semaphore = asyncio.Semaphore(50)

    async with aiohttp.ClientSession() as session:
        end_time = time.time() + duration_seconds
        interval = 1.0 / requests_per_second

        while time.time() < end_time:
            if random.random() < repeat_ratio:
                prompt = random.choice(PROMPTS)
            else:
                prompt = f"Tell me about topic number {random.randint(1000, 9999)}"

            asyncio.create_task(
                send_request(session, prompt, results, semaphore)
            )
            await asyncio.sleep(interval)

        await asyncio.sleep(5)

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rps", type=int, default=10,
                        help="Requests per second")
    parser.add_argument("--duration", type=int, default=30,
                        help="Duration in seconds")
    args = parser.parse_args()

    results = asyncio.run(run_load(args.rps, args.duration))
    successes = [r for r in results if r["success"]]
    print(f"Total requests: {len(results)}")
    print(f"Successful: {len(successes)}")
    if successes:
        latencies = [r["latency_ms"] for r in successes]
        cached = sum(1 for r in successes if r["cached"])
        print(f"Avg latency: {sum(latencies)/len(latencies):.1f}ms")
        print(f"Cache hits: {cached}/{len(successes)} "
              f"({100*cached/len(successes):.1f}%)")