"""
Support for LCN binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.lcn/
"""

import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA, BinarySensorDevice)
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_NAME
import homeassistant.helpers.config_validation as cv

from ..lcn import LcnDevice
from ..lcn.core import (
    BINSENSOR_PORTS, CONF_ADDRESS, CONF_SOURCE, SETPOINTS, is_address)

DEPENDENCIES = ['lcn']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ADDRESS): is_address,
    vol.Required(CONF_SOURCE): vol.Any(*(SETPOINTS + BINSENSOR_PORTS)),
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    })


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the LCN binary sensor platform."""
    device_id = config[CONF_NAME]
    if CONF_FRIENDLY_NAME not in config:
        config[CONF_FRIENDLY_NAME] = device_id

    source = config[CONF_SOURCE]

    if source in SETPOINTS:
        device = LcnRegulatorLockSensor(hass, config)
    elif source in BINSENSOR_PORTS:
        device = LcnBinarySensor(hass, config)

    async_add_entities([device])
    return True


class LcnRegulatorLockSensor(LcnDevice, BinarySensorDevice):
    """Representation of a LCN binary sensor for regulator locks."""

    def __init__(self, hass, config):
        """Initialize the LCN binary sensor."""
        LcnDevice.__init__(self, hass, config)

        self.setpoint_variable = \
            self.pypck.lcn_defs.Var[config[CONF_SOURCE].upper()]

        self._value = None

        self.hass.async_create_task(
            self.module_connection.activate_status_request_handler(
                self.setpoint_variable))

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return self._value

    def module_input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if isinstance(input_obj, self.pypck.input.ModStatusVar):
            if input_obj.get_var() == self.setpoint_variable:
                self._value = input_obj.get_value().is_locked_regulator()

                self.async_schedule_update_ha_state()


class LcnBinarySensor(LcnDevice, BinarySensorDevice):
    """Representation of a LCN binary sensor for binary sensor ports."""

    def __init__(self, hass, config):
        """Initialize the LCN binary sensor."""
        LcnDevice.__init__(self, hass, config)

        self.bin_sensor_port = \
            self.pypck.lcn_defs.BinSensorPort[config[CONF_SOURCE].upper()]

        self._value = None

        self.hass.async_create_task(
            self.module_connection.activate_status_request_handler(
                self.bin_sensor_port))

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return self._value

    def module_input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if isinstance(input_obj, self.pypck.input.ModStatusBinSensors):
            self._value = input_obj.get_state(self.bin_sensor_port.value)

            self.async_schedule_update_ha_state()
