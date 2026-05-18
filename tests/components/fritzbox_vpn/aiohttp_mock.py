"""Queued aiohttp ClientSession mock for coordinator session tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any


class MockAiohttpResponse:
    """Minimal async context manager mimicking aiohttp.ClientResponse."""

    def __init__(
        self,
        status: int,
        *,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._text = text
        self.headers = headers or {}

    async def text(self) -> str:
        return self._text

    async def __aenter__(self) -> MockAiohttpResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class QueuedAiohttpSession:
    """ClientSession that returns queued responses in order for get/post/put."""

    def __init__(self, responses: list[MockAiohttpResponse]) -> None:
        self._responses: Iterator[MockAiohttpResponse] = iter(responses)
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def _dequeue(self, method: str, url: str, **kwargs: Any) -> MockAiohttpResponse:
        self.requests.append((method, url, kwargs))
        try:
            return next(self._responses)
        except StopIteration as err:
            raise AssertionError(
                f"No mock response left for {method} {url}"
            ) from err

    def get(self, url: str, **kwargs: Any) -> MockAiohttpResponse:
        return self._dequeue("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> MockAiohttpResponse:
        return self._dequeue("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> MockAiohttpResponse:
        return self._dequeue("PUT", url, **kwargs)


def json_response(payload: dict[str, Any], status: int = 200) -> MockAiohttpResponse:
    """Build a JSON data.lua style response."""
    return MockAiohttpResponse(
        status,
        text=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
