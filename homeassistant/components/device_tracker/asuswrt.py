"""
Support for ASUSWRT routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.asuswrt/
"""
import asyncio
import logging
import re
from collections import namedtuple

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_PORT, CONF_MODE,
    CONF_PROTOCOL)

REQUIREMENTS = ['asyncssh==1.14.0']

_LOGGER = logging.getLogger(__name__)

CONF_PUB_KEY = 'pub_key'
CONF_SSH_KEY = 'ssh_key'
CONF_REQUIRE_IP = 'require_ip'
DEFAULT_SSH_PORT = 22
SECRET_GROUP = 'Password or SSH Key'

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_PASSWORD, CONF_PUB_KEY, CONF_SSH_KEY),
    PLATFORM_SCHEMA.extend({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PROTOCOL, default='ssh'): vol.In(['ssh', 'telnet']),
        vol.Optional(CONF_MODE, default='router'): vol.In(['router', 'ap']),
        vol.Optional(CONF_PORT, default=DEFAULT_SSH_PORT): cv.port,
        vol.Optional(CONF_REQUIRE_IP, default=True): cv.boolean,
        vol.Exclusive(CONF_PASSWORD, SECRET_GROUP): cv.string,
        vol.Exclusive(CONF_SSH_KEY, SECRET_GROUP): cv.isfile,
        vol.Exclusive(CONF_PUB_KEY, SECRET_GROUP): cv.isfile
    }))


_LEASES_CMD = 'cat /var/lib/misc/dnsmasq.leases'
_LEASES_REGEX = re.compile(
    r'\w+\s' +
    r'(?P<mac>(([0-9a-f]{2}[:-]){5}([0-9a-f]{2})))\s' +
    r'(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\s' +
    r'(?P<host>([^\s]+))')

# Command to get both 5GHz and 2.4GHz clients
_WL_CMD = 'for dev in `nvram get wl_ifnames`; do wl -i $dev assoclist; done'
_WL_REGEX = re.compile(
    r'\w+\s' +
    r'(?P<mac>(([0-9A-F]{2}[:-]){5}([0-9A-F]{2})))')

_IP_NEIGH_CMD = 'ip neigh'
_IP_NEIGH_REGEX = re.compile(
    r'(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3}|'
    r'([0-9a-fA-F]{1,4}:){1,7}[0-9a-fA-F]{0,4}(:[0-9a-fA-F]{1,4}){1,7})\s'
    r'\w+\s'
    r'\w+\s'
    r'(\w+\s(?P<mac>(([0-9a-f]{2}[:-]){5}([0-9a-f]{2}))))?\s'
    r'\s?(router)?'
    r'\s?(nud)?'
    r'(?P<status>(\w+))')

_ARP_CMD = 'arp -n'
_ARP_REGEX = re.compile(
    r'.+\s' +
    r'\((?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\)\s' +
    r'.+\s' +
    r'(?P<mac>(([0-9a-f]{2}[:-]){5}([0-9a-f]{2})))' +
    r'\s' +
    r'.*')


async def async_get_scanner(hass, config):
    """Validate the configuration and return an ASUS-WRT scanner."""
    scanner = AsusWrtDeviceScanner(config[DOMAIN])
    await scanner.async_connect()
    return scanner if scanner.success_init else None


def _parse_lines(lines, regex):
    """Parse the lines using the given regular expression.

    If a line can't be parsed it is logged and skipped in the output.
    """
    results = []
    for line in lines:
        match = regex.search(line)
        if not match:
            _LOGGER.debug("Could not parse row: %s", line)
            continue
        results.append(match.groupdict())
    return results


Device = namedtuple('Device', ['mac', 'ip', 'name'])


class AsusWrtDeviceScanner(DeviceScanner):
    """This class queries a router running ASUSWRT firmware."""

    # Eighth attribute needed for mode (AP mode vs router mode)
    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config.get(CONF_PASSWORD, '')
        self.ssh_key = config.get('ssh_key', config.get('pub_key', ''))
        self.protocol = config[CONF_PROTOCOL]
        self.mode = config[CONF_MODE]
        self.port = config[CONF_PORT]
        self.require_ip = config[CONF_REQUIRE_IP]
        self.last_results = {}
        self.success_init = False
        self.connection = None

    async def async_connect(self):
        """Setup connection."""
        if self.protocol == 'ssh':
            self.connection = SshConnection(
                self.host, self.port, self.username, self.password,
                self.ssh_key)
        else:
            self.connection = TelnetConnection(
                self.host, self.port, self.username, self.password)

        self.last_results = {}

        # Test the router is accessible.
        data = await self.async_get_asuswrt_data()
        self.success_init = data is not None

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self.async_update_info()
        return list(self.last_results.keys())

    async def async_get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if device not in self.last_results:
            return None
        return self.last_results[device].name

    async def async_update_info(self):
        """Ensure the information from the ASUSWRT router is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info('Checking Devices')
        data = await self.async_get_asuswrt_data()
        if not data:
            return False

        self.last_results = data
        return True

    async def async_get_asuswrt_data(self):
        """Retrieve data from ASUSWRT.

        Calls various commands on the router and returns the superset of all
        responses. Some commands will not work on some routers.
        """
        devices = {}
        devices.update(await self.async_get_wl())
        devices.update(await self.async_get_arp())
        devices.update(await self.async_get_neigh(devices))
        if not self.mode == 'ap':
            devices.update(await self.async_get_leases(devices))

        ret_devices = {}
        for key in devices:
            if not self.require_ip or devices[key].ip is not None:
                ret_devices[key] = devices[key]
        return ret_devices

    async def async_get_wl(self):
        lines = await self.connection.async_run_command(_WL_CMD)
        if not lines:
            return {}
        result = _parse_lines(lines, _WL_REGEX)
        devices = {}
        for device in result:
            mac = device['mac'].upper()
            devices[mac] = Device(mac, None, None)
        return devices

    async def async_get_leases(self, cur_devices):
        lines = await self.connection.async_run_command(_LEASES_CMD)
        if not lines:
            return {}
        lines = [line for line in lines if not line.startswith('duid ')]
        result = _parse_lines(lines, _LEASES_REGEX)
        devices = {}
        for device in result:
            # For leases where the client doesn't set a hostname, ensure it
            # is blank and not '*', which breaks entity_id down the line.
            host = device['host']
            if host == '*':
                host = ''
            mac = device['mac'].upper()
            if mac in cur_devices:
                devices[mac] = Device(mac, device['ip'], host)
        return devices

    async def async_get_neigh(self, cur_devices):
        lines = await self.connection.async_run_command(_IP_NEIGH_CMD)
        if not lines:
            return {}
        result = _parse_lines(lines, _IP_NEIGH_REGEX)
        devices = {}
        for device in result:
            status = device['status']
            if status is None or status.upper() != 'REACHABLE':
                continue
            if device['mac'] is not None:
                mac = device['mac'].upper()
                old_device = cur_devices.get(mac)
                old_ip = old_device.ip if old_device else None
                devices[mac] = Device(mac, device.get('ip', old_ip), None)
        return devices

    async def async_get_arp(self):
        lines = await self.connection.async_run_command(_ARP_CMD)
        if not lines:
            return {}
        result = _parse_lines(lines, _ARP_REGEX)
        devices = {}
        for device in result:
            if device['mac'] is not None:
                mac = device['mac'].upper()
                devices[mac] = Device(mac, device['ip'], None)
        return devices


class SshConnection:
    """Maintains an SSH connection to an ASUS-WRT router."""

    def __init__(self, host, port, username, password, ssh_key):
        """Initialize the SSH connection properties."""

        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ssh_key = ssh_key
        self._client = None

    async def async_run_command(self, command):
        """Run commands through an SSH connection.

        Connect to the SSH server if not currently connected, otherwise
        use the existing connection.
        """
        await self.async_init_session()
        result = await self._client.run(command)
        return result.stdout.split('\n')

    async def async_init_session(self):
        """Fetches the client or creates a new one."""
        import asyncssh
        kwargs = {
            'username': self._username if self._username else None,
            'client_keys': [self._ssh_key] if self._ssh_key else None,
            'port': self._port,
            'password': self._password if self._password else None
        }

        if not self._client:
            self._client = await asyncssh.connect(self._host, **kwargs)


class TelnetConnection:
    """Maintains a Telnet connection to an ASUS-WRT router."""

    def __init__(self, host, port, username, password):
        """Initialize the Telnet connection properties."""

        self._reader = None
        self._writer = None
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._prompt_string = None
        self.connected = False

    async def async_run_command(self, command):
        """Run a command through a Telnet connection.
        Connect to the Telnet server if not currently connected, otherwise
        use the existing connection.
        """
        if not self.connected:
            await self.async_connect()
        await self._writer.write('{}\n'.format(command).encode('ascii'))
        data = ((await self._reader.readuntil(self._prompt_string)).
                split(b'\n')[1:-1])
        return [line.decode('utf-8') for line in data]

    async def async_connect(self):
        """Connect to the ASUS-WRT Telnet server."""
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port)
        await self._reader.readuntil(b'login: ')
        await self._writer.write((self._username + '\n').encode('ascii'))
        await self._reader.readuntil(b'Password: ')
        await self._writer.write((self._password + '\n').encode('ascii'))
        self._prompt_string = await self._reader.readuntil(
            b'#').split(b'\n')[-1]
        self.connected = True
