import logging

import hashlib
from http.cookies import SimpleCookie
import json
import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (DOMAIN, PLATFORM_SCHEMA,
                                                     DeviceScanner)
from homeassistant.const import (CONF_HOST, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['quantum-gateway==0.0.2']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'myfiosgateway.com'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string
})


def get_scanner(hass, config):
    scanner = QuantumGatewayDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class QuantumGatewayDeviceScanner(DeviceScanner):

    def __init__(self, config):
        from quantum_gateway import QuantumGatewayScanner
        
        self.host = config[CONF_HOST]
        self.password = config[CONF_PASSWORD]
        _LOGGER.info("Initializing")

        self.quantum = QuantumGatewayScanner(self.host, self.password)

        self.success_init = self.quantum.success_init

        if not self.success_init:
            _LOGGER.error("Unable to login to gateway. Check password and host.")

    def scan_devices(self):
        return self.quantum.scan_devices()

    def get_device_name(self, device):
        return self.quantum.get_device_name(device)
