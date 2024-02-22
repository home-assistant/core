"""YoLink Thermostat."""
from __future__ import annotations

from typing import Any

from yolink.const import ATTR_DEVICE_THERMOSTAT
from yolink.thermostat_request_builder import ThermostatRequestBuilder, ThermostatState

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_ON,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity

YOLINK_MODEL_2_HA = {
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "auto": HVACMode.AUTO,
    "off": HVACMode.OFF,
}

HA_MODEL_2_YOLINK = {v: k for k, v in YOLINK_MODEL_2_HA.items()}

YOLINK_ACTION_2_HA = {
    "cool": HVACAction.COOLING,
    "heat": HVACAction.HEATING,
    "idle": HVACAction.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink Thermostat from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id].device_coordinators
    entities = [
        YoLinkClimateEntity(config_entry, device_coordinator)
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type == ATTR_DEVICE_THERMOSTAT
    ]
    async_add_entities(entities)


class YoLinkClimateEntity(YoLinkEntity, ClimateEntity):
    """YoLink Climate Entity."""

    _attr_name = None
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
    ) -> None:
        """Init YoLink Thermostat."""
        super().__init__(config_entry, coordinator)
        self._attr_unique_id = f"{coordinator.device.device_id}_climate"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_fan_modes = [FAN_ON, FAN_AUTO]
        self._attr_min_temp = -10
        self._attr_max_temp = 50
        self._attr_hvac_modes = [
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.AUTO,
            HVACMode.OFF,
        ]
        self._attr_preset_modes = [PRESET_NONE, PRESET_ECO]
        self._attr_supported_features = (
            ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

    @callback
    def update_entity_state(self, state: dict[str, Any]) -> None:
        """Update HA Entity State."""
        normal_state = state.get("state")
        if normal_state is not None:
            self._attr_current_temperature = normal_state.get("temperature")
            self._attr_current_humidity = normal_state.get("humidity")
            self._attr_target_temperature_low = normal_state.get("lowTemp")
            self._attr_target_temperature_high = normal_state.get("highTemp")
            self._attr_fan_mode = normal_state.get("fan")
            self._attr_hvac_mode = YOLINK_MODEL_2_HA.get(normal_state.get("mode"))
            self._attr_hvac_action = YOLINK_ACTION_2_HA.get(normal_state.get("running"))
        eco_setting = state.get("eco")
        if eco_setting is not None:
            self._attr_preset_mode = (
                PRESET_NONE if eco_setting.get("mode") == "on" else PRESET_ECO
            )
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if (hvac_mode_id := HA_MODEL_2_YOLINK.get(hvac_mode)) is None:
            raise ValueError(f"Received an invalid hvac mode: {hvac_mode}")
        await self.call_device(
            ThermostatRequestBuilder.set_state_request(
                ThermostatState(mode=hvac_mode_id)
            )
        )
        await self.coordinator.async_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        await self.call_device(
            ThermostatRequestBuilder.set_state_request(ThermostatState(fan=fan_mode))
        )
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set temperature."""
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if target_temp_low is not None:
            await self.call_device(
                ThermostatRequestBuilder.set_state_request(
                    ThermostatState(lowTemp=target_temp_low)
                )
            )
            self._attr_target_temperature_low = target_temp_low
        if target_temp_high is not None:
            await self.call_device(
                ThermostatRequestBuilder.set_state_request(
                    ThermostatState(highTemp=target_temp_high)
                )
            )
            self._attr_target_temperature_high = target_temp_high
        await self.coordinator.async_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        eco_params = "on" if preset_mode == PRESET_ECO else "off"
        await self.call_device(ThermostatRequestBuilder.set_eco_request(eco_params))
        self._attr_preset_mode = PRESET_ECO if eco_params == "on" else PRESET_NONE
        self.async_write_ha_state()
