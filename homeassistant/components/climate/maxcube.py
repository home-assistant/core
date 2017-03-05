"""
Support for MAX! Thermostats via MAX! Cube.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/maxcube/
"""

import socket
import logging

from homeassistant.components.climate import ClimateDevice, STATE_AUTO
from homeassistant.components.maxcube import MAXCUBE_HANDLE
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE
from homeassistant.const import STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)

STATE_MANUAL = "manual"
STATE_BOOST = "boost"
STATE_VACATION = "vacation"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Iterate through all MAX! Devices and add thermostats to HASS."""
    cube = hass.data[MAXCUBE_HANDLE].cube

    # List of devices
    devices = []

    for device in cube.devices:
        # Create device name by concatenating room name + device name
        name = "%s %s" % (cube.room_by_id(device.room_id).name, device.name)

        # Only add thermostats and wallthermostats
        if cube.is_thermostat(device) or cube.is_wallthermostat(device):
            # Add device to HASS
            devices.append(MaxCubeClimate(hass, name, device.rf_address))

    # Add all devices at once
    if len(devices) > 0:
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
    def should_poll(self):
        """Polling is required."""
        return True

    @property
    def name(self):
        """Return the name of the ClimateDevice."""
        return self._name

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        # Get the device we want (does not do any IO, just reads from memory)
        device = self._cubehandle.cube.device_by_rf(self._rf_address)

        # Map and return minimum temperature
        return self.map_temperature_max_hass(device.min_temperature)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        # Get the device we want (does not do any IO, just reads from memory)
        device = self._cubehandle.cube.device_by_rf(self._rf_address)

        # Map and return maximum temperature
        return self.map_temperature_max_hass(device.max_temperature)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        # Get the device we want (does not do any IO, just reads from memory)
        device = self._cubehandle.cube.device_by_rf(self._rf_address)

        # Map and return current temperature
        return self.map_temperature_max_hass(device.actual_temperature)

    @property
    def current_operation(self):
        """Return current operation (auto, manual, boost, vacation)."""
        # Get the device we want (does not do any IO, just reads from memory)
        device = self._cubehandle.cube.device_by_rf(self._rf_address)

        # Mode Mapping
        return self.map_mode_max_hass(device.mode)

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        # Get the device we want (does not do any IO, just reads from memory)
        device = self._cubehandle.cube.device_by_rf(self._rf_address)

        # Map and return target temperature
        return self.map_temperature_max_hass(device.target_temperature)

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        # Fail is target temperature has not been supplied as argument
        if kwargs.get(ATTR_TEMPERATURE) is None:
            return False

        # Determine the new target temperature
        target_temperature = kwargs.get(ATTR_TEMPERATURE)

        # Write the target temperature to the MAX! Cube.
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
        # Get the device we want to update
        device = self._cubehandle.cube.device_by_rf(self._rf_address)

        # Mode Mapping
        mode = self.map_mode_hass_max(operation_mode)

        # Write new mode to thermostat
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
        # Update the CubeHandle
        self._cubehandle.update()

    @staticmethod
    def map_temperature_max_hass(temperature):
        """Map Temperature from MAX! to HASS."""
        if temperature is None:
            return STATE_UNKNOWN

        return temperature

    @staticmethod
    def map_mode_hass_max(operation_mode):
        """Map HASS Operation Modes to MAX! Operation Modes."""
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
        """Map MAX! Operation Modes to HASS Operation Modes."""
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
