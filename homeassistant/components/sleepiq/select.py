"""Support for SleepIQ foundation preset selection."""
from __future__ import annotations

from asyncsleepiq import BED_PRESETS, Side, SleepIQBed, SleepIQPreset

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .coordinator import SleepIQData
from .entity import SleepIQBedEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ foundation preset select entities."""
    data: SleepIQData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SleepIQSelectEntity(data.data_coordinator, bed, preset)
        for bed in data.client.beds.values()
        for preset in bed.foundation.presets
    )


class SleepIQSelectEntity(SleepIQBedEntity, SelectEntity):
    """Representation of a SleepIQ select entity."""

    _attr_options = list(BED_PRESETS)

    def __init__(
        self, coordinator: DataUpdateCoordinator, bed: SleepIQBed, preset: SleepIQPreset
    ) -> None:
        """Initialize the select entity."""
        self.preset = preset

        self._attr_name = f"SleepNumber {bed.name} Foundation Preset"
        self._attr_unique_id = f"{bed.id}_preset"
        if preset.side != Side.NONE:
            self._attr_name += f" {preset.side_full}"
            self._attr_unique_id += f"_{preset.side}"

        super().__init__(coordinator, bed)
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update entity attributes."""
        self._attr_current_option = self.preset.preset

    async def async_select_option(self, option: str) -> None:
        """Change the current preset."""
        await self.preset.set_preset(option)
        self._attr_current_option = option
        self.async_write_ha_state()
