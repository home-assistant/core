"""Device tracker support for OPNsense routers."""

from collections.abc import Mapping
from typing import Any, NewType

from pyopnsense import diagnostics

from homeassistant.components.device_tracker import DeviceScanner
from homeassistant.components.device_tracker.legacy import (
    AsyncSeeCallback,
    async_setup_scanner_platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_INTERFACE_CLIENT, CONF_TRACKER_INTERFACES, DOMAIN

DeviceDetails = NewType("DeviceDetails", dict[str, Any])
DeviceDetailsByMAC = NewType("DeviceDetailsByMAC", dict[str, DeviceDetails])


def _resolve_runtime_data(
    hass: HomeAssistant, discovery_info: DiscoveryInfoType | None
) -> dict[str, Any] | None:
    """Resolve runtime data for a specific config entry when available."""
    if isinstance(discovery_info, Mapping) and isinstance(
        discovery_info.get("entry_id"), str
    ):
        if (
            entry := hass.config_entries.async_get_entry(discovery_info["entry_id"])
        ) is not None:
            runtime_data = getattr(entry, "runtime_data", None)
            if isinstance(runtime_data, dict):
                return runtime_data

    # Backward compatibility for legacy setup paths without entry_id.
    for entry in hass.config_entries.async_entries(DOMAIN):
        runtime_data = getattr(entry, "runtime_data", None)
        if isinstance(runtime_data, dict):
            return runtime_data

    return None


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up OPNsense scanner from discovered config entry."""
    runtime_data = _resolve_runtime_data(hass, discovery_info)
    if runtime_data is None:
        return False

    async_setup_scanner_platform(
        hass,
        config,
        OPNsenseDeviceScanner(
            runtime_data[CONF_INTERFACE_CLIENT],
            runtime_data[CONF_TRACKER_INTERFACES],
        ),
        async_see,
        DOMAIN,
    )
    return True


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
        """Ensure the information from the OPNsense router is up to date.

        Return boolean if scanning successful.
        """
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
