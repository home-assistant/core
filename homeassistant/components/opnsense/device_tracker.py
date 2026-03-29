"""Device tracker support for OPNsense routers."""

from __future__ import annotations

from typing import Any, NewType

from pyopnsense import diagnostics

from homeassistant.components.device_tracker import DeviceScanner
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_INTERFACE_CLIENT, CONF_TRACKER_INTERFACES, OPNSENSE_DATA

DeviceDetails = NewType("DeviceDetails", dict[str, Any])
DeviceDetailsByMAC = NewType("DeviceDetailsByMAC", dict[str, DeviceDetails])


async def async_get_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> DeviceScanner | None:
    """Configure the OPNsense device_tracker."""
    opnsense_data: dict[str, Any] = hass.data[OPNSENSE_DATA]

    if (
        isinstance(discovery_info, dict)
        and isinstance(discovery_info.get("entry_id"), str)
        and discovery_info["entry_id"] in opnsense_data
    ):
        entry_data = opnsense_data[discovery_info["entry_id"]]
    else:
        # Backward compatibility for any legacy test/setup path.
        entry_data = opnsense_data

    return OPNsenseDeviceScanner(
        entry_data[CONF_INTERFACE_CLIENT],
        entry_data[CONF_TRACKER_INTERFACES],
    )


class OPNsenseDeviceScanner(DeviceScanner):
    """This class queries a router running OPNsense."""

    def __init__(
        self, client: diagnostics.InterfaceClient, interfaces: list[str]
    ) -> None:
        """Initialize the scanner."""
        self.last_results: dict[str, Any] = {}
        self.client = client
        self.interfaces = interfaces

    def _get_mac_addrs(self, devices: list[DeviceDetails]) -> DeviceDetailsByMAC | dict:
        """Create dict with mac address keys from list of devices."""
        out_devices = {}
        for device in devices:
            if not self.interfaces or device["intf_description"] in self.interfaces:
                out_devices[device["mac"]] = device
        return out_devices

    def scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        self.update_info()
        return list(self.last_results)

    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        if device not in self.last_results:
            return None
        return self.last_results[device].get("hostname") or None

    def update_info(self) -> bool:
        """Ensure the information from the OPNsense router is up to date."""
        devices = self.client.get_arp()
        self.last_results = self._get_mac_addrs(devices)
        return True

    def get_extra_attributes(self, device: str) -> dict[Any, Any]:
        """Return the extra attrs of the given device."""
        if device not in self.last_results:
            return {}
        mfg = self.last_results[device].get("manufacturer")
        if not mfg:
            return {}
        return {"manufacturer": mfg}
