from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cache.redis_client import close_redis
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger(__name__).info("Starting Google Workspace Orchestrator")
    yield
    await close_redis()
    logging.getLogger(__name__).info("Shutting down")


app = FastAPI(
    title="Google Workspace Orchestrator",
    description="Intelligent orchestrator for Gmail, Google Calendar, and Google Drive",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.auth import router as auth_router
from app.api.v1.query import router as query_router
from app.api.v1.sync import router as sync_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(query_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
