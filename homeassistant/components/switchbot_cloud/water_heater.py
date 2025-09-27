"""Support for the Switchbot Smart Radiator Thermostat."""

import asyncio
from typing import Any

from switchbot_api import SmartRadiatorThermostatCommands, SmartRadiatorThermostatMode

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData
from .const import AFTER_COMMAND_REFRESH, DOMAIN
from .entity import SwitchBotCloudEntity

operation_list = [i.name for i in SmartRadiatorThermostatMode.get_all_modes()]


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        SwitchBotSmartRadiatorThermostat(data.api, device, coordinator)
        for device, coordinator in data.devices.water_heaters
    )


class SwitchBotSmartRadiatorThermostat(SwitchBotCloudEntity, WaterHeaterEntity):
    """Representation of a SwitchBot Smart Radiator Thermostat."""

    _attr_name = None
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_max_temp = 35
    _attr_min_temp = 4
    _attr_target_temperature = 21
    _attr_target_temperature_low = 19
    _attr_target_temperature_high = 23
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = [i.name for i in SmartRadiatorThermostatMode.get_all_modes()]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Async set temperature."""
        target_temperature = kwargs["temperature"]
        if self._attr_current_operation == SmartRadiatorThermostatMode.MANUAL.name:
            await self.send_api_command(
                command=SmartRadiatorThermostatCommands.SET_MANUAL_MODE_TEMPERATURE,
                parameters=str(target_temperature),
            )
            await asyncio.sleep(AFTER_COMMAND_REFRESH)
            await self.coordinator.async_request_refresh()
            self._attr_target_temperature = target_temperature
            self._attr_target_temperature_low = target_temperature - 2
            self._attr_target_temperature_high = target_temperature + 2

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Async set operation mode."""
        await self.coordinator.async_request_refresh()
        parameters = self.__mode_map_value(operation_mode)
        await self.send_api_command(
            command=SmartRadiatorThermostatCommands.SET_MODE,
            parameters=str(parameters),
        )
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return
        mode: int = self.coordinator.data["mode"]
        temperature: str = self.coordinator.data["temperature"]
        self._attr_current_temperature = int(temperature)
        self._attr_current_operation = str(self.__value_map_mode(mode))

        if self._attr_current_operation == SmartRadiatorThermostatMode.MANUAL.name:
            self._attr_supported_features = (
                WaterHeaterEntityFeature.TARGET_TEMPERATURE
                | WaterHeaterEntityFeature.OPERATION_MODE
            )
        else:
            self._attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE

    def __value_map_mode(self, value: int) -> Any:
        """Value map SmartRadiatorThermostatMode mode."""
        for i in SmartRadiatorThermostatMode.get_all_modes():
            if i.value == value:
                return i.name
        raise NotImplementedError(f"{value} Not Supported")

    def __mode_map_value(self, mode: str) -> Any:
        """SmartRadiatorThermostatMode mode map value."""
        for i in SmartRadiatorThermostatMode.get_all_modes():
            if i.name == mode:
                return i.value
        raise NotImplementedError(f"{mode} Not Supported")
