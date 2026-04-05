# ids568-milestone5-sgund12
MLOps Milestone 5: LLM Inference Optimization with Batching and Caching

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the server
```bash
uvicorn src.server:app --host 0.0.0.0 --port 8000
```
The model downloads automatically on first start (~30 seconds).

### 3. Test the server
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "The future of AI is", "max_new_tokens": 20}'
```

## Running Benchmarks

With the server running in one terminal:
```bash
python benchmarks/run_benchmarks.py
```

Results are saved to `benchmarks/results/benchmark_results.json`.

## Generating Charts
```bash
python analysis/visualizations/generate_charts.py
```

## Configuration
Edit `src/config.py` to tune:
- `MAX_BATCH_SIZE` — max requests per batch (default: 8)
- `BATCH_TIMEOUT_MS` — batch window in milliseconds (default: 50)
- `CACHE_TTL_SECONDS` — cache expiry time (default: 300)
- `CACHE_MAX_ENTRIES` — max cached responses (default: 1000)

## Architecture
- `src/server.py` — FastAPI app, request routing, cache check
- `src/batching.py` — Hybrid batcher (size + timeout)
- `src/caching.py` — LRU cache with TTL and hashed keys
- `src/config.py` — Centralized configuration