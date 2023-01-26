"""Pyaehw4a1 platform to control of Hisense AEH-W4A1 Climate Devices."""
from __future__ import annotations

import logging
from typing import Any

from pyaehw4a1.aehw4a1 import AehW4a1
import pyaehw4a1.exceptions

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CONF_IP_ADDRESS, DOMAIN

MIN_TEMP_C = 16
MAX_TEMP_C = 32

MIN_TEMP_F = 61
MAX_TEMP_F = 90

HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
]

FAN_MODES = [
    "mute",
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_AUTO,
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
    "0001": HVACMode.HEAT,
    "0010": HVACMode.COOL,
    "0011": HVACMode.DRY,
    "0000": HVACMode.FAN_ONLY,
}

HA_STATE_TO_AC = {
    HVACMode.OFF: "off",
    HVACMode.HEAT: "mode_heat",
    HVACMode.COOL: "mode_cool",
    HVACMode.DRY: "mode_dry",
    HVACMode.FAN_ONLY: "mode_fan",
}

AC_TO_HA_FAN_MODES = {
    "00000000": FAN_AUTO,  # fan value for heat mode
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
    return ClimateAehW4a1(device)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AEH-W4A1 climate platform."""
    # Priority 1: manual config
    if hass.data[DOMAIN].get(CONF_IP_ADDRESS):
        devices = hass.data[DOMAIN][CONF_IP_ADDRESS]
    else:
        # Priority 2: scanned interfaces
        devices = await AehW4a1().discovery()

    entities = [_build_entity(device) for device in devices]
    async_add_entities(entities, True)


class ClimateAehW4a1(ClimateEntity):
    """Representation of a Hisense AEH-W4A1 module for climate device."""

    _attr_hvac_modes = HVAC_MODES
    _attr_precision = PRECISION_WHOLE
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(self, device):
        """Initialize the climate device."""
        self._unique_id = device
        self._device = AehW4a1(device)
        self._fan_modes = FAN_MODES
        self._swing_modes = SWING_MODES
        self._preset_modes = PRESET_MODES
        self._attr_available = False
        self._on = None
        self._current_temperature = None
        self._target_temperature = None
        self._attr_hvac_mode = None
        self._fan_mode = None
        self._swing_mode = None
        self._preset_mode = None
        self._previous_state = None

    async def async_update(self) -> None:
        """Pull state from AEH-W4A1."""
        try:
            status = await self._device.command("status_102_0")
        except pyaehw4a1.exceptions.ConnectionError as library_error:
            _LOGGER.warning(
                "Unexpected error of %s: %s", self._unique_id, library_error
            )
            self._attr_available = False
            return

        self._attr_available = True

        self._on = status["run_status"]

        if status["temperature_Fahrenheit"] == "0":
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        else:
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

        self._current_temperature = int(status["indoor_temperature_status"], 2)

        if self._on == "1":
            device_mode = status["mode_status"]
            self._attr_hvac_mode = AC_TO_HA_STATE[device_mode]

            fan_mode = status["wind_status"]
            self._fan_mode = AC_TO_HA_FAN_MODES[fan_mode]

            swing_mode = f'{status["up_down"]}{status["left_right"]}'
            self._swing_mode = AC_TO_HA_SWING[swing_mode]

            if self._attr_hvac_mode in (HVACMode.COOL, HVACMode.HEAT):
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
        else:
            self._attr_hvac_mode = HVACMode.OFF
            self._fan_mode = None
            self._swing_mode = None
            self._target_temperature = None
            self._preset_mode = None

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._unique_id

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we are trying to reach."""
        return self._target_temperature

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
        if self.temperature_unit == UnitOfTemperature.CELSIUS:
            return MIN_TEMP_C
        return MIN_TEMP_F

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self.temperature_unit == UnitOfTemperature.CELSIUS:
            return MAX_TEMP_C
        return MAX_TEMP_F

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if self._on != "1":
            _LOGGER.warning(
                "AC at %s is off, could not set temperature", self._unique_id
            )
            return
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            _LOGGER.debug("Setting temp of %s to %s", self._unique_id, temp)
            if self._preset_mode != PRESET_NONE:
                await self.async_set_preset_mode(PRESET_NONE)
            if self.temperature_unit == UnitOfTemperature.CELSIUS:
                await self._device.command(f"temp_{int(temp)}_C")
            else:
                await self._device.command(f"temp_{int(temp)}_F")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if self._on != "1":
            _LOGGER.warning("AC at %s is off, could not set fan mode", self._unique_id)
            return
        if self._attr_hvac_mode in (HVACMode.COOL, HVACMode.FAN_ONLY) and (
            self._attr_hvac_mode != HVACMode.FAN_ONLY or fan_mode != FAN_AUTO
        ):
            _LOGGER.debug("Setting fan mode of %s to %s", self._unique_id, fan_mode)
            await self._device.command(HA_FAN_MODES_TO_AC[fan_mode])

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        if self._on != "1":
            _LOGGER.warning(
                "AC at %s is off, could not set swing mode", self._unique_id
            )
            return

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

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self._on != "1":
            if preset_mode == PRESET_NONE:
                return
            await self.async_turn_on()

        _LOGGER.debug("Setting preset mode of %s to %s", self._unique_id, preset_mode)

        if preset_mode == PRESET_ECO:
            await self._device.command("energysave_on")
            self._previous_state = preset_mode
        elif preset_mode == PRESET_BOOST:
            await self._device.command("turbo_on")
            self._previous_state = preset_mode
        elif preset_mode == PRESET_SLEEP:
            await self._device.command("sleep_1")
            self._previous_state = self._attr_hvac_mode
        elif preset_mode == "sleep_2":
            await self._device.command("sleep_2")
            self._previous_state = self._attr_hvac_mode
        elif preset_mode == "sleep_3":
            await self._device.command("sleep_3")
            self._previous_state = self._attr_hvac_mode
        elif preset_mode == "sleep_4":
            await self._device.command("sleep_4")
            self._previous_state = self._attr_hvac_mode
        elif self._previous_state is not None:
            if self._previous_state == PRESET_ECO:
                await self._device.command("energysave_off")
            elif self._previous_state == PRESET_BOOST:
                await self._device.command("turbo_off")
            elif self._previous_state in HA_STATE_TO_AC:
                await self._device.command(HA_STATE_TO_AC[self._previous_state])
            self._previous_state = None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        _LOGGER.debug("Setting operation mode of %s to %s", self._unique_id, hvac_mode)
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self._device.command(HA_STATE_TO_AC[hvac_mode])
            if self._on != "1":
                await self.async_turn_on()

    async def async_turn_on(self) -> None:
        """Turn on."""
        _LOGGER.debug("Turning %s on", self._unique_id)
        await self._device.command("on")

    async def async_turn_off(self) -> None:
        """Turn off."""
        _LOGGER.debug("Turning %s off", self._unique_id)
        await self._device.command("off")
