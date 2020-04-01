"""Support for Salt Fiber Box routers."""
import logging

from saltbox import RouterLoginException, RouterNotReachableException, SaltBox
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def get_scanner(hass, config):
    """Return the Salt device scanner."""
    scanner = SaltDeviceScanner(config[DOMAIN])

    # Test whether the router is accessible.
    data = scanner.get_salt_data()
    return scanner if data is not None else None


class SaltDeviceScanner(DeviceScanner):
    """This class queries a Salt Fiber Box router."""

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        username = config[CONF_USERNAME]
        password = config[CONF_PASSWORD]
        self.saltbox = SaltBox(f"http://{host}", username, password)
        self.online_clients = []

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client["mac"] for client in self.online_clients]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        for client in self.online_clients:
            if client["mac"] == device:
                return client["name"]
        return None

    def get_salt_data(self):
        """Retrieve data from Salt router and return parsed result."""
        try:
            clients = self.saltbox.get_online_clients()
            return clients
        except (RouterLoginException, RouterNotReachableException) as error:
            _LOGGER.warning(error)
            return None

    def _update_info(self):
        """Pull the current information from the Salt router."""
        _LOGGER.debug("Loading data from Salt Fiber Box")
        data = self.get_salt_data()
        self.online_clients = data or []
