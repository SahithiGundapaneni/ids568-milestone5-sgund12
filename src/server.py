# src/server.py

import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import pipeline
from src.config import config
from src.caching import cache, make_cache_key
from src.batching import DynamicBatcher


# ── Model loading ─────────────────────────────────────────────────────────────

generator = None


def run_inference(prompts: list, max_new_tokens: int) -> list:
    """Synchronous inference — called from a thread pool by the batcher."""
    outputs = generator(prompts, max_new_tokens=max_new_tokens,
                        do_sample=False, pad_token_id=50256)
    return [o[0]["generated_text"] for o in outputs]


# ── App lifecycle ─────────────────────────────────────────────────────────────

batcher = DynamicBatcher(inference_fn=run_inference)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global generator
    print("Loading model...")
    generator = pipeline("text-generation", model=config.MODEL_NAME)
    print("Model loaded.")
    await batcher.start()
    yield
    await batcher.stop()


app = FastAPI(title="LLM Inference Server", lifespan=lifespan)


# ── Request/Response schemas ──────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str
    max_new_tokens: int = config.MAX_NEW_TOKENS


class GenerateResponse(BaseModel):
    text: str
    cached: bool
    latency_ms: float


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    start = time.perf_counter()

    # 1. Check cache first
    key = make_cache_key(request.prompt, request.max_new_tokens)
    cached_result = cache.get(key)

    if cached_result is not None:
        latency = (time.perf_counter() - start) * 1000
        return GenerateResponse(text=cached_result, cached=True,
                                latency_ms=round(latency, 2))

    # 2. Submit to batcher
    try:
        result = await batcher.submit(request.prompt, request.max_new_tokens)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 3. Store result in cache
    cache.set(key, result)

    latency = (time.perf_counter() - start) * 1000
    return GenerateResponse(text=result, cached=False,
                            latency_ms=round(latency, 2))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/stats")
async def stats():
    return {
        "cache_size": cache.size(),
        "cache_hit_rate": round(cache.hit_rate(), 3),
        "cache_hits": cache.hits,
        "cache_misses": cache.misses,
    }


@app.post("/cache/clear")
async def clear_cache():
    cache.clear()
    return {"status": "cache cleared"}