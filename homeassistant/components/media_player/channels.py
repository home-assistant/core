"""
Support for interfacing with an instance of Channels.
https://getchannels.com

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.channels/
"""
import logging
import requests

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_CHANNEL, MEDIA_TYPE_TVSHOW, MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_VIDEO, SUPPORT_PLAY, SUPPORT_PAUSE, SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE, SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_PLAY_MEDIA, SUPPORT_SELECT_SOURCE, DOMAIN, MediaPlayerDevice)

from homeassistant.const import (
    CONF_HOST, CONF_PORT, STATE_IDLE, STATE_PAUSED, STATE_PLAYING,
    STATE_UNKNOWN, ATTR_ENTITY_ID)

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

FEATURE_SUPPORT = SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_STOP | \
    SUPPORT_VOLUME_MUTE | SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_PLAY_MEDIA | SUPPORT_SELECT_SOURCE

DATA_CHANNELS = 'channels'
TIMEOUT = 1

SERVICE_SEEK_FORWARD = 'channels_seek_forward'
SERVICE_SEEK_BACKWARD = 'channels_seek_backward'
SERVICE_SEEK_BY = 'channels_seek_by'

# Service call validation schemas
ATTR_SECONDS = 'seconds'

CHANNELS_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
})

CHANNELS_SEEK_BY_SCHEMA = CHANNELS_SCHEMA.extend({
    vol.Required(ATTR_SECONDS): vol.Coerce(int),
})

REQUIREMENTS = ['pychannels==1.0.0']

# pylint: disable=unused-argument, abstract-method
# pylint: disable=too-many-instance-attributes
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Channels platform."""

    device = ChannelsPlayer(
                config.get('name', 'Channels'),
                config.get(CONF_HOST),
                config.get(CONF_PORT, 57000)
             )

    if DATA_CHANNELS not in hass.data:
        hass.data[DATA_CHANNELS] = []

    add_devices([device])
    hass.data[DATA_CHANNELS].append(device)

    def service_handler(service):
        entity_ids = service.data.get(ATTR_ENTITY_ID)

        if entity_ids:
            devices = [device for device in hass.data[DATA_CHANNELS]
                       if device.entity_id in entity_ids]
        else:
            devices = hass.data[DATA_CHANNELS]

        for device in devices:
            if service.service == SERVICE_SEEK_FORWARD:
                device.seek_forward()
            elif service.service == SERVICE_SEEK_BACKWARD:
                device.seek_backward()
            elif service.service == SERVICE_SEEK_BY:
                seconds = service.data.get('seconds')
                device.seek_by(seconds)

    hass.services.register(
        DOMAIN, SERVICE_SEEK_FORWARD, service_handler,
        schema=CHANNELS_SCHEMA)

    hass.services.register(
        DOMAIN, SERVICE_SEEK_BACKWARD, service_handler,
        schema=CHANNELS_SCHEMA)

    hass.services.register(
        DOMAIN, SERVICE_SEEK_BY, service_handler,
        schema=CHANNELS_SEEK_BY_SCHEMA)


class ChannelsPlayer(MediaPlayerDevice):
    """Representation of a Channels instance."""

    from pychannels import Channels

    # pylint: disable=too-many-public-methods
    def __init__(self, name, host, port):
        """Initialize the Channels app."""
        self._name = name
        self._host = host
        self._port = port

        self.client = Channels(self._host, self._port)

        self.status = None
        self.muted = None

        self.channel_number = None
        self.channel_name = None
        self.channel_image_url = None

        self.now_playing_title = None
        self.now_playing_episode_title = None
        self.now_playing_season_number = None
        self.now_playing_episode_number = None
        self.now_playing_summary = None
        self.now_playing_image_url = None

        self.favorite_channels = []

        self.update()

    def update_favorite_channels(self):
        self.favorite_channels = self.client.favorite_channels()

    def update_state(self, state_hash):
        """Update all the state properties with the passed in dictionary."""
        self.status = state_hash.get('status', "stopped")
        self.muted = state_hash.get('muted', False)

        channel_hash = state_hash.get('channel', None)
        np_hash = state_hash.get('now_playing', None)

        if channel_hash:
            self.channel_number = channel_hash.get('channel_number', None)
            self.channel_name = channel_hash.get('channel_name', None)
            self.channel_image_url = channel_hash.get('channel_image_url',
                                                      None)
        else:
            self.channel_number = None
            self.channel_name = None
            self.channel_image_url = None

        if np_hash:
            self.now_playing_title = np_hash.get('title', None)
            self.now_playing_episode_title = np_hash.get('episode_title', None)
            self.now_playing_season_number = np_hash.get('season_number', None)
            self.now_playing_episode_number = np_hash.get('episode_number',
                                                          None)
            self.now_playing_summary = np_hash.get('summary', None)
            self.now_playing_image_url = np_hash.get('image_url', None)
        else:
            self.now_playing_title = None
            self.now_playing_episode_title = None
            self.now_playing_season_number = None
            self.now_playing_episode_number = None
            self.now_playing_summary = None
            self.now_playing_image_url = None

    @property
    def name(self):
        """Return the name of the player."""
        return self._name

    @property
    def state(self):
        """Return the state of the player."""
        if self.status == 'stopped':
            return STATE_IDLE

        if self.status == 'paused':
            return STATE_PAUSED

        if self.status == 'playing':
            return STATE_PLAYING

        return STATE_UNKNOWN

    def update(self):
        """Retrieve latest state."""
        self.update_favorite_channels()
        self.update_state(self.client.status())

    @property
    def source_list(self):
        """List of favorite channels."""
        sources = [channel['name'] for channel in self.favorite_channels]
        return sources

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.muted

    @property
    def media_content_id(self):
        """Content ID of current playing channel."""
        return self.channel_number

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_CHANNEL

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self.now_playing_image_url:
            return self.now_playing_image_url
        elif self.channel_image_url:
            return self.channel_image_url
        else:
            return 'https://getchannels.com/assets/img/icon-1024.png'

    @property
    def media_title(self):
        """Title of current playing media."""
        if self.state == STATE_UNKNOWN:
            return "Offline"
        else:
            return self.now_playing_title

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        return FEATURE_SUPPORT

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) player."""
        if mute != self.muted:
            response = self.client.toggle_muted()
            self.update_state(response)

    def media_stop(self):
        """Send media_stop command to player."""
        self.status = "stopped"
        response = self.client.stop()
        self.update_state(response)

    def media_play(self):
        """Send media_play command to player."""
        response = self.client.resume()
        self.update_state(response)

    def media_pause(self):
        """Send media_pause command to player."""
        response = self.client.pause()
        self.update_state(response)

    def media_next_track(self):
        """Seek ahead."""
        response = self.client.skip_forward()
        self.update_state(response)

    def media_previous_track(self):
        """Seek back."""
        response = self.client.skip_backward()
        self.update_state(response)

    def select_source(self, source):
        for channel in self.favorite_channels:
            if channel["name"] == source:
                response = self.client.play_channel(channel["number"])
                self.update_state(response)

    def play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the player."""
        if media_type == MEDIA_TYPE_CHANNEL:
            response = self.client.play_channel(media_id)
            self.update_state(response)
        elif media_type in [MEDIA_TYPE_VIDEO, MEDIA_TYPE_EPISODE,
                            MEDIA_TYPE_TVSHOW]:
            response = self.client.play_recording(media_id)
            self.update_state(response)

    def seek_forward(self):
        """Seek forward in the timeline."""
        response = self.client.seek_forward()
        self.update_state(response)

    def seek_backward(self):
        """Seek backward in the timeline."""
        response = self.client.seek_backward()
        self.update_state(response)

    def seek_by(self, seconds):
        """Seek backward in the timeline."""
        response = self.client.seek(seconds)
        self.update_state(response)
