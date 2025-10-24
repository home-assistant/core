"""Light platform for Saunum Leil Sauna Control Unit."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry, LeilSaunaCoordinator
from .const import REG_LIGHT
from .entity import LeilSaunaEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil Sauna light entity."""
    coordinator = entry.runtime_data

    async_add_entities([LeilSaunaLight(coordinator)])


class LeilSaunaLight(LeilSaunaEntity, LightEntity):
    """Representation of a Saunum Leil Sauna light."""

    _attr_translation_key = "sauna_light"
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator: LeilSaunaCoordinator) -> None:
        """Initialize the light."""
        super().__init__(coordinator, "light")
        self._optimistic_state: bool | None = None

    @property
    def color_mode(self) -> ColorMode:
        """Return current color mode."""
        return ColorMode.ONOFF

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        # Use optimistic state if available, otherwise use coordinator data
        if self._optimistic_state is not None:
            return self._optimistic_state
        return bool(self.coordinator.data.get("light"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Set optimistic state immediately for responsive UI
        self._optimistic_state = True
        self.async_write_ha_state()

        # Write to device
        success = await self.coordinator.async_write_register(REG_LIGHT, 1)

        # Clear optimistic state after coordinator refresh
        self._optimistic_state = None
        if not success:
            # If write failed, trigger state update to revert to actual state
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        # Set optimistic state immediately for responsive UI
        self._optimistic_state = False
        self.async_write_ha_state()

        # Write to device
        success = await self.coordinator.async_write_register(REG_LIGHT, 0)

        # Clear optimistic state after coordinator refresh
        self._optimistic_state = None
        if not success:
            # If write failed, trigger state update to revert to actual state
            self.async_write_ha_state()
