"""Support for HomematicIP Cloud lock devices."""

from __future__ import annotations

import logging
from typing import Any

from homematicip.aio.device import AsyncDoorLockDrive
from homematicip.base.enums import LockState, MotorState

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import HomematicipGenericEntity
from .helpers import handle_errors

_LOGGER = logging.getLogger(__name__)

ATTR_AUTO_RELOCK_DELAY = "auto_relock_delay"
ATTR_DOOR_HANDLE_TYPE = "door_handle_type"
ATTR_DOOR_LOCK_DIRECTION = "door_lock_direction"
ATTR_DOOR_LOCK_NEUTRAL_POSITION = "door_lock_neutral_position"
ATTR_DOOR_LOCK_TURNS = "door_lock_turns"

DEVICE_DLD_ATTRIBUTES = {
    "autoRelockDelay": ATTR_AUTO_RELOCK_DELAY,
    "doorHandleType": ATTR_DOOR_HANDLE_TYPE,
    "doorLockDirection": ATTR_DOOR_LOCK_DIRECTION,
    "doorLockNeutralPosition": ATTR_DOOR_LOCK_NEUTRAL_POSITION,
    "doorLockTurns": ATTR_DOOR_LOCK_TURNS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP locks from a config entry."""
    hap = hass.data[DOMAIN][config_entry.unique_id]

    async_add_entities(
        HomematicipDoorLockDrive(hap, device)
        for device in hap.home.devices
        if isinstance(device, AsyncDoorLockDrive)
    )


class HomematicipDoorLockDrive(HomematicipGenericEntity, LockEntity):
    """Representation of the HomematicIP DoorLockDrive."""

    _attr_supported_features = LockEntityFeature.OPEN

    @property
    def is_locked(self) -> bool | None:
        """Return true if device is locked."""
        return (
            self._device.lockState == LockState.LOCKED
            and self._device.motorState == MotorState.STOPPED
        )

    @property
    def is_locking(self) -> bool:
        """Return true if device is locking."""
        return self._device.motorState == MotorState.CLOSING

    @property
    def is_unlocking(self) -> bool:
        """Return true if device is unlocking."""
        return self._device.motorState == MotorState.OPENING

    @handle_errors
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        return await self._device.set_lock_state(LockState.LOCKED)

    @handle_errors
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        return await self._device.set_lock_state(LockState.UNLOCKED)

    @handle_errors
    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        return await self._device.set_lock_state(LockState.OPEN)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the device."""
        return super().extra_state_attributes | {
            attr_key: attr_value
            for attr, attr_key in DEVICE_DLD_ATTRIBUTES.items()
            if (attr_value := getattr(self._device, attr, None)) is not None
        }
