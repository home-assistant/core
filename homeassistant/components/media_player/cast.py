"""
Provide functionality to interact with Cast devices on the network.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.cast/
"""
# pylint: disable=import-error
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, MEDIA_TYPE_TVSHOW, MEDIA_TYPE_VIDEO, SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE, SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_STOP, SUPPORT_PLAY, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING,
    STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['pychromecast==1.0.3']

_LOGGER = logging.getLogger(__name__)

CONF_IGNORE_CEC = 'ignore_cec'
CAST_SPLASH = 'https://home-assistant.io/images/cast/splash.png'

DEFAULT_PORT = 8009

SUPPORT_CAST = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_NEXT_TRACK | SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_PLAY

KNOWN_HOSTS_KEY = 'cast_known_hosts'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_IGNORE_CEC): [cv.string],
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the cast platform."""
    import pychromecast

    # Import CEC IGNORE attributes
    pychromecast.IGNORE_CEC += config.get(CONF_IGNORE_CEC, [])

    known_hosts = hass.data.get(KNOWN_HOSTS_KEY)
    if known_hosts is None:
        known_hosts = hass.data[KNOWN_HOSTS_KEY] = []

    if discovery_info:
        host = (discovery_info.get('host'), discovery_info.get('port'))

        if host in known_hosts:
            return

        hosts = [host]

    elif CONF_HOST in config:
        host = (config.get(CONF_HOST), DEFAULT_PORT)

        if host in known_hosts:
            return

        hosts = [host]

    else:
        hosts = [tuple(dev[:2]) for dev in pychromecast.discover_chromecasts()
                 if tuple(dev[:2]) not in known_hosts]

    casts = []

    # get_chromecasts() returns Chromecast objects with the correct friendly
    # name for grouped devices
    all_chromecasts = pychromecast.get_chromecasts()

    for host in hosts:
        (_, port) = host
        found = [device for device in all_chromecasts
                 if (device.host, device.port) == host]
        if found:
            try:
                casts.append(CastDevice(found[0]))
                known_hosts.append(host)
            except pychromecast.ChromecastConnectionError:
                pass

        # do not add groups using pychromecast.Chromecast as it leads to names
        # collision since pychromecast.Chromecast will get device name instead
        # of group name
        elif port == DEFAULT_PORT:
            try:
                # add the device anyway, get_chromecasts couldn't find it
                casts.append(CastDevice(pychromecast.Chromecast(*host)))
                known_hosts.append(host)
            except pychromecast.ChromecastConnectionError:
                pass

    add_devices(casts)


class CastDevice(MediaPlayerDevice):
    """Representation of a Cast device on the network."""

    def __init__(self, chromecast):
        """Initialize the Cast device."""
        self.cast = chromecast

        self.cast.socket_client.receiver_controller.register_status_listener(
            self)
        self.cast.socket_client.media_controller.register_status_listener(self)

        self.cast_status = self.cast.status
        self.media_status = self.cast.media_controller.status
        self.media_status_received = None

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
