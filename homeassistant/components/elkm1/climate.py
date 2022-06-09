"""Support for control of Elk-M1 connected thermostats."""
from __future__ import annotations

from typing import Any

from elkm1_lib.const import ThermostatFan, ThermostatMode, ThermostatSetting
from elkm1_lib.elements import Element
from elkm1_lib.elk import Elk
from elkm1_lib.thermostats import Thermostat

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_ON,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_WHOLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElkEntity, create_elk_entities
from .const import DOMAIN

SUPPORT_HVAC = [
    HVACMode.OFF,
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.HEAT_COOL,
    HVACMode.FAN_ONLY,
]
HASS_TO_ELK_HVAC_MODES = {
    HVACMode.OFF: (ThermostatMode.OFF, ThermostatFan.AUTO),
    HVACMode.HEAT: (ThermostatMode.HEAT, None),
    HVACMode.COOL: (ThermostatMode.COOL, None),
    HVACMode.HEAT_COOL: (ThermostatMode.AUTO, None),
    HVACMode.FAN_ONLY: (ThermostatMode.OFF, ThermostatFan.ON),
}
ELK_TO_HASS_HVAC_MODES = {
    ThermostatMode.OFF: HVACMode.OFF,
    ThermostatMode.COOL: HVACMode.COOL,
    ThermostatMode.HEAT: HVACMode.HEAT,
    ThermostatMode.EMERGENCY_HEAT: HVACMode.HEAT,
    ThermostatMode.AUTO: HVACMode.HEAT_COOL,
}
HASS_TO_ELK_FAN_MODES = {
    FAN_AUTO: (None, ThermostatFan.AUTO),
    FAN_ON: (None, ThermostatFan.ON),
}
ELK_TO_HASS_FAN_MODES = {
    ThermostatFan.AUTO: FAN_AUTO,
    ThermostatFan.ON: FAN_ON,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the Elk-M1 thermostat platform."""
    elk_data = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[ElkEntity] = []
    elk = elk_data["elk"]
    create_elk_entities(
        elk_data, elk.thermostats, "thermostat", ElkThermostat, entities
    )
    async_add_entities(entities, True)


class ElkThermostat(ElkEntity, ClimateEntity):
    """Representation of an Elk-M1 Thermostat."""

    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.AUX_HEAT
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    _element: Thermostat

    def __init__(self, element: Element, elk: Elk, elk_data: dict[str, Any]) -> None:
        """Initialize climate entity."""
        super().__init__(element, elk, elk_data)
        self._state: str | None = None

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit."""
        return self._temperature_unit

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._element.current_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we are trying to reach."""
        if self._element.mode in (
            ThermostatMode.HEAT,
            ThermostatMode.EMERGENCY_HEAT,
        ):
            return self._element.heat_setpoint
        if self._element.mode == ThermostatMode.COOL:
            return self._element.cool_setpoint
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the high target temperature."""
        return self._element.cool_setpoint

    @property
    def target_temperature_low(self) -> float | None:
        """Return the low target temperature."""
        return self._element.heat_setpoint

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._element.humidity

    @property
    def hvac_mode(self) -> str | None:
        """Return current operation ie. heat, cool, idle."""
        return self._state

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available operation modes."""
        return SUPPORT_HVAC

    @property
    def precision(self) -> int:
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def is_aux_heat(self) -> bool:
        """Return if aux heater is on."""
        return self._element.mode == ThermostatMode.EMERGENCY_HEAT

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature supported."""
        return 1

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature supported."""
        return 99

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if self._element.fan is None:
            return None
        return ELK_TO_HASS_FAN_MODES[self._element.fan]

    def _elk_set(self, mode: ThermostatMode | None, fan: ThermostatFan | None) -> None:
        if mode is not None:
            self._element.set(ThermostatSetting.MODE, mode)
        if fan is not None:
            self._element.set(ThermostatSetting.FAN, fan)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set thermostat operation mode."""
        thermostat_mode, fan_mode = HASS_TO_ELK_HVAC_MODES[hvac_mode]
        self._elk_set(thermostat_mode, fan_mode)

    async def async_turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        self._elk_set(ThermostatMode.EMERGENCY_HEAT, None)

    async def async_turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        self._elk_set(ThermostatMode.HEAT, None)

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return [FAN_AUTO, FAN_ON]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        thermostat_mode, elk_fan_mode = HASS_TO_ELK_FAN_MODES[fan_mode]
        self._elk_set(thermostat_mode, elk_fan_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if low_temp is not None:
            self._element.set(ThermostatSetting.HEAT_SETPOINT, round(low_temp))
        if high_temp is not None:
            self._element.set(ThermostatSetting.COOL_SETPOINT, round(high_temp))

    def _element_changed(self, element: Element, changeset: Any) -> None:
        if self._element.mode is None:
            self._state = None
        else:
            self._state = ELK_TO_HASS_HVAC_MODES[self._element.mode]
            if self._state == HVACMode.OFF and self._element.fan == ThermostatFan.ON:
                self._state = HVACMode.FAN_ONLY
