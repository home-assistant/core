"""Device tracker support for OPNsense routers."""
from homeassistant.components.device_tracker import DeviceScanner

from .const import CONF_TRACKER_INTERFACE, OPNSENSE_DATA


async def async_get_scanner(hass, config, discovery_info=None):
    """Configure the OPNsense device_tracker."""
    scanner = OPNsenseDeviceScanner(
        hass.data[OPNSENSE_DATA]["interface_client"],
        hass.data[OPNSENSE_DATA][CONF_TRACKER_INTERFACE],
    )
    return scanner


class OPNsenseDeviceScanner(DeviceScanner):
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
        """Ensure the information from the OPNsense router is up to date.

        Return boolean if scanning successful.
        """

        devices = self.client.get_arp()
        self.last_results = self._get_mac_addrs(devices)

    def get_extra_attributes(self, device):
        """Return the extra attrs of the given device."""
        if device not in self.last_results:
            return None
        mfg = self.last_results[device].get("manufacturer")
        if not mfg:
            return {}
        return {"manufacturer": mfg}
