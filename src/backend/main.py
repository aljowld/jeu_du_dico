"""Main entry point for the FastAPI dictionary game application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.backend.core.database import init_db
from src.backend.routers import auth, game


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan context to run startup and shutdown tasks."""
    init_db()
    yield


app = FastAPI(
    title="Dictionary Game API",
    description="Backend API for the multiplayer dictionary party game.",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(game.router)
app.include_router(game.ws_router)


@app.get("/api/health", tags=["health"], summary="Service health check")
def health_check() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}


# Mount static frontend build if it exists
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
