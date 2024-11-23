"""Support for Linksys Smart Wifi routers."""

from __future__ import annotations

from http import HTTPStatus
import logging

import requests
import base64
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

DEFAULT_TIMEOUT = 10
DEFAULT_USERNAME = "admin"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


def get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> LinksysSmartWifiDeviceScanner | None:
    """Validate the configuration and return a Linksys AP scanner."""
    try:
        return LinksysSmartWifiDeviceScanner(config[DEVICE_TRACKER_DOMAIN])
    except ConnectionError:
        return None


class LinksysSmartWifiDeviceScanner(DeviceScanner):
    """Class which queries a Linksys Access Point."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.auth = ""
        if CONF_PASSWORD in config:
            self.auth = "Basic " + base64.b64encode(
                f"{config[CONF_USERNAME]}:{config[CONF_PASSWORD]}".encode()
            ).decode("utf-8")
        self.last_results = {}

        # Check if the access point is accessible
        response = self._make_request()
        if response.status_code != HTTPStatus.OK:
            raise ConnectionError("Cannot connect to Linksys Access Point")
        data = response.json()
        if data["result"] != "OK":
            raise ConnectionError(
                "Linksys Access Point returned error - incorrect password?"
            )

    def scan_devices(self):
        """Scan for new devices and return a list with device IDs (MACs)."""
        self._update_info()

        return self.last_results.keys()

    def get_device_name(self, device):
        """Return the name (if known) of the device."""
        return self.last_results.get(device)

    def _update_info(self):
        """Check for connected devices."""
        _LOGGER.debug("Checking Linksys Smart Wifi")

        self.last_results = {}
        response = self._make_request()
        if response.status_code != HTTPStatus.OK:
            _LOGGER.error(
                "Got HTTP status code %d when getting device list", response.status_code
            )
            return False
        try:
            data = response.json()
            if data["result"] != "OK":
                _LOGGER.error("Error response when getting device list")
                return False
            responses = data["responses"][0]
            devices = responses["output"]["devices"]
            for device in devices:
                if not (macs := device["knownMACAddresses"]):
                    _LOGGER.warning("Skipping device without known MAC address")
                    continue
                mac = macs[-1]
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
        # Weirdly enough, this doesn't seem to require authentication
        data = [
            {
                "request": {"sinceRevision": 0},
                "action": "http://linksys.com/jnap/devicelist/GetDevices",
            }
        ]
        headers = {"X-JNAP-Action": "http://linksys.com/jnap/core/Transaction"}
        if self.auth:
            headers["X-JNAP-Authorization"] = self.auth
        return requests.post(
            f"http://{self.host}/JNAP/",
            timeout=DEFAULT_TIMEOUT,
            headers=headers,
            json=data,
        )
