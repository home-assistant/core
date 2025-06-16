"""Support for SwitchBot AirPurifier."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from switchbot_api import AirPurifierCommands, CommonCommands

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData
from .const import DEFAULT_DELAY_TIME, DOMAIN, AirPurifierMode
from .entity import SwitchBotCloudEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switchbot air purifier based on a config entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SwitchBotAirPurifierEntity(data.api, device, coordinator)
        for device, coordinator in data.devices.fans
    )


class SwitchBotAirPurifierEntity(SwitchBotCloudEntity, FanEntity):
    """Representation of a Switchbot air purifier."""

    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_preset_modes = AirPurifierMode.get_modes()
    _attr_translation_key = "air_purifier"
    _attr_name = None

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("power") == STATE_ON.upper()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self.coordinator.data is None:
            return None
        mode = self.coordinator.data.get("mode")
        return AirPurifierMode(mode).name.lower() if mode is not None else None

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
        await asyncio.sleep(DEFAULT_DELAY_TIME)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the air purifier."""

        _LOGGER.debug(
            "Switchbot air purifier to set turn on %s %s %s",
            percentage,
            preset_mode,
            self._attr_unique_id,
        )
        await self.send_api_command(CommonCommands.ON)
        await asyncio.sleep(DEFAULT_DELAY_TIME)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the air purifier."""

        _LOGGER.debug("Switchbot air purifier to set turn off %s", self._attr_unique_id)
        await self.send_api_command(CommonCommands.OFF)
        await asyncio.sleep(DEFAULT_DELAY_TIME)
        await self.coordinator.async_request_refresh()
