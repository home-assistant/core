"""The Aprilaire climate component."""

from __future__ import annotations

from collections.abc import Mapping
from enum import IntFlag
from typing import Any

from pyaprilaire.const import Attribute

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_ON,
    PRESET_AWAY,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_HALVES, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AprilaireCoordinator
from .entity import BaseAprilaireEntity

FAN_CIRCULATE = "Circulate"

PRESET_TEMPORARY_HOLD = "Temporary"
PRESET_PERMANENT_HOLD = "Permanent"
PRESET_VACATION = "Vacation"

HVAC_MODE_MAP = {
    1: HVACMode.OFF,
    2: HVACMode.HEAT,
    3: HVACMode.COOL,
    4: HVACMode.HEAT,
    5: HVACMode.AUTO,
}

HVAC_MODES_MAP = {
    1: [HVACMode.OFF, HVACMode.HEAT],
    2: [HVACMode.OFF, HVACMode.COOL],
    3: [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL],
    4: [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL],
    5: [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO],
    6: [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO],
}

PRESET_MODE_MAP = {
    1: PRESET_TEMPORARY_HOLD,
    2: PRESET_PERMANENT_HOLD,
    3: PRESET_AWAY,
    4: PRESET_VACATION,
}

FAN_MODE_MAP = {
    1: FAN_ON,
    2: FAN_AUTO,
    3: FAN_CIRCULATE,
}


class ExtendedClimateEntityFeature(IntFlag):
    """Supported features of the Aprilaire climate entity."""

    TARGET_DEHUMIDITY = 2 << 10
    FRESH_AIR = 2 << 11
    AIR_CLEANING = 2 << 12


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add climates for passed config_entry in HA."""

    coordinator: AprilaireCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([AprilaireClimate(coordinator)])


class AprilaireClimate(BaseAprilaireEntity, ClimateEntity):
    """Climate entity for Aprilaire."""

    _attr_fan_modes = [FAN_AUTO, FAN_ON, FAN_CIRCULATE]
    _attr_min_humidity = 10
    _attr_max_humidity = 50
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    @property
    def precision(self) -> float:
        """Get the precision based on the unit."""
        return (
            PRECISION_HALVES
            if self.hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS
            else PRECISION_WHOLE
        )

    @property
    def name(self) -> str | None:
        """Get name of entity."""
        return "Thermostat"

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Get supported features."""
        features = 0

        if Attribute.MODE not in self._coordinator.data:
            features = features | ClimateEntityFeature.TARGET_TEMPERATURE
        else:
            if self._coordinator.data.get(Attribute.MODE) == 5:
                features = features | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            else:
                features = features | ClimateEntityFeature.TARGET_TEMPERATURE

        if self._coordinator.data.get(Attribute.HUMIDIFICATION_AVAILABLE) == 2:
            features = features | ClimateEntityFeature.TARGET_HUMIDITY

        if self._coordinator.data.get(Attribute.DEHUMIDIFICATION_AVAILABLE) == 1:
            features = features | ExtendedClimateEntityFeature.TARGET_DEHUMIDITY

        if self._coordinator.data.get(Attribute.AIR_CLEANING_AVAILABLE) == 1:
            features = features | ExtendedClimateEntityFeature.AIR_CLEANING

        if self._coordinator.data.get(Attribute.VENTILATION_AVAILABLE) == 1:
            features = features | ExtendedClimateEntityFeature.FRESH_AIR

        features = features | ClimateEntityFeature.PRESET_MODE

        features = features | ClimateEntityFeature.FAN_MODE

        return features

    @property
    def current_humidity(self) -> int | None:
        """Get current humidity."""
        return self._coordinator.data.get(
            Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_VALUE
        )

    @property
    def target_humidity(self) -> int | None:
        """Get current target humidity."""
        return self._coordinator.data.get(Attribute.HUMIDIFICATION_SETPOINT)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Get HVAC mode."""

        if mode := self._coordinator.data.get(Attribute.MODE):
            if hvac_mode := HVAC_MODE_MAP.get(mode):
                return hvac_mode

        return None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Get supported HVAC modes."""

        if modes := self._coordinator.data.get(Attribute.THERMOSTAT_MODES):
            if thermostat_modes := HVAC_MODES_MAP.get(modes):
                return thermostat_modes

        return []

    @property
    def hvac_action(self) -> HVACAction | None:
        """Get the current HVAC action."""

        heating_equipment_status = self._coordinator.data.get(
            Attribute.HEATING_EQUIPMENT_STATUS, 0
        )

        if heating_equipment_status > 0:
            return HVACAction.HEATING

        cooling_equipment_status = self._coordinator.data.get(
            Attribute.COOLING_EQUIPMENT_STATUS, 0
        )

        if cooling_equipment_status > 0:
            return HVACAction.COOLING

        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Get current temperature."""
        return self._coordinator.data.get(
            Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_VALUE
        )

    @property
    def target_temperature(self) -> float | None:
        """Get the target temperature."""

        hvac_mode = self.hvac_mode

        if hvac_mode == HVACMode.COOL:
            return self.target_temperature_high
        if hvac_mode == HVACMode.HEAT:
            return self.target_temperature_low

        return None

    @property
    def target_temperature_step(self) -> float | None:
        """Get the step for the target temperature based on the unit."""
        return (
            PRECISION_HALVES
            if self.hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS
            else PRECISION_WHOLE
        )

    @property
    def target_temperature_high(self) -> float | None:
        """Get cool setpoint."""
        return self._coordinator.data.get(Attribute.COOL_SETPOINT)

    @property
    def target_temperature_low(self) -> float | None:
        """Get heat setpoint."""
        return self._coordinator.data.get(Attribute.HEAT_SETPOINT)

    @property
    def preset_mode(self) -> str | None:
        """Get the current preset mode."""
        if hold := self._coordinator.data.get(Attribute.HOLD):
            if preset_mode := PRESET_MODE_MAP.get(hold):
                return preset_mode

        return PRESET_NONE

    @property
    def preset_modes(self) -> list[str] | None:
        """Get the supported preset modes."""
        presets = [PRESET_NONE, PRESET_VACATION]

        if self._coordinator.data.get(Attribute.AWAY_AVAILABLE) == 1:
            presets.append(PRESET_AWAY)

        hold = self._coordinator.data.get(Attribute.HOLD, 0)

        if hold == 1:
            presets.append(PRESET_TEMPORARY_HOLD)
        elif hold == 2:
            presets.append(PRESET_PERMANENT_HOLD)

        return presets

    @property
    def fan_mode(self) -> str | None:
        """Get fan mode."""

        if mode := self._coordinator.data.get(Attribute.FAN_MODE):
            if fan_mode := FAN_MODE_MAP.get(mode):
                return fan_mode

        return None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return device specific state attributes."""
        return {
            "fan_status": "on"
            if self._coordinator.data.get(Attribute.FAN_STATUS, 0) == 1
            else "off",
            "humidification_setpoint": self._coordinator.data.get(
                Attribute.HUMIDIFICATION_SETPOINT
            ),
            "dehumidification_setpoint": self._coordinator.data.get(
                Attribute.DEHUMIDIFICATION_SETPOINT
            ),
            "air_cleaning_mode": {1: "constant", 2: "automatic"}.get(
                self._coordinator.data.get(Attribute.AIR_CLEANING_MODE, 0), "off"
            ),
            "air_cleaning_event": {3: "3hour", 4: "24hour"}.get(
                self._coordinator.data.get(Attribute.AIR_CLEANING_EVENT, 0), "off"
            ),
            "fresh_air_mode": {1: "automatic"}.get(
                self._coordinator.data.get(Attribute.FRESH_AIR_MODE, 0), "off"
            ),
            "fresh_air_event": {2: "3hour", 3: "24hour"}.get(
                self._coordinator.data.get(Attribute.FRESH_AIR_EVENT, 0), "off"
            ),
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""

        cool_setpoint = 0
        heat_setpoint = 0

        if temperature := kwargs.get("temperature"):
            if self._coordinator.data.get(Attribute.MODE) == 3:
                cool_setpoint = temperature
            else:
                heat_setpoint = temperature
        else:
            if target_temp_low := kwargs.get("target_temp_low"):
                heat_setpoint = target_temp_low
            if target_temp_high := kwargs.get("target_temp_high"):
                cool_setpoint = target_temp_high

        if cool_setpoint == 0 and heat_setpoint == 0:
            return

        await self._coordinator.client.update_setpoint(cool_setpoint, heat_setpoint)

        await self._coordinator.client.read_control()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidification setpoint."""

        await self._coordinator.client.set_humidification_setpoint(humidity)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""

        try:
            fan_mode_value_index = list(FAN_MODE_MAP.values()).index(fan_mode)
        except ValueError as exc:
            raise ValueError(f"Unsupported fan mode {fan_mode}") from exc

        fan_mode_value = list(FAN_MODE_MAP.keys())[fan_mode_value_index]

        await self._coordinator.client.update_fan_mode(fan_mode_value)

        await self._coordinator.client.read_control()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""

        try:
            mode_value_index = list(HVAC_MODE_MAP.values()).index(hvac_mode)
        except ValueError as exc:
            raise ValueError(f"Unsupported HVAC mode {hvac_mode}") from exc

        mode_value = list(HVAC_MODE_MAP.keys())[mode_value_index]

        await self._coordinator.client.update_mode(mode_value)

        await self._coordinator.client.read_control()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""

        if preset_mode == PRESET_AWAY:
            await self._coordinator.client.set_hold(3)
        elif preset_mode == PRESET_VACATION:
            await self._coordinator.client.set_hold(4)
        elif preset_mode == PRESET_NONE:
            await self._coordinator.client.set_hold(0)
        else:
            raise ValueError(f"Unsupported preset mode {preset_mode}")

        await self._coordinator.client.read_scheduling()
