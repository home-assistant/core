"""Support for HomematicIP Cloud lock devices."""
from __future__ import annotations

from typing import Any

from homematicip.aio.device import AsyncDoorLockDrive
from homematicip.base.enums import LockState, MotorState

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN as HMIPC_DOMAIN, HomematicipGenericEntity
from .hap import HomematicipHAP

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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HomematicIP locks from a config entry."""
    hap = hass.data[HMIPC_DOMAIN][config_entry.unique_id]
    entities: list[HomematicipGenericEntity] = []
    for device in hap.home.devices:
        if isinstance(device, AsyncDoorLockDrive):
            entities.append(HomematicipDoorLockDrive(hap, device))

    if entities:
        async_add_entities(entities)


class HomematicipDoorLockDrive(HomematicipGenericEntity, LockEntity):
    """Representation of the HomematicIP DoorLockDrive."""

    _attr_supported_features = LockEntityFeature.OPEN

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        post: str | None = None,
        channel: int | None = None,
        is_multi_channel: bool | None = False,
    ) -> None:
        """Initialize DoorLockDrive."""
        super().__init__(hap, device)

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

    @property
    def is_jammed(self) -> bool:
        """Return true if device is jammed."""
        return (
            self._device.lockState == LockState.LOCKED
            and self._device.motorState == MotorState.STOPPED
        )

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        await self._device.set_lock_state(LockState.LOCKED)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self._device.set_lock_state(LockState.UNLOCKED)

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        await self._device.set_lock_state(LockState.OPEN)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the device."""
        state_attr = super().extra_state_attributes

        for attr, attr_key in DEVICE_DLD_ATTRIBUTES.items():
            if attr_value := getattr(self._device, attr, None):
                state_attr[attr_key] = attr_value

        return state_attr
