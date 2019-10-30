"""Pyaehw4a1 platform to control of Hisense AEH-W4A1 Climate Devices."""

import json
import logging

from pyaehw4a1.aehw4a1 import AehW4a1

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_SWING_MODE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    PRECISION_WHOLE,
)

from .const import DOMAIN
from . import CONF_IP_ADDRESS, DOMAIN as AEHW4A1_DOMAIN

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE

MIN_TEMP_C = 16
MAX_TEMP_C = 32

MIN_TEMP_F = 61
MAX_TEMP_F = 90

HVAC_MODES = [
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
]

FAN_MODES = ["mute", "low", "med", "high", "auto"]

SWING_MODES = [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]

AC_TO_HA_STATE = {
    "0001": HVAC_MODE_HEAT,
    "0010": HVAC_MODE_COOL,
    "0011": HVAC_MODE_DRY,
    "0000": HVAC_MODE_FAN_ONLY,
}

HA_STATE_TO_AC = {
    HVAC_MODE_OFF: "off",
    HVAC_MODE_HEAT: "mode_heat",
    HVAC_MODE_COOL: "mode_cool",
    HVAC_MODE_DRY: "mode_dry",
    HVAC_MODE_FAN_ONLY: "mode_fan",
}

AC_TO_HA_FAN_MODES = {
    "00000000": "stop",
    "00000010": "mute",
    "00000100": "low",
    "00000110": "med",
    "00001000": "high",
    "00000001": "auto",
}

HA_FAN_MODES_TO_AC = {
    "mute": "speed_mute",
    "low": "speed_low",
    "med": "speed_med",
    "high": "speed_max",
    "auto": "speed_auto",
}

AC_TO_HA_SWING = {
    "00": SWING_OFF,
    "10": SWING_VERTICAL,
    "01": SWING_HORIZONTAL,
    "11": SWING_BOTH,
}

HA_SWING_TO_AC = {
    "SWING_VERTICAL_ON": "vert_swing",
    "SWING_HORIZONTAL_ON": "hor_swing",
    "SWING_VERTICAL_OFF": "vert_dir",
    "SWING_HORIZONTAL_OFF": "hor_dir",
}

_LOGGER = logging.getLogger(__name__)


def _build_entity(device):
    _LOGGER.debug("Found device at %s", device)
    print(device)
    return Climate_aeh_w4a1(device)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the AEH-W4A1 climate platform."""
    # Priority 1: manual config
    interfaces = hass.data[AEHW4A1_DOMAIN].get(DOMAIN)
    if not interfaces:
        # Priority 2: scanned interfaces
        devices = AehW4a1().discovery()
        interfaces = [{CONF_IP_ADDRESS: ip} for ip in devices]

    all_devices = [_build_entity(interface["ip_address"]) for interface in interfaces]

    async_add_devices(all_devices, True)


class Climate_aeh_w4a1(ClimateDevice):
    """Representation of a Hisense AEH-W4A1 module for climate device."""

    def __init__(self, device):
        """Initialize the climate device."""
        self._unique_id = device
        self._device = AehW4a1(device)
        self._hvac_modes = HVAC_MODES
        self._fan_modes = FAN_MODES
        self._swing_modes = SWING_MODES
        self._on = None
        self._temperature_unit = None
        self._current_temperature = None
        self._target_temperature = None
        self._hvac_mode = None
        self._fan_mode = None
        self._swing_mode = None

    def update(self):
        """Pull state from AEH-W4A1."""
        data = self._device.command("status_102_0")
        status = json.loads(data)
        self._on = status["run_status"]

        if status["temperature_Fahrenheit"] == "0":
            self._temperature_unit = TEMP_CELSIUS
        else:
            self._temperature_unit = TEMP_FAHRENHEIT

        self._current_temperature = int(status["indoor_temperature_status"], 2)
        self._target_temperature = int(status["indoor_temperature_setting"], 2)

        device_mode = status["mode_status"]
        if self._on:
            self._hvac_mode = AC_TO_HA_STATE[device_mode]
        else:
            self._hvac_mode = HVAC_MODE_OFF

        fan_mode = status["wind_status"]
        self._fan_mode = AC_TO_HA_FAN_MODES[fan_mode]

        swing_mode = status["up_down"] + status["left_right"]
        self._swing_mode = AC_TO_HA_SWING[swing_mode]

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._unique_id

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._temperature_unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we are trying to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return hvac target hvac state."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._hvac_modes

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_modes

    @property
    def swing_mode(self):
        """Return swing operation."""
        return self._swing_mode

    @property
    def swing_modes(self):
        """Return the list of available fan modes."""
        return self._swing_modes

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._temperature_unit == TEMP_CELSIUS:
            return MIN_TEMP_C
        else:
            return MIN_TEMP_F

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._temperature_unit == TEMP_CELSIUS:
            return MAX_TEMP_C
        else:
            return MAX_TEMP_F

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            _LOGGER.debug("Setting temp of %s to %s", self._unique_id, str(temp))
        if self._temperature_unit == TEMP_CELSIUS:
            self._device.command("temp_{0}_C".format(str(int(temp))))
        else:
            self._device.command("temp_{0}_F".format(str(int(temp))))

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        if fan_mode is not None:
            _LOGGER.debug("Setting fan mode of %s to %s", self._unique_id, fan_mode)
            self._device.command(HA_FAN_MODES_TO_AC[fan_mode])

    def set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        _LOGGER.debug("Setting swing mode of %s to %s", self._unique_id, swing_mode)
        swing_act = self._swing_mode

        if swing_mode == SWING_OFF and swing_act != SWING_OFF:
            if swing_act in (SWING_HORIZONTAL, SWING_BOTH):
                self._device.command(HA_SWING_TO_AC["SWING_HORIZONTAL_OFF"])
            if swing_act in (SWING_VERTICAL, SWING_BOTH):
                self._device.command(HA_SWING_TO_AC["SWING_VERTICAL_OFF"])

        if swing_mode == SWING_BOTH and swing_act != SWING_BOTH:
            if swing_act in (SWING_OFF, SWING_HORIZONTAL):
                self._device.command(HA_SWING_TO_AC["SWING_VERTICAL_ON"])
            if swing_act in (SWING_OFF, SWING_VERTICAL):
                self._device.command(HA_SWING_TO_AC["SWING_HORIZONTAL_ON"])

        if swing_mode == SWING_VERTICAL and swing_act != SWING_VERTICAL:
            if swing_act in (SWING_OFF, SWING_HORIZONTAL):
                self._device.command(HA_SWING_TO_AC["SWING_VERTICAL_ON"])
            if swing_act in (SWING_BOTH, SWING_HORIZONTAL):
                self._device.command(HA_SWING_TO_AC["SWING_HORIZONTAL_OFF"])

        if swing_mode == SWING_HORIZONTAL and swing_act != SWING_HORIZONTAL:
            if swing_act in (SWING_BOTH, SWING_VERTICAL):
                self._device.command(HA_SWING_TO_AC["SWING_VERTICAL_OFF"])
            if swing_act in (SWING_OFF, SWING_VERTICAL):
                self._device.command(HA_SWING_TO_AC["SWING_HORIZONTAL_ON"])

    def set_hvac_mode(self, hvac_mode):
        """Set new operation mode."""
        _LOGGER.debug("Setting operation mode of %s to %s", self._unique_id, hvac_mode)
        if hvac_mode is not None:
            if hvac_mode == HVAC_MODE_OFF:
                self.turn_off()
            else:
                self._device.command(HA_STATE_TO_AC[hvac_mode])
                self.turn_on()

    def turn_on(self):
        """Turn on."""
        _LOGGER.debug("Turning %s on", self._unique_id)
        self._device.command("on")

    def turn_off(self):
        """Turn off."""
        _LOGGER.debug("Turning %s off", self._unique_id)
        self._device.command("off")
