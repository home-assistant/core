"""Coordinator for OPNsense device tracker updates."""

from datetime import timedelta
import logging
from typing import Any, override

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

from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL, get_firmware_privilege_issue_id
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

    @override
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


class OPNsenseFirmwareCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll OPNsense for router firmware updates."""

    def __init__(
        self, hass: HomeAssistant, entry: OPNsenseConfigEntry, client: OPNsenseClient
    ) -> None:
        """Initialize the firmware coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="OPNsense firmware",
            update_interval=timedelta(hours=1),
            config_entry=entry,
        )
        self.entry = entry
        self.client = client

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch firmware status."""
        try:
            firmware_info = await self.client.get_firmware_update_info()
        except OPNsensePrivilegeMissing:
            ir.async_create_issue(
                self.hass,
                self.entry.domain,
                get_firmware_privilege_issue_id(self.entry.entry_id),
                is_fixable=False,
                is_persistent=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="firmware_privilege_missing",
                translation_placeholders={
                    "url": self.entry.data[CONF_URL],
                },
            )
            return {}
        except (OPNsenseConnectionError, OPNsenseTimeoutError) as err:
            raise UpdateFailed(
                f"Error communicating with OPNsense router: {err}"
            ) from err
        if firmware_info is None:
            raise UpdateFailed("No firmware information returned by OPNsense")
        ir.async_delete_issue(
            self.hass,
            self.entry.domain,
            get_firmware_privilege_issue_id(self.entry.entry_id),
        )
        return dict(firmware_info)
