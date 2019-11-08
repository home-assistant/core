"""Pyaehw4a1 platform to control of Hisense AEH-W4A1 Climate Devices."""

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
import json
<<<<<<< HEAD
>>>>>>> First working release, but there's a lot to do
=======
=======
>>>>>>> Refined logic
import time
>>>>>>> Added support for preset_modes
=======
>>>>>>> modified:   climate.py
import logging

from pyaehw4a1.aehw4a1 import AehW4a1

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    SUPPORT_FAN_MODE,
<<<<<<< HEAD
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_SWING_MODE,
<<<<<<< HEAD
<<<<<<< HEAD
    SUPPORT_PRESET_MODE,
=======
>>>>>>> First working release, but there's a lot to do
=======
    SUPPORT_PRESET_MODE,
>>>>>>> Added support for preset_modes
=======
    SUPPORT_PRESET_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
>>>>>>> Isort and updated requirements_test_all.txt
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> Added support for preset_modes
=======
    FAN_OFF,
>>>>>>> Refined logic
=======
>>>>>>> Null states when AC off
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_AUTO,
    PRESET_NONE,
    PRESET_ECO,
    PRESET_BOOST,
    PRESET_SLEEP,
<<<<<<< HEAD
=======
>>>>>>> First working release, but there's a lot to do
=======
>>>>>>> Added support for preset_modes
=======
>>>>>>> Isort and updated requirements_test_all.txt
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

from . import CONF_IP_ADDRESS, DOMAIN

<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> Added support for preset_modes
SUPPORT_FLAGS = (
    SUPPORT_TARGET_TEMPERATURE
    | SUPPORT_FAN_MODE
    | SUPPORT_SWING_MODE
    | SUPPORT_PRESET_MODE
)
<<<<<<< HEAD
=======
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE
>>>>>>> First working release, but there's a lot to do
=======
>>>>>>> Added support for preset_modes

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

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
FAN_MODES = [
    "mute",
=======
FAN_MODES = [
<<<<<<< HEAD
<<<<<<< HEAD
    FAN_OFF,
>>>>>>> Refined logic
=======
>>>>>>> Null states when AC off
=======
    "mute",
>>>>>>> Minor fixes
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_AUTO,
<<<<<<< HEAD
<<<<<<< HEAD
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
=======
FAN_MODES = ["mute", "low", "med", "high", "auto"]
=======
FAN_MODES = ["mute", FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO]
>>>>>>> Added support for preset_modes

SWING_MODES = [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]
>>>>>>> First working release, but there's a lot to do
=======
    "mute",
=======
>>>>>>> Minor fixes
]

SWING_MODES = [
    SWING_OFF,
    SWING_VERTICAL,
    SWING_HORIZONTAL,
    SWING_BOTH,
]
>>>>>>> Refined logic

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
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    "00000001": FAN_AUTO,
    "00000010": "mute",
    "00000100": FAN_LOW,
    "00000110": FAN_MEDIUM,
    "00001000": FAN_HIGH,
=======
    "00000000": "stop",
    "00000010": "mute",
    "00000100": "low",
    "00000110": "med",
    "00001000": "high",
    "00000001": "auto",
>>>>>>> First working release, but there's a lot to do
=======
    "00000000": "off",
=======
    "00000000": FAN_OFF,
=======
>>>>>>> Null states when AC off
=======
    "00000000": FAN_AUTO,  # fan value for heat mode
>>>>>>> Updated library and fixed pylint errors
    "00000001": FAN_AUTO,
>>>>>>> Refined logic
    "00000010": "mute",
    "00000100": FAN_LOW,
    "00000110": FAN_MEDIUM,
    "00001000": FAN_HIGH,
<<<<<<< HEAD
    "00000001": FAN_AUTO,
>>>>>>> Added support for preset_modes
=======
>>>>>>> Refined logic
}

HA_FAN_MODES_TO_AC = {
    "mute": "speed_mute",
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> Added support for preset_modes
    FAN_LOW: "speed_low",
    FAN_MEDIUM: "speed_med",
    FAN_HIGH: "speed_max",
    FAN_AUTO: "speed_auto",
<<<<<<< HEAD
=======
    "low": "speed_low",
    "med": "speed_med",
    "high": "speed_max",
    "auto": "speed_auto",
>>>>>>> First working release, but there's a lot to do
=======
>>>>>>> Added support for preset_modes
}

AC_TO_HA_SWING = {
    "00": SWING_OFF,
    "10": SWING_VERTICAL,
    "01": SWING_HORIZONTAL,
    "11": SWING_BOTH,
}

<<<<<<< HEAD
<<<<<<< HEAD
=======
HA_SWING_TO_AC = {
    "SWING_VERTICAL_ON": "vert_swing",
    "SWING_HORIZONTAL_ON": "hor_swing",
    "SWING_VERTICAL_OFF": "vert_dir",
    "SWING_HORIZONTAL_OFF": "hor_dir",
}

>>>>>>> First working release, but there's a lot to do
=======
>>>>>>> Added support for preset_modes
_LOGGER = logging.getLogger(__name__)


def _build_entity(device):
    _LOGGER.debug("Found device at %s", device)
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    return ClimateAehW4a1(device)
=======
    print(device)
=======
>>>>>>> Added support for preset_modes
    return Climate_aeh_w4a1(device)
>>>>>>> First working release, but there's a lot to do
=======
    return ClimateAehW4a1(device)
>>>>>>> Latest updates for TOX


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the AEH-W4A1 climate platform."""
    # Priority 1: manual config
    if hass.data[DOMAIN].get(CONF_IP_ADDRESS):
        devices = hass.data[DOMAIN].get(CONF_IP_ADDRESS, [])
    else:
        # Priority 2: scanned interfaces
        devices = await AehW4a1().discovery()

    all_devices = [_build_entity(device) for device in devices]
    async_add_devices(all_devices, True)


<<<<<<< HEAD
<<<<<<< HEAD
class ClimateAehW4a1(ClimateDevice):
=======
class Climate_aeh_w4a1(ClimateDevice):
>>>>>>> First working release, but there's a lot to do
=======
class ClimateAehW4a1(ClimateDevice):
>>>>>>> Latest updates for TOX
    """Representation of a Hisense AEH-W4A1 module for climate device."""

    def __init__(self, device):
        """Initialize the climate device."""
        self._unique_id = device
        self._device = AehW4a1(device)
        self._hvac_modes = HVAC_MODES
        self._fan_modes = FAN_MODES
        self._swing_modes = SWING_MODES
<<<<<<< HEAD
<<<<<<< HEAD
        self._preset_modes = PRESET_MODES
<<<<<<< HEAD
=======
>>>>>>> First working release, but there's a lot to do
=======
        self._preset_modes = PRESET_MODES
>>>>>>> Added support for preset_modes
=======
        self._available = None
>>>>>>> Implemented available state
        self._on = None
        self._temperature_unit = None
        self._current_temperature = None
        self._target_temperature = None
        self._hvac_mode = None
        self._fan_mode = None
        self._swing_mode = None
<<<<<<< HEAD
<<<<<<< HEAD
        self._preset_mode = None
        self._previous_state = None

    async def async_update(self):
        """Pull state from AEH-W4A1."""
<<<<<<< HEAD
        status = self._device.command("status_102_0")
=======
=======
        self._preset_mode = None
<<<<<<< HEAD
        self._previous_preset = None
>>>>>>> Added support for preset_modes
=======
        self._previous_state = None
>>>>>>> Minor fixes

    def update(self):
        """Pull state from AEH-W4A1."""
<<<<<<< HEAD
        data = self._device.command("status_102_0")
        status = json.loads(data)
>>>>>>> First working release, but there's a lot to do
=======
        status = self._device.command("status_102_0")
>>>>>>> Refined logic
=======
        try:
            status = await self._device.command("status_102_0")
        except Exception as library_error:  # pylint: disable=broad-except
            _LOGGER.debug("Unexpected error: %s", library_error)
            self._available = False
            return

        self._available = True

>>>>>>> Implemented available state
        self._on = status["run_status"]

        if status["temperature_Fahrenheit"] == "0":
            self._temperature_unit = TEMP_CELSIUS
        else:
            self._temperature_unit = TEMP_FAHRENHEIT

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        if self._on == "1":
            device_mode = status["mode_status"]
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
            self._fan_mode = None

        if self._on == "1":
            swing_mode = status["up_down"] + status["left_right"]
            self._swing_mode = AC_TO_HA_SWING[swing_mode]
        else:
            self._swing_mode = None

        if self._on == "1":
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
        else:
            self._preset_mode = None
=======
        self._current_temperature = int(status["indoor_temperature_status"], 2)
        self._target_temperature = int(status["indoor_temperature_setting"], 2)

=======
>>>>>>> Refined logic
        device_mode = status["mode_status"]
=======
>>>>>>> Small changes
=======
        self._current_temperature = int(status["indoor_temperature_status"], 2)

>>>>>>> Code optimization
        if self._on == "1":
            device_mode = status["mode_status"]
            self._hvac_mode = AC_TO_HA_STATE[device_mode]

            fan_mode = status["wind_status"]
            self._fan_mode = AC_TO_HA_FAN_MODES[fan_mode]
<<<<<<< HEAD
        else:
<<<<<<< HEAD
            self._fan_mode = FAN_OFF

        swing_mode = status["up_down"] + status["left_right"]
        self._swing_mode = AC_TO_HA_SWING[swing_mode]
>>>>>>> First working release, but there's a lot to do

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
=======
            self._fan_mode = None
=======
>>>>>>> Code optimization

            swing_mode = status["up_down"] + status["left_right"]
            self._swing_mode = AC_TO_HA_SWING[swing_mode]

            if self._hvac_mode == HVAC_MODE_COOL or self._hvac_mode == HVAC_MODE_HEAT:
                self._target_temperature = int(status["indoor_temperature_setting"], 2)
            else:
                self._target_temperature = None

            if status["efficient"] == "1":
                self._preset_mode = PRESET_BOOST
            elif status["low_electricity"] == "1":
                self._preset_mode = PRESET_ECO
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
>>>>>>> Null states when AC off
        else:
            self._hvac_mode = HVAC_MODE_OFF
            self._fan_mode = None
            self._swing_mode = None
            self._target_temperature = None
            self._preset_mode = None

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

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
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> Added support for preset_modes
    def preset_mode(self):
        """Return the preset mode if on."""
        return self._preset_mode

    @property
    def preset_modes(self):
        """Return the list of available preset modes."""
        return self._preset_modes

    @property
<<<<<<< HEAD
=======
>>>>>>> First working release, but there's a lot to do
=======
>>>>>>> Added support for preset_modes
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
<<<<<<< HEAD
<<<<<<< HEAD
        return MIN_TEMP_F
=======
        else:
            return MIN_TEMP_F
>>>>>>> First working release, but there's a lot to do
=======
        return MIN_TEMP_F
>>>>>>> Latest updates for TOX

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._temperature_unit == TEMP_CELSIUS:
            return MAX_TEMP_C
<<<<<<< HEAD
<<<<<<< HEAD
        return MAX_TEMP_F
=======
        else:
            return MAX_TEMP_F
>>>>>>> First working release, but there's a lot to do
=======
        return MAX_TEMP_F
>>>>>>> Latest updates for TOX

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            _LOGGER.debug("Setting temp of %s to %s", self._unique_id, str(temp))
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> Refined logic
=======
            if self._preset_mode != PRESET_NONE:
                await self.async_set_preset_mode(PRESET_NONE)
>>>>>>> Updated library and fixed pylint errors
            if self._temperature_unit == TEMP_CELSIUS:
                await self._device.command(f"temp_{str(int(temp))}_C")
            else:
<<<<<<< HEAD
                self._device.command(f"temp_{str(int(temp))}_F")
<<<<<<< HEAD

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
                self._previous_state = preset_mode
            elif preset_mode == PRESET_BOOST:
                self._device.command("turbo_on")
                self._previous_state = preset_mode
            elif preset_mode == PRESET_SLEEP:
                self._device.command("sleep_1")
                self._previous_state = self._hvac_mode
            elif preset_mode == "sleep_2":
                self._device.command("sleep_2")
                self._previous_state = self._hvac_mode
            elif preset_mode == "sleep_3":
                self._device.command("sleep_3")
                self._previous_state = self._hvac_mode
            elif preset_mode == "sleep_4":
                self._device.command("sleep_4")
                self._previous_state = self._hvac_mode
            else:
                if self._previous_state == PRESET_ECO:
                    self._device.command("energysave_off")
                elif self._previous_state == PRESET_BOOST:
                    self._device.command("turbo_off")
                elif self._previous_state in HA_STATE_TO_AC:
                    self._device.command(HA_STATE_TO_AC[self._previous_state])
=======
        if self._temperature_unit == TEMP_CELSIUS:
            self._device.command(f"temp_{str(int(temp))}_C")
        else:
            self._device.command(f"temp_{str(int(temp))}_F")
=======
>>>>>>> Refined logic
=======
                await self._device.command(f"temp_{str(int(temp))}_F")
>>>>>>> Switched to async

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        if self._on == "1":
            if self._hvac_mode in (HVAC_MODE_COOL, HVAC_MODE_FAN_ONLY):
                if self._hvac_mode != HVAC_MODE_FAN_ONLY or fan_mode != FAN_AUTO:
                    _LOGGER.debug(
                        "Setting fan mode of %s to %s", self._unique_id, fan_mode
                    )
                    await self._device.command(HA_FAN_MODES_TO_AC[fan_mode])

    async def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
<<<<<<< HEAD
        _LOGGER.debug("Setting swing mode of %s to %s", self._unique_id, swing_mode)
        swing_act = self._swing_mode

        if swing_mode == SWING_OFF and swing_act != SWING_OFF:
            if swing_act in (SWING_HORIZONTAL, SWING_BOTH):
                self._device.command("hor_dir")
                time.sleep(0.5)
            if swing_act in (SWING_VERTICAL, SWING_BOTH):
                self._device.command("vert_dir")

        if swing_mode == SWING_BOTH and swing_act != SWING_BOTH:
            if swing_act in (SWING_OFF, SWING_HORIZONTAL):
                self._device.command("vert_swing")
                time.sleep(0.5)
            if swing_act in (SWING_OFF, SWING_VERTICAL):
                self._device.command("hor_swing")

        if swing_mode == SWING_VERTICAL and swing_act != SWING_VERTICAL:
            if swing_act in (SWING_OFF, SWING_HORIZONTAL):
                self._device.command("vert_swing")
                time.sleep(0.5)
            if swing_act in (SWING_BOTH, SWING_HORIZONTAL):
                self._device.command("hor_dir")

        if swing_mode == SWING_HORIZONTAL and swing_act != SWING_HORIZONTAL:
            if swing_act in (SWING_BOTH, SWING_VERTICAL):
                self._device.command("vert_dir")
                time.sleep(0.5)
            if swing_act in (SWING_OFF, SWING_VERTICAL):
<<<<<<< HEAD
                self._device.command(HA_SWING_TO_AC["SWING_HORIZONTAL_ON"])
>>>>>>> First working release, but there's a lot to do
=======
                self._device.command("hor_swing")

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        _LOGGER.debug("Setting preset mode of %s to %s", self._unique_id, preset_mode)
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
        elif preset_mode == "sleep_3":
            self._device.command("sleep_3")
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
>>>>>>> Added support for preset_modes
=======
        if self._on == "1":
            _LOGGER.debug("Setting swing mode of %s to %s", self._unique_id, swing_mode)
            swing_act = self._swing_mode

            if swing_mode == SWING_OFF and swing_act != SWING_OFF:
                if swing_act in (SWING_HORIZONTAL, SWING_BOTH):
                    await self._device.command("hor_dir")
                if swing_act in (SWING_VERTICAL, SWING_BOTH):
                    await self._device.command("vert_dir")

            if swing_mode == SWING_BOTH and swing_act != SWING_BOTH:
                if swing_act in (SWING_OFF, SWING_HORIZONTAL):
                    await self._device.command("vert_swing")
                if swing_act in (SWING_OFF, SWING_VERTICAL):
                    await self._device.command("hor_swing")

            if swing_mode == SWING_VERTICAL and swing_act != SWING_VERTICAL:
                if swing_act in (SWING_OFF, SWING_HORIZONTAL):
                    await self._device.command("vert_swing")
                if swing_act in (SWING_BOTH, SWING_HORIZONTAL):
                    await self._device.command("hor_dir")

            if swing_mode == SWING_HORIZONTAL and swing_act != SWING_HORIZONTAL:
                if swing_act in (SWING_BOTH, SWING_VERTICAL):
                    await self._device.command("vert_dir")
                if swing_act in (SWING_OFF, SWING_VERTICAL):
                    await self._device.command("hor_swing")

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        if self._on == "1":
            _LOGGER.debug(
                "Setting preset mode of %s to %s", self._unique_id, preset_mode
            )
            if preset_mode == PRESET_ECO:
                await self._device.command("energysave_on")
                self._previous_state = preset_mode
            elif preset_mode == PRESET_BOOST:
                await self._device.command("turbo_on")
                self._previous_state = preset_mode
            elif preset_mode == PRESET_SLEEP:
                await self._device.command("sleep_1")
                self._previous_state = self._hvac_mode
            elif preset_mode == "sleep_2":
                await self._device.command("sleep_2")
                self._previous_state = self._hvac_mode
            elif preset_mode == "sleep_3":
                await self._device.command("sleep_3")
                self._previous_state = self._hvac_mode
            elif preset_mode == "sleep_4":
                await self._device.command("sleep_4")
                self._previous_state = self._hvac_mode
            else:
                if self._previous_state == PRESET_ECO:
                    await self._device.command("energysave_off")
                elif self._previous_state == PRESET_BOOST:
<<<<<<< HEAD
                    self._device.command("turbo_off")
<<<<<<< HEAD
                elif self._previous_preset in HA_STATE_TO_AC:
                    self._device.command(HA_STATE_TO_AC[self._previous_preset])
>>>>>>> Refined logic
=======
                elif self._previous_state in HA_STATE_TO_AC:
                    self._device.command(HA_STATE_TO_AC[self._previous_state])
>>>>>>> Minor fixes
=======
                    await self._device.command("turbo_off")
                elif self._previous_state in HA_STATE_TO_AC:
                    await self._device.command(HA_STATE_TO_AC[self._previous_state])
>>>>>>> Switched to async

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new operation mode."""
        _LOGGER.debug("Setting operation mode of %s to %s", self._unique_id, hvac_mode)
        if hvac_mode is not None:
            if hvac_mode == HVAC_MODE_OFF:
                await self.async_turn_off()
            else:
                await self._device.command(HA_STATE_TO_AC[hvac_mode])
                await self.async_turn_on()

    async def async_turn_on(self):
        """Turn on."""
        _LOGGER.debug("Turning %s on", self._unique_id)
        await self._device.command("on")

    async def async_turn_off(self):
        """Turn off."""
        _LOGGER.debug("Turning %s off", self._unique_id)
        await self._device.command("off")
