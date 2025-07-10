"""The Aprilaire climate component."""

from __future__ import annotations

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
from homeassistant.const import PRECISION_HALVES, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    FAN_CIRCULATE,
    PRESET_PERMANENT_HOLD,
    PRESET_TEMPORARY_HOLD,
    PRESET_VACATION,
)
from .coordinator import AprilaireConfigEntry
from .entity import BaseAprilaireEntity

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AprilaireConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add climates for passed config_entry in HA."""

    async_add_entities(
        [AprilaireClimate(config_entry.runtime_data, config_entry.unique_id)]
    )


class AprilaireClimate(BaseAprilaireEntity, ClimateEntity):
    """Climate entity for Aprilaire."""

    _attr_fan_modes = [FAN_AUTO, FAN_ON, FAN_CIRCULATE]
    _attr_min_humidity = 10
    _attr_max_humidity = 50
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "thermostat"

    @property
    def precision(self) -> float:
        """Get the precision based on the unit."""
        return (
            PRECISION_HALVES
            if self.hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS
            else PRECISION_WHOLE
        )

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Get supported features."""
        features = 0

        if self.coordinator.data.get(Attribute.MODE) == 5:
            features = features | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        else:
            features = features | ClimateEntityFeature.TARGET_TEMPERATURE

        if self.coordinator.data.get(Attribute.HUMIDIFICATION_AVAILABLE) == 2:
            features = features | ClimateEntityFeature.TARGET_HUMIDITY

        features = features | ClimateEntityFeature.PRESET_MODE

        return features | ClimateEntityFeature.FAN_MODE

    @property
    def current_humidity(self) -> int | None:
        """Get current humidity."""
        return self.coordinator.data.get(
            Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_VALUE
        )

    @property
    def target_humidity(self) -> int | None:
        """Get current target humidity."""
        return self.coordinator.data.get(Attribute.HUMIDIFICATION_SETPOINT)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Get HVAC mode."""

        if mode := self.coordinator.data.get(Attribute.MODE):
            if hvac_mode := HVAC_MODE_MAP.get(mode):
                return hvac_mode

        return None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Get supported HVAC modes."""

        if modes := self.coordinator.data.get(Attribute.THERMOSTAT_MODES):
            if thermostat_modes := HVAC_MODES_MAP.get(modes):
                return thermostat_modes

        return []

    @property
    def hvac_action(self) -> HVACAction | None:
        """Get the current HVAC action."""

        if self.coordinator.data.get(Attribute.HEATING_EQUIPMENT_STATUS, 0):
            return HVACAction.HEATING

        if self.coordinator.data.get(Attribute.COOLING_EQUIPMENT_STATUS, 0):
            return HVACAction.COOLING

        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Get current temperature."""
        return self.coordinator.data.get(
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
            0.5
            if self.hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS
            else 1
        )

    @property
    def target_temperature_high(self) -> float | None:
        """Get cool setpoint."""
        return self.coordinator.data.get(Attribute.COOL_SETPOINT)

    @property
    def target_temperature_low(self) -> float | None:
        """Get heat setpoint."""
        return self.coordinator.data.get(Attribute.HEAT_SETPOINT)

    @property
    def preset_mode(self) -> str | None:
        """Get the current preset mode."""
        if hold := self.coordinator.data.get(Attribute.HOLD):
            if preset_mode := PRESET_MODE_MAP.get(hold):
                return preset_mode

        return PRESET_NONE

    @property
    def preset_modes(self) -> list[str] | None:
        """Get the supported preset modes."""
        presets = [PRESET_NONE, PRESET_VACATION]

        if self.coordinator.data.get(Attribute.AWAY_AVAILABLE) == 1:
            presets.append(PRESET_AWAY)

        hold = self.coordinator.data.get(Attribute.HOLD, 0)

        if hold == 1:
            presets.append(PRESET_TEMPORARY_HOLD)
        elif hold == 2:
            presets.append(PRESET_PERMANENT_HOLD)

        return presets

    @property
    def fan_mode(self) -> str | None:
        """Get fan mode."""

        if mode := self.coordinator.data.get(Attribute.FAN_MODE):
            if fan_mode := FAN_MODE_MAP.get(mode):
                return fan_mode

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""

        cool_setpoint = 0
        heat_setpoint = 0

        if temperature := kwargs.get("temperature"):
            if self.coordinator.data.get(Attribute.MODE) == 3:
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

        await self.coordinator.client.update_setpoint(cool_setpoint, heat_setpoint)

        await self.coordinator.client.read_control()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidification setpoint."""

        await self.coordinator.client.set_humidification_setpoint(humidity)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""

        try:
            fan_mode_value_index = list(FAN_MODE_MAP.values()).index(fan_mode)
        except ValueError as exc:
            raise ValueError(f"Unsupported fan mode {fan_mode}") from exc

        fan_mode_value = list(FAN_MODE_MAP.keys())[fan_mode_value_index]

        await self.coordinator.client.update_fan_mode(fan_mode_value)

        await self.coordinator.client.read_control()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""

        try:
            mode_value_index = list(HVAC_MODE_MAP.values()).index(hvac_mode)
        except ValueError as exc:
            raise ValueError(f"Unsupported HVAC mode {hvac_mode}") from exc

        mode_value = list(HVAC_MODE_MAP.keys())[mode_value_index]

        await self.coordinator.client.update_mode(mode_value)

        await self.coordinator.client.read_control()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""

        if preset_mode == PRESET_AWAY:
            await self.coordinator.client.set_hold(3)
        elif preset_mode == PRESET_VACATION:
            await self.coordinator.client.set_hold(4)
        elif preset_mode == PRESET_NONE:
            await self.coordinator.client.set_hold(0)
        else:
            raise ValueError(f"Unsupported preset mode {preset_mode}")

        await self.coordinator.client.read_scheduling()
