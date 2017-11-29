"""
Support for MAX! Thermostats via MAX! Cube.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/maxcube/
"""
import socket
import logging

from homeassistant.components.climate import (
    ClimateDevice, STATE_AUTO, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE)
from homeassistant.components.maxcube import MAXCUBE_HANDLE
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE

_LOGGER = logging.getLogger(__name__)

STATE_MANUAL = 'manual'
STATE_BOOST = 'boost'
STATE_VACATION = 'vacation'

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Iterate through all MAX! Devices and add thermostats."""
    cube = hass.data[MAXCUBE_HANDLE].cube

    devices = []

    for device in cube.devices:
        name = '{} {}'.format(
            cube.room_by_id(device.room_id).name, device.name)

        if cube.is_thermostat(device) or cube.is_wallthermostat(device):
            devices.append(MaxCubeClimate(hass, name, device.rf_address))

    if devices:
        add_devices(devices)


class MaxCubeClimate(ClimateDevice):
    """MAX! Cube ClimateDevice."""

    def __init__(self, hass, name, rf_address):
        """Initialize MAX! Cube ClimateDevice."""
        self._name = name
        self._unit_of_measurement = TEMP_CELSIUS
        self._operation_list = [STATE_AUTO, STATE_MANUAL, STATE_BOOST,
                                STATE_VACATION]
        self._rf_address = rf_address
        self._cubehandle = hass.data[MAXCUBE_HANDLE]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        return self.map_temperature_max_hass(device.min_temperature)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        return self.map_temperature_max_hass(device.max_temperature)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)

        # Map and return current temperature
        return self.map_temperature_max_hass(device.actual_temperature)

    @property
    def current_operation(self):
        """Return current operation (auto, manual, boost, vacation)."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        return self.map_mode_max_hass(device.mode)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        return self.map_temperature_max_hass(device.target_temperature)

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is None:
            return False

        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        device = self._cubehandle.cube.device_by_rf(self._rf_address)

        cube = self._cubehandle.cube

        with self._cubehandle.mutex:
            try:
                cube.set_target_temperature(device, target_temperature)
            except (socket.timeout, socket.error):
                _LOGGER.error("Setting target temperature failed")
                return False

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        mode = self.map_mode_hass_max(operation_mode)

        if mode is None:
            return False

        with self._cubehandle.mutex:
            try:
                self._cubehandle.cube.set_mode(device, mode)
            except (socket.timeout, socket.error):
                _LOGGER.error("Setting operation mode failed")
                return False

    def update(self):
        """Get latest data from MAX! Cube."""
        self._cubehandle.update()

    @staticmethod
    def map_temperature_max_hass(temperature):
        """Map Temperature from MAX! to HASS."""
        if temperature is None:
            return 0.0

        return temperature

    @staticmethod
    def map_mode_hass_max(operation_mode):
        """Map Home Assistant Operation Modes to MAX! Operation Modes."""
        from maxcube.device import \
            MAX_DEVICE_MODE_AUTOMATIC, \
            MAX_DEVICE_MODE_MANUAL, \
            MAX_DEVICE_MODE_VACATION, \
            MAX_DEVICE_MODE_BOOST

        if operation_mode == STATE_AUTO:
            mode = MAX_DEVICE_MODE_AUTOMATIC
        elif operation_mode == STATE_MANUAL:
            mode = MAX_DEVICE_MODE_MANUAL
        elif operation_mode == STATE_VACATION:
            mode = MAX_DEVICE_MODE_VACATION
        elif operation_mode == STATE_BOOST:
            mode = MAX_DEVICE_MODE_BOOST
        else:
            mode = None

        return mode

    @staticmethod
    def map_mode_max_hass(mode):
        """Map MAX! Operation Modes to Home Assistant Operation Modes."""
        from maxcube.device import \
            MAX_DEVICE_MODE_AUTOMATIC, \
            MAX_DEVICE_MODE_MANUAL, \
            MAX_DEVICE_MODE_VACATION, \
            MAX_DEVICE_MODE_BOOST

        if mode == MAX_DEVICE_MODE_AUTOMATIC:
            operation_mode = STATE_AUTO
        elif mode == MAX_DEVICE_MODE_MANUAL:
            operation_mode = STATE_MANUAL
        elif mode == MAX_DEVICE_MODE_VACATION:
            operation_mode = STATE_VACATION
        elif mode == MAX_DEVICE_MODE_BOOST:
            operation_mode = STATE_BOOST
        else:
            operation_mode = None

        return operation_mode
