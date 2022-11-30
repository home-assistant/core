"""Support for Honeywell (US) Total Connect Comfort climate systems."""
from __future__ import annotations

import datetime
from typing import Any

import somecomfort

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_ON,
    PRESET_AWAY,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    _LOGGER,
    CONF_COOL_AWAY_TEMPERATURE,
    CONF_HEAT_AWAY_TEMPERATURE,
    DOMAIN,
)

ATTR_FAN_ACTION = "fan_action"

ATTR_PERMANENT_HOLD = "permanent_hold"

PRESET_HOLD = "Hold"

HVAC_MODE_TO_HW_MODE = {
    "SwitchOffAllowed": {HVACMode.OFF: "off"},
    "SwitchAutoAllowed": {HVACMode.HEAT_COOL: "auto"},
    "SwitchCoolAllowed": {HVACMode.COOL: "cool"},
    "SwitchHeatAllowed": {HVACMode.HEAT: "heat"},
}
HW_MODE_TO_HVAC_MODE = {
    "off": HVACMode.OFF,
    "emheat": HVACMode.HEAT,
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "auto": HVACMode.HEAT_COOL,
}
HW_MODE_TO_HA_HVAC_ACTION = {
    "off": HVACAction.IDLE,
    "fan": HVACAction.FAN,
    "heat": HVACAction.HEATING,
    "cool": HVACAction.COOLING,
}
FAN_MODE_TO_HW = {
    "fanModeOnAllowed": {FAN_ON: "on"},
    "fanModeAutoAllowed": {FAN_AUTO: "auto"},
    "fanModeCirculateAllowed": {FAN_DIFFUSE: "circulate"},
}
HW_FAN_MODE_TO_HA = {
    "on": FAN_ON,
    "auto": FAN_AUTO,
    "circulate": FAN_DIFFUSE,
    "follow schedule": FAN_AUTO,
}

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Honeywell thermostat."""
    cool_away_temp = entry.options.get(CONF_COOL_AWAY_TEMPERATURE)
    heat_away_temp = entry.options.get(CONF_HEAT_AWAY_TEMPERATURE)

    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            HoneywellUSThermostat(data, device, cool_away_temp, heat_away_temp)
            for device in data.devices.values()
        ]
    )


class HoneywellUSThermostat(ClimateEntity):
    """Representation of a Honeywell US Thermostat."""

    def __init__(self, data, device, cool_away_temp, heat_away_temp):
        """Initialize the thermostat."""
        self._data = data
        self._device = device
        self._cool_away_temp = cool_away_temp
        self._heat_away_temp = heat_away_temp
        self._away = False

        self._attr_unique_id = device.deviceid
        self._attr_name = device.name
        self._attr_temperature_unit = (
            TEMP_CELSIUS if device.temperature_unit == "C" else TEMP_FAHRENHEIT
        )
        self._attr_preset_modes = [PRESET_NONE, PRESET_AWAY, PRESET_HOLD]
        self._attr_is_aux_heat = device.system_mode == "emheat"

        # not all honeywell HVACs support all modes
        mappings = [v for k, v in HVAC_MODE_TO_HW_MODE.items() if device.raw_ui_data[k]]
        self._hvac_mode_map = {k: v for d in mappings for k, v in d.items()}
        self._attr_hvac_modes = list(self._hvac_mode_map)

        self._attr_supported_features = (
            ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        )

        if device._data["canControlHumidification"]:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY

        if device.raw_ui_data["SwitchEmergencyHeatAllowed"]:
            self._attr_supported_features |= ClimateEntityFeature.AUX_HEAT

        if not device._data["hasFan"]:
            return

        # not all honeywell fans support all modes
        mappings = [v for k, v in FAN_MODE_TO_HW.items() if device.raw_fan_data[k]]
        self._fan_mode_map = {k: v for d in mappings for k, v in d.items()}

        self._attr_fan_modes = list(self._fan_mode_map)

        self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device specific state attributes."""
        data: dict[str, Any] = {}
        data[ATTR_FAN_ACTION] = "running" if self._device.fan_running else "idle"
        data[ATTR_PERMANENT_HOLD] = self._is_permanent_hold()
        if self._device.raw_dr_data:
            data["dr_phase"] = self._device.raw_dr_data.get("Phase")
        return data

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self.hvac_mode in [HVACMode.COOL, HVACMode.HEAT_COOL]:
            return self._device.raw_ui_data["CoolLowerSetptLimit"]
        if self.hvac_mode == HVACMode.HEAT:
            return self._device.raw_ui_data["HeatLowerSetptLimit"]
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self.hvac_mode == HVACMode.COOL:
            return self._device.raw_ui_data["CoolUpperSetptLimit"]
        if self.hvac_mode in [HVACMode.HEAT, HVACMode.HEAT_COOL]:
            return self._device.raw_ui_data["HeatUpperSetptLimit"]
        return DEFAULT_MAX_TEMP

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._device.current_humidity

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        return HW_MODE_TO_HVAC_MODE[self._device.system_mode]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        if self.hvac_mode == HVACMode.OFF:
            return None
        return HW_MODE_TO_HA_HVAC_ACTION[self._device.equipment_output_status]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVACMode.COOL:
            return self._device.setpoint_cool
        if self.hvac_mode == HVACMode.HEAT:
            return self._device.setpoint_heat
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self._device.setpoint_cool
        return None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self._device.setpoint_heat
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._away:
            return PRESET_AWAY
        if self._is_permanent_hold():
            return PRESET_HOLD

        return None

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return HW_FAN_MODE_TO_HA[self._device.fan_mode]

    def _is_permanent_hold(self) -> bool:
        heat_status = self._device.raw_ui_data.get("StatusHeat", 0)
        cool_status = self._device.raw_ui_data.get("StatusCool", 0)
        return heat_status == 2 or cool_status == 2

    def _set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        try:
            # Get current mode
            mode = self._device.system_mode
            # Set hold if this is not the case
            if getattr(self._device, f"hold_{mode}", None) is False:
                # Get next period key
                next_period_key = f"{mode.capitalize()}NextPeriod"
                # Get next period raw value
                next_period = self._device.raw_ui_data.get(next_period_key)
                # Get next period time
                hour, minute = divmod(next_period * 15, 60)
                # Set hold time
                setattr(self._device, f"hold_{mode}", datetime.time(hour, minute))
            # Set temperature
            setattr(self._device, f"setpoint_{mode}", temperature)
        except somecomfort.SomeComfortError:
            _LOGGER.error("Temperature %.1f out of range", temperature)

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if {HVACMode.COOL, HVACMode.HEAT} & set(self._hvac_mode_map):
            self._set_temperature(**kwargs)

        try:
            if HVACMode.HEAT_COOL in self._hvac_mode_map:
                if temperature := kwargs.get(ATTR_TARGET_TEMP_HIGH):
                    self._device.setpoint_cool = temperature
                if temperature := kwargs.get(ATTR_TARGET_TEMP_LOW):
                    self._device.setpoint_heat = temperature
        except somecomfort.SomeComfortError as err:
            _LOGGER.error("Invalid temperature %s: %s", temperature, err)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        self._device.fan_mode = self._fan_mode_map[fan_mode]

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._device.system_mode = self._hvac_mode_map[hvac_mode]

    def _turn_away_mode_on(self) -> None:
        """Turn away on.

        Somecomfort does have a proprietary away mode, but it doesn't really
        work the way it should. For example: If you set a temperature manually
        it doesn't get overwritten when away mode is switched on.
        """
        self._away = True
        try:
            # Get current mode
            mode = self._device.system_mode
        except somecomfort.SomeComfortError:
            _LOGGER.error("Can not get system mode")
            return
        try:

            # Set permanent hold
            setattr(self._device, f"hold_{mode}", True)
            # Set temperature
            setattr(
                self._device,
                f"setpoint_{mode}",
                getattr(self, f"_{mode}_away_temp"),
            )
        except somecomfort.SomeComfortError:
            _LOGGER.error(
                "Temperature %.1f out of range", getattr(self, f"_{mode}_away_temp")
            )

    def _turn_hold_mode_on(self) -> None:
        """Turn permanent hold on."""
        try:
            # Get current mode
            mode = self._device.system_mode
        except somecomfort.SomeComfortError:
            _LOGGER.error("Can not get system mode")
            return
        # Check that we got a valid mode back
        if mode in HW_MODE_TO_HVAC_MODE:
            try:
                # Set permanent hold
                setattr(self._device, f"hold_{mode}", True)
            except somecomfort.SomeComfortError:
                _LOGGER.error("Couldn't set permanent hold")
        else:
            _LOGGER.error("Invalid system mode returned: %s", mode)

    def _turn_away_mode_off(self) -> None:
        """Turn away/hold off."""
        self._away = False
        try:
            # Disabling all hold modes
            self._device.hold_cool = False
            self._device.hold_heat = False
        except somecomfort.SomeComfortError:
            _LOGGER.error("Can not stop hold mode")

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_AWAY:
            self._turn_away_mode_on()
        elif preset_mode == PRESET_HOLD:
            self._away = False
            self._turn_hold_mode_on()
        else:
            self._turn_away_mode_off()

    def turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        self._device.system_mode = "emheat"

    def turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        if HVACMode.HEAT in self.hvac_modes:
            self.set_hvac_mode(HVACMode.HEAT)
        else:
            self.set_hvac_mode(HVACMode.OFF)

    async def async_update(self) -> None:
        """Get the latest state from the service."""
        await self._data.async_update()
