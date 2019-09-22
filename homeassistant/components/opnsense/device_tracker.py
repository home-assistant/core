"""Device tracker support for OPNSense routers."""
import logging

from homeassistant.components.device_tracker import DeviceScanner

from homeassistant.components.opnsense import OPNSENSE_DATA

_LOGGER = logging.getLogger(__name__)


async def async_get_scanner(hass, config, tracker_interfaces=None):
    """Configure the OPNSense device_tracker."""
    interface_client = hass.data[OPNSENSE_DATA]["interfaces"]
    interfaces = tracker_interfaces or ["LAN"]
    scanner = OPNSenseDeviceScanner(interface_client, interfaces)
    return scanner


class OPNSenseDeviceScanner(DeviceScanner):
    """This class queries a router running ASUSWRT firmware."""

    # Eighth attribute needed for mode (AP mode vs router mode)
    def __init__(self, client, interfaces):
        """Initialize the scanner."""
        self.last_results = {}
        self.success_init = False
        self.client = client
        self.interfaces = interfaces

    def _get_mac_addrs(self, devices):
        out_devices = {}
        for device in devices:
            if device["intf_description"] in self.interfaces:
                out_devices[device["mac"]] = device
        return out_devices

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self.update_info()
        return list(self.last_results.keys())

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
        _LOGGER.info("Checking Devices")

        devices = self.client.get_arp()
        self.last_results = self._get_mac_addrs(devices)
        return True

    def get_extra_attributes(self, device):
        """Return the extra attrs of the given device."""
        if device not in self.last_results:
            return None
        mfg = self.last_results[device].get("manufacturer")
        if mfg:
            return {"manufacturer": mfg}
        return {}
