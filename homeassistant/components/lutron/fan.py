"""Lutron fan platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, LutronData
from .aiolip import LutronController, Output
from .entity import LutronOutput

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron fan platform.

    Adds fans from the Main Repeater associated with the config_entry as
    fan entities.
    """
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [LutronFan(device, entry_data.controller) for device in entry_data.fans],
        True,
    )


class LutronFan(LutronOutput, FanEntity):
    """Representation of a Lutron fan."""

    _attr_should_poll = False
    _attr_speed_count = 3
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _prev_percentage: int | None = None

    def __init__(
        self,
        lutron_device: Output,
        controller: LutronController,
    ) -> None:
        """Initialize the device."""
        super().__init__(lutron_device, controller)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage > 0:
            self._prev_percentage = percentage
        await self._execute_device_command(self._lutron_device.set_level, percentage)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        new_percentage: int | None = None

        if percentage is not None:
            new_percentage = percentage
        elif not self._prev_percentage:
            # Default to medium speed
            new_percentage = 67
        else:
            new_percentage = self._prev_percentage
        await self._execute_device_command(
            self._lutron_device.set_level, new_percentage
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._execute_device_command(self._lutron_device.set_level, 0)

    async def _request_state(self) -> None:
        """Request the state from the device."""
        await self._execute_device_command(self._lutron_device.get_level)

    def _update_callback(self, value: int):
        """Update the state attributes."""
        self._attr_is_on = value > 0
        self._attr_percentage = value
        if self._prev_percentage is None or value != 0:
            self._prev_percentage = value

        self.async_write_ha_state()
