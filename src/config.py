# src/config.py

class Config:
    # Batching settings
    MAX_BATCH_SIZE: int = 8           # Max requests per batch
    BATCH_TIMEOUT_MS: float = 50.0    # Wait up to 50ms to fill a batch

    # Caching settings
    CACHE_MAX_ENTRIES: int = 1000     # Max cached responses
    CACHE_TTL_SECONDS: float = 300.0  # Responses expire after 5 minutes

    # Model settings
    MODEL_NAME: str = "sshleifer/tiny-gpt2"  # Small model, fast for testing
    MAX_NEW_TOKENS: int = 50

config = Config()