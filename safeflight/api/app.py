"""FastAPI app. Phase 1 has only the health check; search, runs and SSE arrive in Phase 9."""

from fastapi import FastAPI

from safeflight.config import get_settings

app = FastAPI(
    title="SafeFlight API",
    version="0.1.0",
    description="Compares the airlines on a route by their public safety record.",
)


@app.get("/health", tags=["health"])
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "models": {"fast": s.model_fast, "strong": s.model_strong}}
