"""
Support for Nest Thermostat Binary Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.nest/
"""
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.sensor.nest import NestSensor
from homeassistant.const import (CONF_SCAN_INTERVAL, CONF_MONITORED_CONDITIONS)
import homeassistant.components.nest as nest
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['nest']
BINARY_TYPES = ['fan',
                'hvac_ac_state',
                'hvac_aux_heater_state',
                'hvac_heater_state',
                'hvac_heat_x2_state',
                'hvac_heat_x3_state',
                'hvac_alt_heat_state',
                'hvac_alt_heat_x2_state',
                'hvac_emer_heat_state',
                'online']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(BINARY_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Nest binary sensors."""
    for structure, device in nest.devices():
        add_devices([NestBinarySensor(structure, device, variable)
                     for variable in config[CONF_MONITORED_CONDITIONS]])


class NestBinarySensor(NestSensor, BinarySensorDevice):
    """Represents a Nest binary sensor."""

    @property
    def is_on(self):
        """True if the binary sensor is on."""
        return bool(getattr(self.device, self.variable))
