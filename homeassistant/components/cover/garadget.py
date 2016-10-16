"""
Platform for the garadget cover component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/garadget/
"""
import logging

import voluptuous as vol

import requests

from homeassistant.components.cover import CoverDevice, PLATFORM_SCHEMA
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.const import CONF_DEVICE, CONF_ACCESS_TOKEN,\
    CONF_NAME, STATE_UNKNOWN, STATE_CLOSED, STATE_OPEN
import homeassistant.helpers.config_validation as cv

DEFAULT_NAME = 'Garadget'

STATE_OPENING = "opening"
STATE_CLOSING = "closing"
STATE_STOPPED = "stopped"

STATES_MAP = {
    "open": STATE_OPEN,
    "opening": STATE_OPENING,
    "closed": STATE_CLOSED,
    "closing": STATE_CLOSING,
    "stopped": STATE_STOPPED
}

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE): cv.string,
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo covers."""
    device_id = config.get(CONF_DEVICE)
    access_token = config.get(CONF_ACCESS_TOKEN)
    name = config.get(CONF_NAME)
    add_devices([GaradgetCover(hass, device_id, access_token, name)])


class GaradgetCover(CoverDevice):
    """Representation of a demo cover."""

    # pylint: disable=no-self-use, too-many-instance-attributes
    def __init__(self, hass, device_id, access_token, name):
        """Initialize the cover."""
        self.hass = hass
        self._name = name
        self._device_id = device_id
        self._access_token = access_token
        self._closing = True
        self._state = STATE_UNKNOWN
        self._time_in_state = None
        self._unsub_listener_cover = None

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def time_in_state(self):
        """Return the time the door has been in its current state."""
        return self._time_in_state

    @property
    def should_poll(self):
        """No polling needed for a demo cover."""
        return True

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._state == STATE_CLOSED

    def _start_watcher(self):
        """Starts watcher."""
        _LOGGER.debug("Starting Watcher")
        if self._unsub_listener_cover is None:
            self._unsub_listener_cover = track_utc_time_change(
                self.hass, self._check_state, second=1)

    def _check_state(self):
        """Check the state of the service during an operation."""
        _LOGGER.debug("Watcher function triggered")
        self.update()
        self.update_ha_state()

    def close_cover(self):
        """Close the cover."""
        if self._state not in ["close", "closing"]:
            _LOGGER.debug("Sending Close Command")
            ret = self._send_command("setState", "close")
            self._start_watcher()
            return ret['return_value'] == 1

        return

    def open_cover(self):
        """Open the cover."""
        if self._state not in ["open", "opening"]:
            _LOGGER.debug("Sending Open Command")
            ret = self._send_command("setState", "open")
            self._start_watcher()
            return ret['return_value'] == 1
        return

    def stop_cover(self):
        """Stops door where it is."""
        if self._state not in ["stopped"]:
            _LOGGER.debug("Sending Stop Command")
            ret = self._send_command("setState", "stop")
            self._start_watcher()
            return ret['return_value'] == 1
        return

    def update(self):
        """Get updated status from API."""
        status = self._send_command("doorStatus")
        self._state = STATES_MAP.get(status['state'], STATE_UNKNOWN)
        _LOGGER.debug("New Status: %s", self._state)
        if self._state not in [STATE_CLOSING, STATE_CLOSED]:
            if self._unsub_listener_cover is not None:
                _LOGGER.debug("Removing Listener")
                self._unsub_listener_cover()
                self._unsub_listener_cover = None

        self._time_in_state = status['time']
        return

    def _send_command(self, func, arg=None):
        """Send commands to API."""
        params = {'access_token': self._access_token}

        if arg:
            params['command'] = arg

        ret = requests.post(
            'https://api.spark.io/v1/devices/{}/{}'.format(
                self._device_id,
                func),
            data=params)
        return ret.text
