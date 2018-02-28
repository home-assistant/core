"""Support for Linksys Smart Wifi routers."""
import logging

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST

DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
})


def get_scanner(hass, config):
    """Validate the configuration and return a Linksys AP scanner."""
    try:
        return LinksysSmartWifiDeviceScanner(config[DOMAIN])
    except ConnectionError:
        return None


class LinksysSmartWifiDeviceScanner(DeviceScanner):
    """This class queries a Linksys Access Point."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.last_results = {}

        # Check if the access point is accessible
        response = self._make_request()
        if not response.status_code == 200:
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
        if response.status_code != 200:
            _LOGGER.error(
                "Got HTTP status code %d when getting device list",
                response.status_code)
            return False
        try:
            data = response.json()
            result = data["responses"][0]
            devices = result["output"]["devices"]
            for device in devices:
                macs = device["knownMACAddresses"]
                if not macs:
                    _LOGGER.warning(
                        "Skipping device without known MAC address")
                    continue
                mac = macs[-1]
                connections = device["connections"]
                if not connections:
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
        data = [{
            "request": {
                "sinceRevision": 0
            },
            "action": "http://linksys.com/jnap/devicelist/GetDevices"
        }]
        headers = {"X-JNAP-Action": "http://linksys.com/jnap/core/Transaction"}
        return requests.post('http://{}/JNAP/'.format(self.host),
                             timeout=DEFAULT_TIMEOUT,
                             headers=headers,
                             json=data)
