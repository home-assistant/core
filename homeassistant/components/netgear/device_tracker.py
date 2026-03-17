"""Support for Netgear routers."""

from __future__ import annotations

import logging

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEVICE_ICONS
from .coordinator import NetgearConfigEntry, NetgearTrackerCoordinator
from .entity import NetgearDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetgearConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for Netgear component."""
    router = entry.runtime_data.router
    coordinator_tracker = entry.runtime_data.coordinator_tracker
    tracked = set()

    @callback
    def new_device_callback() -> None:
        """Add new devices if needed."""
        if not coordinator_tracker.data:
            return

        new_entities = []

        for mac, device in router.devices.items():
            if mac in tracked:
                continue

            new_entities.append(NetgearScannerEntity(coordinator_tracker, device))
            tracked.add(mac)

        async_add_entities(new_entities)

    entry.async_on_unload(coordinator_tracker.async_add_listener(new_device_callback))

    coordinator_tracker.data = True
    new_device_callback()


class NetgearScannerEntity(NetgearDeviceEntity, ScannerEntity):
    """Representation of a device connected to a Netgear router."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: NetgearTrackerCoordinator,
        device: dict,
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(coordinator, device)
        self._hostname = self.get_hostname()
        self._icon = DEVICE_ICONS.get(device["device_type"], "mdi:help-network")
        self._attr_name = self._device_name

    def get_hostname(self) -> str | None:
        """Return the hostname of the given device or None if we don't know."""
        if (hostname := self._device["name"]) == "--":
            return None

        return hostname

    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""
        self._device = self._router.devices[self._mac]
        self._active = self._device["active"]
        self._icon = DEVICE_ICONS.get(self._device["device_type"], "mdi:help-network")

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the router."""
        return self._active

    @property
    def ip_address(self) -> str:
        """Return the IP address."""
        return self._device["ip"]

    @property
    def mac_address(self) -> str:
        """Return the mac address."""
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Return the hostname."""
        return self._hostname

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon
