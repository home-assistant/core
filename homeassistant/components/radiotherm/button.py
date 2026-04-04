"""Support for Radio Thermostat buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RadioThermUpdateCoordinator
from .entity import RadioThermostatEntity
from .util import async_set_time

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons for a radiotherm device."""
    coordinator: RadioThermUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RadioThermSyncTimeButton(coordinator, entry)])


class RadioThermSyncTimeButton(RadioThermostatEntity, ButtonEntity):
    """Provides radiotherm sync time button support."""

    _attr_translation_key = "sync_time"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: RadioThermUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the set time button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.init_data.mac}_sync_time"

    def _process_data(self) -> None:
        """No state to process for a button."""

    async def async_press(self) -> None:
        """Set the time on the thermostat."""
        time_coro = async_set_time(self.hass, self.coordinator.init_data.tstat)
        await time_coro
