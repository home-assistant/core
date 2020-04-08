"""Device tracker for Synology SRM routers."""
import logging

import synology_srm
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_USERNAME = "admin"
DEFAULT_PORT = 8001
DEFAULT_SSL = True
DEFAULT_VERIFY_SSL = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def get_scanner(hass, config):
    """Validate the configuration and return Synology SRM scanner."""
    scanner = SynologySrmDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SynologySrmDeviceScanner(DeviceScanner):
    """This class scans for devices connected to a Synology SRM router."""

    def __init__(self, config):
        """Initialize the scanner."""

        self.client = synology_srm.Client(
            host=config[CONF_HOST],
            port=config[CONF_PORT],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            https=config[CONF_SSL],
        )

        if not config[CONF_VERIFY_SSL]:
            self.client.http.disable_https_verify()

        self.last_results = []
        self.success_init = self._update_info()

        _LOGGER.info("Synology SRM scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device["mac"] for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        filter_named = [
            result["hostname"]
            for result in self.last_results
            if result["mac"] == device
        ]

        if filter_named:
            return filter_named[0]

        return None

    def _update_info(self):
        """Check the router for connected devices."""
        _LOGGER.debug("Scanning for connected devices")

        devices = self.client.core.network_nsm_device({"is_online": True})
        last_results = []

        for device in devices:
            last_results.append({"mac": device["mac"], "hostname": device["hostname"]})

        _LOGGER.debug("Found %d device(s) connected to the router", len(devices))

        self.last_results = last_results
        return True
