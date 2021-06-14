"""Support for Mikrotik routers as device tracker."""
from __future__ import annotations

import logging

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceRegistry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_registry import RegistryEntry
import homeassistant.util.dt as dt_util

from .const import CLIENTS, DOMAIN
from .hub import MikrotikHub
from .mikrotik_client import MikrotikClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up device tracker for Mikrotik component."""
    hub: MikrotikHub = hass.data[DOMAIN][config_entry.entry_id]
    all_clients: dict[str, MikrotikClient] = hass.data[DOMAIN][CLIENTS]
    tracked: dict[str, MikrotikClientTracker] = {}

    # entity_registry = hass.helpers.entity_registry.async_get(hass)

    # # Restore clients that is not a part of active clients list.
    # for entity in entity_registry.entities.values():

    #     if (
    #         entity.config_entry_id == config_entry.entry_id
    #         and entity.domain == DEVICE_TRACKER
    #     ):

    #         if (
    #             entity.unique_id in hub.clients
    #             or entity.unique_id not in all_clients
    #         ):
    #             continue
    #         hub.api.restore_device(entity.unique_id)

    # Restore clients that is not a part of active clients list.
    entity_registry = hass.helpers.entity_registry.async_get(hass)
    hub_clients: list[
        RegistryEntry
    ] = hass.helpers.entity_registry.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    # print(hub.data)
    for entity in hub_clients:
        if entity.unique_id not in hub.data:
            hub.data.append(entity.unique_id)

    @callback
    def update_hub() -> None:
        """Update the status of the device."""
        update_items(hub, tracked, all_clients, async_add_entities)

    config_entry.async_on_unload(hub.async_add_listener(update_hub))

    # hass.helpers.dispatcher.async_dispatcher_connect(hass, "mikrotik-clients-updated", update_hub)
    update_hub()


@callback
def update_items(
    hub: MikrotikHub,
    tracked: dict[str, MikrotikClientTracker],
    all_clients: dict[str, MikrotikClient],
    async_add_entities,
) -> None:
    """Update tracked device state from the hub."""
    new_tracked = []
    for mac in hub.data:
        if mac not in tracked:
            tracked[mac] = MikrotikClientTracker(all_clients[mac], hub)
            new_tracked.append(tracked[mac])

    if new_tracked:
        async_add_entities(new_tracked)


class MikrotikClientTracker(ScannerEntity):
    """Representation of network device."""

    def __init__(self, client: MikrotikClient, hub: MikrotikHub) -> None:
        """Initialize the tracked device."""
        self.client = client
        self.host = self.client.host
        self.hub = hub
        # self.unsub_dispatcher = None
        self.this_device = None

    @property
    def is_connected(self) -> bool:
        """Return true if the client is connected to the network."""
        # client = self.hass.data[DOMAIN][CLIENTS][self.client.mac]
        if self.client.mac == "98:09:CF:0C:98:0F":
            print(self.client.last_seen)
        if (
            self.client.last_seen
            and (dt_util.utcnow() - self.client.last_seen)
            < self.hub.option_detection_time
        ):
            return True
        return False

    @property
    def source_type(self) -> str:
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return self.client.name

    @property
    def hostname(self) -> str:
        """Return the hostname of the client."""
        return self.client.name

    @property
    def mac_address(self) -> str:
        """Return the mac address of the client."""
        return self.client.mac

    @property
    def ip_address(self) -> str:
        """Return the mac address of the client."""
        return self.client.ip_address

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return self.client.mac

    @property
    def extra_state_attributes(self) -> dict:
        """Return the device state attributes."""
        return self.client.attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Return a client description for device registry."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self.client.mac)},
            "identifiers": {(DOMAIN, self.client.mac)},
            # We only get generic info from device discovery and so don't want
            # to override API specific info that integrations can provide
            "default_name": self.name,
        }

    async def async_added_to_hass(self):
        """Client entity created."""
        _LOGGER.debug("New network device tracker %s (%s)", self.name, self.unique_id)

        self.async_on_remove(self.hub.async_add_listener(self._update_callback))

    def async_update_device_details(self):
        """Update the device details if it has changed."""

        device_registry: DeviceRegistry = self.hass.helpers.device_registry.async_get(
            self.hass
        )
        hub_device = device_registry.async_get_device(
            {(DOMAIN, self.client.host)}, set()
        )
        if not hub_device:
            return

        _LOGGER.debug("Updating via_device_id for %s", self.name)
        if not self.this_device:
            self.this_device = device_registry.async_get_device(
                {(DOMAIN, self.client.mac)}, set()
            )
        device_registry.async_update_device(
            self.this_device.id, via_device_id=hub_device.id
        )
        self.host = self.client.host

    @callback
    def _update_callback(self):
        """Update device state and related hub_id."""
        if self.client.host and self.host != self.client.host:
            self.async_update_device_details()
        self.async_write_ha_state()
