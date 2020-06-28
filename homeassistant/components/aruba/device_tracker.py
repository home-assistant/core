"""Support for Aruba Access Points."""
import json
import logging
import re

import requests
from requests import Session
import pexpect
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

_DEVICES_REGEX = re.compile(
    r"(?P<name>([^\s]+)?)\s+"
    + r"(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\s+"
    + r"(?P<mac>([0-9a-f]{2}[:-]){5}([0-9a-f]{2}))\s+"
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)

DEFAULT_USE_API = False
DEFAULT_TIMEOUT = 10
USE_API = False
login_result_sid = ''

def get_scanner(hass, config):
    """Validate the configuration and return a Aruba scanner."""
    scanner = ArubaDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class ArubaDeviceScanner(DeviceScanner):
    """This class queries a Aruba Access Point for connected devices."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        global USE_API
        global login_result_sid

        self.last_results = {}

        # Test if we can use REST API
        # Aruba Instant API only likes double quotes in the json data and rejects single quotes
        login_data = '{"user": "' + self.username+ '", "passwd": "'+ self.password +'" }'
        login_headers = {'Content-Type': 'application/json' }
        login_method = "POST"
        login_resource = "https://" + self.host + ":4343/rest/login"

        rest_login = RestData(
            login_method,
            login_resource,
            login_headers,
            login_data,
            False,
            DEFAULT_TIMEOUT
        )
        rest_login.update()

        if rest_login.headers is not None:
            login_result_content_type = rest_login.headers.get("content-type")
            if login_result_content_type == "application/json":
                login_result_json = json.loads(rest_login.data)
                login_result_status = login_result_json.get("Status")
                if login_result_status == "Success":
                    USE_API = True
                    login_result_sid = login_result_json.get("sid")
                    _LOGGER.debug("Successfully logged in to Aruba Instant REST API")
                else:
                    USE_API = DEFAULT_USE_API
                    _LOGGER.debug("Error logging in to Aruba Instant REST API")

        data = self.get_aruba_data()
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
                return client["name"]
        return None

    def _update_info(self):
        """Ensure the information from the Aruba Access Point is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        data = self.get_aruba_data()
        if not data:
            return False

        self.last_results = data.values()
        return True

    def get_aruba_data(self):
        """Retrieve data from Aruba Access Point and return parsed result."""

        if USE_API == True:
            _LOGGER.debug("Using REST API")
            show_clients_data = ''
            show_clients_headers = {'Content-Type': 'application/json' }
            show_clients_method = "GET"
            show_clients_resource = "https://" + self.host + ":4343/rest/show-cmd?iap_ip_addr=" + self.host + "&cmd=show%20clients&sid=" + login_result_sid

            rest_show_clients = RestData(
                show_clients_method,
                show_clients_resource,
                show_clients_headers,
                show_clients_data,
                False,
                DEFAULT_TIMEOUT
            )
            rest_show_clients.update()

            if rest_show_clients.headers is not None:
                show_clients_result_content_type = rest_show_clients.headers.get("content-type")
                if show_clients_result_content_type == "application/json":
                    show_clients_result_json = json.loads(rest_show_clients.data)
                    show_clients_result_status = show_clients_result_json.get("Status")
                    if show_clients_result_status == "Success":
                        show_clients_result_command_output = show_clients_result_json.get("Command output")
                        show_clients_result_bytes = (json.dumps(show_clients_result_command_output)).encode()
                        devices_result = show_clients_result_bytes.split(b"\\n")
                    else:
                        _LOGGER.debug("Error getting client list via Aruba Instant REST API")
                        return

        else:
            _LOGGER.debug("Using SSH")
            connect = f"ssh {self.username}@{self.host}"
            ssh = pexpect.spawn(connect)
            query = ssh.expect(
                [
                    "password:",
                    pexpect.TIMEOUT,
                    pexpect.EOF,
                    "continue connecting (yes/no)?",
                    "Host key verification failed.",
                    "Connection refused",
                    "Connection timed out",
                ],
                timeout=120,
            )
            if query == 1:
                _LOGGER.error("Timeout")
                return
            if query == 2:
                _LOGGER.error("Unexpected response from router")
                return
            if query == 3:
                ssh.sendline("yes")
                ssh.expect("password:")
            elif query == 4:
                _LOGGER.error("Host key changed")
                return
            elif query == 5:
                _LOGGER.error("Connection refused by server")
                return
            elif query == 6:
                _LOGGER.error("Connection timed out")
                return
            ssh.sendline(self.password)
            ssh.expect("#")
            ssh.sendline("show clients")
            ssh.expect("#")
            devices_result = ssh.before.split(b"\r\n")
            ssh.sendline("exit")

        devices = {}
        for device in devices_result:
            match = _DEVICES_REGEX.search(device.decode("utf-8"))
            if match:
                devices[match.group("ip")] = {
                    "ip": match.group("ip"),
                    "mac": match.group("mac").upper(),
                    "name": match.group("name"),
                }
        return devices

class RestData:
    """Class for handling the data retrieval."""

    def __init__(
        self, method, resource, headers, data, verify_ssl, timeout=DEFAULT_TIMEOUT
    ):
        """Initialize the data object."""
        self._method = method
        self._resource = resource
        self._headers = headers
        self._request_data = data
        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self._http_session = Session()
        self.data = None
        self.headers = None

    def __del__(self):
        """Destroy the http session on destroy."""
        self._http_session.close()

    def update(self):
        """Get the latest data from REST service with provided method."""
        _LOGGER.debug("Updating from %s", self._resource)
        try:
            response = self._http_session.request(
                self._method,
                self._resource,
                headers=self._headers,
                data=self._request_data,
                timeout=self._timeout,
                verify=self._verify_ssl,
            )
            self.data = response.text
            self.headers = response.headers
        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Error fetching data: %s failed with %s", self._resource, ex)
            self.data = None
            self.headers = None
