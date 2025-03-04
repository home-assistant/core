"""OpenEnergyMonitor Thermostat Support."""

from __future__ import annotations

from typing import Any

from oemthermostat import Thermostat
import requests
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
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default="Thermostat"): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
    }
)

SUPPORT_HVAC = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the oemthermostat platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        therm = Thermostat(host, port=port, username=username, password=password)
    except (ValueError, AssertionError, requests.RequestException):
        return

    add_entities((ThermostatDevice(therm, name),), True)


class ThermostatDevice(ClimateEntity):
    """Interface class for the oemthermostat module."""

    _attr_hvac_modes = SUPPORT_HVAC
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, thermostat, name):
        """Initialize the device."""
        self._name = name
        self.thermostat = thermostat

        # set up internal state varS
        self._state = None
        self._temperature = None
        self._setpoint = None
        self._mode = None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self._mode == 2:
            return HVACMode.HEAT
        if self._mode == 1:
            return HVACMode.AUTO
        return HVACMode.OFF

    @property
    def name(self):
        """Return the name of this Thermostat."""
        return self._name

    @property
    def hvac_action(self) -> HVACAction:
        """Return current hvac i.e. heat, cool, idle."""
        if not self._mode:
            return HVACAction.OFF
        if self._state:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._setpoint

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.AUTO:
            self.thermostat.mode = 1
        elif hvac_mode == HVACMode.HEAT:
            self.thermostat.mode = 2
        elif hvac_mode == HVACMode.OFF:
            self.thermostat.mode = 0

    def set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        self.thermostat.setpoint = temp

    def update(self) -> None:
        """Update local state."""
        self._setpoint = self.thermostat.setpoint
        self._temperature = self.thermostat.temperature
        self._state = self.thermostat.state
        self._mode = self.thermostat.mode
