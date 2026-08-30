"""Support for the Switchbot lock."""

from typing import Any, override

from switchbot_api import (
    Device,
    LockCommands,
    LockV2Commands,
    Remote,
    SwitchBotAPI,
    SwitchbotCloudDeviceLockState,
)

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudConfigEntry, SwitchBotCoordinator
from .entity import SwitchBotCloudEntity

# The cloud camel cases these when polled and upper cases them over the
# webhook, so look them up by their lower cased value
LOCK_STATES_BY_VALUE = {
    state.value.lower(): state for state in SwitchbotCloudDeviceLockState
}

# A latch bolt or half locked door is secured, both are resting positions the
# lock can be commanded into
LOCKED_STATES = {
    SwitchbotCloudDeviceLockState.LOCKED,
    SwitchbotCloudDeviceLockState.LATCH_BOLT_LOCKED,
    SwitchbotCloudDeviceLockState.HALF_LOCKED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config: SwitchbotCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data = config.runtime_data
    async_add_entities(
        SwitchBotCloudLock(data.api, device, coordinator)
        for device, coordinator in data.devices.locks
    )


class SwitchBotCloudLock(SwitchBotCloudEntity, LockEntity):
    """Representation of a SwitchBot lock."""

    _attr_name = None

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device | Remote,
        coordinator: SwitchBotCoordinator,
    ) -> None:
        """Init devices."""
        super().__init__(api, device, coordinator)
        self.__model = device.device_type

    @override
    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if coord_data := self.coordinator.data:
            state = LOCK_STATES_BY_VALUE.get(coord_data["lockState"].lower())
            self._attr_is_locked = state in LOCKED_STATES if state else None
            self._attr_is_locking = state is SwitchbotCloudDeviceLockState.LOCKING
            self._attr_is_unlocking = state is SwitchbotCloudDeviceLockState.UNLOCKING
            self._attr_is_jammed = state is SwitchbotCloudDeviceLockState.JAMMED
        if self.__model not in [
            "Smart Lock Lite",
            "Smart Lock Vision",
            "Smart Lock Vision Pro",
            "Lock Vision",
            "Lock Vision Pro",
        ]:
            self._attr_supported_features = LockEntityFeature.OPEN

    @callback
    def _write_optimistic_state(self, *, is_locked: bool) -> None:
        """Write the state the command asked for, until the cloud reports back.

        The transient states have to go with it: they outrank `is_locked` in
        `LockEntity.state`, so a lock commanded out of a jam would keep
        reading jammed until the next poll.
        """
        self._attr_is_locked = is_locked
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self._attr_is_jammed = False
        self.async_write_ha_state()

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self.send_api_command(LockCommands.LOCK)
        self._write_optimistic_state(is_locked=True)

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self.send_api_command(LockCommands.UNLOCK)
        self._write_optimistic_state(is_locked=False)

    @override
    async def async_open(self, **kwargs: Any) -> None:
        """Latch open the lock."""
        await self.send_api_command(LockV2Commands.DEADBOLT)
        self._write_optimistic_state(is_locked=False)
