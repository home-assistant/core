"""Support for switchbot water heaters."""

import logging

import switchbot

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SwitchbotConfigEntry
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switchbot based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([SwitchbotThermostat(coordinator)])


class SwitchbotThermostat(SwitchbotEntity, WaterHeaterEntity):
    """Representation of a Switchbot Thermostat."""

    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _device: switchbot.SwitchbotThermostat
    _attr_translation_key = "thermostat"
    _attr_name = None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.target_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._device.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._device.max_temp
