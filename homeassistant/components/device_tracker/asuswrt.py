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

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_PORT)
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pexpect==4.0.1']

_LOGGER = logging.getLogger(__name__)

CONF_MODE = 'mode'
CONF_PROTOCOL = 'protocol'
CONF_PUB_KEY = 'pub_key'
CONF_SSH_KEY = 'ssh_key'

DEFAULT_SSH_PORT = 22

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

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
        vol.Optional(CONF_PORT, default=DEFAULT_SSH_PORT): cv.port,
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
    r'(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3}|'
    r'([0-9a-fA-F]{1,4}:){1,7}[0-9a-fA-F]{0,4}(:[0-9a-fA-F]{1,4}){1,7})\s'
    r'\w+\s'
    r'\w+\s'
    r'(\w+\s(?P<mac>(([0-9a-f]{2}[:-]){5}([0-9a-f]{2}))))?\s'
    r'\s?(router)?'
    r'(?P<status>(\w+))')

_NVRAM_CMD = 'nvram get client_info_tmp'
_NVRAM_REGEX = re.compile(
    r'.*>.*>' +
    r'(?P<ip>([0-9]{1,3}[\.]){3}[0-9]{1,3})' +
    r'>' +
    r'(?P<mac>(([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})))' +
    r'>' +
    r'.*')


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """Validate the configuration and return an ASUS-WRT scanner."""
    scanner = AsusWrtDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


AsusWrtResult = namedtuple('AsusWrtResult', 'neighbors leases arp nvram')


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

        if self.protocol == 'ssh':
            if not (self.ssh_key or self.password):
                _LOGGER.error("No password or private key specified")
                self.success_init = False
                return

            self.connection = SshConnection(self.host, self.port,
                                            self.username,
                                            self.password,
                                            self.ssh_key,
                                            self.mode == "ap")
        else:
            if not self.password:
                _LOGGER.error("No password specified")
                self.success_init = False
                return

            self.connection = TelnetConnection(self.host, self.port,
                                               self.username,
                                               self.password,
                                               self.mode == "ap")

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
                              client['status'] == 'STALE' or
                              client['status'] == 'IN_NVRAM']
            self.last_results = active_clients
            return True

    def get_asuswrt_data(self):
        """Retrieve data from ASUSWRT and return parsed result."""
        result = self.connection.get_result()

        if not result:
            return {}

        devices = {}
        if self.mode == 'ap':
            for lease in result.leases:
                match = _WL_REGEX.search(lease.decode('utf-8'))

                if not match:
                    _LOGGER.warning("Could not parse wl row: %s", lease)
                    continue

                host = ''

                # match mac addresses to IP addresses in ARP table
                for arp in result.arp:
                    if match.group('mac').lower() in \
                            arp.decode('utf-8').lower():
                        arp_match = _ARP_REGEX.search(
                            arp.decode('utf-8').lower())
                        if not arp_match:
                            _LOGGER.warning("Could not parse arp row: %s", arp)
                            continue

                        devices[arp_match.group('ip')] = {
                            'host': host,
                            'status': '',
                            'ip': arp_match.group('ip'),
                            'mac': match.group('mac').upper(),
                            }

                # match mac addresses to IP addresses in NVRAM table
                for nvr in result.nvram:
                    if match.group('mac').upper() in nvr.decode('utf-8'):
                        nvram_match = _NVRAM_REGEX.search(nvr.decode('utf-8'))
                        if not nvram_match:
                            _LOGGER.warning("Could not parse nvr row: %s", nvr)
                            continue

                        # skip current check if already in ARP table
                        if nvram_match.group('ip') in devices.keys():
                            continue

                        devices[nvram_match.group('ip')] = {
                            'host': host,
                            'status': 'IN_NVRAM',
                            'ip': nvram_match.group('ip'),
                            'mac': match.group('mac').upper(),
                            }

        else:
            for lease in result.leases:
                if lease.startswith(b'duid '):
                    continue
                match = _LEASES_REGEX.search(lease.decode('utf-8'))

                if not match:
                    _LOGGER.warning("Could not parse lease row: %s", lease)
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
                _LOGGER.warning("Could not parse neighbor row: %s", neighbor)
                continue
            if match.group('ip') in devices:
                devices[match.group('ip')]['status'] = match.group('status')
        return devices


class _Connection:
    def __init__(self):
        self._connected = False

    @property
    def connected(self):
        """Return connection state."""
        return self._connected

    def connect(self):
        """Mark currenct connection state as connected."""
        self._connected = True

    def disconnect(self):
        """Mark current connection state as disconnected."""
        self._connected = False


class SshConnection(_Connection):
    """Maintains an SSH connection to an ASUS-WRT router."""

    def __init__(self, host, port, username, password, ssh_key, ap):
        """Initialize the SSH connection properties."""
        super(SshConnection, self).__init__()

        self._ssh = None
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ssh_key = ssh_key
        self._ap = ap

    def get_result(self):
        """Retrieve a single AsusWrtResult through an SSH connection.

        Connect to the SSH server if not currently connected, otherwise
        use the existing connection.
        """
        from pexpect import pxssh, exceptions

        try:
            if not self.connected:
                self.connect()
            self._ssh.sendline(_IP_NEIGH_CMD)
            self._ssh.prompt()
            neighbors = self._ssh.before.split(b'\n')[1:-1]
            if self._ap:
                self._ssh.sendline(_ARP_CMD)
                self._ssh.prompt()
                arp_result = self._ssh.before.split(b'\n')[1:-1]
                self._ssh.sendline(_WL_CMD)
                self._ssh.prompt()
                leases_result = self._ssh.before.split(b'\n')[1:-1]
                self._ssh.sendline(_NVRAM_CMD)
                self._ssh.prompt()
                nvram_result = self._ssh.before.split(b'\n')[1].split(b'<')[1:]
            else:
                arp_result = ['']
                nvram_result = ['']
                self._ssh.sendline(_LEASES_CMD)
                self._ssh.prompt()
                leases_result = self._ssh.before.split(b'\n')[1:-1]
            return AsusWrtResult(neighbors, leases_result, arp_result,
                                 nvram_result)
        except exceptions.EOF as err:
            _LOGGER.error("Connection refused. SSH enabled?")
            self.disconnect()
            return None
        except pxssh.ExceptionPxssh as err:
            _LOGGER.error("Unexpected SSH error: %s", str(err))
            self.disconnect()
            return None
        except AssertionError as err:
            _LOGGER.error("Connection to router unavailable: %s", str(err))
            self.disconnect()
            return None

    def connect(self):
        """Connect to the ASUS-WRT SSH server."""
        from pexpect import pxssh

        self._ssh = pxssh.pxssh()
        if self._ssh_key:
            self._ssh.login(self._host, self._username,
                            ssh_key=self._ssh_key, port=self._port)
        else:
            self._ssh.login(self._host, self._username,
                            password=self._password, port=self._port)

        super(SshConnection, self).connect()

    def disconnect(self):   \
            # pylint: disable=broad-except
        """Disconnect the current SSH connection."""
        try:
            self._ssh.logout()
        except Exception:
            pass
        finally:
            self._ssh = None

        super(SshConnection, self).disconnect()


class TelnetConnection(_Connection):
    """Maintains a Telnet connection to an ASUS-WRT router."""

    def __init__(self, host, port, username, password, ap):
        """Initialize the Telnet connection properties."""
        super(TelnetConnection, self).__init__()

        self._telnet = None
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ap = ap
        self._prompt_string = None

    def get_result(self):
        """Retrieve a single AsusWrtResult through a Telnet connection.

        Connect to the Telnet server if not currently connected, otherwise
        use the existing connection.
        """
        try:
            if not self.connected:
                self.connect()

            self._telnet.write('{}\n'.format(_IP_NEIGH_CMD).encode('ascii'))
            neighbors = (self._telnet.read_until(self._prompt_string).
                         split(b'\n')[1:-1])
            if self._ap:
                self._telnet.write('{}\n'.format(_ARP_CMD).encode('ascii'))
                arp_result = (self._telnet.read_until(self._prompt_string).
                              split(b'\n')[1:-1])
                self._telnet.write('{}\n'.format(_WL_CMD).encode('ascii'))
                leases_result = (self._telnet.read_until(self._prompt_string).
                                 split(b'\n')[1:-1])
                self._telnet.write('{}\n'.format(_NVRAM_CMD).encode('ascii'))
                nvram_result = (self._telnet.read_until(self._prompt_string).
                                split(b'\n')[1].split(b'<')[1:])
            else:
                arp_result = ['']
                nvram_result = ['']
                self._telnet.write('{}\n'.format(_LEASES_CMD).encode('ascii'))
                leases_result = (self._telnet.read_until(self._prompt_string).
                                 split(b'\n')[1:-1])
            return AsusWrtResult(neighbors, leases_result, arp_result,
                                 nvram_result)
        except EOFError:
            _LOGGER.error("Unexpected response from router")
            self.disconnect()
            return None
        except ConnectionRefusedError:
            _LOGGER.error("Connection refused by router. Telnet enabled?")
            self.disconnect()
            return None
        except socket.gaierror as exc:
            _LOGGER.error("Socket exception: %s", exc)
            self.disconnect()
            return None
        except OSError as exc:
            _LOGGER.error("OSError: %s", exc)
            self.disconnect()
            return None

    def connect(self):
        """Connect to the ASUS-WRT Telnet server."""
        self._telnet = telnetlib.Telnet(self._host)
        self._telnet.read_until(b'login: ')
        self._telnet.write((self._username + '\n').encode('ascii'))
        self._telnet.read_until(b'Password: ')
        self._telnet.write((self._password + '\n').encode('ascii'))
        self._prompt_string = self._telnet.read_until(b'#').split(b'\n')[-1]

        super(TelnetConnection, self).connect()

    def disconnect(self):   \
            # pylint: disable=broad-except
        """Disconnect the current Telnet connection."""
        try:
            self._telnet.write('exit\n'.encode('ascii'))
        except Exception:
            pass

        super(TelnetConnection, self).disconnect()
