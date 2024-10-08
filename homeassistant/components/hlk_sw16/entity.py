"""Support for HLK-SW16 relay switches."""

import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


class SW16Entity(Entity):
    """Representation of a HLK-SW16 device.

    Contains the common logic for HLK-SW16 entities.
    """

    _attr_should_poll = False

    def __init__(self, device_port, entry_id, client):
        """Initialize the device."""
        # HLK-SW16 specific attributes for every component type
        self._entry_id = entry_id
        self._device_port = device_port
        self._is_on = None
        self._client = client
        self._attr_name = device_port
        self._attr_unique_id = f"{self._entry_id}_{self._device_port}"

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        _LOGGER.debug("Relay %s new state callback: %r", self.unique_id, event)
        self._is_on = event
        self.async_write_ha_state()

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._client.is_connected)

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(
            self.handle_event_callback, self._device_port
        )
        self._is_on = await self._client.status(self._device_port)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"hlk_sw16_device_available_{self._entry_id}",
                self._availability_callback,
            )
        )
