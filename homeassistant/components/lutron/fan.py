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

    _attr_name = None
    _attr_should_poll = False
    _attr_speed_count = 3
    _attr_supported_features = FanEntityFeature.SET_SPEED
    _lutron_device: Output
    _prev_percentage: int | None = None

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage > 0:
            self._prev_percentage = percentage
        self._lutron_device.level = percentage
        self.schedule_update_ha_state()

    def turn_on(
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
        self.set_percentage(new_percentage)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self.set_percentage(0)

    def _request_state(self) -> None:
        """Request the state from the device."""
        self._lutron_device.level  # pylint: disable=pointless-statement

    def _update_attrs(self) -> None:
        """Update the state attributes."""
        level = self._lutron_device.last_level()
        self._attr_is_on = level > 0
        self._attr_percentage = level
        if self._prev_percentage is None or level != 0:
            self._prev_percentage = level
