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
    CONF_SCAN_INTERVAL,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReadyrom homeassistant.helpers.discovery import load_platform
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER
from .const import (
    DOMAIN,
    MTK_LOGIN_PLAIN,
    MTK_LOGIN_TOKEN,
    DEFAULT_ENCODING,
    DEFAULT_SCAN_INTERVAL,
    IDENTITY,
    CONF_TRACK_DEVICES,
    CONF_ENCODING,
    CONF_ARP_PING,
    CONF_LOGIN_METHOD,
    INFO,
    MIKROTIK_SERVICES,
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
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
            vol.Optional(CONF_ARP_PING, default=False): cv.boolean,
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [MIKROTIK_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


def setup(hass, config):
    """Set up the Mikrotik component."""
    hass.data[DOMAIN] = {}

    for device in config[DOMAIN]:
        host = device[CONF_HOST]
        use_ssl = device.get(CONF_SSL)
        user = device.get(CONF_USERNAME)
        password = device.get(CONF_PASSWORD, "")
        login = device.get(CONF_LOGIN_METHOD)
        encoding = device.get(CONF_ENCODING)
        track_devices = device.get(CONF_TRACK_DEVICES)

        if CONF_PORT in device:
            port = device.get(CONF_PORT)
        else:
            if use_ssl:
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
            api = MikrotikClient(
                host, use_ssl, port, user, password, login_method, encoding
            )
            api.connect_to_device()
            hass.data[DOMAIN][host] = api
        except librouteros.exceptions.ConnectionError as api_error:
            _LOGGER.error("Mikrotik %s connection failed %s", host, api_error)
            raise ConfigEntryNotReady
        except (
            librouteros.exceptions.TrapError,
            librouteros.exceptions.MultiTrapError,
        ) as api_error:
            _LOGGER.error("Mikrotik %s error %s", host, api_error)
            continue

        if track_devices:
            load_platform(
                hass,
                DEVICE_TRACKER,
                DOMAIN,
                {
                    CONF_HOST: host,
                    CONF_METHOD: device.get(CONF_METHOD),
                    CONF_ARP_PING: device.get(CONF_ARP_PING),
                    CONF_SCAN_INTERVAL: device.get(CONF_SCAN_INTERVAL),
                },
                config,
            )

    if not hass.data[DOMAIN]:
        return False
    return True


class MikrotikClient:
    """Handle all communication with the Mikrotik API."""

    def __init__(self, host, use_ssl, port, user, password, login_method, encoding):
        """Initialize the Mikrotik Client."""
        self._host = host
        self._use_ssl = use_ssl
        self._port = port
        self._user = user
        self._password = password
        self._login_method = login_method
        self._encoding = encoding
        self._host_name = ""
        self._info = None
        self._client = None
        self._connecting = False
        self._connected = False

    def connect_to_device(self):
        """Connect to Mikrotik device."""
        if self._connecting:
            return
        self._connecting = True
        self._connected = False
        _LOGGER.debug("[%s] Connecting to Mikrotik device.", self._host)

        kwargs = {
            "encoding": self._encoding,
            "login_methods": self._login_method,
            "port": self._port,
        }

        if self._use_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            kwargs["ssl_wrapper"] = ssl_context.wrap_socket

        try:
            self._client = librouteros.connect(
                self._host, self._user, self._password, **kwargs
            )
        except (librouteros.exceptions.ConnectionError,) as api_error:
            _LOGGER.error("Mikrotik %s connection error: %s", self._host, api_error)
            raise PlatformNotReady
        except (
            librouteros.exceptions.TrapError,
            librouteros.exceptions.MultiTrapError,
            librouteros.exceptions.ConnectionError,
        ) as api_error:
            _LOGGER.error("Mikrotik %s: %s", self._host, api_error)
            self._connecting = False
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

    def update_info(self):
        """Update device info from Mikrotik API."""
        data = self.command(MIKROTIK_SERVICES[INFO])
        if data is None:
            _LOGGER.error("Mikrotik device %s is not connected.", self._host)
            self.connect_to_device()
            return
        self._info = data[0]

    def command(self, cmd, params=None):
        """Retrieve data from Mikrotik API."""
        if not self._connected:
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
                "Mikrotik %s failed to retrieve data. cmd=[%s] Error: %s",
                self._host,
                cmd,
                api_error,
            )
            return None

        if len(response) > 0:
            return response
        else:
            return None
