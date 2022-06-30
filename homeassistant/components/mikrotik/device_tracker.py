"""Support for Mikrotik routers as device tracker."""
from __future__ import annotations

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import (
    DOMAIN as DEVICE_TRACKER,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .hub import MikrotikDataUpdateCoordinator

# These are normalized to ATTR_IP and ATTR_MAC to conform
# to device_tracker
FILTER_ATTRS = ("ip_address", "mac_address")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for Mikrotik component."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    tracked: dict[str, MikrotikDataUpdateCoordinatorTracker] = {}

    registry = entity_registry.async_get(hass)

    # Restore clients that is not a part of active clients list.
    for entity in registry.entities.values():

        if (
            entity.config_entry_id == config_entry.entry_id
            and entity.domain == DEVICE_TRACKER
        ):

            if (
                entity.unique_id in hub.api.devices
                or entity.unique_id not in hub.api.all_devices
            ):
                continue
            hub.api.restore_device(entity.unique_id)

    @callback
    def update_hub():
        """Update the status of the device."""
        update_items(hub, async_add_entities, tracked)

    config_entry.async_on_unload(hub.async_add_listener(update_hub))

    update_hub()


@callback
def update_items(hub, async_add_entities, tracked):
    """Update tracked device state from the hub."""
    new_tracked = []
    for mac, device in hub.api.devices.items():
        if mac not in tracked:
            tracked[mac] = MikrotikDataUpdateCoordinatorTracker(device, hub)
            new_tracked.append(tracked[mac])

    if new_tracked:
        async_add_entities(new_tracked)


class MikrotikDataUpdateCoordinatorTracker(CoordinatorEntity, ScannerEntity):
    """Representation of network device."""

    coordinator: MikrotikDataUpdateCoordinator

    def __init__(self, device, hub):
        """Initialize the tracked device."""
        super().__init__(hub)
        self.device = device

    @property
    def is_connected(self):
        """Return true if the client is connected to the network."""
        if (
            self.device.last_seen
            and (dt_util.utcnow() - self.device.last_seen)
            < self.coordinator.option_detection_time
        ):
            return True
        return False

    @property
    def source_type(self):
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def name(self) -> str:
        """Return the name of the client."""
        # Stringify to ensure we return a string
        return str(self.device.name)

    @property
    def hostname(self) -> str:
        """Return the hostname of the client."""
        return self.device.name

    @property
    def mac_address(self) -> str:
        """Return the mac address of the client."""
        return self.device.mac

    @property
    def ip_address(self) -> str:
        """Return the mac address of the client."""
        return self.device.ip_address

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return self.device.mac

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        if self.is_connected:
            return {k: v for k, v in self.device.attrs.items() if k not in FILTER_ATTRS}
        return None
