"""Platform for fan integration."""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from . import ZimiConfigEntry
from .entity import ZimiEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZimiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zimi Fan platform."""

    api = config_entry.runtime_data

    async_add_entities([ZimiFan(device, api) for device in api.fans])


class ZimiFan(ZimiEntity, FanEntity):
    """Representation of a Zimi fan."""

    _attr_speed_range = (0, 7)

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the desired speed for the fan."""

        if percentage == 0:
            await self.async_turn_off()
            return

        target_speed = math.ceil(
            percentage_to_ranged_value(self._attr_speed_range, percentage)
        )

        _LOGGER.debug(
            "Sending async_set_percentage() for %s with percentage %s",
            self.name,
            percentage,
        )

        await self._device.set_fanspeed(target_speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Instruct the fan to turn on."""

        _LOGGER.debug("Sending turn_on() for %s", self.name)
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the fan to turn off."""

        _LOGGER.debug("Sending turn_off() for %s", self.name)

        await self._device.turn_off()

    @property
    def percentage(self) -> int:
        """Return the current speed percentage for the fan."""
        if not self._device.fanspeed:
            return 0
        return ranged_value_to_percentage(self._attr_speed_range, self._device.fanspeed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self._attr_speed_range)
