"""Support for Verizon FiOS Quantum Gateways."""
from __future__ import annotations

import logging

from quantum_gateway import QuantumGatewayScanner
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "myfiosgateway.com"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_SSL, default=True): cv.boolean,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> QuantumGatewayDeviceScanner | None:
    """Validate the configuration and return a Quantum Gateway scanner."""
    scanner = QuantumGatewayDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class QuantumGatewayDeviceScanner(DeviceScanner):
    """Class which queries a Quantum Gateway."""

    def __init__(self, config):
        """Initialize the scanner."""

        self.host = config[CONF_HOST]
        self.password = config[CONF_PASSWORD]
        self.use_https = config[CONF_SSL]
        _LOGGER.debug("Initializing")

        try:
            self.quantum = QuantumGatewayScanner(
                self.host, self.password, self.use_https
            )
            self.success_init = self.quantum.success_init
        except RequestException:
            self.success_init = False
            _LOGGER.error("Unable to connect to gateway. Check host")

        if not self.success_init:
            _LOGGER.error("Unable to login to gateway. Check password and host")

    def scan_devices(self):
        """Scan for new devices and return a list of found MACs."""
        connected_devices = []
        try:
            connected_devices = self.quantum.scan_devices()
        except RequestException:
            _LOGGER.error("Unable to scan devices. Check connection to router")
        return connected_devices

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        return self.quantum.get_device_name(device)
