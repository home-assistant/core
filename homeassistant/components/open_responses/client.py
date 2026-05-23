"""Open Responses client used by Home Assistant."""

from collections.abc import AsyncGenerator
import json
from typing import Any

import httpx

from .exceptions import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    ModelError,
    RateLimitError,
)

DEFAULT_TIMEOUT = 60.0


def _normalize_base_url(base_url: str) -> str:
    """Return the provider root URL used before the Open Responses path."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized[:-3]
    return normalized


def _extract_error_message(response: httpx.Response) -> tuple[str, Any | None]:
    """Return a useful message and parsed response body."""
    try:
        body = response.json()
    except json.JSONDecodeError:
        text = response.text
        return text or response.reason_phrase, text or None

    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code")
            if message:
                return str(message), body
        if isinstance(error, str):
            return error, body
        message = body.get("message")
        if message:
            return str(message), body

    return response.reason_phrase, body


def _raise_mapped_status(response: httpx.Response) -> None:
    """Raise a Home Assistant Open Responses error for failed status codes."""
    if response.is_success:
        return

    message, body = _extract_error_message(response)
    status_code = response.status_code
    error_kwargs = {"status_code": status_code, "response_body": body}

    if status_code in (401, 403):
        raise AuthenticationError(message, **error_kwargs)
    if status_code == 429:
        raise RateLimitError(message, **error_kwargs)
    if status_code in (400, 422):
        raise BadRequestError(message, **error_kwargs)
    if status_code == 404:
        raise ModelError(message, **error_kwargs)
    raise APIStatusError(message, **error_kwargs)


def _map_connection_error(error: httpx.HTTPError) -> APIConnectionError:
    """Map httpx connection failures to integration errors."""
    mapped_error = APIConnectionError(str(error))
    mapped_error.__cause__ = error
    return mapped_error


async def _parse_async_sse_lines(
    lines: AsyncGenerator[str],
) -> AsyncGenerator[dict[str, Any]]:
    """Parse server-sent events into Open Responses event dictionaries."""
    event_type = "message"
    data_lines: list[str] = []

    async for line in lines:
        if not line:
            if data_lines:
                data_str = "\n".join(data_lines)
                data_lines.clear()
                if data_str != "[DONE]":
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        pass
                    else:
                        if isinstance(data, dict):
                            data.setdefault("type", event_type)
                            yield data
                event_type = "message"
            continue

        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_type = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())


class AsyncOpenResponsesClient:
    """Async client for the Open Responses API."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float | httpx.Timeout | None = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the client."""
        self.base_url = _normalize_base_url(base_url)
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        self._client = http_client
        self._owns_client = http_client is None
        self.timeout = timeout

    @property
    def client(self) -> httpx.AsyncClient:
        """Return the underlying HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def async_close(self) -> None:
        """Close the owned HTTP client."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()

    async def create(
        self,
        *,
        model: str,
        input: str | list[dict[str, Any]],
        stream: bool = False,
        max_tool_calls: int | None = None,
        max_output_tokens: int | None = None,
        store: bool | None = None,
        tools: list[dict[str, Any]] | None = None,
        user: str | None = None,
        text: dict[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **extra_fields: Any,
    ) -> dict[str, Any] | AsyncGenerator[dict[str, Any]]:
        """Create a response."""
        request = {
            "model": model,
            "input": input,
            "stream": stream,
            "max_tool_calls": max_tool_calls,
            "max_output_tokens": max_output_tokens,
            "store": store,
            "tools": tools,
            "user": user,
            "text": text,
            **extra_fields,
        }
        body = {key: value for key, value in request.items() if value is not None}
        url = f"{self.base_url}/v1/responses"

        if stream:
            return self._stream_request(url, body, timeout=timeout)

        try:
            response = await self.client.post(
                url,
                json=body,
                headers=self.headers,
                timeout=self.timeout if timeout is None else timeout,
            )
        except httpx.HTTPError as err:
            raise _map_connection_error(err) from err

        _raise_mapped_status(response)
        return response.json()

    async def _stream_request(
        self,
        url: str,
        body: dict[str, Any],
        *,
        timeout: float | httpx.Timeout | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        """Stream a response."""
        try:
            async with self.client.stream(
                "POST",
                url,
                json=body,
                headers=self.headers,
                timeout=self.timeout if timeout is None else timeout,
            ) as response:
                if not response.is_success:
                    await response.aread()
                _raise_mapped_status(response)
                async for event in _parse_async_sse_lines(response.aiter_lines()):
                    yield event
        except httpx.HTTPError as err:
            raise _map_connection_error(err) from err
