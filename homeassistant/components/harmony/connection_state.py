"""Mixin class for handling connection state changes."""
import logging

from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)

TIME_MARK_DISCONNECTED = 10


class ConnectionStateMixin:
    """Base implementation for connection state handling."""

    def __init__(self):
        """Initialize this mixin instance."""
        super().__init__()
        self._unsub_mark_disconnected = None

    async def got_connected(self, _=None):
        """Notification that we're connected to the HUB."""
        _LOGGER.debug("%s: connected to the HUB", self._name)
        self.async_write_ha_state()

        self._clear_disconnection_delay()

    async def got_disconnected(self, _=None):
        """Notification that we're disconnected from the HUB."""
        _LOGGER.debug("%s: disconnected from the HUB", self._name)
        # We're going to wait for 10 seconds before announcing we're
        # unavailable, this to allow a reconnection to happen.
        self._unsub_mark_disconnected = async_call_later(
            self.hass, TIME_MARK_DISCONNECTED, self._mark_disconnected_if_unavailable
        )

    def _clear_disconnection_delay(self):
        if self._unsub_mark_disconnected:
            self._unsub_mark_disconnected()
            self._unsub_mark_disconnected = None

    def _mark_disconnected_if_unavailable(self, _):
        self._unsub_mark_disconnected = None
        if not self.available:
            # Still disconnected. Let the state engine know.
            self.async_write_ha_state()
