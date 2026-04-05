# src/batching.py

import asyncio
from dataclasses import dataclass, field
from src.config import config


@dataclass
class InferenceRequest:
    prompt: str
    max_new_tokens: int
    future: asyncio.Future = field(default_factory=asyncio.Future)


class DynamicBatcher:
    """
    Collects incoming requests and processes them in batches.
    Uses a hybrid strategy: process when MAX_BATCH_SIZE reached
    OR when BATCH_TIMEOUT_MS elapses — whichever comes first.
    """

    def __init__(self, inference_fn, max_batch_size: int = config.MAX_BATCH_SIZE,
                 timeout_ms: float = config.BATCH_TIMEOUT_MS):
        self.inference_fn = inference_fn
        self.max_batch_size = max_batch_size
        self.timeout_s = timeout_ms / 1000.0
        self._queue = []
        self._lock = asyncio.Lock()
        self._batch_event = asyncio.Event()
        self._running = False

    async def start(self):
        """Start the background batch-processing loop."""
        self._running = True
        asyncio.create_task(self._batch_loop())

    async def stop(self):
        self._running = False

    async def submit(self, prompt: str, max_new_tokens: int) -> str:
        """
        Submit a request and wait for its result.
        The caller awaits this coroutine; it returns when the batch completes.
        """
        loop = asyncio.get_event_loop()
        request = InferenceRequest(
            prompt=prompt,
            max_new_tokens=max_new_tokens,
            future=loop.create_future()
        )

        async with self._lock:
            self._queue.append(request)
            if len(self._queue) >= self.max_batch_size:
                self._batch_event.set()

        return await request.future

    async def _batch_loop(self):
        """Background loop: wait for timeout or full batch, then process."""
        while self._running:
            try:
                await asyncio.wait_for(
                    self._batch_event.wait(),
                    timeout=self.timeout_s
                )
            except asyncio.TimeoutError:
                pass

            self._batch_event.clear()

            async with self._lock:
                if not self._queue:
                    continue
                batch = self._queue[:self.max_batch_size]
                self._queue = self._queue[self.max_batch_size:]

            await self._process_batch(batch)

    async def _process_batch(self, batch):
        """Run the model on a batch and resolve each request's future."""
        prompts = [req.prompt for req in batch]
        max_tokens = max(req.max_new_tokens for req in batch)

        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, self.inference_fn, prompts, max_tokens
            )

            for req, result in zip(batch, results):
                if not req.future.done():
                    req.future.set_result(result)

        except Exception as e:
            for req in batch:
                if not req.future.done():
                    req.future.set_exception(e)