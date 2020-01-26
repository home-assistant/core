"""Base class for UniFi clients."""

import logging

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

LOGGER = logging.getLogger(__name__)


class UniFiClient(Entity):
    """Base class for UniFi clients."""

    def __init__(self, client, controller) -> None:
        """Set up client."""
        self.client = client
        self.controller = controller
        self.listeners = []
        self.is_wired = self.client.mac not in controller.wireless_clients

    async def async_added_to_hass(self) -> None:
        """Client entity created."""
        LOGGER.debug("New UniFi client %s (%s)", self.name, self.client.mac)
        self.client.register_callback(self.async_update_callback)
        self.listeners.append(
            async_dispatcher_connect(
                self.hass, self.controller.signal_reachable, self.async_update_callback
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect client object when removed."""
        self.client.remove_callback(self.async_update_callback)
        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()

    @callback
    def async_update_callback(self) -> None:
        """Update the clients state."""
        if self.is_wired and self.client.mac in self.controller.wireless_clients:
            self.is_wired = False
        LOGGER.debug("Updating client %s %s", self.entity_id, self.client.mac)
        self.async_schedule_update_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return self.client.name or self.client.hostname

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self.controller.available

    @property
    def device_info(self) -> dict:
        """Return a client description for device registry."""
        return {"connections": {(CONNECTION_NETWORK_MAC, self.client.mac)}}

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False
