"""
Support for Yamaha MusicCast Receivers.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/media_player.yamaha_musiccast/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE, SUPPORT_STOP,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, STATE_IDLE, STATE_ON, STATE_PAUSED, STATE_PLAYING,
    STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['pymusiccast==0.1.6']

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = (
    SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_STOP |
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK |
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF |
    SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE |
    SUPPORT_SELECT_SOURCE
)

KNOWN_HOSTS_KEY = 'data_yamaha_musiccast'
INTERVAL_SECONDS = 'interval_seconds'

DEFAULT_PORT = 5005
DEFAULT_INTERVAL = 480

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(INTERVAL_SECONDS, default=DEFAULT_INTERVAL): cv.positive_int,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Yamaha MusicCast platform."""
    import socket
    import pymusiccast

    known_hosts = hass.data.get(KNOWN_HOSTS_KEY)
    if known_hosts is None:
        known_hosts = hass.data[KNOWN_HOSTS_KEY] = []
    _LOGGER.debug("known_hosts: %s", known_hosts)

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    interval = config.get(INTERVAL_SECONDS)

    # Get IP of host to prevent duplicates
    try:
        ipaddr = socket.gethostbyname(host)
    except (OSError) as error:
        _LOGGER.error(
            "Could not communicate with %s:%d: %s", host, port, error)
        return

    if [item for item in known_hosts if item[0] == ipaddr]:
        _LOGGER.warning("Host %s:%d already registered", host, port)
        return

    if [item for item in known_hosts if item[1] == port]:
        _LOGGER.warning("Port %s:%d already registered", host, port)
        return

    reg_host = (ipaddr, port)
    known_hosts.append(reg_host)

    try:
        receiver = pymusiccast.McDevice(
            ipaddr, udp_port=port, mc_interval=interval)
    except pymusiccast.exceptions.YMCInitError as err:
        _LOGGER.error(err)
        receiver = None

    if receiver:
        for zone in receiver.zones:
            _LOGGER.debug(
                "Receiver: %s / Port: %d / Zone: %s", receiver, port, zone)
            add_entities(
                [YamahaDevice(receiver, receiver.zones[zone])], True)
    else:
        known_hosts.remove(reg_host)


class YamahaDevice(MediaPlayerDevice):
    """Representation of a Yamaha MusicCast device."""

    def __init__(self, recv, zone):
        """Initialize the Yamaha MusicCast device."""
        self._recv = recv
        self._name = recv.name
        self._source = None
        self._source_list = []
        self._zone = zone
        self.mute = False
        self.media_status = None
        self.media_status_received = None
        self.power = STATE_UNKNOWN
        self.status = STATE_UNKNOWN
        self.volume = 0
        self.volume_max = 0
        self._recv.set_yamaha_device(self)
        self._zone.set_yamaha_device(self)

    @property
    def name(self):
        """Return the name of the device."""
        return "{} ({})".format(self._name, self._zone.zone_id)

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

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self.media_status and self.state in \
                [STATE_PLAYING, STATE_PAUSED, STATE_IDLE]:
            return self.media_status.media_position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return self.media_status_received if self.media_status else None

    def update(self):
        """Get the latest details from the device."""
        _LOGGER.debug("update: %s", self.entity_id)
        self._recv.update_status()
        self._zone.update_status()

    def update_hass(self):
        """Push updates to HASS."""
        if self.entity_id:
            _LOGGER.debug("update_hass: pushing updates")
            self.schedule_update_ha_state()
            return True

    def turn_on(self):
        """Turn on specified media player or all."""
        _LOGGER.debug("Turn device: on")
        self._zone.set_power(True)

    def turn_off(self):
        """Turn off specified media player or all."""
        _LOGGER.debug("Turn device: off")
        self._zone.set_power(False)

    def media_play(self):
        """Send the media player the command for play/pause."""
        _LOGGER.debug("Play")
        self._recv.set_playback("play")

    def media_pause(self):
        """Send the media player the command for pause."""
        _LOGGER.debug("Pause")
        self._recv.set_playback("pause")

    def media_stop(self):
        """Send the media player the stop command."""
        _LOGGER.debug("Stop")
        self._recv.set_playback("stop")

    def media_previous_track(self):
        """Send the media player the command for prev track."""
        _LOGGER.debug("Previous")
        self._recv.set_playback("previous")

    def media_next_track(self):
        """Send the media player the command for next track."""
        _LOGGER.debug("Next")
        self._recv.set_playback("next")

    def mute_volume(self, mute):
        """Send mute command."""
        _LOGGER.debug("Mute volume: %s", mute)
        self._zone.set_mute(mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        _LOGGER.debug("Volume level: %.2f / %d",
                      volume, volume * self.volume_max)
        self._zone.set_volume(volume * self.volume_max)

    def select_source(self, source):
        """Send the media player the command to select input source."""
        _LOGGER.debug("select_source: %s", source)
        self.status = STATE_UNKNOWN
        self._zone.set_input(source)

    def new_media_status(self, status):
        """Handle updates of the media status."""
        _LOGGER.debug("new media_status arrived")
        self.media_status = status
        self.media_status_received = dt_util.utcnow()
