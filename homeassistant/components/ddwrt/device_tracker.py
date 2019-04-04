"""Support for DD-WRT routers."""
import logging
import re

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_SSL, CONF_TYPE, CONF_USERNAME,
    CONF_VERIFY_SSL, CONF_MONITORED_CONDITIONS)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

_DDWRT_DATA_REGEX = re.compile(r'\{(\w+)::([^\}]*)\}')
_MAC_REGEX = re.compile(r'(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})')

DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
DEFAULT_TYPE = 'lan'

AVAILABLE_ATTRS = [
    'interface', 'tx_rate', 'rx_rate', 'info', 'signal_db', 'signal',
    'noise_db', 'snr'
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(AVAILABLE_ATTRS)]),
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
})


def get_scanner(hass, config):
    """Validate the configuration and return a DD-WRT scanner."""
    try:
        return DdWrtDeviceScanner(config[DOMAIN])
    except ConnectionError:
        return None


class DdWrtDeviceScanner(DeviceScanner):
    """This class queries a wireless router running DD-WRT firmware."""

    def __init__(self, config):
        """Initialize the DD-WRT scanner."""
        self.protocol = 'https' if config[CONF_SSL] else 'http'
        self.verify_ssl = config[CONF_VERIFY_SSL]
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.type = config[CONF_TYPE]
        self.monitored_conditions = config[CONF_MONITORED_CONDITIONS]

        self.last_results = {}
        self.mac2name = {}

        # Test the router is accessible
        url = '{}://{}/Status_Wireless.live.asp'.format(
            self.protocol, self.host)
        data = self.get_ddwrt_data(url)
        if not data:
            raise ConnectionError('Cannot connect to DD-Wrt router')

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return self.last_results

    def get_device_name(self, device):
        """Scan the devices to get a name if it isn't set already."""
        if device not in self.mac2name:
            return self.scan_table(device)

    def scan_table(self, device, table='dhcp_leases'):
        """Return the name of the given device or None if we don't know."""
        # If not initialised and not already scanned and not found.
        url = '{}://{}/Status_Lan.live.asp'.format(
            self.protocol, self.host)
        data = self.get_ddwrt_data(url)

        if not data:
            return None

        dhcp_leases = data.get(table, None)

        if not dhcp_leases:
            return None

        # Remove leading and trailing quotes and spaces
        cleaned_str = dhcp_leases.replace(
            "\"", "").replace("\'", "").replace(" ", "")
        elements = cleaned_str.split(',')
        num_clients = int(len(elements) / 5)
        self.mac2name = {}

        # The data is a single array
        # For 'dhcp_leases', every 5 elements represents one host,
        # the MAC is the third element and the name is the first.
        if table == 'dhcp_leases':
            set_columns = 5

        # For 'arp_table', every 4 elements represents one host,
        # The position of the MAC and the name remains the same.
        else:
            set_columns = 4

        for idx in range(0, num_clients):
            mac_index = (idx * set_columns) + 2
            # Make sure the index is not out of scope.
            if _verify_out_of_scope(mac_index, elements):
                mac = elements[mac_index]
                if mac in self.mac2name:
                    # Make sure the index is not out of scope.
                    if _verify_out_of_scope(idx * set_columns, elements):
                        name = elements[idx * set_columns]
                        self.mac2name[mac] = name
                        # If the name is a *, it means the name wasn't found in
                        # the dhcp_lease table. Check on the arp_table instead.
                        if name == '*' and table != 'arp_table':
                            self.scan_table(device, 'arp_table')

        return self.mac2name.get(device)

    def _update_info(self):
        """Ensure the information from the DD-WRT router is up to date.

        Return boolean if scanning successful.
        """
        if self.type.lower() == 'wireless':
            _LOGGER.info("Checking Wireless ARP")
            url = 'http://{}/Status_Wireless.live.asp'.format(self.host)
            extract_key = 'active_wireless'

        elif self.type.lower() == 'dhcp':
            _LOGGER.info("Checking DHCP leases")
            url = 'http://{}/Status_Lan.live.asp'.format(self.host)
            extract_key = 'dhcp_leases'
        else:
            _LOGGER.info("Checking Lan ARP")
            url = 'http://{}/Status_Lan.live.asp'.format(self.host)
            extract_key = 'arp_table'

        data = self.get_ddwrt_data(url)

        if not data:
            return False

        self.last_results = []

        active_clients = data.get(extract_key, None)

        if not active_clients:
            return False

        # The DD-WRT UI uses its own data format and then
        # regex's out values so this is done here too
        # Remove leading and trailing single quotes.
        clean_str = active_clients.strip().strip("'")
        elements = clean_str.split("','")

        self.last_results.extend(item for item in elements
                                 if _MAC_REGEX.match(item))

        return True

    def get_ddwrt_data(self, url):
        """Retrieve data from DD-WRT and return parsed result."""
        try:
            response = requests.get(
                url, auth=(self.username, self.password),
                timeout=4, verify=self.verify_ssl)
        except requests.exceptions.Timeout:
            _LOGGER.exception("Connection to the router timed out")
            return
        if response.status_code == 200:
            return _parse_ddwrt_response(response.text)
        if response.status_code == 401:
            # Authentication error
            _LOGGER.exception(
                "Failed to authenticate, check your username and password")
            return
        _LOGGER.error("Invalid response from DD-WRT: %s", response)

    def get_extra_attributes(self, device):
        """Return the extra attributes of the devices wireless connections."""
        if not self.monitored_conditions:
            return {}

        url = '{}://{}/Status_Wireless.live.asp'.format(
            self.protocol, self.host)
        data = self.get_ddwrt_data(url)

        if not data:
            return None

        active_wireless = data.get('active_wireless', None)

        # Remove leading and trailing quotes and spaces
        cleaned_str = active_wireless.replace(
            "\"", "").replace("\'", "").replace(" ", "")
        elements = cleaned_str.split(',')

        # The data is a single array
        # For 'active_wireless', every 10 elements represents one host,
        num_clients = int(len(elements) / 10)

        attrs = {}
        # This loops through each wireless client and
        # then assign a variable to each 'column'.
        for idx in range(0, num_clients):
            column_indexes = {
                'mac': 0,
                'interface': 1,
                'tx_rate': 3,
                'rx_rate': 4,
                'info': 5,
                'signal_db': 6,
                'noise_db': 7,
                'snr': 8,
                'signal': 9,
            }

            # The loop stops when the proper MAC address is found.
            current_mac_lookup = idx * 10 + column_indexes['mac']

            if elements[current_mac_lookup] == device:
                # Looping through the requested monitoring conditions
                for monitored_value in self.monitored_conditions:
                    column_index = column_indexes[monitored_value]
                    attrs[monitored_value] = elements[idx * 10 + column_index]
                    # TX and RX rate have a M at the end of the string,
                    # here we remove it for convenience.
                    if monitored_value in ['tx_rate', 'rx_rate']:
                        attrs[monitored_value] = attrs[monitored_value][:-1]

        _LOGGER.debug("Device MAC %s attributes %s", device, attrs)
        return attrs


def _parse_ddwrt_response(data_str):
    """Parse the DD-WRT data format."""
    return {
        key: val for key, val in _DDWRT_DATA_REGEX.findall(data_str)}


def _verify_out_of_scope(index, elements):
    """Check if an index is out of scope.

    Return boolean reflecting the result.
    """
    return bool(index < len(elements))
