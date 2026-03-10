"""Support for the Switchbot Battery Circulator fan."""

import asyncio
import logging
import math
from typing import Any

from switchbot_api import (
    AirPurifierCommands,
    BatteryCirculatorFanCommands,
    BatteryCirculatorFanMode,
    CommonCommands,
    SwitchBotAPI,
)

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import SwitchbotCloudData
from .const import AFTER_COMMAND_REFRESH, DOMAIN, AirPurifierMode
from .entity import SwitchBotCloudEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    for device, coordinator in data.devices.fans:
        if device.device_type.startswith("Air Purifier"):
            async_add_entities(
                [SwitchBotAirPurifierEntity(data.api, device, coordinator)]
            )
        else:
            async_add_entities([SwitchBotCloudFan(data.api, device, coordinator)])


class SwitchBotCloudFan(SwitchBotCloudEntity, FanEntity):
    """Representation of a SwitchBot Battery Circulator Fan."""

    _attr_name = None

    _api: SwitchBotAPI
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_preset_modes = list(BatteryCirculatorFanMode)

    _attr_is_on: bool | None = None

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        return self._attr_is_on

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return

        power: str = self.coordinator.data["power"]
        mode: str = self.coordinator.data["mode"]
        fan_speed: str = self.coordinator.data["fanSpeed"]
        self._attr_is_on = power == "on"
        self._attr_preset_mode = mode
        self._attr_percentage = int(fan_speed)
        self._attr_supported_features = (
            FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )
        if self.is_on and self.preset_mode == BatteryCirculatorFanMode.DIRECT.value:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        await self.send_api_command(CommonCommands.ON)
        await self.send_api_command(
            command=BatteryCirculatorFanCommands.SET_WIND_MODE,
            parameters=str(self.preset_mode),
        )
        if self.preset_mode == BatteryCirculatorFanMode.DIRECT.value:
            await self.send_api_command(
                command=BatteryCirculatorFanCommands.SET_WIND_SPEED,
                parameters=str(self.percentage),
            )
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.send_api_command(CommonCommands.OFF)
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        await self.send_api_command(
            command=BatteryCirculatorFanCommands.SET_WIND_MODE,
            parameters=str(BatteryCirculatorFanMode.DIRECT.value),
        )
        await self.send_api_command(
            command=BatteryCirculatorFanCommands.SET_WIND_SPEED,
            parameters=str(percentage),
        )
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.send_api_command(
            command=BatteryCirculatorFanCommands.SET_WIND_MODE,
            parameters=preset_mode,
        )
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()


class SwitchBotAirPurifierEntity(SwitchBotCloudEntity, FanEntity):
    """Representation of a Switchbot air purifier."""

    _api: SwitchBotAPI
    _attr_preset_modes = AirPurifierMode.get_modes()
    _attr_translation_key = "air_purifier"
    _attr_name = None
    _attr_is_on: bool | None = None
    _attr_speed_count = 3

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._attr_is_on

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return
        self._attr_is_on = self.coordinator.data.get("power") == STATE_ON.upper()
        mode = self.coordinator.data.get("mode")
        self._attr_preset_mode = (
            AirPurifierMode(mode).name.lower() if mode is not None else None
        )
        if self.preset_mode == AirPurifierMode.NORMAL.name.lower():
            self._attr_supported_features = (
                FanEntityFeature.PRESET_MODE
                | FanEntityFeature.TURN_OFF
                | FanEntityFeature.TURN_ON
                | FanEntityFeature.SET_SPEED
            )
        else:
            self._attr_supported_features = (
                FanEntityFeature.PRESET_MODE
                | FanEntityFeature.TURN_OFF
                | FanEntityFeature.TURN_ON
            )

        gear = self.coordinator.data.get("fanGear")
        if gear is not None:
            self._attr_percentage = ranged_value_to_percentage(
                low_high_range=(
                    1,
                    3,
                ),
                value=gear,
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the air purifier."""

        _LOGGER.debug(
            "Switchbot air purifier to set preset mode %s %s",
            preset_mode,
            self._attr_unique_id,
        )
        await self.send_api_command(
            AirPurifierCommands.SET_MODE,
            parameters={"mode": AirPurifierMode[preset_mode.upper()].value},
        )
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the air purifier."""
        await self.send_api_command(CommonCommands.ON)
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the air purifier."""

        await self.send_api_command(CommonCommands.OFF)
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the air purifier."""
        fan_gear = math.ceil(
            percentage_to_ranged_value(low_high_range=(1, 3), percentage=percentage)
        )
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        if fan_gear == 0:
            await self.send_api_command(CommonCommands.OFF)
        else:
            await self.send_api_command(
                AirPurifierCommands.SET_MODE,
                parameters={"mode": 1, "fanGear": fan_gear},
            )
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()
