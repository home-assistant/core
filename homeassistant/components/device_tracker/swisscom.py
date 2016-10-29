"""
Support for Swisscom routers (Internet-Box).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.swisscom/
"""
import logging
import requests
import threading
from datetime import timedelta

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.util import Throttle

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

REQUIREMENTS = ['requests>=2,<3']

_LOGGER = logging.getLogger(__name__)

# pylint: disable=unused-argument
def get_scanner(hass, config):
    scanner = SwisscomDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SwisscomDeviceScanner(object):
    """This class queries a router running Swisscom Internet Box firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.lock = threading.Lock()

        self.last_results = {}

        # Test the router is accessible.
        data = self.get_swisscom_data()
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
        """Ensure the information from the Swisscom router is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        with self.lock:
            _LOGGER.info("Loading data from Swisscom Internet Box")
            data = self.get_swisscom_data()
            if not data:
                return False

            active_clients = [client for client in data.values() if
                              client['status']]
            self.last_results = active_clients
            return True

    def get_access_token(self):
        try:
            r = requests.post('http://' + self.host + '/ws', headers={
                'Authorization': 'X-Sah-Login',
                'Content-Type': 'application/x-sah-ws-4-call+json'
            }, data='{"service":"sah.Device.Information","method":"createContext","parameters":{"applicationName":"webui","username":"'+self.username+'","password":"'+self.password+'"}}')
            return r.json()['data']['contextID']
        except:
            return

    def get_swisscom_data(self):
        """Retrieve data from Swisscom and return parsed result."""
        r = requests.post('http://' + self.host + '/ws', headers={
            'Authorization': 'X-Sah ' + self.get_access_token(),
            'Content-Type': 'application/x-sah-ws-4-call+json'
        }, data='{"service":"Devices","method":"get","parameters":{"expression":"lan and not self"}}')

        devices = {}
        for device in r.json()['status']:
            try:
                devices[device['IPAddress']] = {
                    'ip': device['IPAddress'],
                    'mac': device['PhysAddress'],
                    'host': device['Name'],
                    'status': device['Active']
                    }
            except:
                pass
        devices.pop('', None)
        return devices

