""" Supports scanning a DD-WRT router. """
import logging
from datetime import timedelta
import re
import threading
import requests

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

_DDWRT_DATA_REGEX = re.compile(r'\{(\w+)::([^\}]*)\}')


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """ Validates config and returns a DdWrt scanner. """
    if not validate_config(config,
                           {DOMAIN: [CONF_HOST, CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return None

    scanner = DdWrtDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


# pylint: disable=too-many-instance-attributes
class DdWrtDeviceScanner(object):
    """ This class queries a wireless router running DD-WRT firmware
    for connected devices. Adapted from Tomato scanner.
    """

    def __init__(self, config):
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.lock = threading.Lock()

        self.last_results = {}

        self.mac2name = None

        # Test the router is accessible
        url = 'http://{}/Status_Wireless.live.asp'.format(self.host)
        data = self.get_ddwrt_data(url)
        self.success_init = data is not None

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """

        self._update_info()

        return self.last_results

    def get_device_name(self, device):
        """ Returns the name of the given device or None if we don't know. """

        with self.lock:
            # if not initialised and not already scanned and not found
            if self.mac2name is None or device not in self.mac2name:
                url = 'http://{}/Status_Lan.live.asp'.format(self.host)
                data = self.get_ddwrt_data(url)

                if not data:
                    return

                dhcp_leases = data.get('dhcp_leases', None)
                if dhcp_leases:
                    # remove leading and trailing single quotes
                    cleaned_str = dhcp_leases.strip().strip('"')
                    elements = cleaned_str.split('","')
                    num_clients = int(len(elements)/5)
                    self.mac2name = {}
                    for idx in range(0, num_clients):
                        # this is stupid but the data is a single array
                        # every 5 elements represents one hosts, the MAC
                        # is the third element and the name is the first
                        mac_index = (idx * 5) + 2
                        if mac_index < len(elements):
                            mac = elements[mac_index]
                            self.mac2name[mac] = elements[idx * 5]

            return self.mac2name.get(device, None)

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """ Ensures the information from the DdWrt router is up to date.
            Returns boolean if scanning successful. """
        if not self.success_init:
            return False

        with self.lock:
            _LOGGER.info("Checking ARP")

            url = 'http://{}/Status_Wireless.live.asp'.format(self.host)
            data = self.get_ddwrt_data(url)

            if not data:
                return False

            if data:
                self.last_results = []
                active_clients = data.get('active_wireless', None)
                if active_clients:
                    # This is really lame, instead of using JSON the ddwrt UI
                    # uses it's own data format for some reason and then
                    # regex's out values so I guess I have to do the same,
                    # LAME!!!

                    # remove leading and trailing single quotes
                    clean_str = active_clients.strip().strip("'")
                    elements = clean_str.split("','")

                    num_clients = int(len(elements)/9)
                    for idx in range(0, num_clients):
                        # get every 9th element which is the MAC address
                        index = idx * 9
                        if index < len(elements):
                            self.last_results.append(elements[index])

                    return True

            return False

    def get_ddwrt_data(self, url):
        """ Retrieve data from DD-WRT and return parsed result  """
        try:
            response = requests.get(
                url,
                auth=(self.username, self.password),
                timeout=4)
        except requests.exceptions.Timeout:
            _LOGGER.exception("Connection to the router timed out")
            return
        if response.status_code == 200:
            return _parse_ddwrt_response(response.text)
        elif response.status_code == 401:
            # Authentication error
            _LOGGER.exception(
                "Failed to authenticate, "
                "please check your username and password")
            return
        else:
            _LOGGER.error("Invalid response from ddwrt: %s", response)


def _parse_ddwrt_response(data_str):
    """ Parse the awful DD-WRT data format, why didn't they use JSON????.
        This code is a python version of how they are parsing in the JS  """
    return {
        key: val for key, val in _DDWRT_DATA_REGEX
        .findall(data_str)}
