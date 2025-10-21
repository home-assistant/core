"""HTTP and auth client for Level Lock."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import api
from .const import (
    API_LOCKS_LIST_PATH,
    API_LOCK_STATUS_PATH,
    API_LOCK_COMMAND_LOCK_PATH,
    API_LOCK_COMMAND_UNLOCK_PATH,
)
from .models import LevelLockDevice


class LevelApiClient:
    """Thin HTTP client using OAuth2 for Level Lock cloud API."""

    def __init__(self, hass: HomeAssistant, auth: api.AsyncConfigEntryAuth, base_url: str) -> None:
        self._hass = hass
        self._auth = auth
        self._base_url = base_url.rstrip("/")
        self._session = aiohttp_client.async_get_clientsession(hass)

    async def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        token = await self._auth.async_get_access_token()
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        try:
            async with self._session.request(method, url, headers=headers, json=json) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise UpdateFailed(f"HTTP {resp.status} for {method} {path}: {text}")
                if resp.content_type == "application/json":
                    return await resp.json()
                return await resp.text()
        except ClientError as err:  # aiohttp error
            raise UpdateFailed(f"API error: {err}") from err

    async def async_list_locks(self) -> list[LevelLockDevice]:
        data = await self._request("GET", API_LOCKS_LIST_PATH)
        devices: list[LevelLockDevice] = []
        for item in data.get("locks", []):
            state = item.get("state")
            devices.append(
                LevelLockDevice(
                    lock_id=str(item.get("id")),
                    name=str(item.get("name") or item.get("id") or "Level Lock"),
                    is_locked=_coerce_is_locked(state),
                    state=str(state) if state is not None else None,
                )
            )
        return devices

    async def async_get_lock_status(self, lock_id: str) -> bool | None:
        data = await self._request("GET", API_LOCK_STATUS_PATH.format(lock_id=lock_id))
        return _coerce_is_locked(data.get("state"))

    async def async_lock(self, lock_id: str) -> None:
        await self._request("POST", API_LOCK_COMMAND_LOCK_PATH.format(lock_id=lock_id))

    async def async_unlock(self, lock_id: str) -> None:
        await self._request("POST", API_LOCK_COMMAND_UNLOCK_PATH.format(lock_id=lock_id))


def _coerce_is_locked(state: Any) -> bool | None:
    if state is None:
        return None
    if isinstance(state, str):
        lowered = state.lower()
        if lowered in ("locked", "lock", "secure"):
            return True
        if lowered in ("unlocked", "unlock", "unsecure"):
            return False
        if lowered in ("locking", "unlocking"):
            return None
    if isinstance(state, bool):
        return state
    return None


