"""Coordinator and device mapping for Level Lock devices."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import timedelta
import logging
import time
from typing import Any, Literal

from level_ws_client import LevelWebsocketManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COMMAND_STATE_TIMEOUT,
    STATE_RETRY_INITIAL_DELAY,
    STATE_RETRY_MAX_ELAPSED,
)

LOGGER = logging.getLogger(__name__)
FALLBACK_SCAN_INTERVAL = timedelta(minutes=5)
COMMAND_IGNORE_WINDOW = 2.0


@dataclass(slots=True)
class LevelLockDevice:
    """Representation of a Level lock device."""

    lock_id: str
    uuid: str
    name: str
    is_locked: bool | None
    state: str | None = None
    reachable: bool = True


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
            device_uuid = (
                item.get("device_uuid") or item.get("uuid") or item.get("UUID")
            )
            name = item.get("name") or device_uuid or "Level Lock"
            LOGGER.info("Processing device: uuid=%s, name=%s", device_uuid, name)
            is_locked: bool | None = None
            state: str | None = None
            device_state = await self._ws_manager.async_get_device_state(
                str(device_uuid)
            )
            LOGGER.info("Device state response for %s: %s", device_uuid, device_state)
            if device_state:
                bolt_state = device_state.get("bolt_state")
                if bolt_state:
                    state = str(bolt_state)
                    is_locked = str(bolt_state).lower() == "locked"
                    LOGGER.info(
                        "Device %s: bolt_state=%s, is_locked=%s",
                        device_uuid,
                        state,
                        is_locked,
                    )
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
            LOGGER.info(
                "Created LevelLockDevice: lock_id=%s, is_locked=%s, state=%s",
                device_uuid,
                is_locked,
                state,
            )
        return devices


class LevelLocksCoordinator(DataUpdateCoordinator[dict[str, LevelLockDevice]]):
    """Coordinator to fetch all locks for the account."""

    def __init__(
        self,
        hass: HomeAssistant,
        ws_manager: LevelWebsocketManager,
        *,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the Level locks coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name="Level Lock devices",
            update_interval=FALLBACK_SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self._ws_manager = ws_manager
        self._client = _ClientAdapter(ws_manager)
        self._last_command_time: dict[str, float] = {}
        self._pending_confirmations: dict[str, asyncio.Task[None]] = {}
        self._pending_reachability: dict[str, asyncio.Task[None]] = {}
        self._refreshing_devices: set[str] = set()

    def is_device_refreshing(self, lock_id: str) -> bool:
        """Check if a device is currently refreshing state after a timeout."""
        return lock_id in self._refreshing_devices

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
        is_command_reply = (
            payload is not None
            and "bolt_state" not in payload
            and "device_name" not in payload
        )
        last_cmd_time = self._last_command_time.get(lock_id, 0)
        time_since_command = time.monotonic() - last_cmd_time
        if not is_command_reply and time_since_command < COMMAND_IGNORE_WINDOW:
            LOGGER.debug(
                "Ignoring stale push update for %s (%.1fs since command, within %.1fs window)",
                lock_id,
                time_since_command,
                COMMAND_IGNORE_WINDOW,
            )
            return
        current = dict(self.data or {})
        device = current.get(lock_id)
        if device is None:
            device_name = payload.get("device_name") if payload else None
            if device_name:
                for d in current.values():
                    if d.name == device_name:
                        device = d
                        LOGGER.info(
                            "Matched device by name: %s -> %s", lock_id, device.lock_id
                        )
                        break
            if device is None:
                LOGGER.info(
                    "Creating new device entry from push update: %s (%s)",
                    lock_id,
                    device_name,
                )
                reachable = bool(payload.get("reachable", True)) if payload else True
                device = LevelLockDevice(
                    lock_id=lock_id,
                    uuid=lock_id,
                    name=device_name or lock_id,
                    is_locked=is_locked,
                    state=payload.get("state") if payload else None,
                    reachable=reachable,
                )
                current[lock_id] = device
                self._ws_manager.register_device_uuid(device.lock_id, device.uuid)
                self.async_set_updated_data(current)
                LOGGER.info(
                    "Added new device %s: is_locked=%s, state=%s",
                    device.lock_id,
                    device.is_locked,
                    device.state,
                )
                return

        new_is_locked = device.is_locked
        new_state = device.state
        new_reachable = device.reachable
        if is_locked is not None:
            new_is_locked = is_locked
        if payload is not None and "state" in payload:
            state = payload.get("state")
            new_state = str(state) if state is not None else None
        if payload is not None and "reachable" in payload:
            new_reachable = bool(payload.get("reachable"))
            if new_reachable != device.reachable:
                LOGGER.info(
                    "Device %s reachability changed: %s -> %s",
                    device.lock_id,
                    device.reachable,
                    new_reachable,
                )
        if (
            new_is_locked != device.is_locked
            or new_state != device.state
            or new_reachable != device.reachable
        ):
            updated_device = replace(
                device,
                is_locked=new_is_locked,
                state=new_state,
                reachable=new_reachable,
            )
            current[device.lock_id] = updated_device
            LOGGER.info(
                "Updated device %s: is_locked=%s, state=%s",
                updated_device.lock_id,
                updated_device.is_locked,
                updated_device.state,
            )
            self.async_set_updated_data(current)
            if not new_reachable and device.reachable:
                self._schedule_reachability_recovery(device.lock_id)
            elif new_reachable and not device.reachable:
                self._cancel_reachability_recovery(device.lock_id)
            if (
                new_state
                and new_state.lower() in ("locked", "unlocked")
                and device.lock_id in self._pending_confirmations
            ):
                self._pending_confirmations[device.lock_id].cancel()
                self._pending_confirmations.pop(device.lock_id, None)
                LOGGER.debug(
                    "Cancelled timeout for %s - received final state %s",
                    device.lock_id,
                    new_state,
                )

    async def async_send_command(
        self, lock_id: str, command: Literal["lock", "unlock"]
    ) -> None:
        """Send a command via WebSocket."""
        self._last_command_time[lock_id] = time.monotonic()
        if lock_id in self._pending_confirmations:
            self._pending_confirmations[lock_id].cancel()
        try:
            await self._ws_manager.async_send_command(lock_id, command)
        except Exception as err:
            raise UpdateFailed(f"Command failed: {err}") from err
        self._pending_confirmations[lock_id] = asyncio.create_task(
            self._async_handle_command_timeout(lock_id, command)
        )

    async def _async_handle_command_timeout(self, lock_id: str, command: str) -> None:
        """Handle timeout waiting for state confirmation after a command."""
        try:
            await asyncio.sleep(COMMAND_STATE_TIMEOUT)
        except asyncio.CancelledError:
            return
        self._pending_confirmations.pop(lock_id, None)
        device = self.data.get(lock_id) if self.data else None
        if device is None:
            return
        current_state = device.state.lower() if device.state else None
        if current_state not in ("locking", "unlocking"):
            return
        LOGGER.warning(
            "Timeout waiting for state confirmation for %s after %s command; "
            "fetching latest state with retries",
            lock_id,
            command,
        )
        self._refreshing_devices.add(lock_id)
        self.async_set_updated_data(dict(self.data))
        bolt_state = await self._async_fetch_state_with_retry(lock_id)
        self._refreshing_devices.discard(lock_id)
        if bolt_state:
            is_locked = str(bolt_state).lower() == "locked"
            new_state = str(bolt_state).lower()
            current_data = dict(self.data or {})
            if lock_id in current_data:
                updated_device = replace(
                    current_data[lock_id],
                    is_locked=is_locked,
                    state=new_state,
                )
                current_data[lock_id] = updated_device
                LOGGER.info(
                    "Updated device %s after timeout: is_locked=%s, state=%s",
                    lock_id,
                    is_locked,
                    new_state,
                )
                self.async_set_updated_data(current_data)
                return
        LOGGER.warning(
            "Failed to fetch state for %s after retries; device may be unavailable",
            lock_id,
        )
        current_data = dict(self.data or {})
        if lock_id in current_data:
            updated_device = replace(
                current_data[lock_id],
                is_locked=None,
                state=None,
            )
            current_data[lock_id] = updated_device
            self.async_set_updated_data(current_data)

    async def _async_fetch_state_with_retry(self, lock_id: str) -> str | None:
        """Fetch device state with exponential backoff retries."""
        delay = STATE_RETRY_INITIAL_DELAY
        elapsed = 0.0
        attempt = 0
        while elapsed < STATE_RETRY_MAX_ELAPSED:
            attempt += 1
            try:
                device_state = await self._ws_manager.async_get_device_state(lock_id)
            except (TimeoutError, ConnectionError, RuntimeError, OSError):
                LOGGER.debug(
                    "State fetch attempt %d for %s failed with exception",
                    attempt,
                    lock_id,
                )
                device_state = None
            if device_state:
                bolt_state = device_state.get("bolt_state")
                if bolt_state:
                    LOGGER.debug(
                        "State fetch attempt %d for %s succeeded: %s",
                        attempt,
                        lock_id,
                        bolt_state,
                    )
                    return str(bolt_state)
            remaining = STATE_RETRY_MAX_ELAPSED - elapsed
            if remaining <= 0:
                break
            sleep_time = min(delay, remaining)
            LOGGER.debug(
                "State fetch attempt %d for %s returned no bolt_state; "
                "retrying in %.1fs",
                attempt,
                lock_id,
                sleep_time,
            )
            try:
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                return None
            elapsed += sleep_time
            delay = min(delay * 2, STATE_RETRY_MAX_ELAPSED - elapsed)
        LOGGER.debug(
            "Exhausted %d state fetch attempts for %s over %.1fs",
            attempt,
            lock_id,
            elapsed,
        )
        return None

    def _schedule_reachability_recovery(self, lock_id: str) -> None:
        """Schedule a background task to recover reachability for a device."""
        self._cancel_reachability_recovery(lock_id)
        LOGGER.debug("Scheduling reachability recovery for %s", lock_id)
        self._pending_reachability[lock_id] = asyncio.create_task(
            self._async_recover_reachability(lock_id)
        )

    def _cancel_reachability_recovery(self, lock_id: str) -> None:
        """Cancel any pending reachability recovery task for a device."""
        if task := self._pending_reachability.pop(lock_id, None):
            task.cancel()

    async def _async_recover_reachability(self, lock_id: str) -> None:
        """Attempt to restore reachability by fetching state with retries."""
        bolt_state = await self._async_fetch_state_with_retry(lock_id)
        self._pending_reachability.pop(lock_id, None)
        if bolt_state is None:
            LOGGER.info("Reachability recovery for %s failed after retries", lock_id)
            return
        current_data = dict(self.data or {})
        device = current_data.get(lock_id)
        if device is None:
            return
        is_locked = str(bolt_state).lower() == "locked"
        new_state = str(bolt_state).lower()
        current_data[lock_id] = replace(
            device, reachable=True, is_locked=is_locked, state=new_state
        )
        LOGGER.info(
            "Reachability recovery for %s succeeded: is_locked=%s, state=%s",
            lock_id,
            is_locked,
            new_state,
        )
        self.async_set_updated_data(current_data)

    async def async_handle_devices_update(self, devices: list[dict[str, Any]]) -> None:
        """Handle a device list update from the WebSocket."""
        current = dict(self.data or {})
        new_device_ids: set[str] = {
            str(device_uuid)
            for item in devices
            if (
                device_uuid := item.get("device_uuid")
                or item.get("uuid")
                or item.get("UUID")
            )
        }
        current_device_ids = set(current.keys())
        added_ids = new_device_ids - current_device_ids
        removed_ids = current_device_ids - new_device_ids
        existing_ids = new_device_ids & current_device_ids
        changed = False
        if removed_ids:
            LOGGER.info("Removing devices: %s", removed_ids)
            for device_id in removed_ids:
                current.pop(device_id, None)
            changed = True
        for device_id in existing_ids:
            device = current[device_id]
            if not device.reachable:
                LOGGER.info(
                    "Device %s is back in device list, marking reachable",
                    device_id,
                )
                device_state = await self._ws_manager.async_get_device_state(device_id)
                is_locked = device.is_locked
                state = device.state
                if device_state:
                    bolt_state = device_state.get("bolt_state")
                    if bolt_state:
                        state = str(bolt_state)
                        is_locked = str(bolt_state).lower() == "locked"
                current[device_id] = replace(
                    device, reachable=True, is_locked=is_locked, state=state
                )
                changed = True
        if added_ids:
            LOGGER.info("Adding new devices: %s", added_ids)
            for item in devices:
                device_uuid = (
                    item.get("device_uuid") or item.get("uuid") or item.get("UUID")
                )
                if device_uuid in added_ids:
                    name = item.get("name") or device_uuid or "Level Lock"
                    device_state = await self._ws_manager.async_get_device_state(
                        str(device_uuid)
                    )
                    is_locked = None
                    state = None
                    if device_state:
                        bolt_state = device_state.get("bolt_state")
                        if bolt_state:
                            state = str(bolt_state)
                            is_locked = str(bolt_state).lower() == "locked"
                    device = LevelLockDevice(
                        lock_id=str(device_uuid),
                        uuid=str(device_uuid),
                        name=str(name),
                        is_locked=is_locked,
                        state=state,
                    )
                    current[device.lock_id] = device
                    self._ws_manager.register_device_uuid(device.lock_id, device.uuid)
                    LOGGER.info(
                        "Added device %s: is_locked=%s, state=%s",
                        device.lock_id,
                        is_locked,
                        state,
                    )
            changed = True
        if changed:
            self.async_set_updated_data(current)
