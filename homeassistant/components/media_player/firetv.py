"""
Support for functionality to interact with FireTV devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.firetv/
"""
import logging

import requests

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_SET, MediaPlayerDevice)
from homeassistant.const import (
    STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING, STATE_STANDBY,
    STATE_UNKNOWN)

SUPPORT_FIRETV = SUPPORT_PAUSE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_NEXT_TRACK | SUPPORT_VOLUME_SET

DOMAIN = 'firetv'
DEVICE_LIST_URL = 'http://{0}/devices/list'
DEVICE_STATE_URL = 'http://{0}/devices/state/{1}'
DEVICE_ACTION_URL = 'http://{0}/devices/action/{1}/{2}'

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the FireTV platform."""
    host = config.get('host', 'localhost:5556')
    device_id = config.get('device', 'default')
    try:
        response = requests.get(DEVICE_LIST_URL.format(host)).json()
        if device_id in response['devices'].keys():
            add_devices([
                FireTVDevice(
                    host,
                    device_id,
                    config.get('name', 'Amazon Fire TV')
                )
            ])
            _LOGGER.info(
                'Device %s accessible and ready for control', device_id)
        else:
            _LOGGER.warning(
                'Device %s is not registered with firetv-server', device_id)
    except requests.exceptions.RequestException:
        _LOGGER.error('Could not connect to firetv-server at %s', host)


class FireTV(object):
    """The firetv-server client.

    Should a native Python 3 ADB module become available, python-firetv can
    support Python 3, it can be added as a dependency, and this class can be
    dispensed of.

    For now, it acts as a client to the firetv-server HTTP server (which must
    be running via Python 2).
    """

    def __init__(self, host, device_id):
        """Initialize the FireTV server."""
        self.host = host
        self.device_id = device_id

    @property
    def state(self):
        """Get the device state. An exception means UNKNOWN state."""
        try:
            response = requests.get(
                DEVICE_STATE_URL.format(
                    self.host,
                    self.device_id
                    )
                ).json()
            return response.get('state', STATE_UNKNOWN)
        except requests.exceptions.RequestException:
            _LOGGER.error(
                'Could not retrieve device state for %s', self.device_id)
            return STATE_UNKNOWN

    def action(self, action_id):
        """Perform an action on the device."""
        try:
            requests.get(
                DEVICE_ACTION_URL.format(
                    self.host,
                    self.device_id,
                    action_id
                    )
                )
        except requests.exceptions.RequestException:
            _LOGGER.error(
                'Action request for %s was not accepted for device %s',
                action_id, self.device_id)


class FireTVDevice(MediaPlayerDevice):
    """Representation of an Amazon Fire TV device on the network."""

    # pylint: disable=abstract-method
    def __init__(self, host, device, name):
        """Initialize the FireTV device."""
        self._firetv = FireTV(host, device)
        self._name = name
        self._state = STATE_UNKNOWN

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_FIRETV

    @property
    def state(self):
        """Return the state of the player."""
        return self._state

    def update(self):
        """Get the latest date and update device state."""
        self._state = {
            'idle': STATE_IDLE,
            'off': STATE_OFF,
            'play': STATE_PLAYING,
            'pause': STATE_PAUSED,
            'standby': STATE_STANDBY,
            'disconnected': STATE_UNKNOWN,
        }.get(self._firetv.state, STATE_UNKNOWN)

    def turn_on(self):
        """Turn on the device."""
        self._firetv.action('turn_on')

    def turn_off(self):
        """Turn off the device."""
        self._firetv.action('turn_off')

    def media_play(self):
        """Send play command."""
        self._firetv.action('media_play')

    def media_pause(self):
        """Send pause command."""
        self._firetv.action('media_pause')

    def media_play_pause(self):
        """Send play/pause command."""
        self._firetv.action('media_play_pause')

    def volume_up(self):
        """Send volume up command."""
        self._firetv.action('volume_up')

    def volume_down(self):
        """Send volume down command."""
        self._firetv.action('volume_down')

    def media_previous_track(self):
        """Send previous track command (results in rewind)."""
        self._firetv.action('media_previous')

    def media_next_track(self):
        """Send next track command (results in fast-forward)."""
        self._firetv.action('media_next')
