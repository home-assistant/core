"""Support for MAX! Thermostats via MAX! Cube."""
from __future__ import annotations

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Iterate through all MAX! Devices and add thermostats."""
    devices = []
    for handler in hass.data[DATA_KEY].values():
        for device in handler.cube.devices:
            if device.is_thermostat() or device.is_wallthermostat():
                devices.append(MaxCubeClimate(handler, device))

    if devices:
        add_entities(devices)


class MaxCubeClimate(ClimateEntity):
    """MAX! Cube ClimateEntity."""

    def __init__(self, handler, device):
        """Initialize MAX! Cube ClimateEntity."""
        room = handler.cube.room_by_id(device.room_id)
        self._attr_name = f"{room.name} {device.name}"
        self._cubehandle = handler
        self._device = device
        self._attr_supported_features = SUPPORT_FLAGS
        self._attr_should_poll = True
        self._attr_unique_id = self._device.serial
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_HEAT]
        self._attr_preset_modes = [
            PRESET_NONE,
            PRESET_BOOST,
            PRESET_COMFORT,
            PRESET_ECO,
            PRESET_AWAY,
            PRESET_ON,
        ]

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        temp = self._device.min_temperature or MIN_TEMPERATURE
        # OFF_TEMPERATURE (always off) a is valid temperature to maxcube but not to Home Assistant.
        # We use HVAC_MODE_OFF instead to represent a turned off thermostat.
        return max(temp, MIN_TEMPERATURE)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._device.max_temperature or MAX_TEMPERATURE

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.actual_temperature

    @property
    def hvac_mode(self):
        """Return current operation mode."""
        mode = self._device.mode
        if mode in (MAX_DEVICE_MODE_AUTOMATIC, MAX_DEVICE_MODE_BOOST):
            return HVAC_MODE_AUTO
        if (
            mode == MAX_DEVICE_MODE_MANUAL
            and self._device.target_temperature == OFF_TEMPERATURE
        ):
            return HVAC_MODE_OFF

        return HVAC_MODE_HEAT

    def set_hvac_mode(self, hvac_mode: str):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self._set_target(MAX_DEVICE_MODE_MANUAL, OFF_TEMPERATURE)
        elif hvac_mode == HVAC_MODE_HEAT:
            temp = max(self._device.target_temperature, self.min_temp)
            self._set_target(MAX_DEVICE_MODE_MANUAL, temp)
        elif hvac_mode == HVAC_MODE_AUTO:
            self._set_target(MAX_DEVICE_MODE_AUTOMATIC, None)
        else:
            raise ValueError(f"unsupported HVAC mode {hvac_mode}")

    def _set_target(self, mode: int | None, temp: float | None) -> None:
        """
        Set the mode and/or temperature of the thermostat.

        @param mode: this is the mode to change to.
        @param temp: the temperature to target.

        Both parameters are optional. When mode is undefined, it keeps
        the previous mode. When temp is undefined, it fetches the
        temperature from the weekly schedule when mode is
        MAX_DEVICE_MODE_AUTOMATIC and keeps the previous
        temperature otherwise.
        """
        with self._cubehandle.mutex:
            try:
                self._cubehandle.cube.set_temperature_mode(self._device, temp, mode)
            except (socket.timeout, OSError):
                _LOGGER.error("Setting HVAC mode failed")

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported."""
        valve = 0

        if self._device.is_thermostat():
            valve = self._device.valve_position
        elif self._device.is_wallthermostat():
            cube = self._cubehandle.cube
            room = cube.room_by_id(self._device.room_id)
            for device in cube.devices_by_room(room):
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
        temp = self._device.target_temperature
        if temp is None or temp < self.min_temp or temp > self.max_temp:
            return None
        return temp

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            raise ValueError(
                f"No {ATTR_TEMPERATURE} parameter passed to set_temperature method."
            )
        self._set_target(None, temp)

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        if self._device.mode == MAX_DEVICE_MODE_MANUAL:
            if self._device.target_temperature == self._device.comfort_temperature:
                return PRESET_COMFORT
            if self._device.target_temperature == self._device.eco_temperature:
                return PRESET_ECO
            if self._device.target_temperature == ON_TEMPERATURE:
                return PRESET_ON
        elif self._device.mode == MAX_DEVICE_MODE_BOOST:
            return PRESET_BOOST
        elif self._device.mode == MAX_DEVICE_MODE_VACATION:
            return PRESET_AWAY
        return PRESET_NONE

    def set_preset_mode(self, preset_mode):
        """Set new operation mode."""
        if preset_mode == PRESET_COMFORT:
            self._set_target(MAX_DEVICE_MODE_MANUAL, self._device.comfort_temperature)
        elif preset_mode == PRESET_ECO:
            self._set_target(MAX_DEVICE_MODE_MANUAL, self._device.eco_temperature)
        elif preset_mode == PRESET_ON:
            self._set_target(MAX_DEVICE_MODE_MANUAL, ON_TEMPERATURE)
        elif preset_mode == PRESET_AWAY:
            self._set_target(MAX_DEVICE_MODE_VACATION, None)
        elif preset_mode == PRESET_BOOST:
            self._set_target(MAX_DEVICE_MODE_BOOST, None)
        elif preset_mode == PRESET_NONE:
            self._set_target(MAX_DEVICE_MODE_AUTOMATIC, None)
        else:
            raise ValueError(f"unsupported preset mode {preset_mode}")

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        if not self._device.is_thermostat():
            return {}
        return {ATTR_VALVE_POSITION: self._device.valve_position}

    def update(self):
        """Get latest data from MAX! Cube."""
        self._cubehandle.update()
