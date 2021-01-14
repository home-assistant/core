"""Support for Keenetic routers as device tracker."""
import logging
from typing import List, Set

from ndms2_client import Device

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .router import KeeneticRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up device tracker for Keenetic NDMS2 component."""
    router: KeeneticRouter = hass.data[DOMAIN][config_entry.entry_id]

    tracked = set()

    @callback
    def update_from_router():
        """Update the status of devices."""
        update_items(router, async_add_entities, tracked)

    update_from_router()

    registry = await entity_registry.async_get_registry(hass)
    # Restore devices that are not a part of active clients list.
    restored = []
    for entity_entry in registry.entities.values():
        if (
            entity_entry.config_entry_id == config_entry.entry_id
            and entity_entry.domain == DEVICE_TRACKER_DOMAIN
        ):
            mac = entity_entry.unique_id.partition("@")[0]
            if mac not in tracked:
                tracked.add(mac)
                restored.append(
                    KeeneticTracker(
                        Device(
                            mac=mac,
                            # restore the original name as set by the router before
                            name=entity_entry.original_name,
                            ip=None,
                            interface=None,
                        ),
                        router,
                    )
                )

    if restored:
        async_add_entities(restored)

    async_dispatcher_connect(hass, router.signal_update, update_from_router)

    return True


@callback
def update_items(router: KeeneticRouter, async_add_entities, tracked: Set[str]):
    """Update tracked device state from the hub."""
    new_tracked: List[KeeneticTracker] = []
    for mac, device in router.last_devices.items():
        if mac not in tracked:
            tracked.add(mac)
            new_tracked.append(KeeneticTracker(device, router))

    if new_tracked:
        async_add_entities(new_tracked)


class KeeneticTracker(ScannerEntity):
    """Representation of network device."""

    def __init__(self, device: Device, router: KeeneticRouter):
        """Initialize the tracked device."""
        self.device = device
        self.router = router
        self._last_seen = (
            dt_util.utcnow() if device.mac in router.last_devices else None
        )

    @property
    def should_poll(self) -> bool:
        """Return False since entity pushes its state to HA."""
        return False

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return (
            self._last_seen
            and (dt_util.utcnow() - self._last_seen)
            < self.router.consider_home_interval
        )

    @property
    def source_type(self):
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device.name or self.device.mac

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"{self.device.mac}@{self.router.config_entry.entry_id}"

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self.router.available

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.is_connected:
            return {
                "ip": self.device.ip,
                "interface": self.device.interface,
            }
        return None

    @property
    def device_info(self):
        """Return a client description for device registry."""
        info = {
            "connections": {(CONNECTION_NETWORK_MAC, self.device.mac)},
            "identifiers": {(DOMAIN, self.device.mac)},
        }

        if self.device.name:
            info["name"] = self.device.name

        return info

    async def async_added_to_hass(self):
        """Client entity created."""
        _LOGGER.debug("New network device tracker %s (%s)", self.name, self.unique_id)

        @callback
        def update_device():
            _LOGGER.debug(
                "Updating Keenetic tracked device %s (%s)",
                self.entity_id,
                self.unique_id,
            )
            new_device = self.router.last_devices.get(self.device.mac)
            if new_device:
                self.device = new_device
                self._last_seen = dt_util.utcnow()

            self.async_schedule_update_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.router.signal_update, update_device
            )
        )
