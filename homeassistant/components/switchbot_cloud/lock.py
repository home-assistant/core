"""Support for the Switchbot lock."""

from typing import Any

from switchbot_api import LockCommands

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if coord_data := self.coordinator.data:
            self._attr_is_locked = coord_data["lockState"] == "locked"
            self.async_write_ha_state()

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
