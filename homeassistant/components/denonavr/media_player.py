"""Support for Denon AVR receivers using their HTTP interface."""

import logging

from homeassistant.components.media_player import MediaPlayerEntity
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
    CONF_MAC,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import CONF_RECEIVER
from .config_flow import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SERIAL_NUMBER,
    CONF_TYPE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

ATTR_SOUND_MODE_RAW = "sound_mode_raw"

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


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the DenonAVR receiver from a config entry."""
    entities = []
    receiver = hass.data[DOMAIN][config_entry.entry_id][CONF_RECEIVER]
    for receiver_zone in receiver.zones.values():
        if config_entry.data[CONF_SERIAL_NUMBER] is not None:
            unique_id = f"{config_entry.unique_id}-{receiver_zone.zone}"
        else:
            unique_id = None
        entities.append(DenonDevice(receiver_zone, unique_id, config_entry))
    _LOGGER.debug(
        "%s receiver at host %s initialized", receiver.manufacturer, receiver.host
    )
    async_add_entities(entities)


class DenonDevice(MediaPlayerEntity):
    """Representation of a Denon Media Player Device."""

    def __init__(self, receiver, unique_id, config_entry):
        """Initialize the device."""
        self._receiver = receiver
        self._name = self._receiver.name
        self._unique_id = unique_id
        self._config_entry = config_entry
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
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.signal_handler)
        )

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
    def unique_id(self):
        """Return the unique id of the zone."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info of the receiver."""
        if self._config_entry.data[CONF_SERIAL_NUMBER] is None:
            return None

        device_info = {
            "identifiers": {(DOMAIN, self._config_entry.unique_id)},
            "manufacturer": self._config_entry.data[CONF_MANUFACTURER],
            "name": self._config_entry.title,
            "model": f"{self._config_entry.data[CONF_MODEL]}-{self._config_entry.data[CONF_TYPE]}",
        }
        if self._config_entry.data[CONF_MAC] is not None:
            device_info["connections"] = {
                (dr.CONNECTION_NETWORK_MAC, self._config_entry.data[CONF_MAC])
            }

        return device_info

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
