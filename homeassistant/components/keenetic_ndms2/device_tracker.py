"""Support for Keenetic routers as device tracker."""
from __future__ import annotations

import logging

from ndms2_client import Device

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN, ROUTER
from .router import KeeneticRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for Keenetic NDMS2 component."""
    router: KeeneticRouter = hass.data[DOMAIN][config_entry.entry_id][ROUTER]

    tracked: set[str] = set()

    @callback
    def update_from_router():
        """Update the status of devices."""
        update_items(router, async_add_entities, tracked)

    update_from_router()

    registry = entity_registry.async_get(hass)
    # Restore devices that are not a part of active clients list.
    restored = []
    for entity_entry in registry.entities.values():
        if (
            entity_entry.config_entry_id == config_entry.entry_id
            and entity_entry.domain == DEVICE_TRACKER_DOMAIN
        ):
            mac = entity_entry.unique_id.partition("_")[0]
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


@callback
def update_items(router: KeeneticRouter, async_add_entities, tracked: set[str]):
    """Update tracked device state from the hub."""
    new_tracked: list[KeeneticTracker] = []
    for mac, device in router.last_devices.items():
        if mac not in tracked:
            tracked.add(mac)
            new_tracked.append(KeeneticTracker(device, router))

    if new_tracked:
        async_add_entities(new_tracked)


class KeeneticTracker(ScannerEntity):
    """Representation of network device."""

    def __init__(self, device: Device, router: KeeneticRouter) -> None:
        """Initialize the tracked device."""
        self._device = device
        self._router = router
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
            < self._router.consider_home_interval
        )

    @property
    def source_type(self):
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device.name or self._device.mac

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"{self._device.mac}_{self._router.config_entry.entry_id}"

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self._device.ip if self.is_connected else None

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._device.mac

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self._router.available

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        if self.is_connected:
            return {
                "interface": self._device.interface,
            }
        return None

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
            new_device = self._router.last_devices.get(self._device.mac)
            if new_device:
                self._device = new_device
                self._last_seen = dt_util.utcnow()

            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._router.signal_update, update_device
            )
        )
