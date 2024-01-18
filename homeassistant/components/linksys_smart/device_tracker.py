"""Support for Linksys Smart Wifi routers."""
from __future__ import annotations

from http import HTTPStatus
import logging

import requests
import voluptuous as vol

import base64

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend({vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PASSWORD): cv.string})


def get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> LinksysSmartWifiDeviceScanner | None:
    """Validate the configuration and return a Linksys AP scanner."""
    try:
        return LinksysSmartWifiDeviceScanner(config[DOMAIN])
    except ConnectionError:
        return None


class LinksysSmartWifiDeviceScanner(DeviceScanner):
    """Class which queries a Linksys Access Point."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.key = base64.b64encode(bytes("admin:" + config[CONF_PASSWORD], "utf-8")).decode("utf-8")
        self.last_results = {}

        # Check if the access point is accessible
        response = self._make_request()
        if response.status_code != HTTPStatus.OK:
            raise ConnectionError("Cannot connect to Linksys Access Point")

    def scan_devices(self):
        """Scan for new devices and return a list with device IDs (MACs)."""
        self._update_info()

        return self.last_results.keys()

    def get_device_name(self, device):
        """Return the name (if known) of the device."""
        return self.last_results.get(device)

    def _update_info(self):
        """Check for connected devices."""
        _LOGGER.info("Checking Linksys Smart Wifi")

        self.last_results = {}
        response = self._make_request()
        if response.status_code != HTTPStatus.OK:
            _LOGGER.error(
                "Got HTTP status code %d when getting device list", response.status_code
            )
            return False
        try:
            data = response.json()
            result = data["responses"][0]
            devices = result["output"]["devices"]
            for device in devices:
                if not (device["knownInterfaces"]):
                    _LOGGER.warning("Skipping device without known MAC address")
                    continue
                mac = device["knownInterfaces"][0]["macAddress"]
                if not device["connections"]:
                    _LOGGER.debug("Device %s is not connected", mac)
                    continue

                name = None
                for prop in device["properties"]:
                    if prop["name"] == "userDeviceName":
                        name = prop["value"]
                if not name:
                    name = device.get("friendlyName", device["deviceID"])

                _LOGGER.debug("Device %s is connected", mac)
                self.last_results[mac] = name
        except (KeyError, IndexError):
            _LOGGER.exception("Router returned unexpected response")
            return False
        return True

    def _make_request(self):
        # This endpoint now requires authentication.

        data = [
            {
                "request": {"sinceRevision": 0},
                "action": "http://linksys.com/jnap/devicelist/GetDevices3",
            }
        ]
        headers = {
            "X-JNAP-Action": "http://linksys.com/jnap/core/Transaction",
            "X-JNAP-Authorization": "Basic " + self.key
        }
        return requests.post(
            f"http://{self.host}/JNAP/",
            timeout=DEFAULT_TIMEOUT,
            headers=headers,
            json=data,
        )
