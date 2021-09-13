"""Support for French FAI Bouygues Bbox routers."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BboxCoordinator, BboxScannedDevice
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up device tracker for Freebox component."""
    router: BboxCoordinator = hass.data[DOMAIN][entry.entry_id]
    tracked: set[str] = set()

    @callback
    def update_router():
        """Update the values of the router."""
        add_entities(router, async_add_entities, tracked)

    router.listeners.append(
        async_dispatcher_connect(hass, router.signal_device_new, update_router)
    )

    update_router()


@callback
def add_entities(
    router: BboxCoordinator, async_add_entities: AddEntitiesCallback, tracked: set[str]
) -> None:
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac, device in router.scanned_devices.items():
        if mac not in tracked:
            new_tracked.append(BboxDevice(router, device))
            tracked.add(mac)

    if new_tracked:
        async_add_entities(new_tracked, True)


class BboxDevice(ScannerEntity):
    """Representation of a Freebox device."""

    def __init__(self, router: BboxCoordinator, device: BboxScannedDevice) -> None:
        """Initialize a Freebox device."""
        self._router = router
        self._name = device["hostname"]
        self._mac = device["mac_addr"]
        self._device_info = device["device_info"]
        # self._manufacturer = device["vendor_name"]
        self._icon = "mdi:help-network"
        self._active = False
        self._attrs: dict[str, Any] = {}

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox device."""
        device = self._router.scanned_devices[self._mac]
        self._active = device["active"]
        self._attrs = {"last_time_seen": device["last_seen"], "mac_address": self._mac}

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._mac

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self._active

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes."""
        return self._attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._device_info

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Do NOT enable the entity unless the user requires it."""
        return False

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_device_update,
                self.async_on_demand_update,
            )
        )
