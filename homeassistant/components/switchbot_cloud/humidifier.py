"""Support for Switchbot humidifier."""

import asyncio
from typing import Any

from switchbot_api import CommonCommands, HumidifierCommands, HumidifierV2Commands

from homeassistant.components.humidifier import (
    MODE_AUTO,
    MODE_NORMAL,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData
from .const import AFTER_COMMAND_REFRESH, DOMAIN, HUMIDITY_LEVELS, Humidifier2Mode
from .entity import SwitchBotCloudEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switchbot based on a config entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SwitchBotHumidifier(data.api, device, coordinator)
        if device.device_type == "Humidifier"
        else SwitchBotEvaporativeHumidifier(data.api, device, coordinator)
        for device, coordinator in data.devices.humidifiers
    )


class SwitchBotHumidifier(SwitchBotCloudEntity, HumidifierEntity):
    """Representation of a Switchbot humidifier."""

    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_available_modes = [MODE_NORMAL, MODE_AUTO]
    _attr_min_humidity = 1
    _attr_translation_key = "humidifier"
    _attr_name = None
    _attr_target_humidity = 50

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if coord_data := self.coordinator.data:
            self._attr_is_on = coord_data.get("power") == STATE_ON
            self._attr_mode = MODE_AUTO if coord_data.get("auto") else MODE_NORMAL
            self._attr_current_humidity = coord_data.get("humidity")

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        self.target_humidity, parameters = self._map_humidity_to_supported_level(
            humidity
        )
        await self.send_api_command(
            HumidifierCommands.SET_MODE, parameters=str(parameters)
        )
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_set_mode(self, mode: str) -> None:
        """Set new target humidity."""
        if mode == MODE_AUTO:
            await self.send_api_command(HumidifierCommands.SET_MODE, parameters=mode)
        else:
            await self.send_api_command(
                HumidifierCommands.SET_MODE, parameters=str(102)
            )
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.send_api_command(CommonCommands.ON)
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.send_api_command(CommonCommands.OFF)
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    def _map_humidity_to_supported_level(self, humidity: int) -> tuple[int, int]:
        """Map any humidity to the closest supported level and its parameter."""
        if humidity <= 34:
            return 34, HUMIDITY_LEVELS[34]
        if humidity <= 67:
            return 67, HUMIDITY_LEVELS[67]
        return 100, HUMIDITY_LEVELS[100]


class SwitchBotEvaporativeHumidifier(SwitchBotCloudEntity, HumidifierEntity):
    """Representation of a Switchbot humidifier v2."""

    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_available_modes = Humidifier2Mode.get_modes()
    _attr_translation_key = "evaporative_humidifier"
    _attr_name = None
    _attr_target_humidity = 50

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if coord_data := self.coordinator.data:
            self._attr_is_on = coord_data.get("power") == STATE_ON
            self._attr_mode = (
                Humidifier2Mode(coord_data.get("mode")).name.lower()
                if coord_data.get("mode") is not None
                else None
            )
            self._attr_current_humidity = (
                coord_data.get("humidity")
                if coord_data.get("humidity") != 127
                else None
            )

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        assert self.coordinator.data is not None
        self._attr_target_humidity = humidity
        params = {"mode": self.coordinator.data["mode"], "humidity": humidity}
        await self.send_api_command(HumidifierV2Commands.SET_MODE, parameters=params)
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_set_mode(self, mode: str) -> None:
        """Set new target mode."""
        assert self.coordinator.data is not None
        params = {"mode": Humidifier2Mode[mode.upper()].value}
        await self.send_api_command(HumidifierV2Commands.SET_MODE, parameters=params)
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.send_api_command(CommonCommands.ON)
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.send_api_command(CommonCommands.OFF)
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()
