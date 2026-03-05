"""ISEO BLE Lock entity."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import logging
from typing import Any, cast

from iseo_argo_ble import IseoAuthError, IseoClient, IseoConnectionError, LockState

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.lock import LockEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import IseoConfigEntry
from .const import CONF_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Seconds the entity stays in "unlocked" state before reverting to "locked".
_RELOCK_DELAY = 5

# How often to poll the lock for door state (when door status is supported).
_POLL_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IseoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ISEO lock entity from a config entry."""
    async_add_entities(
        [
            IseoLockEntity(
                entry,
                entry.runtime_data,
            )
        ],
    )


class IseoLockEntity(LockEntity):
    """Represents an ISEO X1R BLE door lock."""

    _attr_has_entity_name = True
    _attr_name = None  # entity name = device name
    _attr_should_poll = False

    def __init__(
        self,
        entry: IseoConfigEntry,
        client: IseoClient,
    ) -> None:
        """Initialize the lock entity."""
        self._entry = entry
        self._relock_task: asyncio.Task[None] | None = None
        self._ble_lock = asyncio.Lock()
        self._door_status_supported: bool | None = None
        self._poll_unsub: CALLBACK_TYPE | None = None
        self._fw_version_set = False
        self.client: IseoClient = client

        self._attr_unique_id = f"{entry.unique_id}_lock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cast(str, entry.unique_id))},
            connections={(CONNECTION_BLUETOOTH, entry.data[CONF_ADDRESS])},
            name=entry.title,
            manufacturer="ISEO",
            model="X1R Smart",
            model_id="X1R",
        )

        self._attr_is_locked = True
        self._attr_is_unlocking = False
        self._attr_available = True
        self._poll_suppress_until: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Probe door-status support; start polling if the lock supports it."""
        await self._poll_state()
        if self._door_status_supported is not False:
            self._poll_unsub = async_track_time_interval(
                self.hass, self._poll_state, _POLL_INTERVAL
            )
            self.async_on_remove(self._poll_unsub)
        self.async_on_remove(self._cancel_relock_task)

    def _cancel_relock_task(self) -> None:
        """Cancel any pending relock task."""
        if self._relock_task and not self._relock_task.done():
            self._relock_task.cancel()

    async def _poll_state(self, _now: datetime | None = None, force: bool = False) -> None:
        """Read door state via TLV_INFO and update HA state."""
        _LOGGER.debug("Polling lock state, current available: %s", self._attr_available)
        if self._door_status_supported is False and _now is not None and not force:
            return

        if self._ble_lock.locked():
            _LOGGER.debug("Skipping poll cycle — BLE operation already in progress")
            return

        if not (
            ble_device := async_ble_device_from_address(
                self.hass,
                self._entry.data[CONF_ADDRESS],
                connectable=True,
            )
        ):
            if self._attr_available:
                _LOGGER.info("Lock is unavailable: device not found")
                self._attr_available = False
                self.async_write_ha_state()
            return

        try:
            async with self._ble_lock:
                self.client.update_ble_device(ble_device)
                state: LockState = await self.client.read_state()
        except (TimeoutError, IseoConnectionError, IseoAuthError, OSError) as exc:
            if self._attr_available:
                _LOGGER.info("Lock is unavailable: %s", exc)
                self._attr_available = False
                self.async_write_ha_state()
            return

        if not self._attr_available:
            _LOGGER.info("Lock is back online")
            self._attr_available = True
            self.async_write_ha_state()

        if not self._fw_version_set and state.firmware_info:
            fw_version = state.firmware_info[5:].strip() or state.firmware_info.strip()
            dev_reg = dr.async_get(self.hass)
            if device := dev_reg.async_get_device(
                identifiers={(DOMAIN, cast(str, self._entry.unique_id))}
            ):
                dev_reg.async_update_device(device.id, sw_version=fw_version)
                self._fw_version_set = True

        if state.door_closed is None:
            if self._door_status_supported is not False:
                _LOGGER.debug("Door status not supported; polling disabled")
                self._door_status_supported = False
                if self._poll_unsub:
                    self._poll_unsub()
                    self._poll_unsub = None
            self.async_write_ha_state()
            return

        self._door_status_supported = True

        if self._attr_is_unlocking:
            # We updated availability, write it now.
            self.async_write_ha_state()
            return
        if (
            not force
            and self._poll_suppress_until
            and datetime.now(tz=UTC) < self._poll_suppress_until
        ):
            # We updated availability, write it now.
            self.async_write_ha_state()
            return

        new_locked = state.door_closed
        if new_locked != self._attr_is_locked:
            self._attr_is_locked = new_locked
        self.async_write_ha_state()

    def _set_unlocking(self, available: bool = True) -> None:
        self._attr_is_locked = False
        self._attr_is_unlocking = True
        self._attr_available = available
        self.async_write_ha_state()

    def _set_unlocked(self, available: bool = True) -> None:
        self._attr_is_unlocking = False
        self._attr_is_locked = False
        self._attr_available = available
        self._poll_suppress_until = datetime.now(tz=UTC) + timedelta(
            seconds=_RELOCK_DELAY
        )
        self.async_write_ha_state()

    def _set_locked(self, available: bool = True) -> None:
        self._attr_is_unlocking = False
        self._attr_is_locked = True
        self._attr_available = available
        self._poll_suppress_until = None
        self.async_write_ha_state()

    async def _auto_relock(self) -> None:
        """Revert to 'locked' after the motor has re-latched."""
        try:
            if self._door_status_supported:
                await asyncio.sleep(2)
                await self._poll_state(force=True)
                # If the poll exited early (BLE busy, device not found, error),
                # the state was not updated — fall back to locked.
                if not self._attr_is_locked:
                    self._set_locked(available=self._attr_available)
                return

            await asyncio.sleep(_RELOCK_DELAY)
            self._set_locked(available=self._attr_available)
        except asyncio.CancelledError:
            pass

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door (not supported)."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="lock_not_supported",
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Open the lock (momentary actuator — always re-latches automatically)."""
        if self._relock_task and not self._relock_task.done():
            self._relock_task.cancel()

        self._set_unlocking()

        if not (
            ble_device := async_ble_device_from_address(
                self.hass,
                self._entry.data[CONF_ADDRESS],
                connectable=True,
            )
        ):
            self._set_locked(available=False)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            )

        try:
            async with self._ble_lock:
                self.client.update_ble_device(ble_device)
                await self.client.gw_open(remote_user_name="Home Assistant")
        except IseoAuthError as exc:
            self._set_locked()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_rejected_identity",
            ) from exc
        except (TimeoutError, IseoConnectionError, OSError) as exc:
            self._set_locked(available=False)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from exc

        self._set_unlocked()
        self._relock_task = self.hass.async_create_task(self._auto_relock())
