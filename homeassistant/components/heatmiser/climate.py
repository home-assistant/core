"""Support for the PRT Heatmiser themostats using the V3 protocol."""
import logging
from typing import List

import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice,
    PLATFORM_SCHEMA,
    HVAC_MODE_HEAT,
)
from homeassistant.components.climate.const import SUPPORT_TARGET_TEMPERATURE
from homeassistant.const import (
    TEMP_CELSIUS,
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PORT,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_THERMOSTATS = "thermostats"
TSTATS_SCHEMA = vol.Schema(
    [{vol.Required("id"): cv.string, vol.Required("name"): cv.string}]
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_THERMOSTATS, default={}): TSTATS_SCHEMA,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the heatmiser thermostat."""
    from heatmiserV3 import heatmiser, connection

    HT = heatmiser.HeatmiserThermostat

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    thermostats = config.get(CONF_THERMOSTATS)

    UH1 = connection.HeatmiserUH1(host, port)

    add_entities(
        [HeatmiserV3Thermostat(HT, thermostat, UH1) for thermostat in thermostats],
        True,
    )


class HeatmiserV3Thermostat(ClimateDevice):
    """Representation of a HeatmiserV3 thermostat."""

    def __init__(self, therm, device, uh1):
        """Initialize the thermostat."""
        self.therm = therm(int(device["id"]), "prt", uh1)
        self.uh1 = uh1
        self._name = device["name"]
        self._current_temperature = None
        self._target_temperature = None
        self._id = device
        self.dcb = None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT]

    @property
    def current_temperature(self):
        """Return the current temperature."""
        _LOGGER.info(self._current_temperature)
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        _LOGGER.info(self._target_temperature)
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self._target_temperature = int(temperature)
        self.therm.set_target_temp(self._target_temperature)

    def update(self):
        """Get the latest data."""
        self.uh1._open()
        self.dcb = self.therm.read_dcb()
        self._current_temperature = int(self.therm.get_floor_temp())
        self._target_temperature = int(self.therm.get_target_temp())
