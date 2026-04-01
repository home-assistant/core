"""Casper Glow integration light platform."""

from __future__ import annotations

from typing import Any

from pycasperglow import GlowState

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DEFAULT_DIMMING_TIME_MINUTES, SORTED_BRIGHTNESS_LEVELS
from .coordinator import CasperGlowConfigEntry, CasperGlowCoordinator
from .entity import CasperGlowEntity

PARALLEL_UPDATES = 1


def _ha_brightness_to_device_pct(brightness: int) -> int:
    """Convert HA brightness (1-255) to device percentage by snapping to nearest."""
    return percentage_to_ordered_list_item(
        SORTED_BRIGHTNESS_LEVELS, round(brightness * 100 / 255)
    )


def _device_pct_to_ha_brightness(pct: int) -> int:
    """Convert device brightness percentage (60-100) to HA brightness (1-255)."""
    percent = ordered_list_item_to_percentage(SORTED_BRIGHTNESS_LEVELS, pct)
    return round(percent * 255 / 100)


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
    _attr_name = None

    def __init__(self, coordinator: CasperGlowCoordinator) -> None:
        """Initialize a Casper Glow light."""
        super().__init__(coordinator)
        self._attr_unique_id = format_mac(coordinator.device.address)
        self._update_from_state(coordinator.device.state)

    async def async_added_to_hass(self) -> None:
        """Register state update callback when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._device.register_callback(self._async_handle_state_update)
        )

    @callback
    def _update_from_state(self, state: GlowState) -> None:
        """Update entity attributes from device state."""
        if state.is_on is not None:
            self._attr_is_on = state.is_on
            self._attr_color_mode = ColorMode.BRIGHTNESS
        if state.brightness_level is not None:
            self._attr_brightness = _device_pct_to_ha_brightness(state.brightness_level)

    @callback
    def _async_handle_state_update(self, state: GlowState) -> None:
        """Handle a state update from the device."""
        self._update_from_state(state)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness_pct: int | None = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness_pct = _ha_brightness_to_device_pct(kwargs[ATTR_BRIGHTNESS])

        await self._async_command(self._device.turn_on())
        self._attr_is_on = True
        self._attr_color_mode = ColorMode.BRIGHTNESS
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

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_command(self._device.turn_off())
        self._attr_is_on = False
