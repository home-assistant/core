"""API helpers and lightweight client for Level Lock.

This module provides two layers:

1) Home Assistant auth glue (ConfigEntryAuth/AsyncConfigEntryAuth)
   that adapts HA's OAuth2 session to a token provider.

2) A minimal, Home Assistant agnostic HTTP client (Client) that accepts
   an aiohttp ClientSession and an async token provider. This allows the
   integration to treat this module as a temporary library surface while
   keeping protocol logic isolated from HA specifics.
"""

from __future__ import annotations

from asyncio import run_coroutine_threadsafe
from typing import Any, Awaitable, Callable

from aiohttp import ClientError, ClientSession

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow


# =========================
# Library-style HTTP client
# =========================

TokenProvider = Callable[[], Awaitable[str]]


class ApiError(Exception):
    """Raised when the Level HTTP API call fails."""


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


class ConfigEntryAuth:
    """Provide Level Lock authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Level Lock Auth."""
        self.hass = hass
        self.session = oauth_session

    def refresh_tokens(self) -> str:
        """Refresh and return new Level Lock tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token["access_token"]


class AsyncConfigEntryAuth:
    """Provide Level Lock authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Level Lock auth."""
        self._websession = websession
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token["access_token"]
