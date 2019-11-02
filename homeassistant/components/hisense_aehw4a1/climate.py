"""Pyaehw4a1 platform to control of Hisense AEH-W4A1 Climate Devices."""

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
    SUPPORT_PRESET_MODE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    FAN_OFF,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_AUTO,
    PRESET_NONE,
    PRESET_ECO,
    PRESET_BOOST,
    PRESET_SLEEP,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    PRECISION_WHOLE,
)

from .const import DOMAIN
from . import CONF_IP_ADDRESS, DOMAIN as AEHW4A1_DOMAIN

SUPPORT_FLAGS = (
    SUPPORT_TARGET_TEMPERATURE
    | SUPPORT_FAN_MODE
    | SUPPORT_SWING_MODE
    | SUPPORT_PRESET_MODE
)

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

FAN_MODES = [
    FAN_OFF,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_AUTO,
    "mute",
]

SWING_MODES = [
    SWING_OFF,
    SWING_VERTICAL,
    SWING_HORIZONTAL,
    SWING_BOTH,
]

PRESET_MODES = [
    PRESET_NONE,
    PRESET_ECO,
    PRESET_BOOST,
    PRESET_SLEEP,
    "sleep_2",
    "sleep_3",
    "sleep_4",
]

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
    "00000000": FAN_OFF,
    "00000001": FAN_AUTO,
    "00000010": "mute",
    "00000100": FAN_LOW,
    "00000110": FAN_MEDIUM,
    "00001000": FAN_HIGH,
}

HA_FAN_MODES_TO_AC = {
    "mute": "speed_mute",
    FAN_LOW: "speed_low",
    FAN_MEDIUM: "speed_med",
    FAN_HIGH: "speed_max",
    FAN_AUTO: "speed_auto",
}

AC_TO_HA_SWING = {
    "00": SWING_OFF,
    "10": SWING_VERTICAL,
    "01": SWING_HORIZONTAL,
    "11": SWING_BOTH,
}

_LOGGER = logging.getLogger(__name__)


def _build_entity(device):
    _LOGGER.debug("Found device at %s", device)
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
        self._preset_modes = PRESET_MODES
        self._on = None
        self._temperature_unit = None
        self._current_temperature = None
        self._target_temperature = None
        self._hvac_mode = None
        self._fan_mode = None
        self._swing_mode = None
        self._preset_mode = None
        self._previous_preset = None

    def update(self):
        """Pull state from AEH-W4A1."""
        status = self._device.command("status_102_0")
        self._on = status["run_status"]

        if status["temperature_Fahrenheit"] == "0":
            self._temperature_unit = TEMP_CELSIUS
        else:
            self._temperature_unit = TEMP_FAHRENHEIT

        device_mode = status["mode_status"]
        if self._on == "1":
            self._hvac_mode = AC_TO_HA_STATE[device_mode]
        else:
            self._hvac_mode = HVAC_MODE_OFF

        self._current_temperature = int(status["indoor_temperature_status"], 2)

        if self._on == "1" and (
            self._hvac_mode == HVAC_MODE_COOL or self._hvac_mode == HVAC_MODE_HEAT
        ):
            self._target_temperature = int(status["indoor_temperature_setting"], 2)
        else:
            self._target_temperature = None

        if self._on == "1":
            if self._hvac_mode == HVAC_MODE_HEAT:
                self._fan_mode = FAN_AUTO
            else:
                fan_mode = status["wind_status"]
                self._fan_mode = AC_TO_HA_FAN_MODES[fan_mode]
        else:
            self._fan_mode = FAN_OFF

        swing_mode = status["up_down"] + status["left_right"]
        self._swing_mode = AC_TO_HA_SWING[swing_mode]

        if status["low_electricity"] == "1":
            self._preset_mode = PRESET_ECO
        elif status["efficient"] == "1":
            self._preset_mode = PRESET_BOOST
        elif status["sleep_status"] == "0000001":
            self._preset_mode = PRESET_SLEEP
        elif status["sleep_status"] == "0000010":
            self._preset_mode = "sleep_2"
        elif status["sleep_status"] == "0000011":
            self._preset_mode = "sleep_3"
        elif status["sleep_status"] == "0000100":
            self._preset_mode = "sleep_4"
        else:
            self._preset_mode = PRESET_NONE

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
    def preset_mode(self):
        """Return the preset mode if on."""
        return self._preset_mode

    @property
    def preset_modes(self):
        """Return the list of available preset modes."""
        return self._preset_modes

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
                self._device.command(f"temp_{str(int(temp))}_C")
            else:
                self._device.command(f"temp_{str(int(temp))}_F")

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        if self._on == "1":
            if self._hvac_mode in (HVAC_MODE_COOL, HVAC_MODE_FAN_ONLY):
                if self._hvac_mode != HVAC_MODE_FAN_ONLY or fan_mode != FAN_AUTO:
                    _LOGGER.debug(
                        "Setting fan mode of %s to %s", self._unique_id, fan_mode
                    )
                    self._device.command(HA_FAN_MODES_TO_AC[fan_mode])

    def set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        if self._on == "1":
            _LOGGER.debug("Setting swing mode of %s to %s", self._unique_id, swing_mode)
            swing_act = self._swing_mode

            if swing_mode == SWING_OFF and swing_act != SWING_OFF:
                if swing_act in (SWING_HORIZONTAL, SWING_BOTH):
                    self._device.command("hor_dir")
                if swing_act in (SWING_VERTICAL, SWING_BOTH):
                    self._device.command("vert_dir")

            if swing_mode == SWING_BOTH and swing_act != SWING_BOTH:
                if swing_act in (SWING_OFF, SWING_HORIZONTAL):
                    self._device.command("vert_swing")
                if swing_act in (SWING_OFF, SWING_VERTICAL):
                    self._device.command("hor_swing")

            if swing_mode == SWING_VERTICAL and swing_act != SWING_VERTICAL:
                if swing_act in (SWING_OFF, SWING_HORIZONTAL):
                    self._device.command("vert_swing")
                if swing_act in (SWING_BOTH, SWING_HORIZONTAL):
                    self._device.command("hor_dir")

            if swing_mode == SWING_HORIZONTAL and swing_act != SWING_HORIZONTAL:
                if swing_act in (SWING_BOTH, SWING_VERTICAL):
                    self._device.command("vert_dir")
                if swing_act in (SWING_OFF, SWING_VERTICAL):
                    self._device.command("hor_swing")

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        if self._on == "1":
            _LOGGER.debug(
                "Setting preset mode of %s to %s", self._unique_id, preset_mode
            )
            if preset_mode == PRESET_ECO:
                self._device.command("energysave_on")
                self._previous_preset = preset_mode
            elif preset_mode == PRESET_BOOST:
                self._device.command("turbo_on")
                self._previous_preset = preset_mode
            elif preset_mode == PRESET_SLEEP:
                self._device.command("sleep_1")
                self._previous_preset = self._hvac_mode
            elif preset_mode == "sleep_2":
                self._device.command("sleep_2")
                self._previous_preset = self._hvac_mode
            elif preset_mode == "sleep_3":
                self._device.command("sleep_3")
                self._previous_preset = self._hvac_mode
            elif preset_mode == "sleep_4":
                self._device.command("sleep_4")
                self._previous_preset = self._hvac_mode
            else:
                if self._previous_preset == PRESET_ECO:
                    self._device.command("energysave_off")
                elif self._previous_preset == PRESET_BOOST:
                    self._device.command("turbo_off")
                elif self._previous_preset == PRESET_BOOST:
                    self._device.command("turbo_off")
                elif self._previous_preset in HA_STATE_TO_AC:
                    self._device.command(HA_STATE_TO_AC[self._previous_preset])

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
