"""
Support to interface with the Emby API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.emby/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_MOVIE, MEDIA_TYPE_MUSIC, MEDIA_TYPE_TVSHOW, PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK, SUPPORT_STOP, MediaPlayerDevice)
from homeassistant.const import (
    CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL, DEVICE_DEFAULT_NAME,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, STATE_IDLE, STATE_OFF,
    STATE_PAUSED, STATE_PLAYING)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['pyemby==1.5']

_LOGGER = logging.getLogger(__name__)

CONF_AUTO_HIDE = 'auto_hide'

MEDIA_TYPE_TRAILER = 'trailer'
MEDIA_TYPE_GENERIC_VIDEO = 'video'

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8096
DEFAULT_SSL_PORT = 8920
DEFAULT_SSL = False
DEFAULT_AUTO_HIDE = False

_LOGGER = logging.getLogger(__name__)

SUPPORT_EMBY = SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_STOP | SUPPORT_SEEK | SUPPORT_PLAY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_AUTO_HIDE, default=DEFAULT_AUTO_HIDE): cv.boolean,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT): cv.port,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Emby platform."""
    from pyemby import EmbyServer

    host = config.get(CONF_HOST)
    key = config.get(CONF_API_KEY)
    port = config.get(CONF_PORT)
    ssl = config.get(CONF_SSL)
    auto_hide = config.get(CONF_AUTO_HIDE)

    if port is None:
        port = DEFAULT_SSL_PORT if ssl else DEFAULT_PORT

    _LOGGER.debug("Setting up Emby server at: %s:%s", host, port)

    emby = EmbyServer(host, key, port, ssl, hass.loop)

    active_emby_devices = {}
    inactive_emby_devices = {}

    @callback
    def device_update_callback(data):
        """Handle devices which are added to Emby."""
        new_devices = []
        active_devices = []
        for dev_id in emby.devices:
            active_devices.append(dev_id)
            if dev_id not in active_emby_devices and \
                    dev_id not in inactive_emby_devices:
                new = EmbyDevice(emby, dev_id)
                active_emby_devices[dev_id] = new
                new_devices.append(new)

            elif dev_id in inactive_emby_devices:
                if emby.devices[dev_id].state != 'Off':
                    add = inactive_emby_devices.pop(dev_id)
                    active_emby_devices[dev_id] = add
                    _LOGGER.debug("Showing %s, item: %s", dev_id, add)
                    add.set_available(True)
                    add.set_hidden(False)

        if new_devices:
            _LOGGER.debug("Adding new devices: %s", new_devices)
            async_add_entities(new_devices, True)

    @callback
    def device_removal_callback(data):
        """Handle the removal of devices from Emby."""
        if data in active_emby_devices:
            rem = active_emby_devices.pop(data)
            inactive_emby_devices[data] = rem
            _LOGGER.debug("Inactive %s, item: %s", data, rem)
            rem.set_available(False)
            if auto_hide:
                rem.set_hidden(True)

    @callback
    def start_emby(event):
        """Start Emby connection."""
        emby.start()

    async def stop_emby(event):
        """Stop Emby connection."""
        await emby.stop()

    emby.add_new_devices_callback(device_update_callback)
    emby.add_stale_devices_callback(device_removal_callback)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_emby)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_emby)


class EmbyDevice(MediaPlayerDevice):
    """Representation of an Emby device."""

    def __init__(self, emby, device_id):
        """Initialize the Emby device."""
        _LOGGER.debug("New Emby Device initialized with ID: %s", device_id)
        self.emby = emby
        self.device_id = device_id
        self.device = self.emby.devices[self.device_id]

        self._hidden = False
        self._available = True

        self.media_status_last_position = None
        self.media_status_received = None

    async def async_added_to_hass(self):
        """Register callback."""
        self.emby.add_update_callback(
            self.async_update_callback, self.device_id)

    @callback
    def async_update_callback(self, msg):
        """Handle device updates."""
        # Check if we should update progress
        if self.device.media_position:
            if self.device.media_position != self.media_status_last_position:
                self.media_status_last_position = self.device.media_position
                self.media_status_received = dt_util.utcnow()
        elif not self.device.is_nowplaying:
            # No position, but we have an old value and are still playing
            self.media_status_last_position = None
            self.media_status_received = None

        self.async_schedule_update_ha_state()

    @property
    def hidden(self):
        """Return True if entity should be hidden from UI."""
        return self._hidden

    def set_hidden(self, value):
        """Set hidden property."""
        self._hidden = value

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    def set_available(self, value):
        """Set available property."""
        self._available = value

    @property
    def unique_id(self):
        """Return the id of this emby client."""
        return self.device_id

    @property
    def supports_remote_control(self):
        """Return control ability."""
        return self.device.supports_remote_control

    @property
    def name(self):
        """Return the name of the device."""
        return ('Emby - {} - {}'.format(self.device.client, self.device.name)
                or DEVICE_DEFAULT_NAME)

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def state(self):
        """Return the state of the device."""
        state = self.device.state
        if state == 'Paused':
            return STATE_PAUSED
        if state == 'Playing':
            return STATE_PLAYING
        if state == 'Idle':
            return STATE_IDLE
        if state == 'Off':
            return STATE_OFF

    @property
    def app_name(self):
        """Return current user as app_name."""
        # Ideally the media_player object would have a user property.
        return self.device.username

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self.device.media_id

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        media_type = self.device.media_type
        if media_type == 'Episode':
            return MEDIA_TYPE_TVSHOW
        if media_type == 'Movie':
            return MEDIA_TYPE_MOVIE
        if media_type == 'Trailer':
            return MEDIA_TYPE_TRAILER
        if media_type == 'Music':
            return MEDIA_TYPE_MUSIC
        if media_type == 'Video':
            return MEDIA_TYPE_GENERIC_VIDEO
        if media_type == 'Audio':
            return MEDIA_TYPE_MUSIC
        return None

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return self.device.media_runtime

    @property
    def media_position(self):
        """Return the position of current playing media in seconds."""
        return self.media_status_last_position

    @property
    def media_position_updated_at(self):
        """
        When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return self.media_status_received

    @property
    def media_image_url(self):
        """Return the image URL of current playing media."""
        return self.device.media_image_url

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self.device.media_title

    @property
    def media_season(self):
        """Season of current playing media (TV Show only)."""
        return self.device.media_season

    @property
    def media_series_title(self):
        """Return the title of the series of current playing media (TV)."""
        return self.device.media_series_title

    @property
    def media_episode(self):
        """Return the episode of current playing media (TV only)."""
        return self.device.media_episode

    @property
    def media_album_name(self):
        """Return the album name of current playing media (Music only)."""
        return self.device.media_album_name

    @property
    def media_artist(self):
        """Return the artist of current playing media (Music track only)."""
        return self.device.media_artist

    @property
    def media_album_artist(self):
        """Return the album artist of current playing media (Music only)."""
        return self.device.media_album_artist

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self.supports_remote_control:
            return SUPPORT_EMBY
        return None

    def async_media_play(self):
        """Play media.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.device.media_play()

    def async_media_pause(self):
        """Pause the media player.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.device.media_pause()

    def async_media_stop(self):
        """Stop the media player.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.device.media_stop()

    def async_media_next_track(self):
        """Send next track command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.device.media_next()

    def async_media_previous_track(self):
        """Send next track command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.device.media_previous()

    def async_media_seek(self, position):
        """Send seek command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.device.media_seek(position)
