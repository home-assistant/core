"""Support for an exposed HttpPlainText API of a device."""

import logging

import requests
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_NAME, CONF_HOST, HTTP_OK
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_RELAYS = "relays"

DEFAULT_NAME = "HttpPlainText switch"

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.url,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_RELAYS): _SWITCHES_SCHEMA,
    }
)


PATH_PATTERN_READ = '/r/{relay_id}'
PATH_PATTERN_WRITE = '/w/{relay_id}/{state}'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HttpPlainText switches."""
    host = config[CONF_HOST]

    try:
        response = requests.get(host, timeout=10)
    except requests.exceptions.MissingSchema:
        _LOGGER.error(
            "Missing host or schema in configuration. Add http:// to your URL"
        )
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to device at %s", host)
        return False

    dev = []
    relays = config[CONF_RELAYS]
    for relayId, name in relays.items():
        dev.append(
            HttpPlainTextSwitch(
                host,
                relayId,
                name,
            )
        )

    add_entities(dev)


class HttpPlainTextSwitch(SwitchEntity):
    """Representation of an HttpPlainText switch."""

    def __init__(self, host, relayId, name):
        """Initialize the switch."""
        self._host = host
        self._relayId = relayId
        self._name = name
        self._state = None
        self._available = True

        self._read()

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._write(True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._write(False)

    def update(self):
        """Get the latest data from HttpPlainText API and update the state."""
        self._read()

    def _read(self):
        path = PATH_PATTERN_READ.replace('{relay_id}', str(self._relayId))
        request = requests.get(self._host + path, timeout=10)
        if request.status_code != HTTP_OK:
            _LOGGER.error("Can't set mode")
            self._available = False
        else:
            self._parseResponse(request)

    def _write(self, state):
        path = PATH_PATTERN_WRITE.replace('{relay_id}', str(self._relayId))
        path = path.replace('{state}', '1' if state else '0')
        request = requests.post(self._host + path, timeout=10)
        if request.status_code == HTTP_OK:
            self._parseResponse(request)
        else:
            _LOGGER.error("Can't switch relay %s at %s", self._relayId, self._host)

    def _parseResponse(self, request):
        response = request.text
        data = response.split()
        self._state = data[0] == '1'
