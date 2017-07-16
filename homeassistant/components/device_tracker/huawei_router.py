"""
Support for HUAWEI routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.huawei/
"""
import base64
import logging
import re
import threading
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import requests
import voluptuous as vol
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.util import Throttle

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

ARRAY_REGEX = re.compile('var UserDevinfo = new Array\((.*),null\);')
DEVICE_REGEX = re.compile('new USERDevice\((.*?)\),')
DEVICE_ATTR_REGEX = re.compile('"(?P<Domain>.*?)","(?P<IpAddr>.*?)",'
                               '"(?P<MacAddr>.*?)","(?P<Port>.*?)",'
                               '"(?P<IpType>.*?)","(?P<DevType>.*?)",'
                               '"(?P<DevStatus>.*?)","(?P<PortType>.*?)",'
                               '"(?P<Time>.*?)","(?P<HostName>.*?)",'
                               '"(?P<IPv4Enabled>.*?)","(?P<IPv6Enabled>.*?)",'
                               '"(?P<DeviceType>.*?)"')
LOGIN_COOKIE = dict(Cookie='body:Language:portuguese:id=-1')


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string
})


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """Validate the configuration and return a HUAWEI scanner."""
    scanner = HuaweiDeviceScanner(config[DOMAIN])

    return scanner


class Device:
    def __init__(self, name, ip, mac, state):
        self._name = name
        self._ip = ip
        self._mac = mac
        self._state = state

    def name(self):
        return self._name

    def ip(self):
        return self._ip

    def mac(self):
        return self._mac

    def state(self):
        return self._state


class HuaweiDeviceScanner(DeviceScanner):
    """This class queries a router running HUAWEI firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = base64.b64encode(bytes(config[CONF_PASSWORD], 'utf-8'))

        self.lock = threading.Lock()

        self.last_results = []

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client.mac() for client in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results:
            if client.mac() == device:
                return client.name()
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Ensure the information from the router is up to date.

        Return boolean if scanning successful.
        """
        with self.lock:
            data = self._get_data()
            if not data:
                return False

            active_clients = [client for client in data if client.state()]
            self.last_results = active_clients

            _LOGGER.debug("Active clients: " + "\n"
                          .join((client.mac() + " " + client.name())
                                for client in active_clients))
            return True

    def _get_data(self):
        array_regex_res = ARRAY_REGEX.search(self._get_devices_response())

        devices = []
        if array_regex_res:
            device_regex_res = DEVICE_REGEX.findall(array_regex_res.group(1))

            for device in device_regex_res:
                device_attrs_regex_res = DEVICE_ATTR_REGEX.search(device)

                devices.append(Device(device_attrs_regex_res.group('HostName'),
                                      device_attrs_regex_res.group('IpAddr'),
                                      device_attrs_regex_res.group('MacAddr'),
                                      device_attrs_regex_res.group(
                                          'DevStatus') == "Online"))

        return devices

    def _get_devices_response(self):
        cnt = requests.post('http://%s/asp/GetRandCount.asp' % self.host)
        cnt_str = str(cnt.content, cnt.apparent_encoding, errors='replace')

        _LOGGER.debug("Loggin in")
        cookie = requests.post('http://%s/login.cgi' % self.host,
                               data=[('UserName', self.username),
                                     ('PassWord', self.password),
                                     ('x.X_HW_Token', cnt_str)],
                               cookies=LOGIN_COOKIE)

        _LOGGER.debug("Requesting lan user info update")
        # this request is needed or else some devices' state won't be updated
        requests.get('http://%s/html/bbsp/common/lanuserinfo.asp' % self.host,
                     cookies=cookie.cookies)

        _LOGGER.debug("Requesting lan user info data")
        devices = requests.get(
            'http://%s/html/bbsp/common/GetLanUserDevInfo.asp' % self.host,
            cookies=cookie.cookies)

        return str(devices.content, devices.apparent_encoding,
                   errors='replace')
