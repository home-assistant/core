"""Support for MAX! Thermostats via MAX! Cube."""
import logging
import socket

from maxcube.device import (
    MAX_DEVICE_MODE_AUTOMATIC,
    MAX_DEVICE_MODE_BOOST,
    MAX_DEVICE_MODE_MANUAL,
    MAX_DEVICE_MODE_VACATION,
)

from homeassistant.components.climate import ClimateEntity
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

ATTR_VALVE_POSITION = "valve_position"
PRESET_ON = "on"

# There are two magic temperature values, which indicate:
# Off (valve fully closed)
OFF_TEMPERATURE = 4.5
# On (valve fully open)
ON_TEMPERATURE = 30.5

# Lowest Value without turning off
MIN_TEMPERATURE = 5.0
# Largest Value without fully opening
MAX_TEMPERATURE = 30.0

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

HASS_PRESET_TO_MAX_MODE = {
    PRESET_AWAY: MAX_DEVICE_MODE_VACATION,
    PRESET_BOOST: MAX_DEVICE_MODE_BOOST,
    PRESET_NONE: MAX_DEVICE_MODE_AUTOMATIC,
    PRESET_ON: MAX_DEVICE_MODE_MANUAL,
}

MAX_MODE_TO_HASS_PRESET = {
    MAX_DEVICE_MODE_AUTOMATIC: PRESET_NONE,
    MAX_DEVICE_MODE_BOOST: PRESET_BOOST,
    MAX_DEVICE_MODE_MANUAL: PRESET_NONE,
    MAX_DEVICE_MODE_VACATION: PRESET_AWAY,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Iterate through all MAX! Devices and add thermostats."""
    devices = []
    for handler in hass.data[DATA_KEY].values():
        cube = handler.cube
        for device in cube.devices:
            name = f"{cube.room_by_id(device.room_id).name} {device.name}"

            if device.is_thermostat() or device.is_wallthermostat():
                devices.append(MaxCubeClimate(handler, name, device.rf_address))

    if devices:
        add_entities(devices)


class MaxCubeClimate(ClimateEntity):
    """MAX! Cube ClimateEntity."""

    def __init__(self, handler, name, rf_address):
        """Initialize MAX! Cube ClimateEntity."""
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
        if device.min_temperature is None:
            return MIN_TEMPERATURE
        return device.min_temperature

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        if device.max_temperature is None:
            return MAX_TEMPERATURE
        return device.max_temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        return device.actual_temperature

    @property
    def hvac_mode(self):
        """Return current operation mode."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        if device.mode in [MAX_DEVICE_MODE_AUTOMATIC, MAX_DEVICE_MODE_BOOST]:
            return HVAC_MODE_AUTO
        if (
            device.mode == MAX_DEVICE_MODE_MANUAL
            and device.target_temperature == OFF_TEMPERATURE
        ):
            return HVAC_MODE_OFF

        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_HEAT]

    def set_hvac_mode(self, hvac_mode: str):
        """Set new target hvac mode."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        temp = device.target_temperature
        mode = MAX_DEVICE_MODE_MANUAL

        if hvac_mode == HVAC_MODE_OFF:
            temp = OFF_TEMPERATURE
        elif hvac_mode != HVAC_MODE_HEAT:
            # Reset the temperature to a sane value.
            # Ideally, we should send 0 and the device will set its
            # temperature according to the schedule. However, current
            # version of the library has a bug which causes an
            # exception when setting values below 8.
            if temp in [OFF_TEMPERATURE, ON_TEMPERATURE]:
                temp = device.eco_temperature
            mode = MAX_DEVICE_MODE_AUTOMATIC

        cube = self._cubehandle.cube
        with self._cubehandle.mutex:
            try:
                cube.set_temperature_mode(device, temp, mode)
            except (socket.timeout, OSError):
                _LOGGER.error("Setting HVAC mode failed")
                return

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported."""
        cube = self._cubehandle.cube
        device = cube.device_by_rf(self._rf_address)
        valve = 0

        if device.is_thermostat():
            valve = device.valve_position
        elif device.is_wallthermostat():
            for device in cube.devices_by_room(cube.room_by_id(device.room_id)):
                if device.is_thermostat() and device.valve_position > 0:
                    valve = device.valve_position
                    break
        else:
            return None

        # Assume heating when valve is open
        if valve > 0:
            return CURRENT_HVAC_HEAT

        return (
            CURRENT_HVAC_OFF if self.hvac_mode == HVAC_MODE_OFF else CURRENT_HVAC_IDLE
        )

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        if (
            device.target_temperature is None
            or device.target_temperature < self.min_temp
            or device.target_temperature > self.max_temp
        ):
            return None
        return device.target_temperature

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
        if self.hvac_mode == HVAC_MODE_OFF:
            return PRESET_NONE

        if device.mode == MAX_DEVICE_MODE_MANUAL:
            if device.target_temperature == device.comfort_temperature:
                return PRESET_COMFORT
            if device.target_temperature == device.eco_temperature:
                return PRESET_ECO
            if device.target_temperature == ON_TEMPERATURE:
                return PRESET_ON
            return PRESET_NONE

        return MAX_MODE_TO_HASS_PRESET[device.mode]

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return [
            PRESET_NONE,
            PRESET_BOOST,
            PRESET_COMFORT,
            PRESET_ECO,
            PRESET_AWAY,
            PRESET_ON,
        ]

    def set_preset_mode(self, preset_mode):
        """Set new operation mode."""
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        temp = device.target_temperature
        mode = MAX_DEVICE_MODE_AUTOMATIC

        if preset_mode in [PRESET_COMFORT, PRESET_ECO, PRESET_ON]:
            mode = MAX_DEVICE_MODE_MANUAL
            if preset_mode == PRESET_COMFORT:
                temp = device.comfort_temperature
            elif preset_mode == PRESET_ECO:
                temp = device.eco_temperature
            else:
                temp = ON_TEMPERATURE
        else:
            mode = HASS_PRESET_TO_MAX_MODE[preset_mode] or MAX_DEVICE_MODE_AUTOMATIC

        with self._cubehandle.mutex:
            try:
                self._cubehandle.cube.set_temperature_mode(device, temp, mode)
            except (socket.timeout, OSError):
                _LOGGER.error("Setting operation mode failed")
                return

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        cube = self._cubehandle.cube
        device = cube.device_by_rf(self._rf_address)

        if not device.is_thermostat():
            return {}
        return {ATTR_VALVE_POSITION: device.valve_position}

    def update(self):
        """Get latest data from MAX! Cube."""
        self._cubehandle.update()
