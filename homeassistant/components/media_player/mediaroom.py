"""
Support for the Mediaroom Set-up-box.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.mediaroom/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_CHANNEL, SUPPORT_PAUSE, SUPPORT_PLAY_MEDIA,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_STOP, PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK, SUPPORT_PLAY,
    SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_MUTE,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_OPTIMISTIC, CONF_TIMEOUT,
    STATE_PAUSED, STATE_PLAYING, STATE_STANDBY,
    STATE_ON)
import homeassistant.helpers.config_validation as cv
REQUIREMENTS = ['pymediaroom==0.5']

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_TITLE = 'Mediaroom Media Player Setup'
NOTIFICATION_ID = 'mediaroom_notification'
DEFAULT_NAME = 'Mediaroom STB'
DEFAULT_TIMEOUT = 9
DATA_MEDIAROOM = "mediaroom_known_stb"

SUPPORT_MEDIAROOM = SUPPORT_PAUSE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
    SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_NEXT_TRACK | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=False): cv.boolean,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Mediaroom platform."""
    hosts = []

    known_hosts = hass.data.get(DATA_MEDIAROOM)
    if known_hosts is None:
        known_hosts = hass.data[DATA_MEDIAROOM] = []

    host = config.get(CONF_HOST, None)
    if host is None:
        _LOGGER.info("Trying to discover Mediaroom STB")

        from pymediaroom import Remote

        host = Remote.discover(known_hosts)
        if host is None:
            _LOGGER.warning("Can't find any STB")
            return
    hosts.append(host)
    known_hosts.append(host)

    stbs = []

    try:
        for host in hosts:
            stbs.append(MediaroomDevice(
                config.get(CONF_NAME),
                host,
                config.get(CONF_OPTIMISTIC),
                config.get(CONF_TIMEOUT)
            ))

    except ConnectionRefusedError:
        hass.components.persistent_notification.create(
            'Error: Unable to initialize mediaroom at {}<br />'
            'Check its network connection or consider '
            'using auto discovery.<br />'
            'You will need to restart hass after fixing.'
            ''.format(host),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)

    add_devices(stbs)


class MediaroomDevice(MediaPlayerDevice):
    """Representation of a Mediaroom set-up-box on the network."""

    def __init__(self, name, host, optimistic=False, timeout=DEFAULT_TIMEOUT):
        """Initialize the device."""
        from pymediaroom import Remote

        self.stb = Remote(host, timeout=timeout)
        _LOGGER.info(
            "Found %s at %s%s", name, host,
            " - I'm optimistic" if optimistic else "")
        self._name = name
        self._is_standby = not optimistic
        self._current = None
        self._optimistic = optimistic
        self._state = STATE_STANDBY

    def update(self):
        """Retrieve latest state."""
        if not self._optimistic:
            self._is_standby = self.stb.get_standby()
        if self._is_standby:
            self._state = STATE_STANDBY
        elif self._state not in [STATE_PLAYING, STATE_PAUSED]:
            self._state = STATE_PLAYING
        _LOGGER.debug(
            "%s(%s) is [%s]",
            self._name, self.stb.stb_ip, self._state)

    def play_media(self, media_type, media_id, **kwargs):
        """Play media."""
        _LOGGER.debug(
            "%s(%s) Play media: %s (%s)",
            self._name, self.stb.stb_ip, media_id, media_type)
        if media_type != MEDIA_TYPE_CHANNEL:
            _LOGGER.error('invalid media type')
            return
        if media_id.isdigit():
            media_id = int(media_id)
        else:
            return
        self.stb.send_cmd(media_id)
        self._state = STATE_PLAYING

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    # MediaPlayerDevice properties and methods
    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_MEDIAROOM

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MEDIA_TYPE_CHANNEL

    def turn_on(self):
        """Turn on the receiver."""
        self.stb.send_cmd('Power')
        self._state = STATE_ON

    def turn_off(self):
        """Turn off the receiver."""
        self.stb.send_cmd('Power')
        self._state = STATE_STANDBY

    def media_play(self):
        """Send play command."""
        _LOGGER.debug("media_play()")
        self.stb.send_cmd('PlayPause')
        self._state = STATE_PLAYING

    def media_pause(self):
        """Send pause command."""
        self.stb.send_cmd('PlayPause')
        self._state = STATE_PAUSED

    def media_stop(self):
        """Send stop command."""
        self.stb.send_cmd('Stop')
        self._state = STATE_PAUSED

    def media_previous_track(self):
        """Send Program Down command."""
        self.stb.send_cmd('ProgDown')
        self._state = STATE_PLAYING

    def media_next_track(self):
        """Send Program Up command."""
        self.stb.send_cmd('ProgUp')
        self._state = STATE_PLAYING

    def volume_up(self):
        """Send volume up command."""
        self.stb.send_cmd('VolUp')

    def volume_down(self):
        """Send volume up command."""
        self.stb.send_cmd('VolDown')

    def mute_volume(self, mute):
        """Send mute command."""
        self.stb.send_cmd('Mute')
