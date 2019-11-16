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
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from . import DATA_KEY

_LOGGER = logging.getLogger(__name__)

PRESET_MANUAL = "manual"
# There are two magic temperature values, which indicate:
# Off (valve fully closed)
OFF_TEMPERATURE = 4.5
# On (valve fully open)
ON_TEMPERATURE = 30.5

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
        """Return current operation mode."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        if device.target_temperature == OFF_TEMPERATURE:
            return HVAC_MODE_OFF
        elif device.target_temperature == ON_TEMPERATURE:
            return HVAC_MODE_HEAT
        else:
            return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_HEAT]

    def set_hvac_mode(self, hvac_mode: str):
        """Set new target hvac mode."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        temp = device.target_temperature
        mode = device.mode

        if hvac_mode == HVAC_MODE_OFF:
            temp = OFF_TEMPERATURE
            mode = MAX_DEVICE_MODE_MANUAL
        elif hvac_mode == HVAC_MODE_HEAT:
            temp = ON_TEMPERATURE
            mode = MAX_DEVICE_MODE_MANUAL
        else:
            # Reset the temperature to a sane value
            # TODO: Ideally, we should send 0 and the device will
            # set its temperature according to the schedule. However
            # current version of the library has a bug which causes
            # an exception when setting values below 8.
            if temp in [OFF_TEMPERATURE, ON_TEMPERATURE]:
                temp = device.eco_temperature
            mode = MAX_DEVICE_MODE_AUTOMATIC

        cube = self._cubehandle.cube
        with self._cubehandle.mutex:
            try:
                cube.set_temperature_mode(device, temp, mode)
            except (socket.timeout, socket.error):
                _LOGGER.error("Setting HVAC mode failed")
                return

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported."""
        cube = self._cubehandle.cube
        device = cube.device_by_rf(self._rf_address)
        valve = 0

        if cube.is_thermostat(device):
            valve = device.valve_position
        elif cube.is_wallthermostat(device):
            for device in cube.devices_by_room(cube.room_by_id(device.room_id)):
                if cube.is_thermostat(device) and device.valve_position > 0:
                    valve = device.valve_position
                    break

        # Assume heating when valve is open
        if valve > 0:
            return CURRENT_HVAC_HEAT
        else:
            return CURRENT_HVAC_IDLE if self.hvac_mode == HVAC_MODE_AUTO else CURRENT_HVAC_OFF

        return None

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
            except (socket.timeout, OSError):
                _LOGGER.error("Setting target temperature failed")
                return False

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        if self.hvac_mode in [HVAC_MODE_OFF, HVAC_MODE_HEAT]:
            return PRESET_NONE

        if device.mode == MAX_DEVICE_MODE_MANUAL:
            if device.target_temperature == device.comfort_temperature:
                return PRESET_COMFORT
            elif device.target_temperature == device.eco_temperature:
                return PRESET_ECO

        return self.map_mode_max_hass(device.mode)

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return [PRESET_NONE, PRESET_BOOST, PRESET_COMFORT, PRESET_ECO, PRESET_MANUAL, PRESET_AWAY]

    def set_preset_mode(self, preset_mode):
        """Set new operation mode."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        temp = device.target_temperature
        mode = MAX_DEVICE_MODE_AUTOMATIC

        if preset_mode in [PRESET_COMFORT, PRESET_ECO]:
            mode = MAX_DEVICE_MODE_MANUAL
            if preset_mode == PRESET_COMFORT:
                temp = device.comfort_temperature
            else:
                temp = device.eco_temperature
        else:
            mode = self.map_mode_hass_max(preset_mode) or MAX_DEVICE_MODE_AUTOMATIC

        with self._cubehandle.mutex:
            try:
                self._cubehandle.cube.set_temperature_mode(device, temp, mode)
            except (socket.timeout, OSError):
                _LOGGER.error("Setting operation mode failed")
                return

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
        if mode == PRESET_NONE:
            mode = MAX_DEVICE_MODE_AUTOMATIC
        elif mode == PRESET_MANUAL:
            mode = MAX_DEVICE_MODE_MANUAL
        elif mode == PRESET_AWAY:
            mode = MAX_DEVICE_MODE_VACATION
        elif mode == PRESET_BOOST:
            mode = MAX_DEVICE_MODE_BOOST
        else:
            mode = None

        return mode

    @staticmethod
    def map_mode_max_hass(mode):
        """Map MAX! Operation Modes to Home Assistant Operation Modes."""
        if mode == MAX_DEVICE_MODE_AUTOMATIC:
            operation_mode = PRESET_NONE
        elif mode == MAX_DEVICE_MODE_MANUAL:
            operation_mode = PRESET_MANUAL
        elif mode == MAX_DEVICE_MODE_VACATION:
            operation_mode = PRESET_AWAY
        elif mode == MAX_DEVICE_MODE_BOOST:
            operation_mode = PRESET_BOOST
        else:
            operation_mode = None

        return operation_mode
