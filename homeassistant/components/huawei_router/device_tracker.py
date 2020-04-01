"""Support for HUAWEI routers."""
import base64
from collections import namedtuple
import logging
import re

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


def get_scanner(hass, config):
    """Validate the configuration and return a HUAWEI scanner."""
    scanner = HuaweiDeviceScanner(config[DOMAIN])

    return scanner


Device = namedtuple("Device", ["name", "ip", "mac", "state"])


class HuaweiDeviceScanner(DeviceScanner):
    """This class queries a router running HUAWEI firmware."""

    ARRAY_REGEX = re.compile(r"var UserDevinfo = new Array\((.*)null\);")
    DEVICE_REGEX = re.compile(r"new USERDevice\((.*?)\),")
    DEVICE_ATTR_REGEX = re.compile(
        '"(?P<Domain>.*?)","(?P<IpAddr>.*?)",'
        '"(?P<MacAddr>.*?)","(?P<Port>.*?)",'
        '"(?P<IpType>.*?)","(?P<DevType>.*?)",'
        '"(?P<DevStatus>.*?)","(?P<PortType>.*?)",'
        '"(?P<Time>.*?)","(?P<HostName>.*?)",'
        '"(?P<IPv4Enabled>.*?)","(?P<IPv6Enabled>.*?)",'
        '"(?P<DeviceType>.*?)"'
    )
    LOGIN_COOKIE = dict(Cookie="body:Language:portuguese:id=-1")

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = base64.b64encode(bytes(config[CONF_PASSWORD], "utf-8"))

        self.last_results = []

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client.mac for client in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results:
            if client.mac == device:
                return client.name
        return None

    def _update_info(self):
        """Ensure the information from the router is up to date.

        Return boolean if scanning successful.
        """
        data = self._get_data()
        if not data:
            return False

        active_clients = [client for client in data if client.state]
        self.last_results = active_clients

        _LOGGER.debug(
            "Active clients: %s",
            "\n".join(f"{client.mac} {client.name}" for client in active_clients),
        )
        return True

    def _get_data(self):
        """Get the devices' data from the router.

        Returns a list with all the devices known to the router DHCP server.
        """
        array_regex_res = self.ARRAY_REGEX.search(self._get_devices_response())

        devices = []
        if array_regex_res:
            device_regex_res = self.DEVICE_REGEX.findall(array_regex_res.group(1))

            for device in device_regex_res:
                device_attrs_regex_res = self.DEVICE_ATTR_REGEX.search(device)

                devices.append(
                    Device(
                        device_attrs_regex_res.group("HostName"),
                        device_attrs_regex_res.group("IpAddr"),
                        device_attrs_regex_res.group("MacAddr"),
                        device_attrs_regex_res.group("DevStatus") == "Online",
                    )
                )

        return devices

    def _get_devices_response(self):
        """Get the raw string with the devices from the router."""
        cnt = requests.post(f"http://{self.host}/asp/GetRandCount.asp")
        cnt_str = str(cnt.content, cnt.apparent_encoding, errors="replace")

        _LOGGER.debug("Logging in")
        cookie = requests.post(
            f"http://{self.host}/login.cgi",
            data=[
                ("UserName", self.username),
                ("PassWord", self.password),
                ("x.X_HW_Token", cnt_str),
            ],
            cookies=self.LOGIN_COOKIE,
        )

        _LOGGER.debug("Requesting lan user info update")
        # this request is needed or else some devices' state won't be updated
        requests.get(
            f"http://{self.host}/html/bbsp/common/lanuserinfo.asp",
            cookies=cookie.cookies,
        )

        _LOGGER.debug("Requesting lan user info data")
        devices = requests.get(
            f"http://{self.host}/html/bbsp/common/GetLanUserDevInfo.asp",
            cookies=cookie.cookies,
        )

        # we need to decode() using the request encoding, then encode() and
        # decode('unicode_escape') to replace \\xXX with \xXX
        # (i.e. \\x2d -> \x2d)
        return (
            devices.content.decode(devices.apparent_encoding)
            .encode()
            .decode("unicode_escape")
        )
