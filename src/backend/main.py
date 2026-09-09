"""Main entry point for the FastAPI dictionary game application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.database import init_db
from src.backend.routers import auth


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


@app.get("/api/health", tags=["health"], summary="Service health check")
def health_check() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}

