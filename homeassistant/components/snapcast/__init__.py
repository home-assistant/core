"""Snapcast Integration."""
from __future__ import annotations

import logging

import snapcast.control
from snapcast.control.client import Snapclient

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PLATFORMS
from .media_player import SnapcastClientDevice, SnapcastGroupDevice

_LOGGER = logging.getLogger(__name__)


class HomeAssistantSnapcast:
    """Snapcast server and data stored in the Home Assistant data object."""

    hass: HomeAssistant

    def __init__(
        self, hass: HomeAssistant, server: snapcast.control.Snapserver, hpid: str
    ) -> None:
        """Initialize the HomeAssistantSnapcast object.

        Parameters
        ----------
        server : snapcast.control.Snapserver
            Snapcast server
        hpid : str
            host and port

        Returns
        -------
        None

        """
        self.hass = hass
        self.server: snapcast.control.Snapserver = server
        self.hpid = hpid
        self.clients: list[SnapcastClientDevice] = []
        self.groups: list[SnapcastGroupDevice] = []
        self.hass_async_add_entities: AddEntitiesCallback
        # connect callbacks
        self.server.set_on_update_callback(self.snapcast_update)
        self.server.set_on_connect_callback(self.snapcast_connected)
        self.server.set_on_disconnect_callback(self.snapcast_disconnected)
        self.server.set_new_client_callback(self.snapcast_add_client)

    def snapcast_update(self) -> None:
        """Update all entities."""
        if not self.hass_async_add_entities:
            return
        new_groups: list[MediaPlayerEntity] = []
        groups: list[MediaPlayerEntity] = []
        hass_groups = {g.identifier: g for g in self.groups}
        for group in self.server.groups:
            if group.identifier in hass_groups:
                groups.append(hass_groups[group.identifier])
                hass_groups[group.identifier].schedule_update_ha_state()
            else:
                new_groups.append(SnapcastGroupDevice(group, self.hpid))
        new_clients: list[MediaPlayerEntity] = []
        clients: list[MediaPlayerEntity] = []
        hass_clients = {c.identifier: c for c in self.clients}
        for client in self.server.clients:
            if client.identifier in hass_clients:
                clients.append(hass_clients[client.identifier])
                hass_clients[client.identifier].schedule_update_ha_state()
            else:
                new_clients.append(SnapcastClientDevice(client, self.hpid))
        del_entities: list[MediaPlayerEntity] = [
            x for x in self.groups if x not in groups
        ]
        del_entities.extend([x for x in self.clients if x not in clients])

        _LOGGER.debug("New clients: %s", str(new_clients))
        _LOGGER.debug("New groups: %s", str(new_groups))
        _LOGGER.debug("Delete: %s", str(del_entities))

        ent_reg = entity_registry.async_get(self.hass)
        for entity in del_entities:
            ent_reg.async_remove(entity.entity_id)
        self.hass_async_add_entities(new_clients + new_groups)

    def snapcast_connected(self) -> None:
        """Activate all entities and update."""
        for client in self.clients:
            client.set_availability(True)
        for group in self.groups:
            group.set_availability(True)
        _LOGGER.info("Server connected")
        self.snapcast_update()

    def snapcast_disconnected(self, ex: Exception | None) -> None:
        """Deactivate all entities."""
        for client in self.clients:
            client.set_availability(False)
        for group in self.groups:
            group.set_availability(False)
        _LOGGER.warning("Server disconnected: %s", str(ex))

    def snapcast_add_client(self, client: Snapclient) -> None:
        """
        Add a Snapcast client.

        Parameters
        ----------
        client : Snapclient
            Snapcast client to be added to HA.
        """
        if not self.hass_async_add_entities:
            return
        clients = [SnapcastClientDevice(client, self.hpid)]
        self.hass_async_add_entities(clients)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Snapcast from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    try:
        server = await snapcast.control.create_server(
            hass.loop, host, port, reconnect=True
        )
    except OSError as ex:
        raise ConfigEntryNotReady(
            f"Could not connect to Snapcast server at {host}:{port}"
        ) from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = HomeAssistantSnapcast(
        hass, server, f"{host}:{port}"
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        snapcast_data = hass.data[DOMAIN].pop(entry.entry_id)
        # remove callbacks
        snapcast_data.server.set_on_update_callback(None)
        snapcast_data.server.set_on_connect_callback(None)
        snapcast_data.server.set_on_disconnect_callback(None)
        snapcast_data.server.set_new_client_callback(None)
        await snapcast_data.server.stop()
    return unload_ok
