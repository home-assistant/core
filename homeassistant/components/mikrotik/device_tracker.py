"""Support for Mikrotik routers as device tracker."""
from __future__ import annotations

import logging

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceEntry,
    DeviceRegistry,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
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

    # Restore clients that are not a part of active clients list.
    entity_registry = hass.helpers.entity_registry.async_get(hass)
    hub_clients: list[
        RegistryEntry
    ] = hass.helpers.entity_registry.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    for entity in hub_clients:
        if entity.unique_id not in hub.data:
            hub.data.append(entity.unique_id)
            all_clients[entity.unique_id] = MikrotikClient(
                entity.unique_id, name=entity.original_name
            )

    @callback
    def update_hub() -> None:
        """Update the status of the device."""
        update_items(hub, tracked, all_clients, async_add_entities)

    config_entry.async_on_unload(hub.async_add_listener(update_hub))

    update_hub()


@callback
def update_items(
    hub: MikrotikHub,
    tracked: dict[str, MikrotikClientTracker],
    all_clients: dict[str, MikrotikClient],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Update tracked device state from the hub."""
    new_tracked = []
    for mac in hub.data:
        if mac not in tracked:
            tracked[mac] = MikrotikClientTracker(mac, hub, all_clients)
            new_tracked.append(tracked[mac])

    if new_tracked:
        async_add_entities(new_tracked)


class MikrotikClientTracker(CoordinatorEntity, ScannerEntity):
    """Representation of network device."""

    coordinator: MikrotikHub

    def __init__(
        self, mac: str, coordinator: MikrotikHub, all_clients: dict[str, MikrotikClient]
    ) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self.mac = mac
        self.all_clients = all_clients
        self.host: str | None = all_clients[mac].host
        self.this_device: DeviceEntry | None = None
        self._attr_name = self.all_clients[self.mac].name
        self._attr_unique_id = self.mac

    @property
    def is_connected(self) -> bool:
        """Return true if the client is connected to the network."""
        last_seen = self.all_clients[self.mac].last_seen
        if last_seen is not None:
            return (
                dt_util.utcnow() - last_seen
            ) < self.coordinator.option_detection_time
        return False

    @property
    def source_type(self) -> str:
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def hostname(self) -> str | None:
        """Return the hostname of the client."""
        return self.all_clients[self.mac].name

    @property
    def mac_address(self) -> str:
        """Return the mac address of the client."""
        return self.mac

    @property
    def ip_address(self) -> str | None:
        """Return the mac address of the client."""
        return self.all_clients[self.mac].ip_address

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return the device state attributes."""
        return self.all_clients[self.mac].attrs if self.is_connected else None

    @property
    def device_info(self) -> DeviceInfo:
        """Return a client description for device registry."""
        device_info: DeviceInfo = {
            "connections": {(CONNECTION_NETWORK_MAC, self.mac)},
            "identifiers": {(DOMAIN, self.mac)},
        }
        if self.host is not None:
            device_info["via_device"] = (DOMAIN, self.host)
        if self.name is not None:
            device_info["name"] = self.name
        return device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self.all_clients[self.mac].host
            and self.host != self.all_clients[self.mac].host
        ):
            self.async_update_device_details()
        self.async_write_ha_state()

    def async_update_device_details(self):
        """Update the device details if it has changed."""

        device_registry: DeviceRegistry = self.hass.helpers.device_registry.async_get(
            self.hass
        )
        hub_device = device_registry.async_get_device(
            {(DOMAIN, self.all_clients[self.mac].host)}, set()
        )
        if not hub_device:
            return

        _LOGGER.debug("Updating via_device_id for %s", self.name)
        if self.this_device is None:
            self.this_device = device_registry.async_get_device(
                {(DOMAIN, self.mac)}, set()
            )
        device_registry.async_update_device(
            self.this_device.id, via_device_id=hub_device.id
        )
        self.host = self.all_clients[self.mac].host
