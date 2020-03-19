"""Support for Denon AVR receivers using their HTTP interface."""

from collections import namedtuple
import logging

import denonavr
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_MUSIC,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_ZONE,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_SOUND_MODE_RAW = "sound_mode_raw"

CONF_INVALID_ZONES_ERR = "Invalid Zone (expected Zone2 or Zone3)"
CONF_SHOW_ALL_SOURCES = "show_all_sources"
CONF_VALID_ZONES = ["Zone2", "Zone3"]
CONF_ZONES = "zones"

DEFAULT_SHOW_SOURCES = False
DEFAULT_TIMEOUT = 2

KEY_DENON_CACHE = "denonavr_hosts"

SUPPORT_DENON = (
    SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_VOLUME_SET
)

SUPPORT_MEDIA_MODES = (
    SUPPORT_PLAY_MEDIA
    | SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_VOLUME_SET
    | SUPPORT_PLAY
)

DENON_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE): vol.In(CONF_VALID_ZONES, CONF_INVALID_ZONES_ERR),
        vol.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_SHOW_ALL_SOURCES, default=DEFAULT_SHOW_SOURCES): cv.boolean,
        vol.Optional(CONF_ZONES): vol.All(cv.ensure_list, [DENON_ZONE_SCHEMA]),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)

NewHost = namedtuple("NewHost", ["host", "name"])


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Denon platform."""
    # Initialize list with receivers to be started
    receivers = []

    cache = hass.data.get(KEY_DENON_CACHE)
    if cache is None:
        cache = hass.data[KEY_DENON_CACHE] = set()

    # Get config option for show_all_sources and timeout
    show_all_sources = config.get(CONF_SHOW_ALL_SOURCES)
    timeout = config.get(CONF_TIMEOUT)

    # Get config option for additional zones
    zones = config.get(CONF_ZONES)
    if zones is not None:
        add_zones = {}
        for entry in zones:
            add_zones[entry[CONF_ZONE]] = entry.get(CONF_NAME)
    else:
        add_zones = None

    # Start assignment of host and name
    new_hosts = []
    # 1. option: manual setting
    if config.get(CONF_HOST) is not None:
        host = config.get(CONF_HOST)
        name = config.get(CONF_NAME)
        new_hosts.append(NewHost(host=host, name=name))

    # 2. option: discovery using netdisco
    if discovery_info is not None:
        host = discovery_info.get("host")
        name = discovery_info.get("name")
        new_hosts.append(NewHost(host=host, name=name))

    # 3. option: discovery using denonavr library
    if config.get(CONF_HOST) is None and discovery_info is None:
        d_receivers = denonavr.discover()
        # More than one receiver could be discovered by that method
        for d_receiver in d_receivers:
            host = d_receiver["host"]
            name = d_receiver["friendlyName"]
            new_hosts.append(NewHost(host=host, name=name))

    for entry in new_hosts:
        # Check if host not in cache, append it and save for later
        # starting
        if entry.host not in cache:
            new_device = denonavr.DenonAVR(
                host=entry.host,
                name=entry.name,
                show_all_inputs=show_all_sources,
                timeout=timeout,
                add_zones=add_zones,
            )
            for new_zone in new_device.zones.values():
                receivers.append(DenonDevice(new_zone))
            cache.add(host)
            _LOGGER.info("Denon receiver at host %s initialized", host)

    # Add all freshly discovered receivers
    if receivers:
        add_entities(receivers)


class DenonDevice(MediaPlayerDevice):
    """Representation of a Denon Media Player Device."""

    def __init__(self, receiver):
        """Initialize the device."""
        self._receiver = receiver
        self._name = self._receiver.name
        self._muted = self._receiver.muted
        self._volume = self._receiver.volume
        self._current_source = self._receiver.input_func
        self._source_list = self._receiver.input_func_list
        self._state = self._receiver.state
        self._power = self._receiver.power
        self._media_image_url = self._receiver.image_url
        self._title = self._receiver.title
        self._artist = self._receiver.artist
        self._album = self._receiver.album
        self._band = self._receiver.band
        self._frequency = self._receiver.frequency
        self._station = self._receiver.station

        self._sound_mode_support = self._receiver.support_sound_mode
        if self._sound_mode_support:
            self._sound_mode = self._receiver.sound_mode
            self._sound_mode_raw = self._receiver.sound_mode_raw
            self._sound_mode_list = self._receiver.sound_mode_list
        else:
            self._sound_mode = None
            self._sound_mode_raw = None
            self._sound_mode_list = None

        self._supported_features_base = SUPPORT_DENON
        self._supported_features_base |= (
            self._sound_mode_support and SUPPORT_SELECT_SOUND_MODE
        )

    async def async_added_to_hass(self):
        """Register signal handler."""
        async_dispatcher_connect(self.hass, DOMAIN, self.signal_handler)

    def signal_handler(self, data):
        """Handle domain-specific signal by calling appropriate method."""
        entity_ids = data[ATTR_ENTITY_ID]

        if entity_ids == ENTITY_MATCH_NONE:
            return

        if entity_ids == ENTITY_MATCH_ALL or self.entity_id in entity_ids:
            params = {
                key: value
                for key, value in data.items()
                if key not in ["entity_id", "method"]
            }
            getattr(self, data["method"])(**params)

    def update(self):
        """Get the latest status information from device."""
        self._receiver.update()
        self._name = self._receiver.name
        self._muted = self._receiver.muted
        self._volume = self._receiver.volume
        self._current_source = self._receiver.input_func
        self._source_list = self._receiver.input_func_list
        self._state = self._receiver.state
        self._power = self._receiver.power
        self._media_image_url = self._receiver.image_url
        self._title = self._receiver.title
        self._artist = self._receiver.artist
        self._album = self._receiver.album
        self._band = self._receiver.band
        self._frequency = self._receiver.frequency
        self._station = self._receiver.station
        if self._sound_mode_support:
            self._sound_mode = self._receiver.sound_mode
            self._sound_mode_raw = self._receiver.sound_mode_raw

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._muted

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        # Volume is sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        return (float(self._volume) + 80) / 100

    @property
    def source(self):
        """Return the current input source."""
        return self._current_source

    @property
    def source_list(self):
        """Return a list of available input sources."""
        return self._source_list

    @property
    def sound_mode(self):
        """Return the current matched sound mode."""
        return self._sound_mode

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return self._sound_mode_list

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._current_source in self._receiver.netaudio_func_list:
            return self._supported_features_base | SUPPORT_MEDIA_MODES
        return self._supported_features_base

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return None

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self._state == STATE_PLAYING or self._state == STATE_PAUSED:
            return MEDIA_TYPE_MUSIC
        return MEDIA_TYPE_CHANNEL

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._current_source in self._receiver.playing_func_list:
            return self._media_image_url
        return None

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._current_source not in self._receiver.playing_func_list:
            return self._current_source
        if self._title is not None:
            return self._title
        return self._frequency

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        if self._artist is not None:
            return self._artist
        return self._band

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        if self._album is not None:
            return self._album
        return self._station

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        return None

    @property
    def media_track(self):
        """Track number of current playing media, music track only."""
        return None

    @property
    def media_series_title(self):
        """Title of series of current playing media, TV show only."""
        return None

    @property
    def media_season(self):
        """Season of current playing media, TV show only."""
        return None

    @property
    def media_episode(self):
        """Episode of current playing media, TV show only."""
        return None

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attributes = {}
        if (
            self._sound_mode_raw is not None
            and self._sound_mode_support
            and self._power == "ON"
        ):
            attributes[ATTR_SOUND_MODE_RAW] = self._sound_mode_raw
        return attributes

    def media_play_pause(self):
        """Play or pause the media player."""
        return self._receiver.toggle_play_pause()

    def media_play(self):
        """Send play command."""
        return self._receiver.play()

    def media_pause(self):
        """Send pause command."""
        return self._receiver.pause()

    def media_previous_track(self):
        """Send previous track command."""
        return self._receiver.previous_track()

    def media_next_track(self):
        """Send next track command."""
        return self._receiver.next_track()

    def select_source(self, source):
        """Select input source."""
        return self._receiver.set_input_func(source)

    def select_sound_mode(self, sound_mode):
        """Select sound mode."""
        return self._receiver.set_sound_mode(sound_mode)

    def turn_on(self):
        """Turn on media player."""
        if self._receiver.power_on():
            self._state = STATE_ON

    def turn_off(self):
        """Turn off media player."""
        if self._receiver.power_off():
            self._state = STATE_OFF

    def volume_up(self):
        """Volume up the media player."""
        return self._receiver.volume_up()

    def volume_down(self):
        """Volume down media player."""
        return self._receiver.volume_down()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        # Volume has to be sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        volume_denon = float((volume * 100) - 80)
        if volume_denon > 18:
            volume_denon = float(18)
        try:
            if self._receiver.set_volume(volume_denon):
                self._volume = volume_denon
        except ValueError:
            pass

    def mute_volume(self, mute):
        """Send mute command."""
        return self._receiver.mute(mute)

    def get_command(self, command, **kwargs):
        """Send generic command."""
        self._receiver.send_get_command(command)
