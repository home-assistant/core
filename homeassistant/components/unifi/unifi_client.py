"""Base class for UniFi clients."""

import logging

from aiounifi.api import SOURCE_EVENT
from aiounifi.events import (
    WIRED_CLIENT_BLOCKED,
    WIRED_CLIENT_CONNECTED,
    WIRED_CLIENT_DISCONNECTED,
    WIRED_CLIENT_UNBLOCKED,
    WIRELESS_CLIENT_BLOCKED,
    WIRELESS_CLIENT_CONNECTED,
    WIRELESS_CLIENT_DISCONNECTED,
    WIRELESS_CLIENT_ROAM,
    WIRELESS_CLIENT_UNBLOCKED,
)

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

LOGGER = logging.getLogger(__name__)

CLIENT_BLOCKED = (WIRED_CLIENT_BLOCKED, WIRELESS_CLIENT_BLOCKED)
CLIENT_UNBLOCKED = (WIRED_CLIENT_UNBLOCKED, WIRELESS_CLIENT_UNBLOCKED)
WIRED_CLIENT = (WIRED_CLIENT_CONNECTED, WIRED_CLIENT_DISCONNECTED)
WIRELESS_CLIENT = (
    WIRELESS_CLIENT_CONNECTED,
    WIRELESS_CLIENT_DISCONNECTED,
    WIRELESS_CLIENT_ROAM,
)


class UniFiClient(Entity):
    """Base class for UniFi clients."""

    def __init__(self, client, controller) -> None:
        """Set up client."""
        self.client = client
        self.controller = controller

        self._is_wired = self.client.mac not in controller.wireless_clients
        self.is_blocked = self.client.blocked
        self.wired_connection = None
        self.wireless_connection = None

    async def async_added_to_hass(self) -> None:
        """Client entity created."""
        LOGGER.debug("New client %s (%s)", self.entity_id, self.client.mac)
        self.client.register_callback(self.async_update_callback)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_reachable, self.async_update_callback
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect client object when removed."""
        self.client.remove_callback(self.async_update_callback)

    @callback
    def async_update_callback(self) -> None:
        """Update the clients state."""
        if self._is_wired and self.client.mac in self.controller.wireless_clients:
            self._is_wired = False

        if self.client.last_updated == SOURCE_EVENT:
            if self.client.event.event in WIRELESS_CLIENT:
                self.wireless_connection = self.client.event.event in (
                    WIRELESS_CLIENT_CONNECTED,
                    WIRELESS_CLIENT_ROAM,
                )

            elif self.client.event.event in WIRED_CLIENT:
                self.wired_connection = (
                    self.client.event.event == WIRED_CLIENT_CONNECTED
                )

            elif self.client.event.event in CLIENT_BLOCKED + CLIENT_UNBLOCKED:
                self.is_blocked = self.client.event.event in CLIENT_BLOCKED

        LOGGER.debug("Updating client %s (%s)", self.entity_id, self.client.mac)
        self.async_write_ha_state()

    @property
    def is_wired(self):
        """Return if the client is wired.

        Allows disabling logic to keep track of clients affected by UniFi wired bug marking wireless devices as wired. This is useful when running a network not only containing UniFi APs.
        """
        if self.controller.option_ignore_wired_bug:
            return self.client.is_wired
        return self._is_wired

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
        return True
