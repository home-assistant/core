"""Support for the Switchbot lock."""

from typing import Any

from switchbot_api import Device, LockCommands, LockV2Commands, Remote, SwitchBotAPI

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import DOMAIN
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
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

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        self.__set_features()
        if coord_data := self.coordinator.data:
            self._attr_is_locked = coord_data["lockState"] == "locked"

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self.send_api_command(LockCommands.LOCK)
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self.send_api_command(LockCommands.UNLOCK)
        self._attr_is_locked = False
        self.async_write_ha_state()

    async def async_open(self, **kwargs: Any) -> None:
        """Latch open the lock."""
        await self.send_api_command(LockV2Commands.DEADBOLT)
        self._attr_is_locked = False
        self.async_write_ha_state()

    def __set_features(self) -> None:
        """Set features ConfigFlow options."""
        if self.device_entry and self.__model in LockV2Commands.get_supported_devices():
            self._attr_supported_features = LockEntityFeature.OPEN
