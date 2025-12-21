"""Light platform for Saunum Leil Sauna Control Unit."""

from __future__ import annotations

from typing import Any

from pysaunum import SaunumException

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry
from .const import DOMAIN
from .entity import LeilSaunaEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil Sauna light entity."""
    coordinator = entry.runtime_data
    async_add_entities([LeilSaunaLight(coordinator)])


class LeilSaunaLight(LeilSaunaEntity, LightEntity):
    """Representation of a Saunum Leil Sauna light entity."""

    _attr_translation_key = "light"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator)
        # Override unique_id to differentiate from climate entity
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_light"

    @property
    def is_on(self) -> bool | None:
        """Return True if light is on."""
        return self.coordinator.data.light_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        try:
            await self.coordinator.client.async_set_light_control(True)
        except SaunumException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_light_on_failed",
            ) from err

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        try:
            await self.coordinator.client.async_set_light_control(False)
        except SaunumException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_light_off_failed",
            ) from err

        await self.coordinator.async_request_refresh()
