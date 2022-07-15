"""Device tracker support for OPNSense routers."""
from homeassistant.components.device_tracker import DeviceScanner
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import CONF_TRACKER_INTERFACE, OPNSENSE_DATA


async def async_get_scanner(hass: HomeAssistant, config: ConfigType) -> DeviceScanner:
    """Configure the OPNSense device_tracker."""
    interface_client = hass.data[OPNSENSE_DATA]["interfaces"]
    scanner = OPNSenseDeviceScanner(
        interface_client, hass.data[OPNSENSE_DATA][CONF_TRACKER_INTERFACE]
    )
    return scanner


class OPNSenseDeviceScanner(DeviceScanner):
    """This class queries a router running OPNsense."""

    def __init__(self, client, interfaces):
        """Initialize the scanner."""
        self.last_results = {}
        self.client = client
        self.interfaces = interfaces

    def _get_mac_addrs(self, devices):
        """Create dict with mac address keys from list of devices."""
        out_devices = {}
        for device in devices:
            if not self.interfaces:
                out_devices[device["mac"]] = device
            elif device["intf_description"] in self.interfaces:
                out_devices[device["mac"]] = device
        return out_devices

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self.update_info()
        return list(self.last_results)

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if device not in self.last_results:
            return None
        hostname = self.last_results[device].get("hostname") or None
        return hostname

    def update_info(self):
        """Ensure the information from the OPNSense router is up to date.

        Return boolean if scanning successful.
        """

        devices = self.client.get_arp()
        self.last_results = self._get_mac_addrs(devices)

    def get_extra_attributes(self, device):
        """Return the extra attrs of the given device."""
        if device not in self.last_results:
            return None
        if not (mfg := self.last_results[device].get("manufacturer")):
            return {}
        return {"manufacturer": mfg}
