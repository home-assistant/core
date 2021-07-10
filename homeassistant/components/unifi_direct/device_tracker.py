"""Support for Unifi AP direct access."""
import json
import logging

from pexpect import exceptions, pxssh
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSH_PORT = 22
UNIFI_COMMAND = 'mca-dump | tr -d "\n"'
UNIFI_SSID_TABLE = "vap_table"
UNIFI_CLIENT_TABLE = "sta_table"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_SSH_PORT): cv.port,
    }
)


def get_scanner(hass, config):
    """Validate the configuration and return a Unifi direct scanner."""
    scanner = UnifiDeviceScanner(config[DOMAIN])
    if not scanner.connected:
        return False
    return scanner


class UnifiDeviceScanner(DeviceScanner):
    """This class queries Unifi wireless access point."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.port = config[CONF_PORT]
        self.ssh = None
        self.connected = False
        self.last_results = {}
        self._connect()

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        result = _response_to_json(self._get_update())
        if result:
            self.last_results = result
        return self.last_results.keys()

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        hostname = next(
            (
                value.get("hostname")
                for key, value in self.last_results.items()
                if key.upper() == device.upper()
            ),
            None,
        )
        if hostname is not None:
            hostname = str(hostname)
        return hostname

    def _connect(self):
        """Connect to the Unifi AP SSH server."""

        self.ssh = pxssh.pxssh()
        try:
            self.ssh.login(
                self.host, self.username, password=self.password, port=self.port
            )
            self.connected = True
        except exceptions.EOF:
            _LOGGER.error("Connection refused. SSH enabled?")
            self._disconnect()

    def _disconnect(self):
        """Disconnect the current SSH connection."""
        try:
            self.ssh.logout()
        except Exception:  # pylint: disable=broad-except
            pass
        finally:
            self.ssh = None

        self.connected = False

    def _get_update(self):

        try:
            if not self.connected:
                self._connect()
            # If we still aren't connected at this point
            # don't try to send anything to the AP.
            if not self.connected:
                return None
            self.ssh.sendline(UNIFI_COMMAND)
            self.ssh.prompt()
            return self.ssh.before
        except pxssh.ExceptionPxssh as err:
            _LOGGER.error("Unexpected SSH error: %s", str(err))
            self._disconnect()
            return None
        except (AssertionError, exceptions.EOF) as err:
            _LOGGER.error("Connection to AP unavailable: %s", str(err))
            self._disconnect()
            return None


def _response_to_json(response):
    try:
        json_response = json.loads(str(response)[31:-1].replace("\\", ""))
        _LOGGER.debug(str(json_response))
        ssid_table = json_response.get(UNIFI_SSID_TABLE)
        active_clients = {}

        for ssid in ssid_table:
            client_table = ssid.get(UNIFI_CLIENT_TABLE)
            for client in client_table:
                active_clients[client.get("mac")] = client

        return active_clients
    except (ValueError, TypeError):
        _LOGGER.error("Failed to decode response from AP")
        return {}
