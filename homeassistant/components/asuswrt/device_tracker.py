"""Support for ASUSWRT routers."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

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

    def __init__(self, router: AsusWrtRouter, device) -> None:
        """Initialize a AsusWrt device."""
        self._router = router
        self._device = device

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._device.mac

    @property
    def name(self) -> str:
        """Return the name."""
        return self._device.name or DEFAULT_DEVICE_NAME

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self._device.is_connected

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes."""
        attrs = {}
        if self._device.last_activity:
            attrs["last_time_reachable"] = self._device.last_activity.isoformat(
                timespec="seconds"
            )
        return attrs

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

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        data = {
            "connections": {(CONNECTION_NETWORK_MAC, self._device.mac)},
        }
        if self._device.name:
            data["default_name"] = self._device.name

        return data

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self._device = self._router.devices[self._device.mac]
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
