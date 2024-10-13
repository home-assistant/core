"""Support for Tomato routers."""

from __future__ import annotations

from http import HTTPStatus
import json
import logging
import re

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
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
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

CONF_HTTP_ID = "http_id"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): vol.Any(cv.boolean, cv.isfile),
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_HTTP_ID): cv.string,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> TomatoDeviceScanner:
    """Validate the configuration and returns a Tomato scanner."""
    return TomatoDeviceScanner(config[DEVICE_TRACKER_DOMAIN])


class TomatoDeviceScanner(DeviceScanner):
    """Class which queries a wireless router running Tomato firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        host, http_id = config[CONF_HOST], config[CONF_HTTP_ID]
        port = config.get(CONF_PORT)
        username, password = config[CONF_USERNAME], config[CONF_PASSWORD]
        self.ssl, self.verify_ssl = config[CONF_SSL], config[CONF_VERIFY_SSL]
        if port is None:
            port = 443 if self.ssl else 80

        protocol = "https" if self.ssl else "http"
        self.req = requests.Request(
            "POST",
            f"{protocol}://{host}:{port}/update.cgi",
            data={"_http_id": http_id, "exec": "devlist"},
            auth=requests.auth.HTTPBasicAuth(username, password),
        ).prepare()

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")

        self.last_results = {"wldev": [], "dhcpd_lease": []}

        self.success_init = self._update_tomato_info()

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_tomato_info()

        return [item[1] for item in self.last_results["wldev"]]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        filter_named = [
            item[0] for item in self.last_results["dhcpd_lease"] if item[2] == device
        ]

        if not filter_named or not filter_named[0]:
            return None

        return filter_named[0]

    def _update_tomato_info(self):
        """Ensure the information from the Tomato router is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.debug("Scanning")

        try:
            if self.ssl:
                response = requests.Session().send(
                    self.req, timeout=60, verify=self.verify_ssl
                )
            else:
                response = requests.Session().send(self.req, timeout=60)

            # Calling and parsing the Tomato api here. We only need the
            # wldev and dhcpd_lease values.
            if response.status_code == HTTPStatus.OK:
                for param, value in self.parse_api_pattern.findall(response.text):
                    if param in ("wldev", "dhcpd_lease"):
                        self.last_results[param] = json.loads(value.replace("'", '"'))
                return True

            if response.status_code == HTTPStatus.UNAUTHORIZED:
                # Authentication error
                _LOGGER.exception(
                    "Failed to authenticate, please check your username and password"
                )
                return False

        except requests.exceptions.ConnectionError:
            # We get this if we could not connect to the router or
            # an invalid http_id was supplied.
            _LOGGER.exception(
                "Failed to connect to the router or invalid http_id supplied"
            )
            return False

        except requests.exceptions.Timeout:
            # We get this if we could not connect to the router or
            # an invalid http_id was supplied.
            _LOGGER.exception("Connection to the router timed out")
            return False

        except ValueError:
            # If JSON decoder could not parse the response.
            _LOGGER.exception("Failed to parse response from router")
            return False
