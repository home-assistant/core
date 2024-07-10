"""Support for Proliphix NT10e Thermostats."""

from __future__ import annotations

from typing import Any

import proliphix
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    PRECISION_TENTHS,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

ATTR_FAN = "fan"

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Proliphix thermostats."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    host = config.get(CONF_HOST)

    pdp = proliphix.PDP(host, username, password)
    pdp.update()

    add_entities([ProliphixThermostat(pdp)], True)


class ProliphixThermostat(ClimateEntity):
    """Representation a Proliphix thermostat."""

    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, pdp):
        """Initialize the thermostat."""
        self._pdp = pdp
        self._name = None

    def update(self) -> None:
        """Update the data from the thermostat."""
        self._pdp.update()
        self._name = self._pdp.name

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        return {ATTR_FAN: self._pdp.fan_state}

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._pdp.cur_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._pdp.setback

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current state of the thermostat."""
        state = self._pdp.hvac_state
        if state == 1:
            return HVACAction.OFF
        if state in (3, 4, 5):
            return HVACAction.HEATING
        if state in (6, 7):
            return HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current state of the thermostat."""
        if self._pdp.is_heating:
            return HVACMode.HEAT
        if self._pdp.is_cooling:
            return HVACMode.COOL
        return HVACMode.OFF

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return available HVAC modes."""
        return []

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self._pdp.setback = temperature
