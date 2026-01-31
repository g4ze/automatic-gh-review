from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import Depends, Request

from app.config import Settings


def get_settings(request: Request) -> Settings:
    return request.state.settings  # type: ignore[no-any-return]


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.state.http_client  # type: ignore[no-any-return]


SettingsDep = Annotated[Settings, Depends(get_settings)]
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
