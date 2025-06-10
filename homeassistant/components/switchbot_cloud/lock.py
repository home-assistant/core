"""Support for the Switchbot lock."""

from types import MappingProxyType
from typing import Any

from switchbot_api import Device, LockCommands, Remote, SwitchBotAPI

from homeassistant.components.lock import LockEntity
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
        SwitchBotCloudLock(data.api, device, coordinator, config.options)
        for device, coordinator in data.devices.locks
    )

    config.async_on_unload(config.add_update_listener(_async_update_listener))


async def _async_update_listener(hass: HomeAssistant, config: ConfigEntry) -> None:
    """Deal with entry update."""
    hass.data[DOMAIN][config.entry_id].api.closed()
    await hass.config_entries.async_reload(config.entry_id)


class SwitchBotCloudLock(SwitchBotCloudEntity, LockEntity):
    """Representation of a SwitchBot lock."""

    _attr_name = None

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device | Remote,
        coordinator: SwitchBotCoordinator,
        entity_options: MappingProxyType,
    ) -> None:
        """Init SwitchBotCloudLock."""
        super().__init__(api, device, coordinator)
        self.entity_options = entity_options

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
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
