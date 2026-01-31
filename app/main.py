from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI

from app.config import Settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict]:
    settings = Settings()

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    async with httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30.0,
    ) as client:
        logger.info("Started with model=%s", settings.litellm_model)
        yield {"settings": settings, "http_client": client}
        logger.info("Shutting down")


app = FastAPI(title="Automatic GH Review", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def create_app() -> FastAPI:
    """Import-time hook so routers can be registered after all modules load."""
    from app.webhook.router import router as webhook_router  # noqa: E402

    app.include_router(webhook_router)
    return app
