"""
Platform for the opengarage.io cover component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.opengarage
"""
import logging

import voluptuous as vol

import requests

from homeassistant.components.cover import (
    CoverDevice, PLATFORM_SCHEMA, SUPPORT_OPEN, SUPPORT_CLOSE)
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.const import (
    CONF_DEVICE, CONF_NAME, STATE_UNKNOWN, STATE_CLOSED, STATE_OPEN,
    CONF_COVERS, CONF_HOST, CONF_PORT)
import homeassistant.helpers.config_validation as cv

DEFAULT_NAME = 'OpenGarage'
DEFAULT_PORT = 80

CONF_DEVICEKEY = "device_key"

ATTR_SIGNAL_STRENGTH = "wifi_signal"
ATTR_DISTANCE_SENSOR = "distance_sensor"
ATTR_DOOR_STATE = "door_state"

STATE_OPENING = "opening"
STATE_CLOSING = "closing"
STATE_STOPPED = "stopped"
STATE_OFFLINE = "offline"

STATES_MAP = {
    0: STATE_CLOSED,
    1: STATE_OPEN
}


# Validation of the user's configuration
COVER_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_DEVICEKEY): cv.string,
    vol.Optional(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): vol.Schema({cv.slug: COVER_SCHEMA}),
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup OpenGarage covers."""
    covers = []
    devices = config.get(CONF_COVERS, {})

    _LOGGER.debug(devices)

    for device_id, device_config in devices.items():
        args = {
            CONF_NAME: device_config.get(CONF_NAME),
            CONF_HOST: device_config.get(CONF_HOST),
            CONF_PORT: device_config.get(CONF_PORT),
            "device_id": device_config.get(CONF_DEVICE, device_id),
            CONF_DEVICEKEY: device_config.get(CONF_DEVICEKEY)
        }

        covers.append(OpenGarageCover(hass, args))

    add_devices(covers)


class OpenGarageCover(CoverDevice):
    """Representation of a OpenGarage cover."""

    # pylint: disable=no-self-use, too-many-instance-attributes
    def __init__(self, hass, args):
        """Initialize the cover."""
        self.opengarage_url = 'http://{}:{}'.format(
            args[CONF_HOST],
            args[CONF_PORT])
        self.hass = hass
        self._name = args[CONF_NAME]
        self.device_id = args['device_id']
        self._devicekey = args[CONF_DEVICEKEY]
        self._state = STATE_UNKNOWN
        self._state_before_move = None
        self.dist = None
        self.signal = None
        self._unsub_listener_cover = None
        self._available = True

        # Lets try to get the configured name if not provided.
        try:
            if self._name is None:
                doorconfig = self._get_status()
                if doorconfig["name"] is not None:
                    self._name = doorconfig["name"]
            self.update()
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error('Unable to connect to server: %(reason)s',
                          dict(reason=ex))
            self._state = STATE_OFFLINE
            self._available = False
            self._name = DEFAULT_NAME
        except KeyError as ex:
            _LOGGER.warning('OpenGarage device %(device)s seems to be offline',
                            dict(device=self.device_id))
            self._name = DEFAULT_NAME
            self._state = STATE_OFFLINE
            self._available = False

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for a demo cover."""
        return True

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
        if self._state == STATE_UNKNOWN:
            return None
        else:
            return self._state in [STATE_CLOSED, STATE_OPENING]

    def _start_watcher(self, command):
        """Start watcher."""
        _LOGGER.debug("Starting Watcher for command: %s ", command)
        if self._unsub_listener_cover is None:
            self._unsub_listener_cover = track_utc_time_change(
                self.hass, self._check_state)

    def _check_state(self, now):
        """Check the state of the service during an operation."""
        self.schedule_update_ha_state(True)

    def close_cover(self):
        """Close the cover."""
        if self._state not in [STATE_CLOSED, STATE_CLOSING]:
            self._state_before_move = self._state
            self._state = STATE_CLOSING
            ret = self._push_button()
            self._start_watcher('close')
            return ret.get('result') == 1

    def open_cover(self):
        """Open the cover."""
        if self._state not in [STATE_OPEN, STATE_OPENING]:
            self._state_before_move = self._state
            self._state = STATE_OPENING
            ret = self._push_button()
            self._start_watcher('open')
            return ret.get('result') == 1

    def stop_cover(self):
        """Stop the door where it is."""
        self._state_before_move = None
        self._state = STATE_STOPPED
        ret = self._push_button()
        return ret.get('result') == 1

    def update(self):
        """Get updated status from API."""
        try:
            status = self._get_status()
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
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error('Unable to connect to OpenGarage device: %(reason)s',
                          dict(reason=ex))
            self._state = STATE_OFFLINE
        except KeyError as ex:
            _LOGGER.warning('OpenGarage device %(device)s seems to be offline',
                            dict(device=self.device_id))
            self._state = STATE_OFFLINE

        if self._state not in [STATE_CLOSING, STATE_OPENING]:
            if self._unsub_listener_cover is not None:
                self._unsub_listener_cover()
                self._unsub_listener_cover = None

    def _get_status(self):
        """Get latest status."""
        url = '{}/jc'.format(
            self.opengarage_url
            )
        ret = requests.get(url)
        return ret.json()

    def _push_button(self):
        """Send commands to API."""
        url = '{}/cc?dkey={}&click=1'.format(
            self.opengarage_url,
            self._devicekey)
        ret = requests.get(url)
        return ret.json()

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'garage'

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE
