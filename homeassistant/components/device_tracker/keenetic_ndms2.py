"""
Support for Zyxel Keenetic NDMS2 based routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.keenetic_ndms2/
"""
import logging
import telnetlib
import re
from collections import namedtuple

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_PASSWORD, CONF_USERNAME
)

_LOGGER = logging.getLogger(__name__)

# Interface name to track devices for. Most likely one will not need to
# change it from default 'Home'. This is needed not to track Guest WI-FI-
# clients and router itself
CONF_INTERFACE = 'interface'

DEFAULT_INTERFACE = 'Home'
DEFAULT_PORT = 23


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_INTERFACE, default=DEFAULT_INTERFACE): cv.string,
})


_ARP_CMD = 'show ip arp'
_ARP_REGEX = re.compile(
    r'(?P<name>([^\ ]+))\s+' +
    r'(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\s+' +
    r'(?P<mac>(([0-9a-f]{2}[:-]){5}([0-9a-f]{2})))\s+' +
    r'(?P<interface>([^\ ]+))\s+'
)


def get_scanner(_hass, config):
    """Validate the configuration and return a Nmap scanner."""
    scanner = KeeneticNDMS2DeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


def _parse_lines(lines, regex):
    """Parse the lines using the given regular expression.

    If a line can't be parsed it is logged and skipped in the output.
    """
    results = []
    for line in lines:
        match = regex.search(line)
        if not match:
            _LOGGER.debug("Could not parse line: %s", line)
            continue
        results.append(match.groupdict())
    return results


Device = namedtuple('Device', ['mac', 'name', 'ip'])


class KeeneticNDMS2DeviceScanner(DeviceScanner):
    """This class scans for devices using keenetic NDMS2 web interface."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = []

        self._host = config[CONF_HOST]
        self._port = config[CONF_PORT]
        self._interface = config[CONF_INTERFACE]

        self._username = config.get(CONF_USERNAME)
        self._password = config.get(CONF_PASSWORD)

        self.connection = TelnetConnection(
            self._host,
            self._port,
            self._username,
            self._password,
        )

        self.success_init = self._update_info()
        _LOGGER.info("Scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, mac):
        """Return the name of the given device or None if we don't know."""
        filter_name = [device.name for device in self.last_results
                       if device.mac == mac]

        if filter_name:
            return filter_name[0]
        return None

    def get_extra_attributes(self, device):
        """Return the IP of the given device."""
        filter_ip = [result.ip for result in self.last_results
                     if result.mac == device]
        if filter_ip:
            return {'ip': filter_ip[0]}
        return {'ip': None}

    def _update_info(self):
        """Get ARP from keenetic router."""
        _LOGGER.info("Fetching...")

        last_results = []

        lines = self.connection.run_command(_ARP_CMD)
        if not lines:
            return False

        result = _parse_lines(lines, _ARP_REGEX)

        for info in result:
            if info.get('interface') != self._interface:
                continue
            mac = info.get('mac')
            name = info.get('name')
            ip = info.get('ip')
            # No address = no item :)
            if mac is None:
                continue

            last_results.append(Device(mac.upper(), name, ip))

        self.last_results = last_results

        _LOGGER.info("Request successful")
        return True


class TelnetConnection(object):
    """Maintains a Telnet connection to a router."""

    def __init__(self, host, port, username, password):
        """Initialize the Telnet connection properties."""

        self._connected = False
        self._telnet = None
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._prompt_string = None

    def run_command(self, command):
        """Run a command through a Telnet connection.

        Connect to the Telnet server if not currently connected, otherwise
        use the existing connection.
        """
        try:
            if not self._telnet:
                self.connect()

            self._telnet.write('{}\n'.format(command).encode('ascii'))
            return self._telnet.read_until(self._prompt_string, 30)\
                .decode('ascii')\
                .split('\n')[1:-1]
        except Exception as e:
            _LOGGER.error("Telnet error: $s", e)
            self.disconnect()
            return None

    def connect(self):
        """Connect to the ASUS-WRT Telnet server."""
        self._telnet = telnetlib.Telnet(self._host)
        self._telnet.read_until(b'Login: ', 30)
        self._telnet.write((self._username + '\n').encode('ascii'))
        self._telnet.read_until(b'Password: ', 30)
        self._telnet.write((self._password + '\n').encode('ascii'))
        self._prompt_string = self._telnet.read_until(b'>').split(b'\n')[-1]

        self._connected = True

    def disconnect(self):
        """Disconnect the current Telnet connection."""
        try:
            self._telnet.write(b'exit\n')
        except Exception as e:
            _LOGGER.error("Telnet error on exit: $s", e)
            pass

        self._telnet = None
