"""Queued aiohttp ClientSession mock for coordinator session tests."""

from collections.abc import Iterator
import json
from typing import Any, Self


class MockAiohttpResponse:
    """Minimal async context manager mimicking aiohttp.ClientResponse."""

    def __init__(
        self,
        status: int,
        *,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize mock aiohttp response."""
        self.status = status
        self._text = text
        self.headers = headers or {}

    async def text(self) -> str:
        """Return response body text."""
        return self._text

    async def __aenter__(self) -> Self:
        """Enter async context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context."""


class QueuedAiohttpSession:
    """ClientSession that returns queued responses in order for get/post/put."""

    def __init__(self, responses: list[MockAiohttpResponse]) -> None:
        """Initialize session with queued responses."""
        self._responses: Iterator[MockAiohttpResponse] = iter(responses)
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def _dequeue(self, method: str, url: str, **kwargs: Any) -> MockAiohttpResponse:
        self.requests.append((method, url, kwargs))
        try:
            return next(self._responses)
        except StopIteration as err:
            raise AssertionError(f"No mock response left for {method} {url}") from err

    def get(self, url: str, **kwargs: Any) -> MockAiohttpResponse:
        """Return next queued GET response."""
        return self._dequeue("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> MockAiohttpResponse:
        """Return next queued POST response."""
        return self._dequeue("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> MockAiohttpResponse:
        """Return next queued PUT response."""
        return self._dequeue("PUT", url, **kwargs)


def json_response(payload: dict[str, Any], status: int = 200) -> MockAiohttpResponse:
    """Build a JSON data.lua style response."""
    return MockAiohttpResponse(
        status,
        text=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
