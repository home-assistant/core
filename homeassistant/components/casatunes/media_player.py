"""
Support for interfacing with CasaTunes devices

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.casatunes/
"""
import logging
import asyncio
import requests
import aiohttp
import voluptuous as vol
import homeassistant.util.dt as dt_util

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_SELECT_SOURCE, SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_MUTE,
    SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK, SUPPORT_PLAY, SUPPORT_PAUSE, SUPPORT_STOP)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_NAME, STATE_IDLE, STATE_OFF, STATE_ON, STATE_PAUSED, STATE_PLAYING, STATE_CLOSED)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'CasaTunes'
DEFAULT_PORT = 8735
DEFAULT_TIMEOUT = 10

SUPPORT_CT_ZONE = SUPPORT_SELECT_SOURCE | SUPPORT_TURN_OFF | SUPPORT_TURN_ON | \
                  SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE

SUPPORT_CT_PLAYER = SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK | SUPPORT_SEEK | \
                    SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_STOP

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


async def _async_request(hass, url, params=None, json=True):
    try:
        session = async_get_clientsession(hass)
        response = await session.get(url, params=params)
        if response.status == 200:
            if json:
                return await response.json()
            else:
                return await response.text()
        else:
            return {'error': 'Code - {}, {}: '.format(response.status, response)}

    except (asyncio.TimeoutError, aiohttp.ClientError) as error:
        return {'error': type(error)}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the CasaTunes platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    url = 'http://{}:{}/api/v1/'.format(host, port)
    service_logo_prefix_url = 'http://{}/CasaTunes/GetImage.ashx?ID='.format(host)

    sources = await _async_request(hass, url + 'sources', {'format': 'json'})
    zones = await _async_request(hass, url + 'zones', {'format': 'json'})
    zone_devices = []
    player_devices = []

    if sources is None or 'error' in sources:
        _LOGGER.error("Sources response is incorrect %s", sources["error"])
        return False

    if zones is None or 'error' in zones:
        _LOGGER.error("Zones response is incorrect %s", zones["error"])
        return False

    for zone in zones:
        try:
            iterator = iter(zone)
            zone_devices.append(CasaTunesZone(hass, zone, url, sources))
        except TypeError:
            _LOGGER.error("Zone is not iterable - %s", zone)

    for source in sources:
        try:
            iterator = iter(source)
            if not source.get('Hidden'):
                player_devices.append(CasaTunesPlayer(hass, source, url, service_logo_prefix_url))
        except TypeError:
            _LOGGER.error("Source is not iterable - %s", source)

    async_add_entities(zone_devices)
    async_add_entities(player_devices)


class CasaTunesPlayer(MediaPlayerDevice):
    """Representation of a CasaTunes player."""

    def __init__(self, hass, source, url, service_logo_prefix_url):
        """Initialize the CasaTunes player."""
        self._hass = hass
        self._source = source
        self._source_id = self._source.get('SourceID')
        self._url = '{}sources/{}'.format(url, self._source_id)
        self._url_now_playing = '{}/nowplaying'.format(self._url)
        self._now_playing = dict()
        self._service_logo_prefix_url = service_logo_prefix_url
        self._media_last_updated = None

        self._update_now_playing()

    async def async_update(self):
        """Get the latest details."""
        await self._update_now_playing()

    async def _update_now_playing(self):
        """Get the latest details."""
        response = await _async_request(self._hass, self._url_now_playing)
        if response is None or 'error' in response:
            _LOGGER.error("Now playing - Update unsuccessful: %s",
                          response.get('error') if response else 'unknown')
        else:
            self._set_now_playing_dict(response)

    async def _set_property(self, prop, value):
        """Send a command to CasaTunes"""
        response = await _async_request(self._hass, self._url_now_playing, {prop: value, 'format': 'json'})
        if response is None or 'error' in response:
            _LOGGER.error("Operation (%s, %s) unsuccessful: %s", prop, value,
                          response.get('error') if response else 'unknown')
        else:
            self._set_now_playing_dict(response)

    async def _send_action(self, action):
        """Send an action to CasaTunes"""
        url = '{}/player/{}'.format(self._url, action)
        response = await _async_request(self._hass, url, json=False)
        if response is None or 'error' in response:
            _LOGGER.error("Player action (%s) unsuccessful: %s", action,
                          response.get('error') if response else 'unknown')
        elif response == '"OK"':
            self.async_schedule_update_ha_state()
        else:
            _LOGGER.error("Player action unknown response: %s", response)

    def _set_now_playing_dict(self, now_playing):
        """Update now playing and timestamp"""
        self._media_last_updated = dt_util.utcnow()
        self._now_playing.update(now_playing)

    def _get_curr_song(self):
        return self._now_playing.get('CurrSong', {})

    def _get_next_song(self):
        return self._now_playing.get('NextSong', {})

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self._get_curr_song().get('ID')

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._get_curr_song().get('Title')

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._get_curr_song().get('Artists')

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._get_curr_song().get('Album')

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        url = self._get_curr_song().get('ArtworkURI')
        logo_url = self._now_playing.get('ServiceLogoURI')
        if not url and logo_url:
            url = '{}{}'.format(self._service_logo_prefix_url, logo_url)
        return url

    @property
    def name(self):
        """Return the name of the device."""
        return self._source.get('Name')

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return self._get_curr_song().get('Duration', 0)

    @property
    def media_track(self):
        """Return the track number of current media (Music track only)."""
        return self._now_playing.get('QueueSongIndex', 0)

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._now_playing.get('ShuffleMode', False)

    @property
    def state(self):
        """Return the state of the device."""
        state = self._now_playing.get('Status', 0)

        if state == 0:
            return STATE_IDLE
        elif state == 1:
            return STATE_PAUSED
        elif state == 2:
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
        return self._now_playing.get('CurrProgress')

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._media_last_updated

    async def async_media_seek(self, position):
        """Send seek command."""
        await self._set_property('CurrProgress', position)

    async def async_media_previous_track(self):
        """Send previous track command."""
        await self._send_action('previous')

    async def async_media_next_track(self):
        """Send next track command."""
        await self._send_action('next')

    async def async_media_play(self):
        """Send play command."""
        await self._send_action('play')

    async def async_media_pause(self):
        """Send pause command."""
        await self._send_action('pause')

    async def async_media_stop(self):
        """Send pause command."""
        await self._send_action('stop')

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        await self._set_property('ShuffleMode', 'true' if shuffle else 'false')


class CasaTunesZone(MediaPlayerDevice):
    """Representation of a CasaTunes zone."""

    def __init__(self, hass, zone, url, sources):
        """Initialize the CasaTunes device."""
        self._hass = hass
        self._sources = sources
        self._zone = zone
        self._zone_id = self._zone.get('ZoneID')
        self._url = '{}zones/{}'.format(url, self._zone_id)

    async def async_update(self):
        """Get the latest details."""
        response = await _async_request(self._hass, self._url)
        if response is None or 'error' in response:
            _LOGGER.error("Update unsuccessful: %s", response.get('error') if response else 'unknown')
        else:
            self._zone.update(response)

    async def _set_property(self, prop, value):
        """Send a command to CasaTunes"""
        response = await _async_request(self._hass, self._url, {prop: value, 'format': 'json'})

        if response is None or 'error' in response:
            _LOGGER.error("Operation (%s, %s) unsuccessful: %s", prop, value,
                          response.get('error') if response else 'unknown')
        else:
            self._zone.update(response)

    @property
    def name(self):
        """Return the name of the device."""
        return self._zone.get('Name')

    @property
    def state(self):
        """Return the state of the device."""
        power = self._zone.get('Power', False)

        if power:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return int(self._zone.get('Volume', 0)) / 100.0

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._zone.get('Mute', False) is True

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_CT_ZONE

    @property
    def source(self):
        """Name of the current input source."""
        for source in self._sources:
            if source.get('SourceID') == self._zone.get('SourceID'):
                return source.get('Name')
        return None

    @property
    def source_list(self):
        """List of available input sources."""
        return [source.get('Name') for source in self._sources if not source.get('Hidden', False)]

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._set_property('Volume', int(volume * 100))

    async def async_mute_volume(self, mute):
        """Mute the volume."""
        await self._set_property('Mute', 'true' if mute else 'false')

    async def async_turn_off(self):
        """Turn the media player off."""
        await self._set_property('Power', 'off')

    async def async_turn_on(self):
        """Turn the media player off."""
        await self._set_property('Power', 'on')

    async def async_select_source(self, source):
        """Select input source."""
        for source_item in self._sources:
            if source_item.get('Name') == source:
                await self._set_property('SourceID', source_item.get('SourceID'))
