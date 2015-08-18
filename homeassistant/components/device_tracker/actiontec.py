"""
homeassistant.components.device_tracker.actiontec
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Device tracker platform that supports scanning a Actiontec MI424WR (Verizon FIOS) router for device
presence.

This device tracker needs telnet to be enabled on the router.

Configuration:

To use the Actiontec tracker you will need to add something like the following
to your config/configuration.yaml

device_tracker:
  platform: actiontec
  host: YOUR_ROUTER_IP
  username: YOUR_ADMIN_USERNAME
  password: YOUR_ADMIN_PASSWORD

Variables:

host
*Required
The IP address of your router, e.g. 192.168.1.1.

username
*Required
The username of an user with administrative privileges, usually 'admin'.

password
*Required
The password for your given admin account.
"""
import logging
from datetime import timedelta
import re
import threading
import telnetlib

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

_LEASES_REGEX = re.compile(r'(?P<mac>([0-9a-f]{2}[:-]){5}([0-9a-f]{2}))')



# pylint: disable=unused-argument
def get_scanner(hass, config):
    """ Validates config and returns a DD-WRT scanner. """
    if not validate_config(config,
                           {DOMAIN: [CONF_HOST, CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return None

    scanner = ActiontecDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class ActiontecDeviceScanner(object):
    """ This class queries a an actiontec router
    for connected devices. Adapted from DD-WRT scanner.
    """

    def __init__(self, config):
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.lock = threading.Lock()

        self.last_results = {}

        # Test the router is accessible
        data = self.get_actiontec_data()
        self.success_init = data is not None

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """

        self._update_info()
        return self.last_results

    def get_device_name(self, device):
        """ Returns the name of the given device or None if we don't know. """
        if not self.last_results:
            return None
        for client in self.last_results:
            if client == device:
                return client
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """ Ensures the information from the ASUSWRT router is up to date.
            Returns boolean if scanning successful. """
        if not self.success_init:
            return False

        with self.lock:
            # _LOGGER.info("Checking ARP")
            data = self.get_actiontec_data()
            if not data:
                return False

            self.last_results = data
            return True

    def get_actiontec_data(self):
        """ Retrieve data from ASUSWRT and return parsed result.  """
        try:
            telnet = telnetlib.Telnet(self.host)
            telnet.read_until(b'Username: ')
            telnet.write((self.username + '\n').encode('ascii'))
            telnet.read_until(b'Password: ')
            telnet.write((self.password + '\n').encode('ascii'))
            prompt_string = telnet.read_until(b'Wireless Broadband Router> ').split(b'\n')[-1]
            telnet.write('firewall mac_cache_dump\n'.encode('ascii'))
            telnet.write('\n'.encode('ascii'))
            telnet.read_until(prompt_string).split(b'\n')[1:-1]
            leases_result = telnet.read_until(prompt_string).split(b'\n')[1:-1]
            telnet.write('exit\n'.encode('ascii'))
        except EOFError:
            _LOGGER.exception("Unexpected response from router")
            return
        except ConnectionRefusedError:
            _LOGGER.exception("Connection refused by router," +
                              " is telnet enabled?")
            return

        devices = []
        for lease in leases_result:
            match = _LEASES_REGEX.search(lease.decode('utf-8'))
            if match is not None: devices.append(match.group('mac'))

        return devices