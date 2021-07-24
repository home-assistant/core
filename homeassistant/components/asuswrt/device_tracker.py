"""Support for ASUSWRT routers."""
from __future__ import annotations

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_ASUSWRT, DOMAIN
from .router import AsusWrtRouter

DEFAULT_DEVICE_NAME = "Unknown device"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up device tracker for AsusWrt component."""
    router = hass.data[DOMAIN][entry.entry_id][DATA_ASUSWRT]
    tracked = set()

    @callback
    def update_router():
        """Update the values of the router."""
        add_entities(router, async_add_entities, tracked)

    router.async_on_close(
        async_dispatcher_connect(hass, router.signal_device_new, update_router)
    )

    update_router()


@callback
def add_entities(router, async_add_entities, tracked):
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac, device in router.devices.items():
        if mac in tracked:
            continue

        new_tracked.append(AsusWrtDevice(router, device))
        tracked.add(mac)

    if new_tracked:
        async_add_entities(new_tracked)


class AsusWrtDevice(ScannerEntity):
    """Representation of a AsusWrt device."""

    _attr_should_poll = False

    def __init__(self, router: AsusWrtRouter, device) -> None:
        """Initialize a AsusWrt device."""
        self._router = router
        self._device = device
        self._attr_unique_id = device.mac
        self._attr_name = device.name or DEFAULT_DEVICE_NAME

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self._device.is_connected

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def hostname(self) -> str:
        """Return the hostname of device."""
        return self._device.name

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self._device.ip_address

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._device.mac

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self._device = self._router.devices[self._device.mac]
        self._attr_device_info = {
            "connections": {(CONNECTION_NETWORK_MAC, self._device.mac)},
        }
        if self._device.name:
            self._attr_device_info["default_name"] = self._device.name
        self._attr_extra_state_attributes = {}
        if self._device.last_activity:
            self._attr_extra_state_attributes[
                "last_time_reachable"
            ] = self._device.last_activity.isoformat(timespec="seconds")
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_device_update,
                self.async_on_demand_update,
            )
        )
