"""The mikrotik component."""
import logging
import ssl

import voluptuous as vol
import librouteros
from librouteros.login import login_plain, login_token

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_PORT,
    CONF_SSL,
    CONF_METHOD,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.util import slugify
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER
from .const import (
    DOMAIN,
    MTK_LOGIN_PLAIN,
    MTK_LOGIN_TOKEN,
    DEFAULT_ENCODING,
    IDENTITY,
    CONF_TRACK_DEVICES,
    CONF_ENCODING,
    CONF_ARP_PING,
    CONF_LOGIN_METHOD,
    INFO,
    ARP,
    DHCP,
    MIKROTIK_SERVICES,
    ATTR_DEVICE_TRACKER,
)

_LOGGER = logging.getLogger(__name__)

MTK_DEFAULT_API_PORT = "8728"
MTK_DEFAULT_API_SSL_PORT = "8729"

MIKROTIK_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_METHOD): cv.string,
            vol.Optional(CONF_LOGIN_METHOD): vol.Any(MTK_LOGIN_PLAIN, MTK_LOGIN_TOKEN),
            vol.Optional(CONF_PORT): cv.port,
            vol.Optional(CONF_SSL, default=False): cv.boolean,
            vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
            vol.Optional(CONF_TRACK_DEVICES, default=True): cv.boolean,
            vol.Optional(CONF_ARP_PING, default=False): cv.boolean,
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [MIKROTIK_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Set up the Mikrotik component."""
    hass.data[DOMAIN] = {}

    for device in config[DOMAIN]:
        host = device[CONF_HOST]
        ssl = device.get(CONF_SSL)
        user = device.get(CONF_USERNAME)
        password = device.get(CONF_PASSWORD, "")
        login = device.get(CONF_LOGIN_METHOD)
        encoding = device.get(CONF_ENCODING)
        method = device.get(CONF_METHOD)
        arp_ping = device.get(CONF_ARP_PING)
        track_devices = device.get(CONF_TRACK_DEVICES)

        if CONF_PORT in device:
            port = device.get(CONF_PORT)
        else:
            if ssl:
                port = MTK_DEFAULT_API_SSL_PORT
            else:
                port = MTK_DEFAULT_API_PORT

        if login == MTK_LOGIN_PLAIN:
            login_method = (login_plain,)
        elif login == MTK_LOGIN_TOKEN:
            login_method = (login_token,)
        else:
            login_method = (login_plain, login_token)

        try:
            api = MikrotikAPI(
                host,
                ssl,
                port,
                user,
                password,
                login_method,
                encoding,
                arp_ping,
                track_devices,
            )
            api.connect_to_device()
            hass.data[DOMAIN][host] = api
        except (
            librouteros.exceptions.TrapError,
            librouteros.exceptions.MultiTrapError,
            librouteros.exceptions.ConnectionError,
        ) as api_error:
            _LOGGER.error("Mikrotik API login failed %s", api_error)
            continue

        if track_devices:
            hass.async_create_task(
                async_load_platform(
                    hass,
                    DEVICE_TRACKER,
                    DOMAIN,
                    {CONF_HOST: host, CONF_METHOD: method},
                    config,
                )
            )

    if not hass.data[DOMAIN]:
        return False
    return True


class MikrotikAPI:
    """Handle all communication with the Mikrotik API."""

    def __init__(
        self,
        host,
        ssl,
        port,
        user,
        password,
        login_method,
        encoding,
        arp_ping,
        track_devices,
    ):
        """Initialize the Mikrotik Client."""
        self._host = host
        self._ssl = ssl
        self._port = port
        self._user = user
        self._password = password
        self._login_method = login_method
        self._encoding = encoding
        self._host_name = ""
        self._arp_ping = arp_ping
        self._track_devices = track_devices
        self._arp = {}
        self._dhcp = {}
        self._device_tracker = None
        self._info = None
        self._client = None
        self._connecting = False
        self._connected = False

    def connect_to_device(self):
        """Connect to Mikrotik method."""
        if self._connecting:
            return
        self._connecting = True
        _LOGGER.debug("[%s] Connecting to Mikrotik device.", self._host)

        kwargs = {
            "encoding": self._encoding,
            "login_methods": self._login_method,
            "port": self._port,
        }

        if self._ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            kwargs["ssl_wrapper"] = ssl_context.wrap_socket

        try:
            self._client = librouteros.connect(
                self._host, self._user, self._password, **kwargs
            )
        except (
            librouteros.exceptions.TrapError,
            librouteros.exceptions.MultiTrapError,
            librouteros.exceptions.ConnectionError,
        ) as e:
            _LOGGER.error(
                "Mikrotik error for device %s. " "Connection error: %s", self._host, e
            )
            self._connecting = False
            self._connected = False
            self._client = None
            return False

        self.get_hostname()
        if not self._host_name:
            _LOGGER.error("Mikrotik failed to connect to %s.", self._host)
            return False
        _LOGGER.info("Mikrotik Connected to %s (%s).", self._host_name, self._host)
        self._connecting = False
        self._connected = True
        return True

    def get_hostname(self):
        """Return device host name."""
        if not self._connected:
            self.connect_to_device()
        if not self._host_name:
            cmd = MIKROTIK_SERVICES[IDENTITY]
            self._host_name = (self._client(cmd=cmd))[0]["name"]
        return self._host_name

    def connected(self):
        """Return connected boolean."""
        return self._connected

    async def update_info(self):
        """Update info from Mikrotik API."""
        _LOGGER.debug("[%s] Updating Mikrotik info.", self._host)
        if not self._connected:
            self.connect_to_device()
        data = self.get_api(MIKROTIK_SERVICES[INFO])
        if data is None:
            _LOGGER.error("Mikrotik device %s is not connected.", self._host)
            self._connected = False
            return
        self._info = data[0]

    def get_info(self):
        """Return device info."""
        return self._info

    def arp_ping(self, mac, interface):
        """Attempt to arp ping MAC address via interface."""
        params = {
            "arp-ping": "yes",
            "interval": "100ms",
            "count": 3,
            "interface": interface,
            "address": mac,
        }
        cmd = "/ping"
        data = self._client(cmd, params)
        status = 0
        for result in data:
            if "status" in result:
                status += 1
        if status == len(data):
            return None
        return data

    async def update_device_tracker(self, method=None):
        """Update device_tracker from Mikrotik API."""
        self._device_tracker = {}
        if method is None:
            return
        _LOGGER.debug(
            "[%s] Updating Mikrotik device_tracker using %s.", self._host, method
        )

        data = self.get_api(MIKROTIK_SERVICES[method])
        if data is None:
            self.update_info()
            return

        arp = self.get_api(MIKROTIK_SERVICES[ARP])
        for device in arp:
            if "mac-address" in device and device["invalid"] is False:
                mac = device["mac-address"]
                self._arp[mac] = device

        for device in data:
            mac = device["mac-address"]
            if method == DHCP:
                if "active-address" not in device:
                    continue
                self._dhcp[mac] = data
                if self._arp_ping and mac in arp:
                    interface = arp[mac]["interface"]
                    if not self.arp_ping(mac, interface):
                        continue

            attributes = {}
            for attrib in ATTR_DEVICE_TRACKER:
                if attrib in device:
                    attributes[slugify(attrib)] = device[attrib]
            attributes["source_type"] = "router"
            attributes["scanner_type"] = method
            attributes["scanner_host"] = self._host
            attributes["scanner_host_name"] = self._host_name

            if mac in self._arp:
                attributes["ip_address"] = self._arp[mac]["address"]

            if mac in self._arp:
                attributes["host_name"] = self._dhcp[mac]["host-name"]

            self._device_tracker[mac] = attributes

    def get_device_tracker(self):
        """Return device tracker data."""
        return self._device_tracker

    def get_api(self, cmd, params=None):
        """Retrieve data from Mikrotik API."""
        if not self._client or not self._connected:
            if not self.connect_to_device():
                return None
        try:
            if params:
                response = self._client(cmd=cmd, **params)
            else:
                response = self._client(cmd=cmd)
        except (
            librouteros.exceptions.TrapError,
            librouteros.exceptions.MultiTrapError,
            librouteros.exceptions.ConnectionError,
        ) as api_error:
            _LOGGER.error(
                "Failed to retrieve data. " "%s cmd=[%s] Error: %s",
                self._host,
                cmd,
                api_error,
            )
            self._connected = False
            return None
        return response
