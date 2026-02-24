"""Base entity for Lyngdorf integration."""

from __future__ import annotations

import logging

from lyngdorf.device import Receiver

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


class LyngdorfEntity(Entity):
    """Base Lyngdorf entity."""

    _attr_has_entity_name = True
    _attr_available = True
    _attr_should_poll = False

    def __init__(self, receiver: Receiver) -> None:
        """Initialize the entity."""
        self._receiver = receiver
        self._unavailable_logged: bool = False

    async def async_added_to_hass(self) -> None:
        """Register notification callback when added to hass."""
        await super().async_added_to_hass()
        self._receiver.register_notification_callback(self._handle_receiver_update)
        self._update_availability()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister notification callback when removed from hass."""
        await super().async_will_remove_from_hass()
        self._receiver.un_register_notification_callback(self._handle_receiver_update)

    @callback
    def _handle_receiver_update(self) -> None:
        """Handle receiver updates."""
        self._update_availability()
        self.async_write_ha_state()

    @callback
    def _update_availability(self) -> None:
        """Update availability from receiver connection status."""
        connected = self._receiver.connected
        self._attr_available = connected

        if connected == self._unavailable_logged:
            self._unavailable_logged = not connected
            if connected:
                _LOGGER.info("Device is back online: %s", self.name)
            else:
                _LOGGER.info("Device is unavailable: %s", self.name)
