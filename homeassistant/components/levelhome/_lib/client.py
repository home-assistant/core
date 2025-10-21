"""Library HTTP client for Level Lock (no Home Assistant dependencies)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import ClientError, ClientSession

from .protocol import coerce_is_locked

# Async token provider callable type
TokenProvider = Callable[[], Awaitable[str]]


class ApiError(Exception):
    """Raised when a Level HTTP API call fails."""


class Client:
    """Minimal async HTTP client for Level endpoints (library-style).

    This class is intentionally HA-agnostic. It relies on an injected
    aiohttp ClientSession and an async token provider callable.
    """

    def __init__(
        self, session: ClientSession, base_url: str, get_token: TokenProvider
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._get_token = get_token

    async def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> Any:
        token = await self._get_token()
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        try:
            async with self._session.request(
                method, url, headers=headers, json=json
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise ApiError(f"HTTP {resp.status} for {method} {path}: {text}")
                if resp.content_type == "application/json":
                    return await resp.json()
                return await resp.text()
        except ClientError as err:  # aiohttp error
            raise ApiError(f"API error: {err}") from err

    async def async_list_locks(self) -> list[dict[str, Any]]:
        """Return a list of locks as raw dictionaries from the API."""
        data = await self._request("GET", "/v1/locks")
        return list(data.get("locks", []))

    async def async_get_lock_status(self, lock_id: str) -> dict[str, Any]:
        """Return the raw status payload for a lock."""
        return await self._request("GET", f"/v1/locks/{lock_id}")

    async def async_lock(self, lock_id: str) -> None:
        await self._request("POST", f"/v1/locks/{lock_id}/lock")

    async def async_unlock(self, lock_id: str) -> None:
        await self._request("POST", f"/v1/locks/{lock_id}/unlock")

    async def async_list_locks_normalized(self) -> list[dict[str, Any]]:
        """Return locks with derived boolean is_locked alongside raw state."""
        locks = await self.async_list_locks()
        normalized: list[dict[str, Any]] = []
        for item in locks:
            state = item.get("state")
            normalized.append(
                {
                    **item,
                    "is_locked": coerce_is_locked(state),
                }
            )
        return normalized

    async def async_get_lock_status_bool(self, lock_id: str) -> bool | None:
        """Return boolean locked status derived from the raw status payload."""
        data = await self.async_get_lock_status(lock_id)
        return coerce_is_locked(data.get("state"))
