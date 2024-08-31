"""Support for myStrom switches/plugs."""

from __future__ import annotations

import logging
from typing import Any

from pymystrom.exceptions import MyStromConnectionError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER

DEFAULT_NAME = "myStrom Switch"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the myStrom entities."""
    device = hass.data[DOMAIN][entry.entry_id].device
    async_add_entities([MyStromSwitch(device, entry.title)])


class MyStromSwitch(SwitchEntity):
    """Representation of a myStrom switch/plug."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, plug, name):
        """Initialize the myStrom switch/plug."""
        self.plug = plug
        self._attr_unique_id = self.plug.mac
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.plug.mac)},
            name=name,
            manufacturer=MANUFACTURER,
            sw_version=self.plug.firmware,
            connections={("mac", format_mac(self.plug.mac))},
            configuration_url=self.plug.uri,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.plug.turn_on()
        except MyStromConnectionError:
            _LOGGER.error("No route to myStrom plug")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.plug.turn_off()
        except MyStromConnectionError:
            _LOGGER.error("No route to myStrom plug")

    async def async_update(self) -> None:
        """Get the latest data from the device and update the data."""
        try:
            await self.plug.get_state()
            self._attr_is_on = self.plug.relay
            self._attr_available = True
        except MyStromConnectionError:
            if self.available:
                self._attr_available = False
                _LOGGER.error("No route to myStrom plug")
