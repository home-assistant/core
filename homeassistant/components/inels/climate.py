"""iNELS climate entity."""
from __future__ import annotations

from typing import Any

from inelsmqtt.devices import Device
import inelsmqtt.util as InelsUtil

from homeassistant.components.climate import (
    STATE_OFF,
    STATE_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import InelsBaseEntity
from .const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DEVICES, DOMAIN

OPERATION_LIST = [
    STATE_OFF,
    STATE_ON,
]

SUPPORT_FLAGS_CLIMATE = ClimateEntityFeature.TARGET_TEMPERATURE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load iNELS water heater from config entry."""
    device_list: list[Device] = hass.data[DOMAIN][config_entry.entry_id][DEVICES]

    async_add_entities(
        [
            InelsClimate(device)
            for device in device_list
            if device.device_type == Platform.CLIMATE
        ],
    )


class InelsClimate(InelsBaseEntity, ClimateEntity):
    """Water heater class for HA."""

    _attr_supported_features: ClimateEntityFeature = SUPPORT_FLAGS_CLIMATE
    _attr_hvac_modes: list[HVACMode] = [HVACMode.OFF, HVACMode.HEAT]
    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS
    _attr_hvac_mode: HVACMode = HVACMode.OFF

    def __init__(self, device: Device) -> None:
        """Initialize a climate."""
        super().__init__(device=device)

        self._attr_max_temp = DEFAULT_MAX_TEMP
        self._attr_min_temp = DEFAULT_MIN_TEMP

        if self._device.state is not None:
            self._attr_current_temperature = self._device.state.current
            self._attr_target_temperature = self._device.state.required

    @property
    def current_temperature(self) -> float | None:
        """Get current temperature."""
        if self._device.state.current is not None:
            return self._device.state.current

        return super().current_temperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set required temperature."""
        _s = self._device.state

        new_value = InelsUtil.new_object(
            battery=_s.battery,
            current=_s.current,
            required=kwargs.get(ATTR_TEMPERATURE),
            open_in_percentage=_s.open_in_percentage,
        )
        await self.hass.async_add_executor_job(self._device.set_ha_value, new_value)
