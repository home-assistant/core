"""YoLink Thermostat."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_ON,
    PRESET_ECO,
    PRESET_NONE,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_COORDINATORS, ATTR_DEVICE_THERMOSTAT, DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink Thermostat from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id][ATTR_COORDINATORS]
    entities = [
        YoLinkClimateEntity(config_entry, device_coordinator)
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type == ATTR_DEVICE_THERMOSTAT
    ]
    async_add_entities(entities)


class YoLinkClimateEntity(YoLinkEntity, ClimateEntity):
    """YoLink Climate Entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
    ) -> None:
        """Init YoLink Thermostat."""
        super().__init__(config_entry, coordinator)
        self._attr_unique_id = f"{coordinator.device.device_id}_climate"
        self._attr_name = f"{coordinator.device.device_name} (Thermostat)"
        self._attr_temperature_unit = TEMP_CELSIUS
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
        )

    @callback
    def update_entity_state(self, state: dict[str, Any]) -> None:
        """Update HA Entity State."""
        normal_state = state["state"]
        self._attr_current_temperature = normal_state[ATTR_TEMPERATURE]
        self._attr_current_humidity = normal_state["humidity"]
        self._attr_target_temperature_low = normal_state["lowTemp"]
        self._attr_target_temperature_high = normal_state["highTemp"]
        self._attr_fan_mode = normal_state["fan"]
        self._attr_hvac_mode = normal_state["mode"]
        self._attr_hvac_action = normal_state["running"]
        self._attr_preset_mode = (
            PRESET_NONE if state["eco"]["mode"] == "on" else PRESET_ECO
        )
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        await self.call_device_api("setState", {"mode": hvac_mode.value})
        self._attr_hvac_mode = hvac_mode.value
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        await self.call_device_api("setState", {"fan": fan_mode})
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set temperature."""
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if target_temp_low is not None:
            await self.call_device_api("setState", {"lowTemp": target_temp_low})
            self._attr_target_temperature_low = target_temp_low
        if target_temp_high is not None:
            await self.call_device_api("setState", {"highTemp": target_temp_high})
            self._attr_target_temperature_high = target_temp_high
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        eco_params = "on" if preset_mode == PRESET_ECO else "off"
        await self.call_device_api("setECO", {"mode": eco_params})
        self._attr_preset_mode = PRESET_ECO if eco_params == "on" else PRESET_NONE
        self.async_write_ha_state()
