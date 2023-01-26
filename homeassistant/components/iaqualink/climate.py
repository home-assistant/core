"""Support for Aqualink Thermostats."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AqualinkEntity, refresh_system
from .const import DOMAIN as AQUALINK_DOMAIN
from .utils import await_or_reraise

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][CLIMATE_DOMAIN]:
        devs.append(HassAqualinkThermostat(dev))
    async_add_entities(devs, True)


class HassAqualinkThermostat(AqualinkEntity, ClimateEntity):
    """Representation of a thermostat."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def name(self) -> str:
        """Return the name of the thermostat."""
        return self.dev.label.split(" ")[0]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if self.dev.is_on is True:
            return HVACMode.HEAT
        return HVACMode.OFF

    @refresh_system
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the underlying heater switch on or off."""
        if hvac_mode == HVACMode.HEAT:
            await await_or_reraise(self.dev.turn_on())
        elif hvac_mode == HVACMode.OFF:
            await await_or_reraise(self.dev.turn_off())
        else:
            _LOGGER.warning("Unknown operation mode: %s", hvac_mode)

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self.dev.unit == "F":
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def min_temp(self) -> int:
        """Return the minimum temperature supported by the thermostat."""
        return self.dev.min_temperature

    @property
    def max_temp(self) -> int:
        """Return the minimum temperature supported by the thermostat."""
        return self.dev.max_temperature

    @property
    def target_temperature(self) -> float:
        """Return the current target temperature."""
        return float(self.dev.state)

    @refresh_system
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await await_or_reraise(self.dev.set_temperature(int(kwargs[ATTR_TEMPERATURE])))

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.dev.current_temperature != "":
            return float(self.dev.current_temperature)
        return None
