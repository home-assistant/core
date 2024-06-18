"""Support for Big Ass Fans auto comfort."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BAFConfigEntry
from .entity import BAFEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BAFConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BAF fan auto comfort."""
    device = entry.runtime_data
    if device.has_fan and device.has_auto_comfort:
        async_add_entities([BAFAutoComfort(device)])


class BAFAutoComfort(BAFEntity, ClimateEntity):
    """BAF climate auto comfort."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.FAN_ONLY]
    _attr_translation_key = "auto_comfort"
    _enable_turn_on_off_backwards_compatibility = False

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        device = self._device
        auto_on = device.auto_comfort_enable
        self._attr_hvac_mode = HVACMode.FAN_ONLY if auto_on else HVACMode.OFF
        self._attr_hvac_action = HVACAction.FAN if device.speed else HVACAction.OFF
        self._attr_target_temperature = device.comfort_ideal_temperature
        self._attr_current_temperature = device.temperature

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        self._device.auto_comfort_enable = hvac_mode == HVACMode.FAN_ONLY

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        if not self._device.auto_comfort_enable:
            self._device.auto_comfort_enable = True
        self._device.comfort_ideal_temperature = kwargs[ATTR_TEMPERATURE]
