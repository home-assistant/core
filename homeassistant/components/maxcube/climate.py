"""Support for MAX! Thermostats via MAX! Cube."""
import logging
import socket

from maxcube.device import (
    MAX_DEVICE_MODE_AUTOMATIC,
    MAX_DEVICE_MODE_BOOST,
    MAX_DEVICE_MODE_MANUAL,
    MAX_DEVICE_MODE_VACATION,
)

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from . import DATA_KEY

_LOGGER = logging.getLogger(__name__)

PRESET_MANUAL = "manual"
PRESET_BOOST = "boost"
PRESET_VACATION = "vacation"

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Iterate through all MAX! Devices and add thermostats."""
    devices = []
    for handler in hass.data[DATA_KEY].values():
        cube = handler.cube
        for device in cube.devices:
            name = f"{cube.room_by_id(device.room_id).name} {device.name}"

            if cube.is_thermostat(device) or cube.is_wallthermostat(device):
                devices.append(MaxCubeClimate(handler, name, device.rf_address))

    if devices:
        add_entities(devices)


class MaxCubeClimate(ClimateDevice):
    """MAX! Cube ClimateDevice."""

    def __init__(self, handler, name, rf_address):
        """Initialize MAX! Cube ClimateDevice."""
        self._name = name
        self._operation_list = [HVAC_MODE_AUTO]
        self._rf_address = rf_address
        self._cubehandle = handler

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
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)

        # Map and return current temperature
        return self.map_temperature_max_hass(device.actual_temperature)

    @property
    def hvac_mode(self):
        """Return current operation (auto, manual, boost, vacation)."""
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
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

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        return self.map_mode_max_hass(device.mode)

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return [PRESET_BOOST, PRESET_MANUAL, PRESET_VACATION]

    def set_preset_mode(self, preset_mode):
        """Set new operation mode."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        mode = self.map_mode_hass_max(preset_mode) or MAX_DEVICE_MODE_AUTOMATIC

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
        """Map Temperature from MAX! to Home Assistant."""
        if temperature is None:
            return 0.0

        return temperature

    @staticmethod
    def map_mode_hass_max(mode):
        """Map Home Assistant Operation Modes to MAX! Operation Modes."""
        if mode == PRESET_MANUAL:
            mode = MAX_DEVICE_MODE_MANUAL
        elif mode == PRESET_VACATION:
            mode = MAX_DEVICE_MODE_VACATION
        elif mode == PRESET_BOOST:
            mode = MAX_DEVICE_MODE_BOOST
        else:
            mode = None

        return mode

    @staticmethod
    def map_mode_max_hass(mode):
        """Map MAX! Operation Modes to Home Assistant Operation Modes."""
        if mode == MAX_DEVICE_MODE_MANUAL:
            operation_mode = PRESET_MANUAL
        elif mode == MAX_DEVICE_MODE_VACATION:
            operation_mode = PRESET_VACATION
        elif mode == MAX_DEVICE_MODE_BOOST:
            operation_mode = PRESET_BOOST
        else:
            operation_mode = None

        return operation_mode
