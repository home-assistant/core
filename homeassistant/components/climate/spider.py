"""
Support for Spider thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.spider/
"""

import logging

from homeassistant.components.climate import (
    ATTR_TEMPERATURE, STATE_COOL, STATE_HEAT, STATE_IDLE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE, ClimateDevice)
from homeassistant.components.spider import DOMAIN as SPIDER_DOMAIN
from homeassistant.const import TEMP_CELSIUS

DEPENDENCIES = ['spider']

OPERATION_LIST = [
    STATE_HEAT,
    STATE_COOL,
]

HA_STATE_TO_SPIDER = {
    STATE_COOL: 'Cool',
    STATE_HEAT: 'Heat',
}

SPIDER_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_SPIDER.items()}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Spider thermostat."""
    if discovery_info is None:
        return

    devices = [SpiderThermostat(hass.data[SPIDER_DOMAIN]['controller'], device)
               for device in hass.data[SPIDER_DOMAIN]['thermostats']]
    add_devices(devices, True)


class SpiderThermostat(ClimateDevice):
    """Representation of a thermostat."""

    def __init__(self, client, thermostat):
        """Initialize the thermostat."""
        self.client = client
        self._id = thermostat['id']
        self._name = thermostat['name']
        self._master = False
        self._thermostat = thermostat
        self._current_temperature = None
        self._target_temperature = None
        self._min_temp = None
        self._max_temp = None
        self._operation = STATE_IDLE

    @property
    def supported_features(self):
        """Return the list of supported features."""
        supports = SUPPORT_TARGET_TEMPERATURE

        if self._master:
            supports = supports | SUPPORT_OPERATION_MODE

        return supports

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def current_operation(self: ClimateDevice) -> str:
        """Return current operation ie. heat, cool, idle."""
        return self._operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return OPERATION_LIST

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self.client.set_temperature(self._thermostat, temperature)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        self.client.set_operation_mode(self._thermostat,
                                       HA_STATE_TO_SPIDER.get(operation_mode))

    def update(self):
        """Get the latest data."""
        try:
            # Only let the master thermostat refresh
            # and let the others use the cache
            thermostats = self.client.get_thermostats(
                force_refresh=self._master)
            for thermostat in thermostats:
                if thermostat['id'] == self._id:
                    self._thermostat = thermostat

        except StopIteration:
            _LOGGER.error("No data from the Itho Daalderop API")
            return

        for prop in self._thermostat['properties']:
            if prop['id'] == 'AmbientTemperature':
                self._current_temperature = float(prop['status'])
            if prop['id'] == 'SetpointTemperature':
                self._target_temperature = float(prop['status'])
                self._min_temp = float(prop['min'])
                self._max_temp = float(prop['max'])
            if prop['id'] == 'OperationMode':
                self._master = True
                self._operation = SPIDER_STATE_TO_HA[prop['status']]
