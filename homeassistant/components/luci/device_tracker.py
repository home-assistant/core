"""Support for OpenWRT (luci) routers."""
import logging

from openwrt_luci_rpc import OpenWrtRpc
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def get_scanner(hass, config):
    """Validate the configuration and return a Luci scanner."""
    scanner = LuciDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class LuciDeviceScanner(DeviceScanner):
    """This class scans for devices connected to an OpenWrt router."""

    def __init__(self, config):
        """Initialize the scanner."""

        self.router = OpenWrtRpc(
            config[CONF_HOST],
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            config[CONF_SSL],
            config[CONF_VERIFY_SSL],
        )

        self.last_results = {}
        self.success_init = self.router.is_logged_in()

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        name = next(
            (result.hostname for result in self.last_results if result.mac == device),
            None,
        )
        return name

    def get_extra_attributes(self, device):
        """
        Get extra attributes of a device.

        Some known extra attributes that may be returned in the device tuple
        include MAC address (mac), network device (dev), IP address
        (ip), reachable status (reachable), associated router
        (host), hostname if known (hostname) among others.
        """
        device = next(
            (result for result in self.last_results if result.mac == device), None
        )
        return device._asdict()

    def _update_info(self):
        """Check the Luci router for devices."""
        result = self.router.get_all_connected_devices(only_reachable=True)

        _LOGGER.debug("Luci get_all_connected_devices returned: %s", result)

        last_results = []
        for device in result:
            last_results.append(device)

        self.last_results = last_results
