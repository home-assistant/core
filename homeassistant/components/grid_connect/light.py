"""Light platform for Grid Connect."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Grid Connect light platform."""
    coordinator: DataUpdateCoordinator[Any] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GridConnectLight(coordinator)])

    async def handle_turn_on_service(call: ServiceCall):
        """Handle the service call to turn on the light."""
        # Logic to turn on the light
        light_entity = hass.data[DOMAIN][entry.entry_id]
        await light_entity.async_turn_on()

    async def handle_turn_off_service(call: ServiceCall):
        """Handle the service call to turn off the light."""
        # Logic to turn off the light
        light_entity = hass.data[DOMAIN][entry.entry_id]
        await light_entity.async_turn_off()

    # Register the services
    hass.services.async_register(DOMAIN, "turn_on_light", handle_turn_on_service)
    hass.services.async_register(DOMAIN, "turn_off_light", handle_turn_off_service)


class GridConnectLight(CoordinatorEntity[DataUpdateCoordinator[Any]], LightEntity):
    """Representation of a Grid Connect light."""

    def __init__(self, coordinator: DataUpdateCoordinator[Any]) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._attr_name = "Grid Connect Light"
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_is_on = False
        self._attr_brightness = 255  # Default to max brightness

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self._attr_is_on or False  # Ensure a boolean is returned

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        # Directly control the light here
        self._send_command_to_device("turn_on", brightness)
        self._attr_is_on = True
        self._attr_brightness = brightness
        _LOGGER.debug("Turned on light with brightness %s", brightness)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        # Directly control the light here
        self._send_command_to_device("turn_off")
        self._attr_is_on = False
        _LOGGER.debug("Turned off light")
        self.async_write_ha_state()

    def _send_command_to_device(self, command: str, brightness: int = 0) -> None:
        """Send a command to the device."""
        # Implement the logic to send a command to the device
        # This could be a Bluetooth command, a local network request, etc.

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return self._attr_brightness or 0  # Ensure an integer is returned
