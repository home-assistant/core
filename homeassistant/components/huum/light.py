"""Control for light."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONFIG_LIGHT, CONFIG_STEAMER_AND_LIGHT
from .coordinator import HuumConfigEntry, HuumDataUpdateCoordinator
from .entity import HuumBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HuumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up light if applicable."""
    coordinator = config_entry.runtime_data

    # Light is configured for this sauna.
    if coordinator.data.config in [CONFIG_LIGHT, CONFIG_STEAMER_AND_LIGHT]:
        async_add_entities([HuumLight(coordinator)])


class HuumLight(HuumBaseEntity, LightEntity):
    """Representation of a light."""

    _attr_translation_key = "light"
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(self, coordinator: HuumDataUpdateCoordinator) -> None:
        """Initialize the light."""
        super().__init__(coordinator)

        self._attr_unique_id = coordinator.config_entry.entry_id

    @property
    def is_on(self) -> bool | None:
        """Return the current light status."""
        return self.coordinator.data.light == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        if not self.is_on:
            await self._toggle_light()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        if self.is_on:
            await self._toggle_light()

    async def _toggle_light(self) -> None:
        await self.coordinator.huum.toggle_light()
        await self.coordinator.async_refresh()
