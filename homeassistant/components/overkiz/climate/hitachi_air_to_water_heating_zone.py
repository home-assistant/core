"""Support for HitachiAirToWaterHeatingZone."""

from typing import Any, cast, override

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from ..const import DOMAIN
from ..entity import OverkizDataUpdateCoordinator, OverkizEntity

OVERKIZ_TO_HVAC_MODE: dict[str, HVACMode] = {
    OverkizCommandParam.MANU: HVACMode.HEAT,
    OverkizCommandParam.AUTO: HVACMode.AUTO,
}

HVAC_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODE.items()}

OVERKIZ_TO_PRESET_MODE: dict[str, str] = {
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
    OverkizCommandParam.ECO: PRESET_ECO,
}

PRESET_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODE.items()}


class HitachiAirToWaterHeatingZone(OverkizEntity, ClimateEntity):
    """Representation of HitachiAirToWaterHeatingZone."""

    _attr_hvac_modes = [*HVAC_MODE_TO_OVERKIZ]
    _attr_preset_modes = [*PRESET_MODE_TO_OVERKIZ]
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )
    _attr_min_temp = 5.0
    _attr_max_temp = 35.0
    _attr_precision = 0.1
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN

    # A heat pump exposes each heating zone as its own device, carrying only
    # that zone's states and command. Zone 1 is the default; zone 2 overrides.
    _auto_manu_mode_state = OverkizState.MODBUS_AUTO_MANU_MODE_ZONE_1
    _room_temperature_state = OverkizState.MODBUS_ROOM_AMBIENT_TEMPERATURE_STATUS_ZONE_1
    _thermostat_setting_state = OverkizState.MODBUS_THERMOSTAT_SETTING_CONTROL_ZONE_1
    _set_thermostat_setting_command = (
        OverkizCommand.SET_THERMOSTAT_SETTING_CONTROL_ZONE_1
    )

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        if self._attr_device_info:
            self._attr_device_info["manufacturer"] = "Hitachi"

        if "Zone2" in self.device.controllable_name:
            self._auto_manu_mode_state = OverkizState.MODBUS_AUTO_MANU_MODE_ZONE2
            self._room_temperature_state = (
                OverkizState.MODBUS_ROOM_AMBIENT_TEMPERATURE_STATUS_ZONE2
            )
            self._thermostat_setting_state = (
                OverkizState.MODBUS_THERMOSTAT_SETTING_CONTROL_ZONE2
            )
            self._set_thermostat_setting_command = (
                OverkizCommand.SET_THERMOSTAT_SETTING_CONTROL_ZONE_2
            )

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if (
            state := self.device.states.get(self._auto_manu_mode_state)
        ) and state.value_as_str:
            return OVERKIZ_TO_HVAC_MODE[state.value_as_str]

        return HVACMode.OFF

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_AUTO_MANU_MODE, HVAC_MODE_TO_OVERKIZ[hvac_mode]
        )

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if (
            state := self.device.states.get(OverkizState.MODBUS_YUTAKI_TARGET_MODE)
        ) and state.value_as_str:
            return OVERKIZ_TO_PRESET_MODE[state.value_as_str]

        return PRESET_NONE

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_MODE, PRESET_MODE_TO_OVERKIZ[preset_mode]
        )

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        current_temperature = self.device.states.get(self._room_temperature_state)

        if current_temperature:
            return current_temperature.value_as_float

        return None

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        target_temperature = self.device.states.get(self._thermostat_setting_state)

        if target_temperature:
            return target_temperature.value_as_float

        return None

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = cast(float, kwargs.get(ATTR_TEMPERATURE))

        await self.executor.async_execute_command(
            self._set_thermostat_setting_command, float(temperature)
        )
