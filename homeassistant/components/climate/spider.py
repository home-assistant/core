"""
Support for Spider thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.spider/
"""

import logging

from homeassistant.components.climate import (
    ATTR_TEMPERATURE, STATE_COOL, STATE_HEAT, STATE_IDLE,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE, ClimateDevice)
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
    STATE_IDLE: 'Idle'
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

    def __init__(self, api, thermostat):
        """Initialize the thermostat."""
        self.api = api
        self.thermostat = thermostat

    @property
    def supported_features(self):
        """Return the list of supported features."""
        supports = SUPPORT_TARGET_TEMPERATURE

        if self.thermostat.has_operation_mode:
            supports = supports | SUPPORT_OPERATION_MODE

        return supports

    @property
    def unique_id(self):
        """Return the id of the thermostat, if any."""
        return self.thermostat.id

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self.thermostat.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.thermostat.current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.thermostat.target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.thermostat.temperature_steps

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.thermostat.minimum_temperature

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.thermostat.maximum_temperature

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return SPIDER_STATE_TO_HA[self.thermostat.operation_mode]

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return OPERATION_LIST

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self.thermostat.set_temperature(temperature)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        self.thermostat.set_operation_mode(
            HA_STATE_TO_SPIDER.get(operation_mode))

    def update(self):
        """Get the latest data."""
        self.thermostat = self.api.get_thermostat(self.unique_id)
