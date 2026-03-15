"""Client for the LM Studio REST API."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
import json
import logging
from typing import Any, Final

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

_HEADER_AUTHORIZATION: Final = "Authorization"


class LMStudioError(Exception):
    """Base error for LM Studio client."""


class LMStudioAuthError(LMStudioError):
    """Raised when authentication fails."""


class LMStudioConnectionError(LMStudioError):
    """Raised when a connection error occurs."""


class LMStudioResponseError(LMStudioError):
    """Raised when the server returns an unexpected response."""


@dataclass(frozen=True, slots=True)
class LMStudioStreamEvent:
    """Represents a single SSE event from LM Studio."""

    name: str
    data: dict[str, Any]


class LMStudioClient:
    """Client for the LM Studio REST API."""

    def __init__(
        self, hass: HomeAssistant, base_url: str, api_key: str | None, timeout: float
    ) -> None:
        """Initialize the client."""
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._session = async_get_clientsession(hass)

    def _headers(self) -> dict[str, str]:
        """Return headers for requests."""
        if not self._api_key:
            return {}
        return {_HEADER_AUTHORIZATION: f"Bearer {self._api_key}"}

    async def async_list_models(self) -> list[dict[str, Any]]:
        """Return the list of available models."""
        url = f"{self._base_url}/api/v1/models"
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        try:
            async with self._session.get(
                url, headers=self._headers(), timeout=timeout
            ) as resp:
                if resp.status in (401, 403):
                    raise LMStudioAuthError("Authentication failed")
                if resp.status >= 400:
                    message = await resp.text()
                    raise LMStudioResponseError(
                        f"Unexpected response ({resp.status}): {message}"
                    )
                payload = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LMStudioConnectionError("Unable to connect") from err

        models = payload.get("models")
        if not isinstance(models, list):
            raise LMStudioResponseError("Invalid models response")

        return [model for model in models if isinstance(model, dict)]

    async def async_stream_chat(
        self, payload: dict[str, Any]
    ) -> AsyncGenerator[LMStudioStreamEvent]:
        """Stream chat events from the server."""
        url = f"{self._base_url}/api/v1/chat"
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=self._timeout)
        try:
            async with self._session.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=timeout,
            ) as resp:
                if resp.status in (401, 403):
                    raise LMStudioAuthError("Authentication failed")
                if resp.status >= 400:
                    message = await resp.text()
                    raise LMStudioResponseError(
                        f"Unexpected response ({resp.status}): {message}"
                    )
                async for event in _iter_sse(resp):
                    yield event
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LMStudioConnectionError("Unable to connect") from err


async def _iter_sse(
    response: aiohttp.ClientResponse,
) -> AsyncGenerator[LMStudioStreamEvent]:
    """Yield parsed SSE events from a response."""
    event_name: str | None = None
    data_lines: list[str] = []

    async for raw_line in response.content:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if not line:
            if not data_lines:
                event_name = None
                continue

            data_text = "\n".join(data_lines)
            data_lines = []

            try:
                payload = json.loads(data_text) if data_text else {}
            except json.JSONDecodeError:
                _LOGGER.debug("Skipping invalid SSE payload: %s", data_text)
                event_name = None
                continue

            resolved_name = event_name or payload.get("type")
            if not isinstance(resolved_name, str):
                event_name = None
                continue

            event_name = None
            yield LMStudioStreamEvent(resolved_name, payload)
            continue

        if line.startswith(":"):
            continue

        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
            continue

        if line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
            continue

    if data_lines:
        data_text = "\n".join(data_lines)
        try:
            payload = json.loads(data_text) if data_text else {}
        except json.JSONDecodeError:
            _LOGGER.debug("Skipping invalid SSE payload: %s", data_text)
            return

        resolved_name = event_name or payload.get("type")
        if isinstance(resolved_name, str):
            yield LMStudioStreamEvent(resolved_name, payload)
