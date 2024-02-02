"""Support for Fibaro thermostats."""
from __future__ import annotations

from contextlib import suppress
import logging
from typing import Any

from pyfibaro.fibaro_device import DeviceModel

from homeassistant.components.climate import (
    ENTITY_ID_FORMAT,
    PRESET_AWAY,
    PRESET_BOOST,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FibaroController, FibaroDevice
from .const import DOMAIN

PRESET_RESUME = "resume"
PRESET_MOIST = "moist"
PRESET_FURNACE = "furnace"
PRESET_CHANGEOVER = "changeover"
PRESET_ECO_HEAT = "eco_heat"
PRESET_ECO_COOL = "eco_cool"
PRESET_FORCE_OPEN = "force_open"

_LOGGER = logging.getLogger(__name__)

# SDS13781-10 Z-Wave Application Command Class Specification 2019-01-04
# Table 128, Thermostat Fan Mode Set version 4::Fan Mode encoding
FANMODES = {
    0: "off",
    1: "low",
    2: "auto_high",
    3: "medium",
    4: "auto_medium",
    5: "high",
    6: "circulation",
    7: "humidity_circulation",
    8: "left_right",
    9: "up_down",
    10: "quiet",
    128: "auto",
}

HA_FANMODES = {v: k for k, v in FANMODES.items()}

# SDS13781-10 Z-Wave Application Command Class Specification 2019-01-04
# Table 130, Thermostat Mode Set version 3::Mode encoding.
# 4 AUXILIARY
OPMODES_PRESET = {
    5: PRESET_RESUME,
    7: PRESET_FURNACE,
    9: PRESET_MOIST,
    10: PRESET_CHANGEOVER,
    11: PRESET_ECO_HEAT,
    12: PRESET_ECO_COOL,
    13: PRESET_AWAY,
    15: PRESET_BOOST,
    31: PRESET_FORCE_OPEN,
}

HA_OPMODES_PRESET = {v: k for k, v in OPMODES_PRESET.items()}

OPMODES_HVAC = {
    0: HVACMode.OFF,
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
    3: HVACMode.AUTO,
    4: HVACMode.HEAT,
    5: HVACMode.AUTO,
    6: HVACMode.FAN_ONLY,
    7: HVACMode.HEAT,
    8: HVACMode.DRY,
    9: HVACMode.DRY,
    10: HVACMode.AUTO,
    11: HVACMode.HEAT,
    12: HVACMode.COOL,
    13: HVACMode.AUTO,
    15: HVACMode.AUTO,
    31: HVACMode.HEAT,
}

HA_OPMODES_HVAC = {
    HVACMode.OFF: 0,
    HVACMode.HEAT: 1,
    HVACMode.COOL: 2,
    HVACMode.AUTO: 3,
    HVACMode.FAN_ONLY: 6,
    HVACMode.DRY: 8,
}

TARGET_TEMP_ACTIONS = (
    "setTargetLevel",
    "setThermostatSetpoint",
    "setHeatingThermostatSetpoint",
)

OP_MODE_ACTIONS = ("setMode", "setOperatingMode", "setThermostatMode")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Fibaro controller devices."""
    controller: FibaroController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FibaroThermostat(device)
            for device in controller.fibaro_devices[Platform.CLIMATE]
        ],
        True,
    )


class FibaroThermostat(FibaroDevice, ClimateEntity):
    """Representation of a Fibaro Thermostat."""

    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, fibaro_device: DeviceModel) -> None:
        """Initialize the Fibaro device."""
        super().__init__(fibaro_device)
        self._temp_sensor_device: FibaroDevice | None = None
        self._target_temp_device: FibaroDevice | None = None
        self._op_mode_device: FibaroDevice | None = None
        self._fan_mode_device: FibaroDevice | None = None
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

        siblings = fibaro_device.fibaro_controller.get_siblings(fibaro_device)
        _LOGGER.debug("%s siblings: %s", fibaro_device.ha_id, siblings)
        tempunit = "C"
        for device in siblings:
            # Detecting temperature device, one strong and one weak way of
            # doing so, so we prefer the hard evidence, if there is such.
            if device.type == "com.fibaro.temperatureSensor":
                self._temp_sensor_device = FibaroDevice(device)
                tempunit = device.unit
            elif (
                self._temp_sensor_device is None
                and device.has_unit
                and (device.value.has_value or device.has_heating_thermostat_setpoint)
                and device.unit in ("C", "F")
            ):
                self._temp_sensor_device = FibaroDevice(device)
                tempunit = device.unit

            if any(
                action for action in TARGET_TEMP_ACTIONS if action in device.actions
            ):
                self._target_temp_device = FibaroDevice(device)
                self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
                if device.has_unit:
                    tempunit = device.unit

            if any(action for action in OP_MODE_ACTIONS if action in device.actions):
                self._op_mode_device = FibaroDevice(device)
                self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

            if "setFanMode" in device.actions:
                self._fan_mode_device = FibaroDevice(device)
                self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        if tempunit == "F":
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        else:
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        if self._fan_mode_device:
            fan_modes = self._fan_mode_device.fibaro_device.supported_modes
            self._attr_fan_modes = []
            for mode in fan_modes:
                if mode not in FANMODES:
                    _LOGGER.warning("%d unknown fan mode", mode)
                    continue
                self._attr_fan_modes.append(FANMODES[int(mode)])

        self._attr_hvac_modes = [HVACMode.AUTO]  # default
        if self._op_mode_device:
            self._attr_preset_modes = []
            self._attr_hvac_modes: list[HVACMode] = []
            device = self._op_mode_device.fibaro_device
            if device.has_supported_thermostat_modes:
                for mode in device.supported_thermostat_modes:
                    try:
                        self._attr_hvac_modes.append(HVACMode(mode.lower()))
                    except ValueError:
                        self._attr_preset_modes.append(mode)
            else:
                if device.has_supported_operating_modes:
                    op_modes = device.supported_operating_modes
                else:
                    op_modes = device.supported_modes
                for mode in op_modes:
                    if (
                        mode in OPMODES_HVAC
                        and (mode_ha := OPMODES_HVAC.get(mode))
                        and mode_ha not in self._attr_hvac_modes
                    ):
                        self._attr_hvac_modes.append(mode_ha)
                    if mode in OPMODES_PRESET:
                        self._attr_preset_modes.append(OPMODES_PRESET[mode])

        if HVACMode.OFF in self._attr_hvac_modes and len(self._attr_hvac_modes) > 1:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        _LOGGER.debug(
            (
                "Climate %s\n"
                "- _temp_sensor_device %s\n"
                "- _target_temp_device %s\n"
                "- _op_mode_device %s\n"
                "- _fan_mode_device %s"
            ),
            self.ha_id,
            self._temp_sensor_device.ha_id if self._temp_sensor_device else "None",
            self._target_temp_device.ha_id if self._target_temp_device else "None",
            self._op_mode_device.ha_id if self._op_mode_device else "None",
            self._fan_mode_device.ha_id if self._fan_mode_device else "None",
        )
        await super().async_added_to_hass()

        # Register update callback for child devices
        siblings = self.fibaro_device.fibaro_controller.get_siblings(self.fibaro_device)
        for device in siblings:
            if device != self.fibaro_device:
                self.controller.register(device.fibaro_id, self._update_callback)

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if not self._fan_mode_device:
            return None
        mode = self._fan_mode_device.fibaro_device.mode
        return FANMODES[mode]

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if not self._fan_mode_device:
            return
        self._fan_mode_device.action("setFanMode", HA_FANMODES[fan_mode])

    @property
    def fibaro_op_mode(self) -> str | int:
        """Return the operating mode of the device."""
        if not self._op_mode_device:
            return HA_OPMODES_HVAC[HVACMode.AUTO]

        device = self._op_mode_device.fibaro_device

        if device.has_operating_mode:
            return device.operating_mode
        if device.has_thermostat_mode:
            return device.thermostat_mode
        return device.mode

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool, idle."""
        fibaro_operation_mode = self.fibaro_op_mode
        if isinstance(fibaro_operation_mode, str):
            with suppress(ValueError):
                return HVACMode(fibaro_operation_mode.lower())
        elif fibaro_operation_mode in OPMODES_HVAC:
            return OPMODES_HVAC[fibaro_operation_mode]
        return None

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        if not self._op_mode_device:
            return
        if self.preset_mode:
            return

        if "setOperatingMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action("setOperatingMode", HA_OPMODES_HVAC[hvac_mode])
        elif "setThermostatMode" in self._op_mode_device.fibaro_device.actions:
            device = self._op_mode_device.fibaro_device
            if device.has_supported_thermostat_modes:
                for mode in device.supported_thermostat_modes:
                    if mode.lower() == hvac_mode:
                        self._op_mode_device.action("setThermostatMode", mode)
                        break
        elif "setMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action("setMode", HA_OPMODES_HVAC[hvac_mode])

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        if not self._op_mode_device:
            return None

        device = self._op_mode_device.fibaro_device
        if device.has_thermostat_operating_state:
            with suppress(ValueError):
                return HVACAction(device.thermostat_operating_state.lower())

        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        if not self._op_mode_device:
            return None

        if self._op_mode_device.fibaro_device.has_thermostat_mode:
            mode = self._op_mode_device.fibaro_device.thermostat_mode
            if self.preset_modes is not None and mode in self.preset_modes:
                return mode
            return None
        if self._op_mode_device.fibaro_device.has_operating_mode:
            mode = self._op_mode_device.fibaro_device.operating_mode
        else:
            mode = self._op_mode_device.fibaro_device.mode

        if mode not in OPMODES_PRESET:
            return None
        return OPMODES_PRESET[mode]

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self._op_mode_device is None:
            return

        if "setThermostatMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action("setThermostatMode", preset_mode)
        elif "setOperatingMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action(
                "setOperatingMode", HA_OPMODES_PRESET[preset_mode]
            )
        elif "setMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action("setMode", HA_OPMODES_PRESET[preset_mode])

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self._temp_sensor_device:
            device = self._temp_sensor_device.fibaro_device
            if device.has_heating_thermostat_setpoint:
                return device.heating_thermostat_setpoint
            return device.value.float_value()
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self._target_temp_device:
            device = self._target_temp_device.fibaro_device
            if device.has_heating_thermostat_setpoint_future:
                return device.heating_thermostat_setpoint_future
            return device.target_level
        return None

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        target = self._target_temp_device
        if target is not None and temperature is not None:
            if "setThermostatSetpoint" in target.fibaro_device.actions:
                target.action("setThermostatSetpoint", self.fibaro_op_mode, temperature)
            elif "setHeatingThermostatSetpoint" in target.fibaro_device.actions:
                target.action("setHeatingThermostatSetpoint", temperature)
            else:
                target.action("setTargetLevel", temperature)
