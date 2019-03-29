"""
Support for interfacing with CasaTunes devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.casatunes/
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady
from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_SELECT_SOURCE, SUPPORT_TURN_ON, SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_SET, SUPPORT_VOLUME_MUTE, SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK, SUPPORT_PLAY, SUPPORT_PAUSE,
    SUPPORT_STOP)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_NAME, STATE_IDLE, STATE_OFF, STATE_ON,
    STATE_PAUSED, STATE_PLAYING)

REQUIREMENTS = ['casatunes==0.0.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'CasaTunes'
DEFAULT_PORT = 8735
DEFAULT_TIMEOUT = 10

SUPPORT_CT_ZONE = SUPPORT_SELECT_SOURCE | SUPPORT_TURN_OFF | \
                  SUPPORT_TURN_ON | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE

SUPPORT_CT_PLAYER = SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK | \
                    SUPPORT_SEEK | SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_STOP

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the CasaTunes platform."""
    from casatunes import CasaTunes

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    ct = CasaTunes(host, port)

    sources = await ct.get_sources()
    zones = await ct.get_zones()

    zone_devices = []
    player_devices = []

    if sources is False:
        _LOGGER.error("Sources response is incorrect")
        return False

    if zones is False:
        _LOGGER.error("Zones response is incorrect")
        return False

    for zone in zones:
        try:
            zone_devices.append(CasaTunesZone(zone))
        except TypeError:
            _LOGGER.error("Unable to create a zone")
            raise PlatformNotReady

    for source in sources:
        try:
            player_devices.append(CasaTunesPlayer(source))
        except TypeError:
            _LOGGER.error("Unable to create a player")
            raise PlatformNotReady

    async_add_entities(zone_devices)
    async_add_entities(player_devices)


class CasaTunesPlayer(MediaPlayerDevice):
    """Representation of a CasaTunes player."""

    def __init__(self, player):
        """Initialize the CasaTunes player."""
        self._player = player

    async def async_update(self):
        """Get the latest details."""
        await self._player.update()

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self._player.content_id

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._player.title

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._player.artist

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._player.album

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._player.image_url

    @property
    def name(self):
        """Return the name of the device."""
        return self._player.name

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return self._player.duration

    @property
    def media_track(self):
        """Return the track number of current media (Music track only)."""
        return self._player.track

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._player.shuffle

    @property
    def state(self):
        """Return the state of the device."""
        status = self._player.status

        if status == 0:
            return STATE_IDLE
        elif status == 1:
            return STATE_PAUSED
        elif status == 2:
            return STATE_PLAYING
        else:
            return STATE_ON

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_CT_PLAYER

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._player.position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._player.position_updated_at

    async def async_media_seek(self, position):
        """Send seek command."""
        await self._player.seek(position)

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self._player.previous_track()

    async def async_media_next_track(self):
        """Send next track command."""
        await self._player.next_track()

    async def async_media_play(self):
        """Send play command."""
        await self._player.play()

    async def async_media_pause(self):
        """Send pause command."""
        await self._player.pause()

    async def async_media_stop(self):
        """Send pause command."""
        await self._player.stop()

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        await self._player.set_shuffle(shuffle)


class CasaTunesZone(MediaPlayerDevice):
    """Representation of a CasaTunes zone."""

    def __init__(self, zone):
        """Initialize the CasaTunes device."""
        self._zone = zone

    async def async_update(self):
        """Get the latest details."""
        await self._zone.update()

    @property
    def name(self):
        """Return the name of the device."""
        return self._zone.name

    @property
    def state(self):
        """Return the state of the device."""
        if self._zone.power:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return int(self._zone.volume) / 100.0

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._zone.muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_CT_ZONE

    @property
    def source(self):
        """Name of the current input source."""
        return self._zone.source_name

    @property
    def source_list(self):
        """List of available input sources."""
        return self._zone.source_list

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._zone.set_volume(int(volume * 100))

    async def async_mute_volume(self, mute):
        """Mute the volume."""
        await self._zone.mute(mute)

    async def async_turn_off(self):
        """Turn the media player off."""
        await self._zone.turn_off()

    async def async_turn_on(self):
        """Turn the media player off."""
        await self._zone.turn_on()

    async def async_select_source(self, source):
        """Select input source."""
        await self._zone.set_source(source)
