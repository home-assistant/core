"""Dune HD implementation of the media player."""
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
import homeassistant.helpers.config_validation as cv

from .const import ATTR_MANUFACTURER, DEFAULT_NAME, DOMAIN

CONF_SOURCES = "sources"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_SOURCES): vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

DUNEHD_PLAYER_SUPPORT = (
    SUPPORT_PAUSE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PLAY
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Dune HD media player platform."""
    host = config.get(CONF_HOST)

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: host}
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add Dune HD entities from a config_entry."""
    unique_id = config_entry.entry_id

    player = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([DuneHDPlayerEntity(player, DEFAULT_NAME, unique_id)], True)


class DuneHDPlayerEntity(MediaPlayerEntity):
    """Implementation of the Dune HD player."""

    def __init__(self, player, name, unique_id):
        """Initialize entity to control Dune HD."""
        self._player = player
        self._name = name
        self._media_title = None
        self._state = None
        self._unique_id = unique_id

    def update(self):
        """Update internal status of the entity."""
        self._state = self._player.update_state()
        self.__update_title()
        return True

    @property
    def state(self):
        """Return player state."""
        state = STATE_OFF
        if "playback_position" in self._state:
            state = STATE_PLAYING
        if self._state.get("player_state") in ("playing", "buffering", "photo_viewer"):
            state = STATE_PLAYING
        if int(self._state.get("playback_speed", 1234)) == 0:
            state = STATE_PAUSED
        if self._state.get("player_state") == "navigator":
            state = STATE_ON
        return state

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._state)

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": DEFAULT_NAME,
            "manufacturer": ATTR_MANUFACTURER,
        }

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return int(self._state.get("playback_volume", 0)) / 100

    @property
    def is_volume_muted(self):
        """Return a boolean if volume is currently muted."""
        return int(self._state.get("playback_mute", 0)) == 1

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return DUNEHD_PLAYER_SUPPORT

    def volume_up(self):
        """Volume up media player."""
        self._state = self._player.volume_up()

    def volume_down(self):
        """Volume down media player."""
        self._state = self._player.volume_down()

    def mute_volume(self, mute):
        """Mute/unmute player volume."""
        self._state = self._player.mute(mute)

    def turn_off(self):
        """Turn off media player."""
        self._media_title = None
        self._state = self._player.turn_off()

    def turn_on(self):
        """Turn off media player."""
        self._state = self._player.turn_on()

    def media_play(self):
        """Play media player."""
        self._state = self._player.play()

    def media_pause(self):
        """Pause media player."""
        self._state = self._player.pause()

    @property
    def media_title(self):
        """Return the current media source."""
        self.__update_title()
        if self._media_title:
            return self._media_title

    def __update_title(self):
        if self._state.get("player_state") == "bluray_playback":
            self._media_title = "Blu-Ray"
        elif self._state.get("player_state") == "photo_viewer":
            self._media_title = "Photo Viewer"
        elif self._state.get("playback_url"):
            self._media_title = self._state["playback_url"].split("/")[-1]
        else:
            self._media_title = None

    def media_previous_track(self):
        """Send previous track command."""
        self._state = self._player.previous_track()

    def media_next_track(self):
        """Send next track command."""
        self._state = self._player.next_track()
