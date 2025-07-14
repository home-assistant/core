"""Control for light."""

from __future__ import annotations

import logging
from typing import Any

from huum.huum import Huum

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HuumDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up light if applicable."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Light is configured
    if coordinator.data.config >= 2:
        async_add_entities([HuumLight(coordinator)], True)


class HuumLight(CoordinatorEntity[HuumDataUpdateCoordinator], LightEntity):
    """Representation of a light."""

    _attr_has_entity_name = True
    _attr_name = "Light"
    _attr_supported_color_modes = set(ColorMode.ONOFF)
    _attr_color_mode = ColorMode.ONOFF

    def __init__(self, coordinator: HuumDataUpdateCoordinator) -> None:
        """Initialize the light."""
        CoordinatorEntity.__init__(self, coordinator)

        self._attr_unique_id = f"{coordinator.unique_id}_light"
        self._attr_device_info = coordinator.device_info

        self._coordinator: HuumDataUpdateCoordinator = coordinator
        self._huum: Huum = coordinator.huum

    @property
    def is_on(self) -> bool | None:
        """Return the current light status."""
        return self._coordinator.data.light == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        if not self.is_on:
            await self._toggle_light()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        if self.is_on:
            await self._toggle_light()

    async def _toggle_light(self) -> None:
        await self._huum.toggle_light()
