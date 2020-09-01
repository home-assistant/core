"""Support for an exposed http_inline API of a device."""

import logging

import requests
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_HOST, CONF_NAME, HTTP_OK
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_NB_RELAYS,
    CONF_PATH_PATTERN_READ,
    CONF_PATH_PATTERN_WRITE,
    CONF_RELAY_NAMES,
    CONF_RELAYS,
    DEFAULT_NAME,
    DEFAULT_PATH_PATTERN_READ,
    DEFAULT_PATH_PATTERN_WRITE,
)

_LOGGER = logging.getLogger(__name__)

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.url,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(
            CONF_PATH_PATTERN_READ, default=DEFAULT_PATH_PATTERN_READ
        ): cv.string,
        vol.Optional(
            CONF_PATH_PATTERN_WRITE, default=DEFAULT_PATH_PATTERN_WRITE
        ): cv.string,
        vol.Required(CONF_RELAYS): _SWITCHES_SCHEMA,
    }
)


def async_setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Set up the http_inline switches."""
    host = config[CONF_HOST]
    path_read = config[CONF_PATH_PATTERN_READ]
    path_write = config[CONF_PATH_PATTERN_WRITE]

    try:
        requests.get(host, timeout=10)
    except requests.exceptions.MissingSchema:
        _LOGGER.error(
            "Missing host or schema in configuration. Add http:// to your URL"
        )
        return
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to device at %d", host)
        return

    net_config = {
        CONF_HOST: host,
        CONF_PATH_PATTERN_READ: path_read,
        CONF_PATH_PATTERN_WRITE: path_write,
    }

    dev = []
    relays = config[CONF_RELAYS]
    for relay_id, name in relays.items():
        dev.append(
            HttpInlineSwitch(
                net_config,
                relay_id,
                name,
            )
        )

    async_add_entities(dev, True)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up WebController-Relay entities based on a config entry."""
    # name = config_entry.data[CONF_NAME]
    host = config_entry.data[CONF_HOST]
    path_read = config_entry.data[CONF_PATH_PATTERN_READ]
    path_write = config_entry.data[CONF_PATH_PATTERN_WRITE]
    nb_relays = config_entry.data[CONF_NB_RELAYS]
    relay_names = config_entry.data[CONF_RELAY_NAMES]

    net_config = {
        CONF_HOST: host,
        CONF_PATH_PATTERN_READ: path_read,
        CONF_PATH_PATTERN_WRITE: path_write,
    }

    dev = []
    for i in range(0, nb_relays):
        dev.append(
            HttpInlineSwitch(
                net_config,
                i,
                relay_names[i],
            )
        )

    async_add_entities(dev, True)


class HttpInlineSwitch(SwitchEntity):
    """Representation of an http_inline switch."""

    def __init__(self, net_config, relay_id, name) -> None:
        """Initialize the switch."""
        self._host = net_config[CONF_HOST]
        self._path_read = net_config[CONF_PATH_PATTERN_READ]
        self._path_write = net_config[CONF_PATH_PATTERN_WRITE]
        self._relay_id = relay_id
        self._name = name
        self._state = None
        self._available = True

        self._read()

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self._available

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self._write(True)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        self._write(False)

    async def async_update(self):
        """Get the latest data from http_inline API and update the state."""
        self._read()

    def _read(self):
        path = self._path_read
        path = path.replace("{relay_id}", str(self._relay_id))
        request = requests.get(self._host + path, timeout=10)
        if request.status_code != HTTP_OK:
            _LOGGER.error("Can't set mode")
            self._available = False
        else:
            self._parse_response(request)

    def _write(self, state):
        path = self._path_write
        path = path.replace("{relay_id}", str(self._relay_id))
        path = path.replace("{state}", "1" if state else "0")
        request = requests.post(self._host + path, timeout=10)
        if request.status_code == HTTP_OK:
            self._parse_response(request)
        else:
            _LOGGER.error("Can't switch relay %d at %s", self._relay_id, self._host)

    def _parse_response(self, request) -> None:
        response = request.text
        data = response.split()
        self._state = data[0] == "1"
