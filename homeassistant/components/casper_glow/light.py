"""Casper Glow integration light platform."""

from __future__ import annotations

from typing import Any

from pycasperglow import GlowState

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BRIGHTNESS_PCT_TO_HA, DEFAULT_DIMMING_TIME_MINUTES
from .coordinator import CasperGlowCoordinator
from .entity import CasperGlowEntity
from .models import CasperGlowConfigEntry

PARALLEL_UPDATES = 0


def _ha_brightness_to_device_pct(brightness: int) -> int:
    """Convert HA brightness (1-255) to device percentage by snapping to nearest."""
    closest_pct, closest_ha_val = next(iter(BRIGHTNESS_PCT_TO_HA.items()))
    closest_dist = abs(brightness - closest_ha_val)
    for pct, ha_val in BRIGHTNESS_PCT_TO_HA.items():
        dist = abs(brightness - ha_val)
        if dist < closest_dist:
            closest_dist = dist
            closest_pct = pct
    return closest_pct


def _device_pct_to_ha_brightness(pct: int) -> int:
    """Convert device brightness percentage (60-100) to HA brightness (1-255)."""
    return BRIGHTNESS_PCT_TO_HA[pct]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CasperGlowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the light platform for Casper Glow."""
    async_add_entities([CasperGlowLight(entry.runtime_data)])


class CasperGlowLight(CasperGlowEntity, LightEntity):
    """Representation of a Casper Glow light."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_name = None

    def __init__(self, coordinator: CasperGlowCoordinator) -> None:
        """Initialize a Casper Glow light."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.device.address
        self._attr_is_on = coordinator.device.is_on

    async def async_added_to_hass(self) -> None:
        """Register state update callback when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._device.register_callback(self._async_handle_state_update)
        )

    @callback
    def _async_handle_state_update(self, state: GlowState) -> None:
        """Handle a state update from the device."""
        if state.is_on is not None:
            self._attr_is_on = state.is_on
        if state.brightness_level is not None:
            self._attr_brightness = _device_pct_to_ha_brightness(state.brightness_level)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness_pct: int | None = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness_pct = _ha_brightness_to_device_pct(kwargs[ATTR_BRIGHTNESS])

        await self._async_command(self._device.turn_on())
        self._attr_is_on = True
        if brightness_pct is not None:
            await self._async_command(
                self._device.set_brightness_and_dimming_time(
                    brightness_pct,
                    self.coordinator.last_dimming_time_minutes
                    if self.coordinator.last_dimming_time_minutes is not None
                    else DEFAULT_DIMMING_TIME_MINUTES,
                )
            )
            self._attr_brightness = _device_pct_to_ha_brightness(brightness_pct)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_command(self._device.turn_off())
        self._attr_is_on = False
        self.async_write_ha_state()
