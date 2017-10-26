"""Example for configuration.yaml.

media_player:
  - platform: yamaha_musiccast
    name: "Living Room"
    host: 192.168.xxx.xx
    port: 5005

"""

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT,
    STATE_UNKNOWN, STATE_ON
)
from homeassistant.components.media_player import (
    MediaPlayerDevice, MEDIA_TYPE_MUSIC, PLATFORM_SCHEMA,
    SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_NEXT_TRACK,
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_PLAY,
    SUPPORT_VOLUME_SET, SUPPORT_VOLUME_MUTE,
    SUPPORT_SELECT_SOURCE, SUPPORT_STOP
)
_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = (
    SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_STOP |
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK |
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF |
    SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE |
    SUPPORT_SELECT_SOURCE
)

KNOWN_HOSTS_KEY = 'data_yamaha_musiccast'

REQUIREMENTS = ['pymusiccast==0.1.2']

DEFAULT_NAME = "Yamaha Receiver"
DEFAULT_PORT = 5005

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Yamaha MusicCast platform."""
    import socket
    import pymusiccast

    known_hosts = hass.data.get(KNOWN_HOSTS_KEY)
    if known_hosts is None:
        known_hosts = hass.data[KNOWN_HOSTS_KEY] = []
    _LOGGER.debug("known_hosts: %s", known_hosts)

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    # Get IP of host to prevent duplicates
    try:
        ipaddr = socket.gethostbyname(host)
    except (OSError) as error:
        _LOGGER.error(
            "Could not communicate with %s:%d: %s", host, port, error)
        return

    if [item for item in known_hosts if item[0] == ipaddr]:
        _LOGGER.warning("Host %s:%d already registered.", host, port)
        return

    if [item for item in known_hosts if item[1] == port]:
        _LOGGER.warning("Port %s:%d already registered.", host, port)
        return

    reg_host = (ipaddr, port)
    known_hosts.append(reg_host)

    try:
        receiver = pymusiccast.McDevice(ipaddr, udp_port=port)
    except pymusiccast.exceptions.YMCInitError as err:
        _LOGGER.error(err)
        receiver = None

    if receiver:
        _LOGGER.debug("receiver: %s / Port: %d", receiver, port)
        add_devices([YamahaDevice(receiver, name)], True)
    else:
        known_hosts.remove(reg_host)


class YamahaDevice(MediaPlayerDevice):
    """Representation of a Yamaha MusicCast device."""

    def __init__(self, receiver, name):
        """Initialize the Yamaha MusicCast device."""
        self._receiver = receiver
        self._name = name
        self.power = STATE_UNKNOWN
        self.volume = 0
        self.volume_max = 0
        self.mute = False
        self._source = None
        self._source_list = []
        self.status = STATE_UNKNOWN
        self.media_status = None
        self._receiver.set_yamaha_device(self)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self.power == STATE_ON and self.status is not STATE_UNKNOWN:
            return self.status
        return self.power

    @property
    def should_poll(self):
        """Push an update after each command."""
        return True

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.mute

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self.volume

    @property
    def supported_features(self):
        """Flag of features that are supported."""
        return SUPPORTED_FEATURES

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @source_list.setter
    def source_list(self, value):
        """Set source_list attribute."""
        self._source_list = value

    @property
    def media_content_type(self):
        """Return the media content type."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self.media_status.media_duration \
            if self.media_status else None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self.media_status.media_image_url \
            if self.media_status else None

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self.media_status.media_artist if self.media_status else None

    @property
    def media_album(self):
        """Album of current playing media, music track only."""
        return self.media_status.media_album if self.media_status else None

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        return self.media_status.media_track if self.media_status else None

    @property
    def media_title(self):
        """Title of current playing media."""
        return self.media_status.media_title if self.media_status else None

    def update(self):
        """Get the latest details from the device."""
        _LOGGER.debug("update: %s", self.entity_id)

        # call from constructor setup_platform()
        if not self.entity_id:
            _LOGGER.debug("First run")
            self._receiver.update_status(push=False)
        # call from regular polling
        else:
            # update_status_timer was set before
            if self._receiver.update_status_timer:
                _LOGGER.debug(
                    "is_alive: %s",
                    self._receiver.update_status_timer.is_alive())
                # e.g. computer was suspended, while hass was running
                if not self._receiver.update_status_timer.is_alive():
                    _LOGGER.debug("Reinitializing")
                    self._receiver.update_status()

    def turn_on(self):
        """Turn on specified media player or all."""
        _LOGGER.debug("Turn device: on")
        self._receiver.set_power(True)

    def turn_off(self):
        """Turn off specified media player or all."""
        _LOGGER.debug("Turn device: off")
        self._receiver.set_power(False)

    def media_play(self):
        """Send the media player the command for play/pause."""
        _LOGGER.debug("Play")
        self._receiver.set_playback("play")

    def media_pause(self):
        """Send the media player the command for pause."""
        _LOGGER.debug("Pause")
        self._receiver.set_playback("pause")

    def media_stop(self):
        """Send the media player the stop command."""
        _LOGGER.debug("Stop")
        self._receiver.set_playback("stop")

    def media_previous_track(self):
        """Send the media player the command for prev track."""
        _LOGGER.debug("Previous")
        self._receiver.set_playback("previous")

    def media_next_track(self):
        """Send the media player the command for next track."""
        _LOGGER.debug("Next")
        self._receiver.set_playback("next")

    def mute_volume(self, mute):
        """Send mute command."""
        _LOGGER.debug("Mute volume: %s", mute)
        self._receiver.set_mute(mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        _LOGGER.debug("Volume level: %.2f / %d",
                      volume, volume * self.volume_max)
        self._receiver.set_volume(volume * self.volume_max)

    def select_source(self, source):
        """Send the media player the command to select input source."""
        _LOGGER.debug("select_source: %s", source)
        self.status = STATE_UNKNOWN
        self._receiver.set_input(source)
