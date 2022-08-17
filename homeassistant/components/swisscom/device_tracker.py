"""Support for Swisscom routers (Internet-Box)."""
from __future__ import annotations

from contextlib import suppress
import logging

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DEFAULT_IP = "192.168.1.1"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_HOST, default=DEFAULT_IP): cv.string}
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> DeviceScanner | None:
    """Return the Swisscom device scanner."""
    scanner = SwisscomDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SwisscomDeviceScanner(DeviceScanner):
    """This class queries a router running Swisscom Internet-Box firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.last_results = {}

        # Test the router is accessible.
        data = self.get_swisscom_data()
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client["mac"] for client in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results:
            if client["mac"] == device:
                return client["host"]
        return None

    def _update_info(self):
        """Ensure the information from the Swisscom router is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Loading data from Swisscom Internet Box")
        if not (data := self.get_swisscom_data()):
            return False

        active_clients = [client for client in data.values() if client["status"]]
        self.last_results = active_clients
        return True

    def get_swisscom_data(self):
        """Retrieve data from Swisscom and return parsed result."""
        url = f"http://{self.host}/ws"
        headers = {"Content-Type": "application/x-sah-ws-4-call+json"}
        data = """
        {"service":"Devices", "method":"get",
        "parameters":{"expression":"lan and not self"}}"""

        devices = {}

        try:
            request = requests.post(url, headers=headers, data=data, timeout=10)
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectTimeout,
        ):
            _LOGGER.info("No response from Swisscom Internet Box")
            return devices

        if "status" not in request.json():
            _LOGGER.info("No status in response from Swisscom Internet Box")
            return devices

        for device in request.json()["status"]:
            with suppress(KeyError, requests.exceptions.RequestException):
                devices[device["Key"]] = {
                    "ip": device["IPAddress"],
                    "mac": device["PhysAddress"],
                    "host": device["Name"],
                    "status": device["Active"],
                }
        return devices
