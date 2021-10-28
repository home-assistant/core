"""Select entity to pick type of radar."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["radar_coordinator"]
    async_add_entities([ECSelect(coordinator)])


class ECSelect(CoordinatorEntity, SelectEntity, RestoreEntity):
    """Representation of a EC select entity."""

    _attr_should_poll = False

    def __init__(self, coordinator) -> None:
        """Initialize select entity."""
        super().__init__(coordinator)
        self.radar_object = coordinator.ec_data
        self._attr_current_option = self.radar_object.precip_type.capitalize()
        self._attr_name = f"{coordinator.config_entry.title} Radar Type"
        self._attr_options = ["Auto", "Rain", "Snow"]
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-radar-type"

    async def async_added_to_hass(self):
        """Restore state now added."""
        await super().async_added_to_hass()

        if not (last_state := await self.async_get_last_state()):
            return

        if last_state.state:
            self.radar_object.precip_type = last_state.state.lower()
            self._attr_current_option = last_state.state
            await self.coordinator.async_refresh()

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        self.radar_object.precip_type = option.lower()
        self._attr_current_option = option
        self.async_write_ha_state()
        await self.coordinator.async_refresh()
