"""Climate on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/zha.climate/
"""

from __future__ import annotations

from collections.abc import Mapping
import functools
from typing import Any

from zha.application.platforms.climate.const import (
    ClimateEntityFeature as ZHAClimateEntityFeature,
    HVACAction as ZHAHVACAction,
    HVACMode as ZHAHVACMode,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_TENTHS, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
    async_add_entities as zha_async_add_entities,
    convert_zha_error_to_ha_error,
    exclude_none_values,
    get_zha_data,
)

ZHA_TO_HA_HVAC_MODE = {
    ZHAHVACMode.OFF: HVACMode.OFF,
    ZHAHVACMode.AUTO: HVACMode.AUTO,
    ZHAHVACMode.HEAT: HVACMode.HEAT,
    ZHAHVACMode.COOL: HVACMode.COOL,
    ZHAHVACMode.HEAT_COOL: HVACMode.HEAT_COOL,
    ZHAHVACMode.DRY: HVACMode.DRY,
    ZHAHVACMode.FAN_ONLY: HVACMode.FAN_ONLY,
}

ZHA_TO_HA_HVAC_ACTION = {
    ZHAHVACAction.OFF: HVACAction.OFF,
    ZHAHVACAction.HEATING: HVACAction.HEATING,
    ZHAHVACAction.COOLING: HVACAction.COOLING,
    ZHAHVACAction.DRYING: HVACAction.DRYING,
    ZHAHVACAction.IDLE: HVACAction.IDLE,
    ZHAHVACAction.FAN: HVACAction.FAN,
    ZHAHVACAction.PREHEATING: HVACAction.PREHEATING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation sensor from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.CLIMATE]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, Thermostat, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class Thermostat(ZHAEntity, ClimateEntity):
    """Representation of a ZHA Thermostat device."""

    _attr_precision = PRECISION_TENTHS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key: str = "thermostat"
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, entity_data: EntityData, **kwargs: Any) -> None:
        """Initialize the ZHA thermostat entity."""
        super().__init__(entity_data, **kwargs)
        self._attr_hvac_modes = [
            ZHA_TO_HA_HVAC_MODE[mode] for mode in self.entity_data.entity.hvac_modes
        ]
        self._attr_hvac_mode = ZHA_TO_HA_HVAC_MODE.get(
            self.entity_data.entity.hvac_mode
        )
        self._attr_hvac_action = ZHA_TO_HA_HVAC_ACTION.get(
            self.entity_data.entity.hvac_action
        )

        features: ClimateEntityFeature = ClimateEntityFeature(0)
        zha_features: ZHAClimateEntityFeature = (
            self.entity_data.entity.supported_features
        )

        if ZHAClimateEntityFeature.TARGET_TEMPERATURE in zha_features:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if ZHAClimateEntityFeature.TARGET_TEMPERATURE_RANGE in zha_features:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        if ZHAClimateEntityFeature.TARGET_HUMIDITY in zha_features:
            features |= ClimateEntityFeature.TARGET_HUMIDITY
        if ZHAClimateEntityFeature.PRESET_MODE in zha_features:
            features |= ClimateEntityFeature.PRESET_MODE
        if ZHAClimateEntityFeature.FAN_MODE in zha_features:
            features |= ClimateEntityFeature.FAN_MODE
        if ZHAClimateEntityFeature.SWING_MODE in zha_features:
            features |= ClimateEntityFeature.SWING_MODE
        if ZHAClimateEntityFeature.TURN_OFF in zha_features:
            features |= ClimateEntityFeature.TURN_OFF
        if ZHAClimateEntityFeature.TURN_ON in zha_features:
            features |= ClimateEntityFeature.TURN_ON

        self._attr_supported_features = features

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        state = self.entity_data.entity.state

        return exclude_none_values(
            {
                "occupancy": state.get("occupancy"),
                "occupied_cooling_setpoint": state.get("occupied_cooling_setpoint"),
                "occupied_heating_setpoint": state.get("occupied_heating_setpoint"),
                "pi_cooling_demand": state.get("pi_cooling_demand"),
                "pi_heating_demand": state.get("pi_heating_demand"),
                "system_mode": state.get("system_mode"),
                "unoccupied_cooling_setpoint": state.get("unoccupied_cooling_setpoint"),
                "unoccupied_heating_setpoint": state.get("unoccupied_heating_setpoint"),
            }
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.entity_data.entity.current_temperature

    @property
    def fan_mode(self) -> str | None:
        """Return current FAN mode."""
        return self.entity_data.entity.fan_mode

    @property
    def fan_modes(self) -> list[str] | None:
        """Return supported FAN modes."""
        return self.entity_data.entity.fan_modes

    @property
    def preset_mode(self) -> str:
        """Return current preset mode."""
        return self.entity_data.entity.preset_mode

    @property
    def preset_modes(self) -> list[str] | None:
        """Return supported preset modes."""
        return self.entity_data.entity.preset_modes

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.entity_data.entity.target_temperature

    @property
    def target_temperature_high(self) -> float | None:
        """Return the upper bound temperature we try to reach."""
        return self.entity_data.entity.target_temperature_high

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lower bound temperature we try to reach."""
        return self.entity_data.entity.target_temperature_low

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.entity_data.entity.max_temp

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.entity_data.entity.min_temp

    @callback
    def _handle_entity_events(self, event: Any) -> None:
        """Entity state changed."""
        self._attr_hvac_mode = self._attr_hvac_mode = ZHA_TO_HA_HVAC_MODE.get(
            self.entity_data.entity.hvac_mode
        )
        self._attr_hvac_action = ZHA_TO_HA_HVAC_ACTION.get(
            self.entity_data.entity.hvac_action
        )
        super()._handle_entity_events(event)

    @convert_zha_error_to_ha_error
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        await self.entity_data.entity.async_set_fan_mode(fan_mode=fan_mode)
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        await self.entity_data.entity.async_set_hvac_mode(hvac_mode=hvac_mode)
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.entity_data.entity.async_set_preset_mode(preset_mode=preset_mode)
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.entity_data.entity.async_set_temperature(
            target_temp_low=kwargs.get(ATTR_TARGET_TEMP_LOW),
            target_temp_high=kwargs.get(ATTR_TARGET_TEMP_HIGH),
            temperature=kwargs.get(ATTR_TEMPERATURE),
            hvac_mode=kwargs.get(ATTR_HVAC_MODE),
        )
        self.async_write_ha_state()
