"""Coordinator for OPNsense device tracker updates."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiopnsense import OPNsenseClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL
from .types import DeviceDetails, DeviceDetailsByMAC

if TYPE_CHECKING:
    from .device_tracker import OPNsenseDeviceTrackerEntity

_LOGGER = logging.getLogger(__name__)


class OPNsenseDeviceTrackerCoordinator(DataUpdateCoordinator):
    """Coordinator for OPNsense device tracker updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: OPNsenseClient,
        interfaces: list[str],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="OPNsense Device Tracker",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.interfaces = interfaces
        self.last_results: DeviceDetailsByMAC = {}
        self.tracked_devices: dict[str, OPNsenseDeviceTrackerEntity] = {}

    def _get_mac_addrs(self, devices: list[DeviceDetails]) -> DeviceDetailsByMAC:
        """Create dict with mac address keys from list of devices."""
        out_devices = {}
        for device in devices:
            if not self.interfaces or device["intf_description"] in self.interfaces:
                out_devices[device["mac"]] = device
        return out_devices

    async def _async_update_data(self) -> DeviceDetailsByMAC:
        """Fetch data from OPNsense."""
        try:
            devices = await self.client.get_arp_table(True)
            return self._get_mac_addrs(devices)
        except Exception as err:
            raise UpdateFailed(
                f"Error communicating with OPNsense router: {err}"
            ) from err

    @callback
    def async_update_listeners(self) -> None:
        """Update all registered listeners."""
        super().async_update_listeners()

        # Check for new devices
        current_macs = set(self.data.keys())
        tracked_macs = set(self.tracked_devices.keys())

        # Add new devices
        new_macs = current_macs - tracked_macs
        if new_macs:
            self.hass.async_create_task(self._async_add_new_devices(new_macs))

    async def _async_add_new_devices(self, new_macs: set[str]) -> None:
        """Add new device entities."""
        # This would typically be handled by async_setup_entry
        # For now, this is a placeholder for future dynamic device addition
