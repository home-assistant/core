"""Device tracker support for OPNsense routers."""

from typing import Any, NewType

from aiopnsense import OPNsenseClient

from homeassistant.components.device_tracker import DeviceScanner
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_TRACKER_INTERFACES, OPNSENSE_DATA

DeviceDetails = NewType("DeviceDetails", dict[str, Any])
DeviceDetailsByMAC = NewType("DeviceDetailsByMAC", dict[str, DeviceDetails])


async def async_get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> DeviceScanner | None:
    """Configure the OPNsense device_tracker."""
    return OPNsenseDeviceScanner(
        hass.data[OPNSENSE_DATA]["client"],
        hass.data[OPNSENSE_DATA][CONF_TRACKER_INTERFACES],
        hass.data[OPNSENSE_DATA]["interface_map"],
    )


class OPNsenseDeviceScanner(DeviceScanner):
    """This class queries a router running OPNsense."""

    def __init__(
        self,
        client: OPNsenseClient,
        interfaces: list[str],
        interface_map: dict[str, str],
    ) -> None:
        """Initialize the scanner."""
        self.last_results: dict[str, Any] = {}
        self.client = client
        self.interfaces = interfaces
        self.interface_map = interface_map

    def _get_mac_addrs(self, devices: list[DeviceDetails]) -> DeviceDetailsByMAC | dict:
        """Create dict with mac address keys from list of devices."""
        out_devices = {}
        for device in devices:
            if not self.interfaces:
                out_devices[device["mac-address"]] = device
            else:
                intf_description = self.interface_map.get(
                    device.get("interface", ""), ""
                )
                if intf_description in self.interfaces:
                    out_devices[device["mac-address"]] = device
        return out_devices

    async def async_scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        await self.async_update_info()
        return list(self.last_results)

    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        if device not in self.last_results:
            return None
        hostname = self.last_results[device].get("hostname")
        if not hostname or hostname == "?":
            return None
        return hostname

    async def async_update_info(self) -> bool:
        """Ensure the information from the OPNsense router is up to date.

        Return boolean if scanning successful.
        """
        devices = await self.client.get_arp_table()
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
