"""iNELS water heater valve."""
from __future__ import annotations

from typing import Any

from inelsmqtt.devices import Device
import inelsmqtt.util as InelsUtil

from homeassistant.components.water_heater import (
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, STATE_ON, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import InelsBaseEntity
from .const import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEVICES,
    DOMAIN,
    ICON_WATER_HEATER_DICT,
)

SUPPORT_FLAGS_HEATER = (
    WaterHeaterEntityFeature.TARGET_TEMPERATURE
    | WaterHeaterEntityFeature.OPERATION_MODE
)

OPERATION_LIST = [
    STATE_OFF,
    STATE_ON,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load iNELS water heater from config entry."""
    device_list: list[Device] = hass.data[DOMAIN][config_entry.entry_id][DEVICES]

    async_add_entities(
        [
            InelsWaterHeater(device)
            for device in device_list
            if device.device_type == Platform.WATER_HEATER
        ],
    )


class InelsWaterHeater(InelsBaseEntity, WaterHeaterEntity):
    """Water heater class for HA."""

    _attr_supported_features = SUPPORT_FLAGS_HEATER

    def __init__(self, device: Device) -> None:
        """Initialize a water heater."""
        super().__init__(device=device)

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_operation_list = OPERATION_LIST
        self._attr_min_temp = DEFAULT_MIN_TEMP
        self._attr_max_temp = DEFAULT_MAX_TEMP
        self._attr_icon = ICON_WATER_HEATER_DICT.get(STATE_OFF)
        self._attr_current_operation = STATE_OFF

    @property
    def icon(self) -> str | None:
        """Get icon of the water heater."""
        if self._device.state.open_in_percentage is not None:
            return ICON_WATER_HEATER_DICT.get(
                STATE_ON if self._device.state.open_in_percentage > 0.0 else STATE_OFF
            )

        return super().icon

    @property
    def current_temperature(self) -> float | None:
        """Get current temperature."""
        if self._device.state.current is not None:
            return self._device.state.current

        return super().current_temperature

    @property
    def current_operation(self) -> str | None:
        """Get current operation mode."""
        if self._device.state.open_in_percentage is not None:
            return (
                STATE_ON if self._device.state.open_in_percentage > 0.0 else STATE_OFF
            )

        return super().current_operation

    @property
    def target_temperature(self) -> float | None:
        """Target temperature."""
        if self._device.state.required is not None:
            return self._device.state.required

        return super().target_temperature

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set operation mode."""
        _s = self._device.state
        new_value = InelsUtil.new_object(
            battery=_s.battery,
            current=_s.current,
            required=_s.current,
            open_in_percentage=_s.open_in_percentage,
        )

        await self.hass.async_add_executor_job(self._device.set_ha_value, new_value)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        _s = self._device.state
        new_value = InelsUtil.new_object(
            battery=_s.battery,
            current=_s.current,
            required=kwargs.get(ATTR_TEMPERATURE),
            open_in_percentage=_s.open_in_percentage,
        )

        await self.hass.async_add_executor_job(self._device.set_ha_value, new_value)
