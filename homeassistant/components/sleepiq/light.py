"""Support for SleepIQ outlet lights."""

import logging
from typing import Any

from asyncsleepiq import SleepIQBed, SleepIQLight

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SleepIQData, SleepIQDataUpdateCoordinator
from .entity import SleepIQBedEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed lights."""
    data: SleepIQData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SleepIQLightEntity(data.data_coordinator, bed, light)
        for bed in data.client.beds.values()
        for light in bed.foundation.lights
    )


class SleepIQLightEntity(SleepIQBedEntity[SleepIQDataUpdateCoordinator], LightEntity):
    """Representation of a light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed: SleepIQBed,
        light: SleepIQLight,
    ) -> None:
        """Initialize the light."""
        self.light = light
        super().__init__(coordinator, bed)
        self._attr_name = f"SleepNumber {bed.name} Light {light.outlet_id}"
        self._attr_unique_id = f"{bed.id}-light-{light.outlet_id}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        await self.light.turn_on()
        self._handle_coordinator_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        await self.light.turn_off()
        self._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update light attributes."""
        self._attr_is_on = self.light.is_on
