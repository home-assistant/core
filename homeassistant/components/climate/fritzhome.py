"""
Support for AVM Fritz!Box fritzhome thermostate devices.

For more details about this component, please refer to the documentation at
http://home-assistant.io/components/climate.fritzhome/
"""
import logging

from homeassistant.components.fritzhome import (
    ATTR_AIN, ATTR_FW_VERSION, ATTR_ID, ATTR_MANUFACTURER, ATTR_OPERATION_MODE,
    ATTR_PRODUCTNAME, DOMAIN)
from homeassistant.components.climate import (ClimateDevice, STATE_ECO)
from homeassistant.const import (PRECISION_HALVES)
from homeassistant.const import (TEMP_CELSIUS, ATTR_TEMPERATURE)

DEPENDENCIES = ['fritzhome']

_LOGGER = logging.getLogger(__name__)

STATE_COMFORT = 'comfort'

OPERATION_LIST = [STATE_ECO, STATE_COMFORT]

MIN_TEMPERATURE = 8
MAX_TEMPERATURE = 28


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Fritzhome thermostat platform."""
    if DOMAIN not in hass.data:
        return False

    device_list = hass.data[DOMAIN]

    devices = []
    for device in device_list:
        if device.has_thermostat:
            devices.append(FritzhomeThermostat(hass, device))

    add_devices(devices)


class FritzhomeThermostat(ClimateDevice):
    """The thermostat class for Fritzhome thermostates."""

    def __init__(self, hass, device):
        """Initialize the thermostat."""
        self._device = device
        self._current_temperature = None
        self._target_temperature = None
        self._eco_temperature = None
        self._comfort_temperature = None

    @property
    def available(self):
        """Return if thermostat is available."""
        return self._device.present

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return precision 0.5."""
        return PRECISION_HALVES

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_OPERATION_MODE) is not None:
            operation_mode = kwargs.get(ATTR_OPERATION_MODE)
            self.set_operation_mode(operation_mode)
        elif kwargs.get(ATTR_OPERATION_MODE) is not None:
            temperature = kwargs.get(ATTR_TEMPERATURE)
            self._device.set_target_temperature(temperature)

    @property
    def current_operation(self):
        """Return the current operation mode."""
        if not self.available:
            return None
        if self._target_temperature == self._comfort_temperature:
            return STATE_COMFORT
        elif self._target_temperature == self._eco_temperature:
            return STATE_ECO
        return 'unknown'

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self.OPERATION_LIST

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        if operation_mode == STATE_COMFORT:
            self.set_temperature(temperature=self._comfort_temperature)
        elif operation_mode == STATE_ECO:
            self.set_temperature(temperature=self._eco_temperature)


    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return MIN_TEMPERATURE

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMPERATURE

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attr = {
            ATTR_AIN: self._device.ain,
            ATTR_FW_VERSION: self._device.fw_version,
            ATTR_ID: self._device.id,
            ATTR_MANUFACTURER: self._device.manufacturer,
            ATTR_PRODUCTNAME: self._device.productname,
        }
        return attr

    def update(self):
        """Update the data from the thermostat."""
        self._device.update()
        self._current_temperature = self._device.actual_temperature
        self._target_temperature = self._device.target_temperature
        self._comfort_temperature = self._device.comfort_temperature
        self._eco_temperature = self._device.eco_temperature
