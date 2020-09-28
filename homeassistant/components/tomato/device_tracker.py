"""Support for Tomato routers."""
import json
import logging
import re

import requests
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
    HTTP_OK,
    HTTP_UNAUTHORIZED,
)
import homeassistant.helpers.config_validation as cv

CONF_HTTP_ID = "http_id"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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


def get_scanner(hass, config):
    """Validate the configuration and returns a Tomato scanner."""
    return TomatoDeviceScanner(config[DOMAIN])


class TomatoDeviceScanner(DeviceScanner):
    """This class queries a wireless router running Tomato firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        host, http_id = config[CONF_HOST], config[CONF_HTTP_ID]
        port = config.get(CONF_PORT)
        username, password = config[CONF_USERNAME], config[CONF_PASSWORD]
        self.ssl, self.verify_ssl = config[CONF_SSL], config[CONF_VERIFY_SSL]
        if port is None:
            port = 443 if self.ssl else 80

        self.req = requests.Request(
            "POST",
            "http{}://{}:{}/update.cgi".format("s" if self.ssl else "", host, port),
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
        _LOGGER.info("Scanning")

        try:
            if self.ssl:
                response = requests.Session().send(
                    self.req, timeout=3, verify=self.verify_ssl
                )
            else:
                response = requests.Session().send(self.req, timeout=3)

            # Calling and parsing the Tomato api here. We only need the
            # wldev and dhcpd_lease values.
            if response.status_code == HTTP_OK:

                for param, value in self.parse_api_pattern.findall(response.text):

                    if param in ("wldev", "dhcpd_lease"):
                        self.last_results[param] = json.loads(value.replace("'", '"'))
                return True

            if response.status_code == HTTP_UNAUTHORIZED:
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
