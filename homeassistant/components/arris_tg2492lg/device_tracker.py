"""Support for Arris TG2492LG router."""
import logging

from arris_tg2492lg import ConnectBox
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_IP = "http://192.168.178.1"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_IP): cv.string,
    }
)


def get_scanner(hass, config):
    """Return the Arris device scanner."""
    conf = config[DOMAIN]
    connect_box = ConnectBox(conf[CONF_HOST], conf[CONF_PASSWORD])
    return ArrisDeviceScanner(connect_box)


class ArrisDeviceScanner(DeviceScanner):
    """This class queries a Arrus TG2492LG router for connected devices."""

    def __init__(self, connect_box):
        """Initialize the scanner."""
        self.connect_box: ConnectBox = connect_box

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        devices = self.connect_box.get_connected_devices()

        def filter_online(device):
            return device.online is True

        def map_mac_address(device):
            return device.mac

        # filter online devices
        online_devices = list(filter(filter_online, devices))

        # show only mac address
        mac_addresses = list(map(map_mac_address, online_devices))

        # remove duplicates as some devices are returned with ipv4 and ipv6
        return list(set(mac_addresses))

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        return None
