"""Lutron fan platform."""
from __future__ import annotations

import logging
from typing import Any

from pylutron import Output

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, LutronData
from .entity import LutronDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron fan platform.

    Adds fan controls from the Main Repeater associated with the config_entry as
    fan entities.
    """
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            LutronFan(area_name, device, entry_data.client)
            for area_name, device in entry_data.fans
        ],
        True,
    )


class LutronFan(LutronDevice, FanEntity):
    """Representation of a Lutron fan."""

    _attr_should_poll = False
    _attr_speed_count = 3
    _attr_supported_features = FanEntityFeature.SET_SPEED
    _lutron_device: Output
    _prev_percentage: int | None = None

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        new_percentage = self._lutron_device.last_level()
        if new_percentage != 0:
            self._prev_percentage = new_percentage
        return new_percentage

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage > 0:
            self._prev_percentage = percentage
        self._lutron_device.level = percentage
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        new_percentage: int | None = None

        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
            return
        if percentage is not None:
            new_percentage = percentage
        elif not self._prev_percentage:
            # Default to medium speed
            new_percentage = 67
        else:
            new_percentage = self._prev_percentage
        await self.async_set_percentage(new_percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.async_set_percentage(0)

    def update(self) -> None:
        """Call when forcing a refresh of the device."""

        # Reading the property (rather than last_level()) fetches value
        _LOGGER.debug(
            "Lutron ID: %d updated to %f",
            self._lutron_device.id,
            self._lutron_device.level,
        )
        if self._prev_percentage is None:
            self._prev_percentage = self._lutron_device.level
