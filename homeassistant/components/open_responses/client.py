"""Client for Open Responses endpoints."""

from collections.abc import AsyncGenerator, AsyncIterable
import json
from typing import Any

from httpx import AsyncClient, HTTPStatusError, RequestError, Response
from openresponses_types.types import CreateResponseBody


class OpenResponsesError(Exception):
    """Base Open Responses client error."""


class OpenResponsesAuthError(OpenResponsesError):
    """Open Responses authentication error."""


class OpenResponsesRateLimitError(OpenResponsesError):
    """Open Responses rate limit error."""


class OpenResponsesInvalidModelError(OpenResponsesError):
    """Open Responses model validation error."""


class OpenResponsesConnectionError(OpenResponsesError):
    """Open Responses connection error."""


class OpenResponsesClient:
    """Minimal Open Responses HTTP client."""

    def __init__(self, http_client: AsyncClient, api_key: str, base_url: str) -> None:
        """Initialize the client."""
        self._http_client = http_client
        self._url = f"{base_url.rstrip('/')}/responses"
        self._json_headers = {
            "authorization": f"Bearer {api_key}",
            "accept": "application/json",
        }
        self._stream_headers = {
            "authorization": f"Bearer {api_key}",
            "accept": "text/event-stream",
        }

    async def create_response(self, **params: Any) -> dict[str, Any]:
        """Create a non-streaming response."""
        body = _format_request_body({**params, "stream": False})

        try:
            response = await self._http_client.post(
                self._url,
                json=body,
                headers=self._json_headers,
            )
            response.raise_for_status()
        except HTTPStatusError as err:
            _raise_client_error(err)
        except RequestError as err:
            raise OpenResponsesConnectionError(
                "Error connecting to Open Responses endpoint"
            ) from err

        try:
            return response.json()
        except ValueError as err:
            raise OpenResponsesConnectionError(
                "Open Responses endpoint returned invalid JSON"
            ) from err

    async def stream_response(self, **params: Any) -> AsyncGenerator[dict[str, Any]]:
        """Create a streaming response."""
        body = _format_request_body({**params, "stream": True})

        try:
            async with self._http_client.stream(
                "POST",
                self._url,
                json=body,
                headers=self._stream_headers,
            ) as response:
                if response.is_error:
                    await response.aread()
                response.raise_for_status()
                async for event in _iter_sse_events(response.aiter_lines()):
                    yield event
        except HTTPStatusError as err:
            _raise_client_error(err)
        except RequestError as err:
            raise OpenResponsesConnectionError(
                "Error connecting to Open Responses endpoint"
            ) from err


def _format_request_body(params: dict[str, Any]) -> dict[str, Any]:
    """Validate and format an Open Responses request body."""
    CreateResponseBody(**params)
    return _strip_none_values(params)


def _strip_none_values(value: Any) -> Any:
    """Strip null values while preserving request dictionaries."""
    if isinstance(value, dict):
        return {
            key: _strip_none_values(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [_strip_none_values(item) for item in value]
    return value


async def _iter_sse_events(lines: AsyncIterable[str]) -> AsyncGenerator[dict[str, Any]]:
    """Yield JSON server-sent events from an Open Responses stream."""
    event_type: str | None = None
    data_lines: list[str] = []
    done = False

    async def flush_event() -> dict[str, Any] | None:
        nonlocal done, event_type, data_lines

        if not data_lines:
            event_type = None
            return None

        data = "\n".join(data_lines)
        event_type_for_payload = event_type
        event_type = None
        data_lines = []

        if data == "[DONE]":
            done = True
            return None

        try:
            event = json.loads(data)
        except json.JSONDecodeError as err:
            raise OpenResponsesConnectionError(
                "Open Responses endpoint returned invalid event data"
            ) from err
        if event_type_for_payload and "type" not in event:
            event["type"] = event_type_for_payload
        return event

    async for line in lines:
        if done:
            return
        if not line:
            if event := await flush_event():
                yield event
            if done:
                return
            continue
        if line.startswith("event:"):
            event_type = line.split(":", 1)[1].strip()
            continue
        if not line.startswith("data:"):
            continue

        data_lines.append(line.split(":", 1)[1].removeprefix(" "))

    if event := await flush_event():
        yield event


def _raise_client_error(err: HTTPStatusError) -> None:
    """Raise Home Assistant-friendly client errors."""
    status_code = err.response.status_code
    if status_code in (401, 403):
        raise OpenResponsesAuthError("Authentication failed")
    if status_code == 429:
        raise OpenResponsesRateLimitError("Rate limited")
    if status_code == 400 and _response_error_mentions_model(err.response):
        raise OpenResponsesInvalidModelError("Invalid model")
    raise OpenResponsesConnectionError("Open Responses endpoint error")


def _response_error_mentions_model(response: Response) -> bool:
    """Return whether an error response points at the requested model."""
    try:
        body = response.json()
    except ValueError:
        return False

    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return False

    return any(
        "model" in str(error.get(key, "")).lower()
        for key in ("code", "param", "message")
    )
