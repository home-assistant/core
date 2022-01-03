"""Support for Steamist switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import SteamistEntity

ACTIVE_SWITCH = SwitchEntityDescription(
    key="active", icon="mdi:pot-steam", name="Steam Active"
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([SteamistSwitchEntity(coordinator, config_entry, ACTIVE_SWITCH)])


class SteamistSwitchEntity(SteamistEntity, SwitchEntity):
    """Representation of an Steamist binary sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry, description)
        self._attr_is_on = self._status.active

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self._status.active
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified device on."""
        await self.coordinator.client.async_turn_on_steam()
        self._attr_is_on = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the specified device off."""
        await self.coordinator.client.async_turn_off_steam()
        self._attr_is_on = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
