"""Support for Fibaro thermostats."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import ENTITY_ID_FORMAT, ClimateEntity
from homeassistant.components.climate.const import (
    PRESET_AWAY,
    PRESET_BOOST,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FIBARO_DEVICES, FibaroDevice
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
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Fibaro controller devices."""
    async_add_entities(
        [
            FibaroThermostat(device)
            for device in hass.data[DOMAIN][entry.entry_id][FIBARO_DEVICES][
                Platform.CLIMATE
            ]
        ],
        True,
    )


class FibaroThermostat(FibaroDevice, ClimateEntity):
    """Representation of a Fibaro Thermostat."""

    def __init__(self, fibaro_device):
        """Initialize the Fibaro device."""
        super().__init__(fibaro_device)
        self._temp_sensor_device: FibaroDevice | None = None
        self._target_temp_device: FibaroDevice | None = None
        self._op_mode_device: FibaroDevice | None = None
        self._fan_mode_device: FibaroDevice | None = None
        self._attr_supported_features = 0
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

        siblings = fibaro_device.fibaro_controller.get_siblings(fibaro_device)
        _LOGGER.debug("%s siblings: %s", fibaro_device.ha_id, siblings)
        tempunit = "C"
        for device in siblings:
            # Detecting temperature device, one strong and one weak way of
            # doing so, so we prefer the hard evidence, if there is such.
            if device.type == "com.fibaro.temperatureSensor":
                self._temp_sensor_device = FibaroDevice(device)
                tempunit = device.properties.unit
            elif (
                self._temp_sensor_device is None
                and "unit" in device.properties
                and (
                    "value" in device.properties
                    or "heatingThermostatSetpoint" in device.properties
                )
                and device.properties.unit in ("C", "F")
            ):
                self._temp_sensor_device = FibaroDevice(device)
                tempunit = device.properties.unit

            if (
                "setTargetLevel" in device.actions
                or "setThermostatSetpoint" in device.actions
                or "setHeatingThermostatSetpoint" in device.actions
            ):
                self._target_temp_device = FibaroDevice(device)
                self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
                tempunit = device.properties.unit

            if "setMode" in device.actions or "setOperatingMode" in device.actions:
                self._op_mode_device = FibaroDevice(device)
                self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

            if "setFanMode" in device.actions:
                self._fan_mode_device = FibaroDevice(device)
                self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        if tempunit == "F":
            self._attr_temperature_unit = TEMP_FAHRENHEIT
        else:
            self._attr_temperature_unit = TEMP_CELSIUS

        if self._fan_mode_device:
            fan_modes = (
                self._fan_mode_device.fibaro_device.properties.supportedModes.split(",")
            )
            self._attr_fan_modes = []
            for mode in fan_modes:
                mode = int(mode)
                if mode not in FANMODES:
                    _LOGGER.warning("%d unknown fan mode", mode)
                    continue
                self._attr_fan_modes.append(FANMODES[int(mode)])

        self._attr_hvac_modes = [HVACMode.AUTO]  # default
        if self._op_mode_device:
            self._attr_preset_modes = []
            self._attr_hvac_modes = []
            prop = self._op_mode_device.fibaro_device.properties
            if "supportedOperatingModes" in prop:
                op_modes = prop.supportedOperatingModes.split(",")
            elif "supportedModes" in prop:
                op_modes = prop.supportedModes.split(",")
            for mode in op_modes:
                mode = int(mode)
                if mode in OPMODES_HVAC:
                    mode_ha = OPMODES_HVAC[mode]
                    if mode_ha not in self._attr_hvac_modes:
                        self._attr_hvac_modes.append(mode_ha)
                if mode in OPMODES_PRESET:
                    self._attr_preset_modes.append(OPMODES_PRESET[mode])

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        _LOGGER.debug(
            "Climate %s\n"
            "- _temp_sensor_device %s\n"
            "- _target_temp_device %s\n"
            "- _op_mode_device %s\n"
            "- _fan_mode_device %s",
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
                self.controller.register(device.id, self._update_callback)

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if not self._fan_mode_device:
            return None
        mode = int(self._fan_mode_device.fibaro_device.properties.mode)
        return FANMODES[mode]

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if not self._fan_mode_device:
            return
        self._fan_mode_device.action("setFanMode", HA_FANMODES[fan_mode])

    @property
    def fibaro_op_mode(self) -> int:
        """Return the operating mode of the device."""
        if not self._op_mode_device:
            return 3  # Default to AUTO

        if "operatingMode" in self._op_mode_device.fibaro_device.properties:
            return int(self._op_mode_device.fibaro_device.properties.operatingMode)

        return int(self._op_mode_device.fibaro_device.properties.mode)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        return OPMODES_HVAC[self.fibaro_op_mode]

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        if not self._op_mode_device:
            return
        if self.preset_mode:
            return

        if "setOperatingMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action("setOperatingMode", HA_OPMODES_HVAC[hvac_mode])
        elif "setMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action("setMode", HA_OPMODES_HVAC[hvac_mode])

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        if not self._op_mode_device:
            return None

        if "operatingMode" in self._op_mode_device.fibaro_device.properties:
            mode = int(self._op_mode_device.fibaro_device.properties.operatingMode)
        else:
            mode = int(self._op_mode_device.fibaro_device.properties.mode)

        if mode not in OPMODES_PRESET:
            return None
        return OPMODES_PRESET[mode]

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self._op_mode_device is None:
            return
        if "setOperatingMode" in self._op_mode_device.fibaro_device.actions:
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
            if "heatingThermostatSetpoint" in device.properties:
                return float(device.properties.heatingThermostatSetpoint)
            return float(device.properties.value)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self._target_temp_device:
            device = self._target_temp_device.fibaro_device
            if "heatingThermostatSetpointFuture" in device.properties:
                return float(device.properties.heatingThermostatSetpointFuture)
            return float(device.properties.targetLevel)
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
