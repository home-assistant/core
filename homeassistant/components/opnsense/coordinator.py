"""Coordinator for OPNsense device tracker updates."""

import logging

from aiopnsense import (
    OPNsenseBelowMinFirmware,
    OPNsenseClient,
    OPNsenseConnectionError,
    OPNsenseInvalidAuth,
    OPNsenseInvalidURL,
    OPNsensePrivilegeMissing,
    OPNsenseSSLError,
    OPNsenseTimeoutError,
    OPNsenseUnknownFirmware,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL
from .types import DeviceDetails, DeviceDetailsByMAC, OPNsenseConfigEntry

_LOGGER = logging.getLogger(__name__)


class OPNsenseDeviceTrackerCoordinator(DataUpdateCoordinator[DeviceDetailsByMAC]):
    """Coordinator for OPNsense device tracker updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OPNsenseConfigEntry,
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
        self.tracked_devices: set[str] = set()

    def _get_mac_addrs(self, devices: list[DeviceDetails]) -> DeviceDetailsByMAC:
        """Create dict with mac address keys from list of devices."""
        out_devices: DeviceDetailsByMAC = {}
        for device in devices:
            if not self.interfaces or device["intf_description"] in self.interfaces:
                formatted_mac = format_mac(device["mac"])
                out_devices[formatted_mac] = device
        return out_devices

    async def _async_update_data(self) -> DeviceDetailsByMAC:
        """Fetch data from OPNsense."""
        try:
            devices = await self.client.get_arp_table(True)
        except (
            OPNsenseInvalidAuth,
            OPNsenseInvalidURL,
            OPNsensePrivilegeMissing,
            OPNsenseSSLError,
            OPNsenseBelowMinFirmware,
            OPNsenseUnknownFirmware,
        ) as err:
            raise ConfigEntryError(f"Error with OPNsense configuration: {err}") from err
        except (
            OPNsenseConnectionError,
            OPNsenseTimeoutError,
        ) as err:
            raise UpdateFailed(
                f"Error communicating with OPNsense router: {err}"
            ) from err

        return self._get_mac_addrs(devices)
