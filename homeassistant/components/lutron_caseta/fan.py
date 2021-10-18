"""Support for Lutron Caseta fans."""
from __future__ import annotations

import logging

from pylutron_caseta import FAN_HIGH, FAN_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_OFF

from homeassistant.components.fan import DOMAIN, SUPPORT_SET_SPEED, FanEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import LutronCasetaDevice
from .const import BRIDGE_DEVICE, BRIDGE_LEAP, DOMAIN as CASETA_DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_ON_PERCENTAGE = 50
ORDERED_NAMED_FAN_SPEEDS = [FAN_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_HIGH]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Lutron Caseta fan platform.

    Adds fan controllers from the Caseta bridge associated with the config_entry
    as fan entities.
    """
    entities = []
    data = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data[BRIDGE_LEAP]
    bridge_device = data[BRIDGE_DEVICE]
    fan_devices = bridge.get_devices_by_domain(DOMAIN)

    for fan_device in fan_devices:
        entity = LutronCasetaFan(fan_device, bridge, bridge_device)
        entities.append(entity)

    async_add_entities(entities, True)


class LutronCasetaFan(LutronCasetaDevice, FanEntity):
    """Representation of a Lutron Caseta fan. Including Fan Speed."""

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

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @property
    def supported_features(self) -> int:
        """Flag supported features. Speed Only."""
        return SUPPORT_SET_SPEED

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ):
        """Turn the fan on."""
        if percentage is None:
            percentage = DEFAULT_ON_PERCENTAGE

        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs):
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
    def is_on(self):
        """Return true if device is on."""
        return self.percentage and self.percentage > 0

    async def async_update(self):
        """Update when forcing a refresh of the device."""
        self._device = self._smartbridge.get_device_by_id(self.device_id)
        _LOGGER.debug("State of this lutron fan device is %s", self._device)
