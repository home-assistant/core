"""
Support for ASUSWRT routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.asuswrt/
"""
import logging
import re
import socket
import telnetlib
import threading
from collections import namedtuple
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

CONF_PROTOCOL = 'protocol'
CONF_MODE = 'mode'
CONF_SSH_KEY = 'ssh_key'
CONF_PUB_KEY = 'pub_key'
SECRET_GROUP = 'Password or SSH Key'

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_PASSWORD, CONF_PUB_KEY, CONF_SSH_KEY),
    PLATFORM_SCHEMA.extend({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PROTOCOL, default='ssh'):
            vol.In(['ssh', 'telnet']),
        vol.Optional(CONF_MODE, default='router'):
            vol.In(['router', 'ap']),
        vol.Exclusive(CONF_PASSWORD, SECRET_GROUP): cv.string,
        vol.Exclusive(CONF_SSH_KEY, SECRET_GROUP): cv.isfile,
        vol.Exclusive(CONF_PUB_KEY, SECRET_GROUP): cv.isfile
    }))


_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pexpect==4.0.1']

_LEASES_CMD = 'cat /var/lib/misc/dnsmasq.leases'
_LEASES_REGEX = re.compile(
    r'\w+\s' +
    r'(?P<mac>(([0-9a-f]{2}[:-]){5}([0-9a-f]{2})))\s' +
    r'(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\s' +
    r'(?P<host>([^\s]+))')

# command to get both 5GHz and 2.4GHz clients
_WL_CMD = '{ wl -i eth2 assoclist & wl -i eth1 assoclist ; }'
_WL_REGEX = re.compile(
    r'\w+\s' +
    r'(?P<mac>(([0-9A-F]{2}[:-]){5}([0-9A-F]{2})))')

_ARP_CMD = 'arp -n'
_ARP_REGEX = re.compile(
    r'.+\s' +
    r'\((?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})\)\s' +
    r'.+\s' +
    r'(?P<mac>(([0-9a-f]{2}[:-]){5}([0-9a-f]{2})))' +
    r'\s' +
    r'.*')

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
    scanner = AsusWrtDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None

AsusWrtResult = namedtuple('AsusWrtResult', 'neighbors leases arp')


class AsusWrtDeviceScanner(object):
    """This class queries a router running ASUSWRT firmware."""

    # pylint: disable=too-many-instance-attributes, too-many-branches
    # Eighth attribute needed for mode (AP mode vs router mode)

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config.get(CONF_PASSWORD, '')
        self.ssh_key = config.get('ssh_key', config.get('pub_key', ''))
        self.protocol = config[CONF_PROTOCOL]
        self.mode = config[CONF_MODE]

        if self.protocol == 'ssh':
            if self.ssh_key:
                self.ssh_secret = {'ssh_key': self.ssh_key}
            elif self.password:
                self.ssh_secret = {'password': self.password}
            else:
                _LOGGER.error('No password or private key specified')
                self.success_init = False
                return
        else:
            if not self.password:
                _LOGGER.error('No password specified')
                self.success_init = False
                return

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
            _LOGGER.info('Checking ARP')
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
        from pexpect import pxssh, exceptions

        ssh = pxssh.pxssh()
        try:
            ssh.login(self.host, self.username, **self.ssh_secret)
        except exceptions.EOF as err:
            _LOGGER.error('Connection refused. Is SSH enabled?')
            return None
        except pxssh.ExceptionPxssh as err:
            _LOGGER.error('Unable to connect via SSH: %s', str(err))
            return None

        try:
            ssh.sendline(_IP_NEIGH_CMD)
            ssh.prompt()
            neighbors = ssh.before.split(b'\n')[1:-1]
            if self.mode == 'ap':
                ssh.sendline(_ARP_CMD)
                ssh.prompt()
                arp_result = ssh.before.split(b'\n')[1:-1]
                ssh.sendline(_WL_CMD)
                ssh.prompt()
                leases_result = ssh.before.split(b'\n')[1:-1]
            else:
                arp_result = ['']
                ssh.sendline(_LEASES_CMD)
                ssh.prompt()
                leases_result = ssh.before.split(b'\n')[1:-1]
            ssh.logout()
            return AsusWrtResult(neighbors, leases_result, arp_result)
        except pxssh.ExceptionPxssh as exc:
            _LOGGER.error('Unexpected response from router: %s', exc)
            return None

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
            if self.mode == 'ap':
                telnet.write('{}\n'.format(_ARP_CMD).encode('ascii'))
                arp_result = (telnet.read_until(prompt_string).
                              split(b'\n')[1:-1])
                telnet.write('{}\n'.format(_WL_CMD).encode('ascii'))
                leases_result = (telnet.read_until(prompt_string).
                                 split(b'\n')[1:-1])
            else:
                arp_result = ['']
                telnet.write('{}\n'.format(_LEASES_CMD).encode('ascii'))
                leases_result = (telnet.read_until(prompt_string).
                                 split(b'\n')[1:-1])
            telnet.write('exit\n'.encode('ascii'))
            return AsusWrtResult(neighbors, leases_result, arp_result)
        except EOFError:
            _LOGGER.error('Unexpected response from router')
            return None
        except ConnectionRefusedError:
            _LOGGER.error('Connection refused by router, is telnet enabled?')
            return None
        except socket.gaierror as exc:
            _LOGGER.error('Socket exception: %s', exc)
            return None
        except OSError as exc:
            _LOGGER.error('OSError: %s', exc)
            return None

    def get_asuswrt_data(self):
        """Retrieve data from ASUSWRT and return parsed result."""
        if self.protocol == 'ssh':
            result = self.ssh_connection()
        elif self.protocol == 'telnet':
            result = self.telnet_connection()
        else:
            # autodetect protocol
            result = self.ssh_connection()
            if result:
                self.protocol = 'ssh'
            else:
                result = self.telnet_connection()
                if result:
                    self.protocol = 'telnet'

        if not result:
            return {}

        devices = {}
        if self.mode == 'ap':
            for lease in result.leases:
                match = _WL_REGEX.search(lease.decode('utf-8'))

                if not match:
                    _LOGGER.warning('Could not parse wl row: %s', lease)
                    continue

                host = ''

                # match mac addresses to IP addresses in ARP table
                for arp in result.arp:
                    if match.group('mac').lower() in arp.decode('utf-8'):
                        arp_match = _ARP_REGEX.search(arp.decode('utf-8'))
                        if not arp_match:
                            _LOGGER.warning('Could not parse arp row: %s', arp)
                            continue

                        devices[arp_match.group('ip')] = {
                            'host': host,
                            'status': '',
                            'ip': arp_match.group('ip'),
                            'mac': match.group('mac').upper(),
                            }
        else:
            for lease in result.leases:
                match = _LEASES_REGEX.search(lease.decode('utf-8'))

                if not match:
                    _LOGGER.warning('Could not parse lease row: %s', lease)
                    continue

                # For leases where the client doesn't set a hostname, ensure it
                # is blank and not '*', which breaks entity_id down the line.
                host = match.group('host')
                if host == '*':
                    host = ''

                devices[match.group('ip')] = {
                    'host': host,
                    'status': '',
                    'ip': match.group('ip'),
                    'mac': match.group('mac').upper(),
                    }

        for neighbor in result.neighbors:
            match = _IP_NEIGH_REGEX.search(neighbor.decode('utf-8'))
            if not match:
                _LOGGER.warning('Could not parse neighbor row: %s', neighbor)
                continue
            if match.group('ip') in devices:
                devices[match.group('ip')]['status'] = match.group('status')
        return devices
