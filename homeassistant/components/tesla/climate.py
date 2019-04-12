"""Support for Tesla HVAC system."""
import logging

from homeassistant.components.climate import ENTITY_ID_FORMAT, ClimateDevice
from homeassistant.components.climate.const import (
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    ATTR_TEMPERATURE, STATE_OFF, STATE_ON, TEMP_CELSIUS, TEMP_FAHRENHEIT)

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['tesla']

OPERATION_LIST = [STATE_ON, STATE_OFF]

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Tesla climate platform."""
    devices = [TeslaThermostat(device, hass.data[TESLA_DOMAIN]['controller'])
               for device in hass.data[TESLA_DOMAIN]['devices']['climate']]
    add_entities(devices, True)


class TeslaThermostat(TeslaDevice, ClimateDevice):
    """Representation of a Tesla climate."""

    def __init__(self, tesla_device, controller):
        """Initialize the Tesla device."""
        super().__init__(tesla_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.tesla_id)
        self._target_temperature = None
        self._temperature = None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def current_operation(self):
        """Return current operation ie. On or Off."""
        mode = self.tesla_device.is_hvac_enabled()
        if mode:
            return OPERATION_LIST[0]  # On
        return OPERATION_LIST[1]  # Off

    @property
    def operation_list(self):
        """List of available operation modes."""
        return OPERATION_LIST

    def update(self):
        """Call by the Tesla device callback to update state."""
        _LOGGER.debug("Updating: %s", self._name)
        self.tesla_device.update()
        self._target_temperature = self.tesla_device.get_goal_temp()
        self._temperature = self.tesla_device.get_current_temp()

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        tesla_temp_units = self.tesla_device.measurement

        if tesla_temp_units == 'F':
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        _LOGGER.debug("Setting temperature for: %s", self._name)
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature:
            self.tesla_device.set_temperature(temperature)

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode (auto, cool, heat, off)."""
        _LOGGER.debug("Setting mode for: %s", self._name)
        if operation_mode == OPERATION_LIST[1]:  # off
            self.tesla_device.set_status(False)
        elif operation_mode == OPERATION_LIST[0]:  # heat
            self.tesla_device.set_status(True)
