"""
Platform for Stiebel Eltron heat pumps with ISGWeb Modbus module.

Example configuration:

modbus:
  type: tcp
  host: 192.168.1.20
  port: 502

climate:
  - platform: stiebel_eltron
    name: LWZ504e
    slave: 1

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.stiebel_eltron/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY, STATE_AUTO, STATE_IDLE, STATE_MANUAL,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.components.modbus import (
    CONF_HUB, DEFAULT_HUB, DOMAIN as MODBUS_DOMAIN)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_NAME, CONF_SLAVE, DEVICE_DEFAULT_NAME, TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pystiebeleltron==0.0.1.dev2']
DEPENDENCIES = ['modbus']


DEFAULT_SLAVE = 1

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
    vol.Required(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SLAVE, default=DEFAULT_SLAVE):
        vol.All(int, vol.Range(min=0, max=32)),
})

_LOGGER = logging.getLogger(__name__)


SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

STATE_DAYMODE = 'Tagbetrieb'
STATE_SETBACK = 'Absenkbetrieb'
STATE_DHW = 'Warmwasserbetrieb'
STATE_EMERGENCY = 'Notbetrieb'

"""Mapping Stiebel Eltron states to homeassistant states."""
STE_TO_HA_STATE = {'AUTOMATIC': STATE_AUTO,
                   'MANUAL MODE': STATE_MANUAL,
                   'STANDBY': STATE_IDLE,
                   'DAY MODE': STATE_DAYMODE,
                   'SETBACK MODE': STATE_SETBACK,
                   'DHW': STATE_DHW,
                   'EMERGENCY OPERATION': STATE_EMERGENCY}

"""Mapping homeassistant states to Stiebel Eltron states."""
HA_TO_STE_STATE = {value: key for key, value in STE_TO_HA_STATE.items()}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the StiebelEltron platform."""
    name = config.get(CONF_NAME, DEVICE_DEFAULT_NAME)
    modbus_slave = config.get(CONF_SLAVE, DEFAULT_SLAVE)
    modbus_client = hass.data[MODBUS_DOMAIN][config.get(CONF_HUB)]

    add_devices([StiebelEltron(name, modbus_client, modbus_slave)], True)
    return True


class StiebelEltron(ClimateDevice):
    """Representation of a Stiebel Eltron heat pump."""

    def __init__(self, name, modbus_client, modbus_slave):
        """Initialize the unit."""
        from pystiebeleltron import pystiebeleltron
        self._name = name
        self._modbus_client = modbus_client
        self._modbus_slave = modbus_slave

        self._target_temperature = None
        self._current_temperature = None
        self._current_humidity = None
        self._operation_modes = [STATE_AUTO, STATE_IDLE, STATE_DHW]
        self._current_operation = None
        self._filter_alarm = None
        self.unit = pystiebeleltron.StiebelEltronAPI(self._modbus_client,
                                                     self._modbus_slave)
        _LOGGER.debug("Initialized StiebelEltron climat component.")

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def update(self):
        """Update unit attributes."""
        if not self.unit.update():
            _LOGGER.warning("Modbus read failed")

        self._target_temperature = self.unit.get_target_temp()
        self._current_temperature = self.unit.get_current_temp()
        self._current_humidity = self.unit.get_current_humidity()
        self._filter_alarm = self.unit.get_filter_alarm_status()
        self._current_operation = self.unit.get_operation()

        _LOGGER.debug("Update %s, current temp: %s", self._name,
                      self._current_temperature)

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            ATTR_CURRENT_HUMIDITY: self._current_humidity,
            'filter_alarm':     self._filter_alarm
        }

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    # Handle SUPPORT_TARGET_TEMPERATURE
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
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.1

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 10.0

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 30.0

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("set_temperature: %s", self._target_temperature)
        self.unit.set_target_temp(self._target_temperature)

    # Handle SUPPORT_OPERATION_MODE
    @property
    def operation_list(self):
        """List of the operation modes."""
        return self._operation_modes

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return STE_TO_HA_STATE.get(self._current_operation)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        new_mode = HA_TO_STE_STATE.get(operation_mode)
        _LOGGER.debug("set_operation_mode: %s -> %s", self._current_operation,
                      new_mode)
        self._current_operation = new_mode
        self.unit.set_operation(new_mode)
