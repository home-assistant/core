"""
Provide functionality to interact with Cast devices on the network.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.cast/
"""
# pylint: disable=import-error
import asyncio
import logging
import threading

import voluptuous as vol

from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (dispatcher_send,
                                              async_dispatcher_connect)
from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, MEDIA_TYPE_TVSHOW, MEDIA_TYPE_VIDEO, SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE, SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_STOP, SUPPORT_PLAY, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING,
    STATE_UNKNOWN, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['pychromecast==2.0.0']

_LOGGER = logging.getLogger(__name__)

CONF_IGNORE_CEC = 'ignore_cec'
CAST_SPLASH = 'https://home-assistant.io/images/cast/splash.png'

DEFAULT_PORT = 8009

SUPPORT_CAST = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_NEXT_TRACK | SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_PLAY

INTERNAL_DISCOVERY_RUNNING_KEY = 'cast_discovery_running'
# UUID -> CastDevice mapping; cast devices without UUID are not stored
ADDED_CAST_DEVICES_KEY = 'cast_added_cast_devices'
# Stores every discovered (host, port, uuid)
KNOWN_CHROMECASTS_KEY = 'cast_all_chromecasts'

SIGNAL_CAST_DISCOVERED = 'cast_discovered'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_IGNORE_CEC): [cv.string],
})


def _setup_internal_discovery(hass: HomeAssistantType) -> None:
    """Set up the pychromecast internal discovery."""
    hass.data.setdefault(INTERNAL_DISCOVERY_RUNNING_KEY, threading.Lock())
    if not hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].acquire(blocking=False):
        # Internal discovery is already running
        return

    import pychromecast

    def internal_callback(name):
        """Called when zeroconf has discovered a new chromecast."""
        mdns = listener.services[name]
        ip_address, port, uuid, _, _ = mdns
        key = (ip_address, port, uuid)

        if key in hass.data[KNOWN_CHROMECASTS_KEY]:
            _LOGGER.debug("Discovered previous chromecast %s", mdns)
            return

        _LOGGER.debug("Discovered new chromecast %s", mdns)
        try:
            # pylint: disable=protected-access
            chromecast = pychromecast._get_chromecast_from_host(
                mdns, blocking=True)
        except pychromecast.ChromecastConnectionError:
            _LOGGER.debug("Can't set up cast with mDNS info %s. "
                          "Assuming it's not a Chromecast", mdns)
            return
        hass.data[KNOWN_CHROMECASTS_KEY][key] = chromecast
        dispatcher_send(hass, SIGNAL_CAST_DISCOVERED, chromecast)

    _LOGGER.debug("Starting internal pychromecast discovery.")
    listener, browser = pychromecast.start_discovery(internal_callback)

    def stop_discovery(event):
        """Stop discovery of new chromecasts."""
        pychromecast.stop_discovery(browser)
        hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].release()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_discovery)


@callback
def _async_create_cast_device(hass, chromecast):
    """Create a CastDevice Entity from the chromecast object.

    Returns None if the cast device has already been added. Additionally,
    automatically updates existing chromecast entities.
    """
    if chromecast.uuid is None:
        # Found a cast without UUID, we don't store it because we won't be able
        # to update it anyway.
        return CastDevice(chromecast)

    # Found a cast with UUID
    added_casts = hass.data[ADDED_CAST_DEVICES_KEY]
    old_cast_device = added_casts.get(chromecast.uuid)
    if old_cast_device is None:
        # -> New cast device
        cast_device = CastDevice(chromecast)
        added_casts[chromecast.uuid] = cast_device
        return cast_device

    old_key = (old_cast_device.cast.host,
               old_cast_device.cast.port,
               old_cast_device.cast.uuid)
    new_key = (chromecast.host, chromecast.port, chromecast.uuid)

    if old_key == new_key:
        # Re-discovered with same data, ignore
        return None

    # -> Cast device changed host
    # Remove old pychromecast.Chromecast from global list, because it isn't
    # valid anymore
    old_cast_device.async_set_chromecast(chromecast)
    return None


@asyncio.coroutine
def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                         async_add_devices, discovery_info=None):
    """Set up the cast platform."""
    import pychromecast

    # Import CEC IGNORE attributes
    pychromecast.IGNORE_CEC += config.get(CONF_IGNORE_CEC, [])
    hass.data.setdefault(ADDED_CAST_DEVICES_KEY, {})
    hass.data.setdefault(KNOWN_CHROMECASTS_KEY, {})

    # None -> use discovery; (host, port) -> manually specify chromecast.
    want_host = None
    if discovery_info:
        want_host = (discovery_info.get('host'), discovery_info.get('port'))
    elif CONF_HOST in config:
        want_host = (config.get(CONF_HOST), DEFAULT_PORT)

    enable_discovery = False
    if want_host is None:
        # We were explicitly told to enable pychromecast discovery.
        enable_discovery = True
    elif want_host[1] != DEFAULT_PORT:
        # We're trying to add a group, so we have to use pychromecast's
        # discovery to get the correct friendly name.
        enable_discovery = True

    if enable_discovery:
        @callback
        def async_cast_discovered(chromecast):
            """Callback for when a new chromecast is discovered."""
            if want_host is not None and \
                    (chromecast.host, chromecast.port) != want_host:
                return  # for groups, only add requested device
            cast_device = _async_create_cast_device(hass, chromecast)

            if cast_device is not None:
                async_add_devices([cast_device])

        async_dispatcher_connect(hass, SIGNAL_CAST_DISCOVERED,
                                 async_cast_discovered)
        # Re-play the callback for all past chromecasts, store the objects in
        # a list to avoid concurrent modification resulting in exception.
        for chromecast in list(hass.data[KNOWN_CHROMECASTS_KEY].values()):
            async_cast_discovered(chromecast)

        hass.async_add_job(_setup_internal_discovery, hass)
    else:
        # Manually add a "normal" Chromecast, we can do that without discovery.
        try:
            chromecast = yield from hass.async_add_job(
                pychromecast.Chromecast, *want_host)
        except pychromecast.ChromecastConnectionError:
            _LOGGER.warning("Can't set up chromecast on %s", want_host[0])
            raise
        key = (chromecast.host, chromecast.port, chromecast.uuid)
        cast_device = _async_create_cast_device(hass, chromecast)
        if cast_device is not None:
            hass.data[KNOWN_CHROMECASTS_KEY][key] = chromecast
            async_add_devices([cast_device])


class CastDevice(MediaPlayerDevice):
    """Representation of a Cast device on the network."""

    def __init__(self, chromecast):
        """Initialize the Cast device."""
        self.cast = None  # type: pychromecast.Chromecast
        self.cast_status = None
        self.media_status = None
        self.media_status_received = None

        self.async_set_chromecast(chromecast)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self.cast.device.friendly_name

    # MediaPlayerDevice properties and methods
    @property
    def state(self):
        """Return the state of the player."""
        if self.media_status is None:
            return STATE_UNKNOWN
        elif self.media_status.player_is_playing:
            return STATE_PLAYING
        elif self.media_status.player_is_paused:
            return STATE_PAUSED
        elif self.media_status.player_is_idle:
            return STATE_IDLE
        elif self.cast.is_idle:
            return STATE_OFF
        return STATE_UNKNOWN

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self.cast_status.volume_level if self.cast_status else None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.cast_status.volume_muted if self.cast_status else None

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self.media_status.content_id if self.media_status else None

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self.media_status is None:
            return None
        elif self.media_status.media_is_tvshow:
            return MEDIA_TYPE_TVSHOW
        elif self.media_status.media_is_movie:
            return MEDIA_TYPE_VIDEO
        elif self.media_status.media_is_musictrack:
            return MEDIA_TYPE_MUSIC
        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self.media_status.duration if self.media_status else None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self.media_status is None:
            return None

        images = self.media_status.images

        return images[0].url if images and images[0].url else None

    @property
    def media_title(self):
        """Title of current playing media."""
        return self.media_status.title if self.media_status else None

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self.media_status.artist if self.media_status else None

    @property
    def media_album(self):
        """Album of current playing media (Music track only)."""
        return self.media_status.album_name if self.media_status else None

    @property
    def media_album_artist(self):
        """Album artist of current playing media (Music track only)."""
        return self.media_status.album_artist if self.media_status else None

    @property
    def media_track(self):
        """Track number of current playing media (Music track only)."""
        return self.media_status.track if self.media_status else None

    @property
    def media_series_title(self):
        """Return the title of the series of current playing media."""
        return self.media_status.series_title if self.media_status else None

    @property
    def media_season(self):
        """Season of current playing media (TV Show only)."""
        return self.media_status.season if self.media_status else None

    @property
    def media_episode(self):
        """Episode of current playing media (TV Show only)."""
        return self.media_status.episode if self.media_status else None

    @property
    def app_id(self):
        """Return the ID of the current running app."""
        return self.cast.app_id

    @property
    def app_name(self):
        """Name of the current running app."""
        return self.cast.app_display_name

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_CAST

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self.media_status is None or \
                not (self.media_status.player_is_playing or
                     self.media_status.player_is_paused or
                     self.media_status.player_is_idle):
            return None

        return self.media_status.current_time

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return self.media_status_received

    def turn_on(self):
        """Turn on the ChromeCast."""
        # The only way we can turn the Chromecast is on is by launching an app
        if not self.cast.status or not self.cast.status.is_active_input:
            import pychromecast

            if self.cast.app_id:
                self.cast.quit_app()

            self.cast.play_media(
                CAST_SPLASH, pychromecast.STREAM_TYPE_BUFFERED)

    def turn_off(self):
        """Turn Chromecast off."""
        self.cast.quit_app()

    def mute_volume(self, mute):
        """Mute the volume."""
        self.cast.set_volume_muted(mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.cast.set_volume(volume)

    def media_play(self):
        """Send play command."""
        self.cast.media_controller.play()

    def media_pause(self):
        """Send pause command."""
        self.cast.media_controller.pause()

    def media_stop(self):
        """Send stop command."""
        self.cast.media_controller.stop()

    def media_previous_track(self):
        """Send previous track command."""
        self.cast.media_controller.rewind()

    def media_next_track(self):
        """Send next track command."""
        self.cast.media_controller.skip()

    def media_seek(self, position):
        """Seek the media to a specific location."""
        self.cast.media_controller.seek(position)

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from a URL."""
        self.cast.media_controller.play_media(media_id, media_type)

    # Implementation of chromecast status_listener methods
    def new_cast_status(self, status):
        """Handle updates of the cast status."""
        self.cast_status = status
        self.schedule_update_ha_state()

    def new_media_status(self, status):
        """Handle updates of the media status."""
        self.media_status = status
        self.media_status_received = dt_util.utcnow()
        self.schedule_update_ha_state()

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        if self.cast.uuid is not None:
            return str(self.cast.uuid)
        return None

    @callback
    def async_set_chromecast(self, chromecast):
        """Set the internal Chromecast object and disconnect the previous."""
        self._async_disconnect()

        self.cast = chromecast

        self.cast.socket_client.receiver_controller.register_status_listener(
            self)
        self.cast.socket_client.media_controller.register_status_listener(self)

        self.cast_status = self.cast.status
        self.media_status = self.cast.media_controller.status

    @asyncio.coroutine
    def async_will_remove_from_hass(self):
        """Disconnect Chromecast object when removed."""
        self._async_disconnect()

    @callback
    def _async_disconnect(self):
        """Disconnect Chromecast object if it is set."""
        if self.cast is None:
            return
        _LOGGER.debug("Disconnecting existing chromecast object")
        old_key = (self.cast.host, self.cast.port, self.cast.uuid)
        self.hass.data[KNOWN_CHROMECASTS_KEY].pop(old_key)
        self.cast.disconnect(blocking=False)
