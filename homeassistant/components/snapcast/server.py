"""Snapcast Integration."""

from __future__ import annotations

import logging

import snapcast.control
from snapcast.control.client import Snapclient

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .media_player import SnapcastClientDevice, SnapcastGroupDevice

_LOGGER = logging.getLogger(__name__)


class HomeAssistantSnapcast:
    """Snapcast server and data stored in the Home Assistant data object."""

    hass: HomeAssistant

    def __init__(
        self,
        hass: HomeAssistant,
        server: snapcast.control.Snapserver,
        hpid: str,
        entry_id: str,
    ) -> None:
        """Initialize the HomeAssistantSnapcast object.

        Parameters
        ----------
        hass: HomeAssistant
            hass object
        server : snapcast.control.Snapserver
            Snapcast server
        hpid : str
            host and port
        entry_id: str
            ConfigEntry entry_id

        Returns
        -------
        None

        """
        self.hass: HomeAssistant = hass
        self.server: snapcast.control.Snapserver = server
        self.hpid: str = hpid
        self._entry_id = entry_id
        self.clients: list[SnapcastClientDevice] = []
        self.groups: list[SnapcastGroupDevice] = []
        self.hass_async_add_entities: AddEntitiesCallback
        # connect callbacks
        self.server.set_on_update_callback(self.on_update)
        self.server.set_on_connect_callback(self.on_connect)
        self.server.set_on_disconnect_callback(self.on_disconnect)
        self.server.set_new_client_callback(self.on_add_client)

    async def disconnect(self) -> None:
        """Disconnect from server."""
        self.server.set_on_update_callback(None)
        self.server.set_on_connect_callback(None)
        self.server.set_on_disconnect_callback(None)
        self.server.set_new_client_callback(None)
        self.server.stop()

    def on_update(self) -> None:
        """Update all entities.

        Retrieve all groups/clients from server and add/update/delete entities.
        """
        if not self.hass_async_add_entities:
            return
        new_groups: list[MediaPlayerEntity] = []
        groups: list[MediaPlayerEntity] = []
        hass_groups = {g.identifier: g for g in self.groups}
        for group in self.server.groups:
            if group.identifier in hass_groups:
                groups.append(hass_groups[group.identifier])
                hass_groups[group.identifier].async_schedule_update_ha_state()
            else:
                new_groups.append(SnapcastGroupDevice(group, self.hpid, self._entry_id))
        new_clients: list[MediaPlayerEntity] = []
        clients: list[MediaPlayerEntity] = []
        hass_clients = {c.identifier: c for c in self.clients}
        for client in self.server.clients:
            if client.identifier in hass_clients:
                clients.append(hass_clients[client.identifier])
                hass_clients[client.identifier].async_schedule_update_ha_state()
            else:
                new_clients.append(
                    SnapcastClientDevice(client, self.hpid, self._entry_id)
                )
        del_entities: list[MediaPlayerEntity] = [
            x for x in self.groups if x not in groups
        ]
        del_entities.extend([x for x in self.clients if x not in clients])

        _LOGGER.debug("New clients: %s", str([c.name for c in new_clients]))
        _LOGGER.debug("New groups: %s", str([g.name for g in new_groups]))
        _LOGGER.debug("Delete: %s", str(del_entities))

        ent_reg = er.async_get(self.hass)
        for entity in del_entities:
            ent_reg.async_remove(entity.entity_id)
        self.hass_async_add_entities(new_clients + new_groups)

    def on_connect(self) -> None:
        """Activate all entities and update."""
        for client in self.clients:
            client.set_availability(True)
        for group in self.groups:
            group.set_availability(True)
        _LOGGER.debug("Server connected: %s", self.hpid)
        self.on_update()

    def on_disconnect(self, ex: Exception | None) -> None:
        """Deactivate all entities."""
        for client in self.clients:
            client.set_availability(False)
        for group in self.groups:
            group.set_availability(False)
        _LOGGER.warning(
            "Server disconnected: %s. Trying to reconnect. %s", self.hpid, str(ex or "")
        )

    def on_add_client(self, client: Snapclient) -> None:
        """Add a Snapcast client.

        Parameters
        ----------
        client : Snapclient
            Snapcast client to be added to HA.

        """
        if not self.hass_async_add_entities:
            return
        clients = [SnapcastClientDevice(client, self.hpid, self._entry_id)]
        self.hass_async_add_entities(clients)
