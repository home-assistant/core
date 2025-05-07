"""Support for Aqualink Thermostats."""

from __future__ import annotations

import logging
from typing import Any

from iaqualink.device import AqualinkThermostat
from iaqualink.systems.iaqua.device import AqualinkState

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import refresh_system
from .const import DOMAIN
from .entity import AqualinkEntity
from .utils import await_or_reraise

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up discovered switches."""
    async_add_entities(
        (HassAqualinkThermostat(dev) for dev in hass.data[DOMAIN][CLIMATE_DOMAIN]),
        True,
    )


class HassAqualinkThermostat(AqualinkEntity, ClimateEntity):
    """Representation of a thermostat."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, dev: AqualinkThermostat) -> None:
        """Initialize AquaLink thermostat."""
        super().__init__(dev)
        self._attr_name = dev.label.split(" ")[0]
        self._attr_temperature_unit = (
            UnitOfTemperature.FAHRENHEIT
            if dev.unit == "F"
            else UnitOfTemperature.CELSIUS
        )
        self._attr_min_temp = dev.min_temperature
        self._attr_max_temp = dev.max_temperature

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
    def hvac_action(self) -> HVACAction:
        """Return the current HVAC action."""
        state = AqualinkState(self.dev._heater.state)  # noqa: SLF001
        if state == AqualinkState.ON:
            return HVACAction.HEATING
        if state == AqualinkState.ENABLED:
            return HVACAction.IDLE
        return HVACAction.OFF

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
