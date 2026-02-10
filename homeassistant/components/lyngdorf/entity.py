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
        self._receiver.un_register_notification_callback(self._handle_receiver_update)

    @callback
    def _handle_receiver_update(self) -> None:
        """Handle receiver updates."""
        self._update_availability()
        self.async_write_ha_state()

    def _get_is_connected(self) -> bool | None:
        """Return receiver connection status if available."""
        for attribute in ("connected", "is_connected"):
            if (value := getattr(self._receiver, attribute, None)) is not None:
                return bool(value)
        return None

    @callback
    def _update_availability(self) -> None:
        """Update availability and log transition events."""
        is_connected = self._get_is_connected()
        if is_connected is None or is_connected == self._attr_available:
            return

        self._attr_available = is_connected

        if not is_connected:
            if not self._unavailable_logged:
                _LOGGER.info("Device is unavailable: %s", self.name)
                self._unavailable_logged = True
            return

        if self._unavailable_logged:
            _LOGGER.info("Device is back online: %s", self.name)
            self._unavailable_logged = False
