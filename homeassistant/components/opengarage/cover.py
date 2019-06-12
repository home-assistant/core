"""Platform for the opengarage.io cover component."""
import logging

import requests
import voluptuous as vol

from homeassistant.components.cover import (
    CoverDevice, PLATFORM_SCHEMA, SUPPORT_OPEN, SUPPORT_CLOSE)
from homeassistant.const import (
    CONF_DEVICE, CONF_NAME, STATE_UNKNOWN, STATE_CLOSED, STATE_OPEN,
    CONF_COVERS, CONF_HOST, CONF_PORT)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_DISTANCE_SENSOR = 'distance_sensor'
ATTR_DOOR_STATE = 'door_state'
ATTR_SIGNAL_STRENGTH = 'wifi_signal'

CONF_DEVICE_ID = 'device_id'
CONF_DEVICE_KEY = 'device_key'

DEFAULT_NAME = 'OpenGarage'
DEFAULT_PORT = 80

STATE_CLOSING = 'closing'
STATE_OFFLINE = 'offline'
STATE_OPENING = 'opening'
STATE_STOPPED = 'stopped'

STATES_MAP = {
    0: STATE_CLOSED,
    1: STATE_OPEN,
}

COVER_SCHEMA = vol.Schema({
    vol.Required(CONF_DEVICE_KEY): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): cv.schema_with_slug_keys(COVER_SCHEMA),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the OpenGarage covers."""
    covers = []
    devices = config.get(CONF_COVERS)

    for device_id, device_config in devices.items():
        args = {
            CONF_NAME: device_config.get(CONF_NAME),
            CONF_HOST: device_config.get(CONF_HOST),
            CONF_PORT: device_config.get(CONF_PORT),
            CONF_DEVICE_ID: device_config.get(CONF_DEVICE, device_id),
            CONF_DEVICE_KEY: device_config.get(CONF_DEVICE_KEY)
        }

        covers.append(OpenGarageCover(hass, args))

    add_entities(covers, True)


class OpenGarageCover(CoverDevice):
    """Representation of a OpenGarage cover."""

    def __init__(self, hass, args):
        """Initialize the cover."""
        self.opengarage_url = 'http://{}:{}'.format(
            args[CONF_HOST], args[CONF_PORT])
        self.hass = hass
        self._name = args[CONF_NAME]
        self.device_id = args['device_id']
        self._device_key = args[CONF_DEVICE_KEY]
        self._state = None
        self._state_before_move = None
        self.dist = None
        self.signal = None
        self._available = True

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        data = {}

        if self.signal is not None:
            data[ATTR_SIGNAL_STRENGTH] = self.signal

        if self.dist is not None:
            data[ATTR_DISTANCE_SENSOR] = self.dist

        if self._state is not None:
            data[ATTR_DOOR_STATE] = self._state

        return data

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._state in [STATE_UNKNOWN, STATE_OFFLINE]:
            return None
        return self._state in [STATE_CLOSED, STATE_OPENING]

    def close_cover(self, **kwargs):
        """Close the cover."""
        if self._state not in [STATE_CLOSED, STATE_CLOSING]:
            self._state_before_move = self._state
            self._state = STATE_CLOSING
            self._push_button()

    def open_cover(self, **kwargs):
        """Open the cover."""
        if self._state not in [STATE_OPEN, STATE_OPENING]:
            self._state_before_move = self._state
            self._state = STATE_OPENING
            self._push_button()

    def update(self):
        """Get updated status from API."""
        try:
            status = self._get_status()
            if self._name is None:
                if status['name'] is not None:
                    self._name = status['name']
            state = STATES_MAP.get(status.get('door'), STATE_UNKNOWN)
            if self._state_before_move is not None:
                if self._state_before_move != state:
                    self._state = state
                    self._state_before_move = None
            else:
                self._state = state

            _LOGGER.debug("%s status: %s", self._name, self._state)
            self.signal = status.get('rssi')
            self.dist = status.get('dist')
            self._available = True
        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Unable to connect to OpenGarage device: %(reason)s",
                          dict(reason=ex))
            self._state = STATE_OFFLINE

    def _get_status(self):
        """Get latest status."""
        url = '{}/jc'.format(self.opengarage_url)
        ret = requests.get(url, timeout=10)
        return ret.json()

    def _push_button(self):
        """Send commands to API."""
        url = '{}/cc?dkey={}&click=1'.format(
            self.opengarage_url, self._device_key)
        try:
            response = requests.get(url, timeout=10).json()
            if response['result'] == 2:
                _LOGGER.error("Unable to control %s: Device key is incorrect",
                              self._name)
                self._state = self._state_before_move
                self._state_before_move = None
        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Unable to connect to OpenGarage device: %(reason)s",
                          dict(reason=ex))
            self._state = self._state_before_move
            self._state_before_move = None

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'garage'

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE
