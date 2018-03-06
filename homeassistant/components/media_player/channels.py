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


class Channels(object):
    """Channels API client."""

    def __init__(self, host, port):
        """Initialize the Channels client."""
        self.host = host
        self.port = port

    @property
    def _base_url(self):
        """Return the base url for endpoints."""
        return "http://" + self.host + ":" + str(self.port)

    def _request(self, method, path, params=None):
        """Make the actual request and returns the parsed response."""
        url = self._base_url + path

        try:
            if method == 'GET':
                response = requests.get(url, timeout=TIMEOUT)
            elif method == "POST":
                response = requests.post(url, params, timeout=TIMEOUT)
            elif method == "PUT":
                response = requests.put(url, params, timeout=TIMEOUT)
            elif method == "DELETE":
                response = requests.delete(url, timeout=TIMEOUT)

            if response:
                return response.json()
            else:
                return {'status': 'error'}
        except requests.exceptions.HTTPError:
            return {'status': 'error'}
        except requests.exceptions.Timeout:
            return {'status': 'offline'}
        except requests.exceptions.RequestException:
            return {'status': 'offline'}

    def _command(self, named_command):
        """Make a request for a controlling command."""
        return self._request('POST', '/api/' + named_command)

    def status(self):
        """Return the current state."""
        return self._request('GET', '/api/status')

    def favorite_channels(self):
        """Return the favorite channels."""
        response = self._request('GET', '/api/favorite_channels')
        if "favorite_channels" in response:
            return response["favorite_channels"]
        else:
            return []

    def pause(self):
        """Set playback to paused and returns the current state."""
        return self._command('pause')

    def resume(self):
        """Set playback to play and returns the current state."""
        return self._command('resume')

    def stop(self):
        """Set playback to stop and returns the current state."""
        return self._command('stop')

    def seek(self, seconds):
        """Seek number of seconds."""
        seconds = str(seconds or 0)
        return self._command('seek/' + seconds)

    def seek_forward(self):
        """Seek forward."""
        return self._command('seek_forward')

    def seek_backward(self):
        """Seek backward."""
        return self._command('seek_backward')

    def skip_forward(self):
        """Skip forward to the next chapter mark."""
        return self._command('skip_forward')

    def skip_backward(self):
        """Skip backward to the previous chapter mark."""
        return self._command('skip_backward')

    def toggle_muted(self):
        """Mute and returns the current state."""
        return self._command('toggle_mute')

    def play_channel(self, channel_number):
        """Set a channel to play and returns the current state."""
        return self._request('POST', '/api/play/channel/' +
                             str(channel_number))

    def play_recording(self, recording_id):
        """Set a recording to play and returns the current state."""
        return self._request('POST', '/api/play/recording/' +
                             str(recording_id))

# pylint: disable=unused-argument, abstract-method
# pylint: disable=too-many-instance-attributes
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Channels platform."""

    device = ChannelsApp(
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

class ChannelsApp(MediaPlayerDevice):
    """Representation of a Channels instance."""

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
