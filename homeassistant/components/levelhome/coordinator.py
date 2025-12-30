"""Coordinator and device mapping for Level Lock devices."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ._lib.level_ha import WebsocketManager as LevelWebsocketManager

LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL: timedelta | None = None  # Use push updates; no periodic polling


@dataclass(slots=True)
class LevelLockDevice:
    """Representation of a Level lock device."""

    lock_id: str
    uuid: str
    name: str
    is_locked: bool | None
    state: str | None = None


class _ClientAdapter:
    """Adapter to parse device data from WebSocket responses."""

    def __init__(self, ws_manager: LevelWebsocketManager) -> None:
        self._ws_manager = ws_manager

    async def async_list_locks(self) -> list[LevelLockDevice]:
        LOGGER.info("Fetching device list from WebSocket")
        devices_data = await self._ws_manager.async_get_devices()
        LOGGER.info("Retrieved %d devices from WebSocket", len(devices_data))
        devices: list[LevelLockDevice] = []
        for item in devices_data:
            device_uuid = item.get("device_uuid") or item.get("uuid") or item.get("UUID")
            name = item.get("name") or device_uuid or "Level Lock"
            LOGGER.info("Processing device: uuid=%s, name=%s", device_uuid, name)
            is_locked: bool | None = None
            state: str | None = None
            device_state = await self._ws_manager.async_get_device_state(str(device_uuid))
            LOGGER.info("Device state response for %s: %s", device_uuid, device_state)
            if device_state:
                bolt_state = device_state.get("bolt_state")
                if bolt_state:
                    state = str(bolt_state)
                    is_locked = str(bolt_state).lower() == "locked"
                    LOGGER.info("Device %s: bolt_state=%s, is_locked=%s", device_uuid, state, is_locked)
                else:
                    LOGGER.warning("Device %s: No bolt_state in response", device_uuid)
            else:
                LOGGER.warning("Device %s: No device_state received", device_uuid)
            devices.append(
                LevelLockDevice(
                    lock_id=str(device_uuid),
                    uuid=str(device_uuid),
                    name=str(name),
                    is_locked=is_locked,
                    state=state,
                )
            )
            LOGGER.info("Created LevelLockDevice: lock_id=%s, is_locked=%s, state=%s", device_uuid, is_locked, state)
        return devices


class LevelLocksCoordinator(DataUpdateCoordinator[dict[str, LevelLockDevice]]):
    """Coordinator to fetch all locks for the account."""

    def __init__(
        self, hass: HomeAssistant, ws_manager: LevelWebsocketManager, *, config_entry: ConfigEntry
    ) -> None:
        """Initialize the Level locks coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name="Level Lock devices",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self._ws_manager = ws_manager
        self._client = _ClientAdapter(ws_manager)

    async def _async_update_data(self) -> dict[str, LevelLockDevice]:
        try:
            devices = await self._client.async_list_locks()
        except Exception as err:
            raise UpdateFailed(str(err)) from err
        result: dict[str, LevelLockDevice] = {d.lock_id: d for d in devices}
        for device in result.values():
            self._ws_manager.register_device_uuid(device.lock_id, device.uuid)
        return result

    async def async_stop_push(self) -> None:
        """Stop push connections."""
        await self._ws_manager.async_stop()

    async def async_handle_push_update(
        self, lock_id: str, is_locked: bool | None, payload: dict[str, Any] | None
    ) -> None:
        """Handle a push state update from the WebSocket."""
        current = dict(self.data or {})
        device = current.get(lock_id)
        if device is None:
            device_name = payload.get("device_name") if payload else None
            if device_name:
                for d in current.values():
                    if d.name == device_name:
                        device = d
                        LOGGER.info("Matched device by name: %s -> %s", lock_id, device.lock_id)
                        break
            if device is None:
                LOGGER.info("Creating new device entry from push update: %s (%s)", lock_id, device_name)
                device = LevelLockDevice(
                    lock_id=lock_id,
                    uuid=lock_id,
                    name=device_name or lock_id,
                    is_locked=is_locked,
                    state=payload.get("state") if payload else None,
                )
                current[lock_id] = device
                self._ws_manager.register_device_uuid(device.lock_id, device.uuid)
                self.async_set_updated_data(current)
                LOGGER.info("Added new device %s: is_locked=%s, state=%s", device.lock_id, device.is_locked, device.state)
                return

        updates = {}
        if is_locked is not None:
            updates["is_locked"] = is_locked
        if payload is not None and "state" in payload:
            state = payload.get("state")
            updates["state"] = str(state) if state is not None else None
        if updates:
            updated_device = replace(device, **updates)
            current[device.lock_id] = updated_device
            LOGGER.info("Updated device %s: is_locked=%s, state=%s", updated_device.lock_id, updated_device.is_locked, updated_device.state)
            self.async_set_updated_data(current)

    async def async_send_command(self, lock_id: str, command: str) -> None:
        """Send a command via WebSocket."""
        if command in ("lock", "unlock"):
            try:
                await self._ws_manager.async_send_command(
                    lock_id,
                    command,  # type: ignore[arg-type]
                )
            except Exception as err:
                raise UpdateFailed(f"Command failed: {err}") from err
