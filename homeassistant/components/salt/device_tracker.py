"""Support for Salt Fiber Box routers."""
import logging

from saltbox import SaltBox
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_IP = "192.168.1.1"
DEFAULT_USERNAME = "admin"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_IP): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def get_scanner(hass, config):
    """Return the Salt device scanner."""
    scanner = SaltDeviceScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


class SaltDeviceScanner(DeviceScanner):
    """This class queries a Salt Fiber Box router."""

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        username = config[CONF_USERNAME]
        password = config[CONF_PASSWORD]
        self.saltbox = SaltBox(f"http://{host}", username, password)
        self.online_clients = []

        # Test the router is accessible.
        data = self.get_salt_data()
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client["mac"] for client in self.online_clients]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.online_clients:
            return None
        for client in self.online_clients:
            if client["mac"] == device:
                return client["name"]
        return None

    def _update_info(self):
        """Pull the current information from the Salt router."""
        if not self.success_init:
            return False

        _LOGGER.info("Loading data from Salt Fiber Box")
        data = self.get_salt_data()
        if not data:
            return False

        self.online_clients = data
        return True

    def get_salt_data(self):
        """Retrieve data from Salt router and return parsed result."""
        try:
            return self.saltbox.get_online_clients()
        except:  # noqa: E722  # pylint: disable=bare-except
            _LOGGER.info("Could not get data from Salt Fiber Box")
        return self.online_clients
