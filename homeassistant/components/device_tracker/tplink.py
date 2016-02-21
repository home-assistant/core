"""
homeassistant.components.device_tracker.tplink
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Device tracker platform that supports scanning a TP-Link router for device
presence.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.tplink/
"""
import base64
import logging
import re
import threading
from datetime import timedelta

import requests

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)


def get_scanner(hass, config):
    """ Validates config and returns a TP-Link scanner. """
    if not validate_config(config,
                           {DOMAIN: [CONF_HOST, CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return None

    scanner = Tplink3DeviceScanner(config[DOMAIN])

    if not scanner.success_init:
        scanner = Tplink2DeviceScanner(config[DOMAIN])

        if not scanner.success_init:
            scanner = TplinkDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class TplinkDeviceScanner(object):
    """
    This class queries a wireless router running TP-Link firmware
    for connected devices.
    """

    def __init__(self, config):
        host = config[CONF_HOST]
        username, password = config[CONF_USERNAME], config[CONF_PASSWORD]

        self.parse_macs = re.compile('[0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2}-' +
                                     '[0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2}')

        self.host = host
        self.username = username
        self.password = password

        self.last_results = {}
        self.lock = threading.Lock()
        self.success_init = self._update_info()

    def scan_devices(self):
        """
        Scans for new devices and return a list containing found device ids.
        """

        self._update_info()

        return self.last_results

    # pylint: disable=no-self-use
    def get_device_name(self, device):
        """
        The TP-Link firmware doesn't save the name of the wireless device.
        """

        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """
        Ensures the information from the TP-Link router is up to date.
        Returns boolean if scanning successful.
        """

        with self.lock:
            _LOGGER.info("Loading wireless clients...")

            url = 'http://{}/userRpm/WlanStationRpm.htm'.format(self.host)
            referer = 'http://{}'.format(self.host)
            page = requests.get(url, auth=(self.username, self.password),
                                headers={'referer': referer})

            result = self.parse_macs.findall(page.text)

            if result:
                self.last_results = [mac.replace("-", ":") for mac in result]
                return True

            return False


class Tplink2DeviceScanner(TplinkDeviceScanner):
    """
    This class queries a wireless router running newer version of TP-Link
    firmware for connected devices.
    """

    def scan_devices(self):
        """
        Scans for new devices and return a list containing found device ids.
        """

        self._update_info()
        return self.last_results.keys()

    # pylint: disable=no-self-use
    def get_device_name(self, device):
        """
        The TP-Link firmware doesn't save the name of the wireless device.
        """

        return self.last_results.get(device)

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """
        Ensures the information from the TP-Link router is up to date.
        Returns boolean if scanning successful.
        """

        with self.lock:
            _LOGGER.info("Loading wireless clients...")

            url = 'http://{}/data/map_access_wireless_client_grid.json' \
                .format(self.host)
            referer = 'http://{}'.format(self.host)

            # Router uses Authorization cookie instead of header
            # Let's create the cookie
            username_password = '{}:{}'.format(self.username, self.password)
            b64_encoded_username_password = base64.b64encode(
                username_password.encode('ascii')
            ).decode('ascii')
            cookie = 'Authorization=Basic {}' \
                .format(b64_encoded_username_password)

            response = requests.post(url, headers={'referer': referer,
                                                   'cookie': cookie})

            try:
                result = response.json().get('data')
            except ValueError:
                _LOGGER.error("Router didn't respond with JSON. "
                              "Check if credentials are correct.")
                return False

            if result:
                self.last_results = {
                    device['mac_addr'].replace('-', ':'): device['name']
                    for device in result
                    }
                return True

            return False


class Tplink3DeviceScanner(TplinkDeviceScanner):
    """
    This class queries the Archer C9 router running version 150811 or higher
    of TP-Link firmware for connected devices.
    """

    def __init__(self, config):
        self.stok = ''
        self.sysauth = ''
        super(Tplink3DeviceScanner, self).__init__(config)

    def scan_devices(self):
        """
        Scans for new devices and return a list containing found device ids.
        """

        self._update_info()
        return self.last_results.keys()

    # pylint: disable=no-self-use
    def get_device_name(self, device):
        """
        The TP-Link firmware doesn't save the name of the wireless device.
        We are forced to use the MAC address as name here.
        """

        return self.last_results.get(device)

    def _get_auth_tokens(self):
        """
        Retrieves auth tokens from the router.
        """

        _LOGGER.info("Retrieving auth tokens...")

        url = 'http://{}/cgi-bin/luci/;stok=/login?form=login' \
            .format(self.host)
        referer = 'http://{}/webpages/login.html'.format(self.host)

        # if possible implement rsa encryption of password here

        response = requests.post(url,
                                 params={'operation': 'login',
                                         'username': self.username,
                                         'password': self.password},
                                 headers={'referer': referer})

        try:
            self.stok = response.json().get('data').get('stok')
            _LOGGER.info(self.stok)
            regex_result = re.search('sysauth=(.*);',
                                     response.headers['set-cookie'])
            self.sysauth = regex_result.group(1)
            _LOGGER.info(self.sysauth)
            return True
        except ValueError:
            _LOGGER.error("Couldn't fetch auth tokens!")
            return False

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """
        Ensures the information from the TP-Link router is up to date.
        Returns boolean if scanning successful.
        """

        with self.lock:
            if (self.stok == '') or (self.sysauth == ''):
                self._get_auth_tokens()

            _LOGGER.info("Loading wireless clients...")

            url = ('http://{}/cgi-bin/luci/;stok={}/admin/wireless?'
                   'form=statistics').format(self.host, self.stok)
            referer = 'http://{}/webpages/index.html'.format(self.host)

            response = requests.post(url,
                                     params={'operation': 'load'},
                                     headers={'referer': referer},
                                     cookies={'sysauth': self.sysauth})

            try:
                json_response = response.json()

                if json_response.get('success'):
                    result = response.json().get('data')
                else:
                    if json_response.get('errorcode') == 'timeout':
                        _LOGGER.info("Token timed out. "
                                     "Relogging on next scan.")
                        self.stok = ''
                        self.sysauth = ''
                        return False
                    else:
                        _LOGGER.error("An unknown error happened "
                                      "while fetching data.")
                        return False
            except ValueError:
                _LOGGER.error("Router didn't respond with JSON. "
                              "Check if credentials are correct.")
                return False

            if result:
                self.last_results = {
                    device['mac'].replace('-', ':'): device['mac']
                    for device in result
                    }
                return True

            return False
