"""
Support for the PRT Heatmiser themostats using the V3 protocol.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.heatmiser/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice, PLATFORM_SCHEMA, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE, CONF_PORT, CONF_NAME, CONF_ID)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['heatmiserV3==0.9.1']

_LOGGER = logging.getLogger(__name__)

CONF_IPADDRESS = 'ipaddress'
CONF_TSTATS = 'tstats'

TSTATS_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.string,
    vol.Required(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IPADDRESS): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Required(CONF_TSTATS, default={}):
        vol.Schema({cv.string: TSTATS_SCHEMA}),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the heatmiser thermostat."""
    from heatmiserV3 import heatmiser, connection

    ipaddress = config.get(CONF_IPADDRESS)
    port = str(config.get(CONF_PORT))
    tstats = config.get(CONF_TSTATS)

    serport = connection.connection(ipaddress, port)
    serport.open()

    for tstat in tstats.values():
        add_devices([
            HeatmiserV3Thermostat(
                heatmiser, tstat.get(CONF_ID), tstat.get(CONF_NAME), serport)
            ])


class HeatmiserV3Thermostat(ClimateDevice):
    """Representation of a HeatmiserV3 thermostat."""

    def __init__(self, heatmiser, device, name, serport):
        """Initialize the thermostat."""
        self.heatmiser = heatmiser
        self.device = device
        self.serport = serport
        self._current_temperature = None
        self._name = name
        self._id = device
        self.dcb = None
        self.update()
        self._target_temperature = int(self.dcb.get('roomset'))

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
    def current_temperature(self):
        """Return the current temperature."""
        if self.dcb is not None:
            low = self.dcb.get('floortemplow ')
            high = self.dcb.get('floortemphigh')
            temp = (high * 256 + low) / 10.0
            self._current_temperature = temp
        else:
            self._current_temperature = None
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self.heatmiser.hmSendAddress(
            self._id,
            18,
            temperature,
            1,
            self.serport)
        self._target_temperature = temperature

    def update(self):
        """Get the latest data."""
        self.dcb = self.heatmiser.hmReadAddress(self._id, 'prt', self.serport)
