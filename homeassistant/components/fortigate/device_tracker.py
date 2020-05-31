"""Device tracker for Fortigate firewalls."""
from collections import namedtuple
import logging

from homeassistant.components.device_tracker import DeviceScanner

from . import DATA_FGT

_LOGGER = logging.getLogger(__name__)

DETECTED_DEVICES = "/monitor/user/detected-device"


async def async_get_scanner(hass, config):
    """Validate the configuration and return a Fortigate scanner."""
    scanner = FortigateDeviceScanner(hass.data[DATA_FGT])
    await scanner.async_connect()
    return scanner if scanner.success_init else None


Device = namedtuple("Device", ["hostname", "mac"])


def _build_device(device_dict):
    """Return a Device from data."""
    return Device(device_dict["hostname"], device_dict["mac"])


class FortigateDeviceScanner(DeviceScanner):
    """Query the Fortigate firewall."""

    def __init__(self, hass_data):
        """Initialize the scanner."""
        self.last_results = {}
        self.success_init = False
        self.connection = hass_data["fgt"]
        self.devices = hass_data["devices"]

    def get_results(self):
        """Get the results from the Fortigate."""
        results = self.connection.get(DETECTED_DEVICES, "vdom=root")[1]["results"]

        ret = []
        for result in results:
            if "hostname" not in result:
                continue

            ret.append(result)

        return ret

    async def async_connect(self):
        """Initialize connection to the router."""
        # Test if the firewall is accessible
        data = self.get_results()
        self.success_init = data is not None

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device MACs."""
        await self.async_update_info()
        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        name = next(
            (result.hostname for result in self.last_results if result.mac == device),
            None,
        )
        return name

    async def async_update_info(self):
        """Ensure the information from the Fortigate firewall is up to date."""
        _LOGGER.debug("Checking devices")

        hosts = self.get_results()

        all_results = [_build_device(device) for device in hosts if device["is_online"]]

        # If the 'devices' configuration field is filled
        if self.devices is not None:
            last_results = [
                device for device in all_results if device.hostname in self.devices
            ]
            _LOGGER.debug(last_results)
        # If the 'devices' configuration field is not filled
        else:
            last_results = all_results

        self.last_results = last_results
