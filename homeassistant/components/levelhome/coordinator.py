"""Coordinator and API client for Level Lock devices."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import api
from .const import (
    API_LOCK_COMMAND_LOCK_PATH,
    API_LOCK_COMMAND_UNLOCK_PATH,
    API_LOCK_STATUS_PATH,
    API_LOCKS_LIST_PATH,
)
from .ws import LevelWebsocketManager

LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = None  # Use push updates; no periodic polling


@dataclass(slots=True)
class LevelLockDevice:
    """Representation of a Level lock device."""

    lock_id: str
    name: str
    is_locked: bool | None
    state: str | None = None  # Raw state from API for transitional states


class LevelApiClient:
    """Thin API client using the OAuth2 session for auth."""

    def __init__(
        self, hass: HomeAssistant, auth: api.AsyncConfigEntryAuth, base_url: str
    ) -> None:
        self._hass = hass
        self._auth = auth
        self._base_url = base_url.rstrip("/")
        self._session = aiohttp_client.async_get_clientsession(hass)

    async def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> Any:
        token = await self._auth.async_get_access_token()
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        try:
            async with self._session.request(
                method, url, headers=headers, json=json
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise UpdateFailed(
                        f"HTTP {resp.status} for {method} {path}: {text}"
                    )
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
        await self._request(
            "POST", API_LOCK_COMMAND_UNLOCK_PATH.format(lock_id=lock_id)
        )


def _coerce_is_locked(state: Any) -> bool | None:
    if state is None:
        return None
    if isinstance(state, str):
        lowered = state.lower()
        if lowered in ("locked", "lock", "secure"):
            return True
        if lowered in ("unlocked", "unlock", "unsecure"):
            return False
        # Transitional states should return None for is_locked
        if lowered in ("locking", "unlocking"):
            return None
    if isinstance(state, bool):
        return state
    return None


class LevelLocksCoordinator(DataUpdateCoordinator[dict[str, LevelLockDevice]]):
    """Coordinator to fetch all locks for the account."""

    def __init__(
        self, hass: HomeAssistant, client: LevelApiClient, *, config_entry: ConfigEntry
    ) -> None:
        super().__init__(
            hass,
            logger=LOGGER,
            name="Level Lock devices",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self._client = client
        self._ws_manager: LevelWebsocketManager | None = None

    async def _async_update_data(self) -> dict[str, LevelLockDevice]:
        devices = await self._client.async_list_locks()
        result: dict[str, LevelLockDevice] = {d.lock_id: d for d in devices}
        missing_status = [d for d in result.values() if d.is_locked is None]
        if missing_status:
            for device in missing_status:
                device.is_locked = await self._client.async_get_lock_status(
                    device.lock_id
                )
        return result

    def attach_ws_manager(self, ws_manager: LevelWebsocketManager) -> None:
        """Attach a WebSocket manager and start listening for push updates."""
        self._ws_manager = ws_manager

    async def async_start_push(self) -> None:
        """Start push connections for current locks."""
        if self._ws_manager is None:
            return
        if not self.data:
            return
        await self._ws_manager.async_start(list(self.data.keys()))

    async def async_stop_push(self) -> None:
        """Stop push connections."""
        if self._ws_manager is not None:
            await self._ws_manager.async_stop()

    async def async_handle_push_update(
        self, lock_id: str, is_locked: bool | None, payload: dict[str, Any] | None
    ) -> None:
        """Handle a push state update from the WebSocket."""
        current = dict(self.data or {})
        device = current.get(lock_id)
        if device is None:
            # Unknown lock; fetch list once to incorporate
            try:
                devices = await self._client.async_list_locks()
                current = {d.lock_id: d for d in devices}
                device = current.get(lock_id)
            except Exception:  # noqa: BLE001
                LOGGER.debug("Push update for unknown lock %s", lock_id)
                return
        if device is not None:
            if is_locked is not None:
                device.is_locked = is_locked
            # Update the raw state from payload if available
            if payload is not None and "state" in payload:
                state = payload.get("state")
                device.state = str(state) if state is not None else None
        self.async_set_updated_data(current)

    async def async_send_command(self, lock_id: str, command: str) -> None:
        """Send a command via push channel if available; fallback to HTTP."""
        if self._ws_manager is not None and command in ("lock", "unlock"):
            try:
                # type: ignore[arg-type]
                await self._ws_manager.async_send_command(lock_id, command)
                return
            except Exception as err:  # noqa: BLE001
                LOGGER.debug("WS command failed; falling back to HTTP: %s", err)
        if command == "lock":
            await self._client.async_lock(lock_id)
        elif command == "unlock":
            await self._client.async_unlock(lock_id)
