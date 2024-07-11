"""Support for Lutron Caseta fans."""

from __future__ import annotations

from typing import Any

from pylutron_caseta import FAN_HIGH, FAN_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_OFF

from homeassistant.components.fan import DOMAIN, FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import LutronCasetaDeviceUpdatableEntity
from .const import DOMAIN as CASETA_DOMAIN
from .models import LutronCasetaData

DEFAULT_ON_PERCENTAGE = 50
ORDERED_NAMED_FAN_SPEEDS = [FAN_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_HIGH]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta fan platform.

    Adds fan controllers from the Caseta bridge associated with the config_entry
    as fan entities.
    """
    data: LutronCasetaData = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data.bridge
    fan_devices = bridge.get_devices_by_domain(DOMAIN)
    async_add_entities(LutronCasetaFan(fan_device, data) for fan_device in fan_devices)


class LutronCasetaFan(LutronCasetaDeviceUpdatableEntity, FanEntity):
    """Representation of a Lutron Caseta fan. Including Fan Speed."""

    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_speed_count = len(ORDERED_NAMED_FAN_SPEEDS)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._device["fan_speed"] is None:
            return None
        if self._device["fan_speed"] == FAN_OFF:
            return 0
        return ordered_list_item_to_percentage(
            ORDERED_NAMED_FAN_SPEEDS, self._device["fan_speed"]
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if percentage is None:
            percentage = DEFAULT_ON_PERCENTAGE

        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.async_set_percentage(0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""
        if percentage == 0:
            named_speed = FAN_OFF
        else:
            named_speed = percentage_to_ordered_list_item(
                ORDERED_NAMED_FAN_SPEEDS, percentage
            )

        await self._smartbridge.set_fan(self.device_id, named_speed)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return bool(self.percentage)
