"""
Support for Apple TV.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.apple_tv/
"""
import asyncio
import logging
import hashlib

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK,
    SUPPORT_STOP, SUPPORT_PLAY, SUPPORT_PLAY_MEDIA, SUPPORT_TURN_ON,
    SUPPORT_TURN_OFF, MediaPlayerDevice, PLATFORM_SCHEMA, MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_VIDEO, MEDIA_TYPE_TVSHOW)
from homeassistant.const import (
    STATE_IDLE, STATE_PAUSED, STATE_PLAYING, STATE_STANDBY, CONF_HOST,
    STATE_OFF, CONF_NAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util


REQUIREMENTS = ['pyatv==0.2.1']

_LOGGER = logging.getLogger(__name__)

CONF_LOGIN_ID = 'login_id'
CONF_START_OFF = 'start_off'

DEFAULT_NAME = 'Apple TV'

DATA_APPLE_TV = 'apple_tv'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_LOGIN_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_START_OFF, default=False): cv.boolean
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Apple TV platform."""
    import pyatv

    if discovery_info is not None:
        name = discovery_info['name']
        host = discovery_info['host']
        login_id = discovery_info['properties']['hG']
        start_off = False
    else:
        name = config.get(CONF_NAME)
        host = config.get(CONF_HOST)
        login_id = config.get(CONF_LOGIN_ID)
        start_off = config.get(CONF_START_OFF)

    if DATA_APPLE_TV not in hass.data:
        hass.data[DATA_APPLE_TV] = []

    if host in hass.data[DATA_APPLE_TV]:
        return False
    hass.data[DATA_APPLE_TV].append(host)

    details = pyatv.AppleTVDevice(name, host, login_id)
    session = async_get_clientsession(hass)
    atv = pyatv.connect_to_apple_tv(details, hass.loop, session=session)
    entity = AppleTvDevice(atv, name, start_off)

    @callback
    def on_hass_stop(event):
        """Stop push updates when hass stops."""
        atv.push_updater.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)

    async_add_devices([entity])


class AppleTvDevice(MediaPlayerDevice):
    """Representation of an Apple TV device."""

    def __init__(self, atv, name, is_off):
        """Initialize the Apple TV device."""
        self._atv = atv
        self._name = name
        self._is_off = is_off
        self._playing = None
        self._artwork_hash = None
        self._atv.push_updater.listener = self

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        if not self._is_off:
            self._atv.push_updater.start()

    @callback
    def _set_power_off(self, is_off):
        """Set the power to off."""
        self._playing = None
        self._artwork_hash = None
        self._is_off = is_off
        if is_off:
            self._atv.push_updater.stop()
        else:
            self._atv.push_updater.start()
        self.hass.async_add_job(self.async_update_ha_state())

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def state(self):
        """Return the state of the device."""
        if self._is_off:
            return STATE_OFF

        if self._playing is not None:
            from pyatv import const
            state = self._playing.play_state
            if state == const.PLAY_STATE_NO_MEDIA:
                return STATE_IDLE
            elif state == const.PLAY_STATE_PLAYING or \
                    state == const.PLAY_STATE_LOADING:
                return STATE_PLAYING
            elif state == const.PLAY_STATE_PAUSED or \
                    state == const.PLAY_STATE_FAST_FORWARD or \
                    state == const.PLAY_STATE_FAST_BACKWARD:
                # Catch fast forward/backward here so "play" is default action
                return STATE_PAUSED
            else:
                return STATE_STANDBY  # Bad or unknown state?

    @callback
    def playstatus_update(self, updater, playing):
        """Print what is currently playing when it changes."""
        self._playing = playing

        if self.state == STATE_IDLE:
            self._artwork_hash = None
        elif self._has_playing_media_changed(playing):
            base = str(playing.title) + str(playing.artist) + \
                str(playing.album) + str(playing.total_time)
            self._artwork_hash = hashlib.md5(
                base.encode('utf-8')).hexdigest()

        self.hass.async_add_job(self.async_update_ha_state())

    def _has_playing_media_changed(self, new_playing):
        if self._playing is None:
            return True
        old_playing = self._playing
        return new_playing.media_type != old_playing.media_type or \
            new_playing.title != old_playing.title

    @callback
    def playstatus_error(self, updater, exception):
        """Inform about an error and restart push updates."""
        _LOGGER.warning('A %s error occurred: %s',
                        exception.__class__, exception)

        # This will wait 10 seconds before restarting push updates. If the
        # connection continues to fail, it will flood the log (every 10
        # seconds) until it succeeds. A better approach should probably be
        # implemented here later.
        updater.start(initial_delay=10)
        self._playing = None
        self._artwork_hash = None
        self.hass.async_add_job(self.async_update_ha_state())

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self._playing is not None:
            from pyatv import const
            media_type = self._playing.media_type
            if media_type == const.MEDIA_TYPE_VIDEO:
                return MEDIA_TYPE_VIDEO
            elif media_type == const.MEDIA_TYPE_MUSIC:
                return MEDIA_TYPE_MUSIC
            elif media_type == const.MEDIA_TYPE_TV:
                return MEDIA_TYPE_TVSHOW

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self._playing is not None:
            return self._playing.total_time

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._playing is not None:
            return self._playing.position

    @property
    def media_position_updated_at(self):
        """Last valid time of media position."""
        state = self.state
        if state == STATE_PLAYING or state == STATE_PAUSED:
            return dt_util.utcnow()

    @asyncio.coroutine
    def async_play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player."""
        yield from self._atv.remote_control.play_url(media_id, 0)

    @property
    def media_image_hash(self):
        """Hash value for media image."""
        if self.state != STATE_IDLE:
            return self._artwork_hash

    @asyncio.coroutine
    def async_get_media_image(self):
        """Fetch media image of current playing image."""
        return (yield from self._atv.metadata.artwork()), 'image/png'

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._playing is not None:
            if self.state == STATE_IDLE:
                return 'Nothing playing'
            title = self._playing.title
            return title if title else "No title"

        return 'Not connected to Apple TV'

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        features = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PLAY_MEDIA
        if self._playing is None or self.state == STATE_IDLE:
            return features

        features |= SUPPORT_PAUSE | SUPPORT_PLAY | SUPPORT_SEEK | \
            SUPPORT_STOP | SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK

        return features

    @asyncio.coroutine
    def async_turn_on(self):
        """Turn the media player on."""
        self._set_power_off(False)

    @asyncio.coroutine
    def async_turn_off(self):
        """Turn the media player off."""
        self._set_power_off(True)

    def async_media_play_pause(self):
        """Pause media on media player.

        This method must be run in the event loop and returns a coroutine.
        """
        if self._playing is not None:
            state = self.state
            if state == STATE_PAUSED:
                return self._atv.remote_control.play()
            elif state == STATE_PLAYING:
                return self._atv.remote_control.pause()

    def async_media_play(self):
        """Play media.

        This method must be run in the event loop and returns a coroutine.
        """
        if self._playing is not None:
            return self._atv.remote_control.play()

    def async_media_pause(self):
        """Pause the media player.

        This method must be run in the event loop and returns a coroutine.
        """
        if self._playing is not None:
            return self._atv.remote_control.pause()

    def async_media_next_track(self):
        """Send next track command.

        This method must be run in the event loop and returns a coroutine.
        """
        if self._playing is not None:
            return self._atv.remote_control.next()

    def async_media_previous_track(self):
        """Send previous track command.

        This method must be run in the event loop and returns a coroutine.
        """
        if self._playing is not None:
            return self._atv.remote_control.previous()

    def async_media_seek(self, position):
        """Send seek command.

        This method must be run in the event loop and returns a coroutine.
        """
        if self._playing is not None:
            return self._atv.remote_control.set_position(position)
