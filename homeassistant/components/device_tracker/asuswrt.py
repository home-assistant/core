"""
Support for ASUSWRT routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.asuswrt/
"""
import logging
import re
import telnetlib
import threading
from datetime import timedelta

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pexpect==4.0.1']

_LEASES_CMD = 'cat /var/lib/misc/dnsmasq.leases'
_LEASES_REGEX = re.compile(
    r'\w+\s' +
    r'(?P<mac>(([0-9a-f]{2}[:-]){5}([0-9a-f]{2})))\s' +
    r'(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\s' +
    r'(?P<host>([^\s]+))')

_IP_NEIGH_CMD = 'ip neigh'
_IP_NEIGH_REGEX = re.compile(
    r'(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\s' +
    r'\w+\s' +
    r'\w+\s' +
    r'(\w+\s(?P<mac>(([0-9a-f]{2}[:-]){5}([0-9a-f]{2}))))?\s' +
    r'(?P<status>(\w+))')


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """Validate the configuration and return an ASUS-WRT scanner."""
    if not validate_config(config,
                           {DOMAIN: [CONF_HOST, CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return None

    scanner = AsusWrtDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class AsusWrtDeviceScanner(object):
    """This class queries a router running ASUSWRT firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = str(config[CONF_USERNAME])
        self.password = str(config[CONF_PASSWORD])
        self.protocol = config.get('protocol')

        self.lock = threading.Lock()

        self.last_results = {}

        # Test the router is accessible.
        data = self.get_asuswrt_data()
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client['mac'] for client in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results:
            if client['mac'] == device:
                return client['host']
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Ensure the information from the ASUSWRT router is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        with self.lock:
            _LOGGER.info("Checking ARP")
            data = self.get_asuswrt_data()
            if not data:
                return False

            active_clients = [client for client in data.values() if
                              client['status'] == 'REACHABLE' or
                              client['status'] == 'DELAY' or
                              client['status'] == 'STALE']
            self.last_results = active_clients
            return True

    def ssh_connection(self):
        """Retrieve data from ASUSWRT via the ssh protocol."""
        from pexpect import pxssh
        try:
            ssh = pxssh.pxssh()
            ssh.login(self.host, self.username, self.password)
            ssh.sendline(_IP_NEIGH_CMD)
            ssh.prompt()
            neighbors = ssh.before.split(b'\n')[1:-1]
            ssh.sendline(_LEASES_CMD)
            ssh.prompt()
            leases_result = ssh.before.split(b'\n')[1:-1]
            ssh.logout()
            return (neighbors, leases_result)
        except pxssh.ExceptionPxssh as exc:
            _LOGGER.exception('Unexpected response from router: %s', exc)
            return ('', '')

    def telnet_connection(self):
        """Retrieve data from ASUSWRT via the telnet protocol."""
        try:
            telnet = telnetlib.Telnet(self.host)
            telnet.read_until(b'login: ')
            telnet.write((self.username + '\n').encode('ascii'))
            telnet.read_until(b'Password: ')
            telnet.write((self.password + '\n').encode('ascii'))
            prompt_string = telnet.read_until(b'#').split(b'\n')[-1]
            telnet.write('{}\n'.format(_IP_NEIGH_CMD).encode('ascii'))
            neighbors = telnet.read_until(prompt_string).split(b'\n')[1:-1]
            telnet.write('{}\n'.format(_LEASES_CMD).encode('ascii'))
            leases_result = telnet.read_until(prompt_string).split(b'\n')[1:-1]
            telnet.write('exit\n'.encode('ascii'))
            return (neighbors, leases_result)
        except EOFError:
            _LOGGER.exception("Unexpected response from router")
            return ('', '')
        except ConnectionRefusedError:
            _LOGGER.exception("Connection refused by router,"
                              " is telnet enabled?")
            return ('', '')

    def get_asuswrt_data(self):
        """Retrieve data from ASUSWRT and return parsed result."""
        if self.protocol == 'telnet':
            neighbors, leases_result = self.telnet_connection()
        else:
            neighbors, leases_result = self.ssh_connection()

        devices = {}
        for lease in leases_result:
            match = _LEASES_REGEX.search(lease.decode('utf-8'))

            if not match:
                _LOGGER.warning("Could not parse lease row: %s", lease)
                continue

            # For leases where the client doesn't set a hostname, ensure it is
            # blank and not '*', which breaks the entity_id down the line.
            host = match.group('host')
            if host == '*':
                host = ''

            devices[match.group('ip')] = {
                'host': host,
                'status': '',
                'ip': match.group('ip'),
                'mac': match.group('mac').upper(),
                }

        for neighbor in neighbors:
            match = _IP_NEIGH_REGEX.search(neighbor.decode('utf-8'))
            if not match:
                _LOGGER.warning("Could not parse neighbor row: %s", neighbor)
                continue
            if match.group('ip') in devices:
                devices[match.group('ip')]['status'] = match.group('status')
        return devices
