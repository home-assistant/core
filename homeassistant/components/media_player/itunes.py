"""
Support for interfacing to iTunes API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.itunes/
"""
import logging

import requests

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, MEDIA_TYPE_PLAYLIST, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK, SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    MediaPlayerDevice)
from homeassistant.const import (
    STATE_IDLE, STATE_OFF, STATE_ON, STATE_PAUSED, STATE_PLAYING)

_LOGGER = logging.getLogger(__name__)

SUPPORT_ITUNES = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_SEEK | \
    SUPPORT_PLAY_MEDIA

SUPPORT_AIRPLAY = SUPPORT_VOLUME_SET | SUPPORT_TURN_ON | SUPPORT_TURN_OFF

DOMAIN = 'itunes'


class Itunes(object):
    """iTunes API client."""

    def __init__(self, host, port):
        """Initialize the iTunes device."""
        self.host = host
        self.port = port

    @property
    def _base_url(self):
        """Return the base url for endpoints."""
        if self.port:
            return self.host + ":" + str(self.port)
        else:
            return self.host

    def _request(self, method, path, params=None):
        """Make the actual request and returns the parsed response."""
        url = self._base_url + path

        try:
            if method == 'GET':
                response = requests.get(url)
            elif method == "POST":
                response = requests.put(url, params)
            elif method == "PUT":
                response = requests.put(url, params)
            elif method == "DELETE":
                response = requests.delete(url)

            return response.json()
        except requests.exceptions.HTTPError:
            return {'player_state': 'error'}
        except requests.exceptions.RequestException:
            return {'player_state': 'offline'}

    def _command(self, named_command):
        """Make a request for a controlling command."""
        return self._request('PUT', '/' + named_command)

    def now_playing(self):
        """Return the current state."""
        return self._request('GET', '/now_playing')

    def set_volume(self, level):
        """Set the volume and returns the current state, level 0-100."""
        return self._request('PUT', '/volume', {'level': level})

    def set_muted(self, muted):
        """Mute and returns the current state, muted True or False."""
        return self._request('PUT', '/mute', {'muted': muted})

    def play(self):
        """Set playback to play and returns the current state."""
        return self._command('play')

    def pause(self):
        """Set playback to paused and returns the current state."""
        return self._command('pause')

    def next(self):
        """Skip to the next track and returns the current state."""
        return self._command('next')

    def previous(self):
        """Skip back and returns the current state."""
        return self._command('previous')

    def play_playlist(self, playlist_id_or_name):
        """Set a playlist to be current and returns the current state."""
        response = self._request('GET', '/playlists')
        playlists = response.get('playlists', [])

        found_playlists = \
            [playlist for playlist in playlists if
             (playlist_id_or_name in [playlist["name"], playlist["id"]])]

        if len(found_playlists) > 0:
            playlist = found_playlists[0]
            path = '/playlists/' + playlist['id'] + '/play'
            return self._request('PUT', path)

    def artwork_url(self):
        """Return a URL of the current track's album art."""
        return self._base_url + '/artwork'

    def airplay_devices(self):
        """Return a list of AirPlay devices."""
        return self._request('GET', '/airplay_devices')

    def airplay_device(self, device_id):
        """Return an AirPlay device."""
        return self._request('GET', '/airplay_devices/' + device_id)

    def toggle_airplay_device(self, device_id, toggle):
        """Toggle airplay device on or off, id, toggle True or False."""
        command = 'on' if toggle else 'off'
        path = '/airplay_devices/' + device_id + '/' + command
        return self._request('PUT', path)

    def set_volume_airplay_device(self, device_id, level):
        """Set volume, returns current state of device, id,level 0-100."""
        path = '/airplay_devices/' + device_id + '/volume'
        return self._request('PUT', path, {'level': level})


# pylint: disable=unused-argument, abstract-method
# pylint: disable=too-many-instance-attributes
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the itunes platform."""
    add_devices([
        ItunesDevice(
            config.get('name', 'iTunes'),
            config.get('host'),
            config.get('port'),
            add_devices
        )
    ])


class ItunesDevice(MediaPlayerDevice):
    """Representation of an iTunes API instance."""

    # pylint: disable=too-many-public-methods
    def __init__(self, name, host, port, add_devices):
        """Initialize the iTunes device."""
        self._name = name
        self._host = host
        self._port = port
        self._add_devices = add_devices

        self.client = Itunes(self._host, self._port)

        self.current_volume = None
        self.muted = None
        self.current_title = None
        self.current_album = None
        self.current_artist = None
        self.current_playlist = None
        self.content_id = None

        self.player_state = None

        self.airplay_devices = {}

        self.update()

    def update_state(self, state_hash):
        """Update all the state properties with the passed in dictionary."""
        self.player_state = state_hash.get('player_state', None)

        self.current_volume = state_hash.get('volume', 0)
        self.muted = state_hash.get('muted', None)
        self.current_title = state_hash.get('name', None)
        self.current_album = state_hash.get('album', None)
        self.current_artist = state_hash.get('artist', None)
        self.current_playlist = state_hash.get('playlist', None)
        self.content_id = state_hash.get('id', None)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self.player_state == 'offline' or self.player_state is None:
            return 'offline'

        if self.player_state == 'error':
            return 'error'

        if self.player_state == 'stopped':
            return STATE_IDLE

        if self.player_state == 'paused':
            return STATE_PAUSED
        else:
            return STATE_PLAYING

    def update(self):
        """Retrieve latest state."""
        now_playing = self.client.now_playing()
        self.update_state(now_playing)

        found_devices = self.client.airplay_devices()
        found_devices = found_devices.get('airplay_devices', [])

        new_devices = []

        for device_data in found_devices:
            device_id = device_data.get('id')

            if self.airplay_devices.get(device_id):
                # update it
                airplay_device = self.airplay_devices.get(device_id)
                airplay_device.update_state(device_data)
            else:
                # add it
                airplay_device = AirPlayDevice(device_id, self.client)
                airplay_device.update_state(device_data)
                self.airplay_devices[device_id] = airplay_device
                new_devices.append(airplay_device)

        if new_devices:
            self._add_devices(new_devices)

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.muted

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self.current_volume/100.0

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self.content_id

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self.player_state in (STATE_PLAYING, STATE_IDLE, STATE_PAUSED) and \
           self.current_title is not None:
            return self.client.artwork_url()
        else:
            return 'https://cloud.githubusercontent.com/assets/260/9829355' \
                '/33fab972-58cf-11e5-8ea2-2ca74bdaae40.png'

    @property
    def media_title(self):
        """Title of current playing media."""
        return self.current_title

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self.current_artist

    @property
    def media_album_name(self):
        """Album of current playing media (Music track only)."""
        return self.current_album

    @property
    def media_playlist(self):
        """Title of the currently playing playlist."""
        return self.current_playlist

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_ITUNES

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        response = self.client.set_volume(int(volume * 100))
        self.update_state(response)

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        response = self.client.set_muted(mute)
        self.update_state(response)

    def media_play(self):
        """Send media_play command to media player."""
        response = self.client.play()
        self.update_state(response)

    def media_pause(self):
        """Send media_pause command to media player."""
        response = self.client.pause()
        self.update_state(response)

    def media_next_track(self):
        """Send media_next command to media player."""
        response = self.client.next()
        self.update_state(response)

    def media_previous_track(self):
        """Send media_previous command media player."""
        response = self.client.previous()
        self.update_state(response)

    def play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player."""
        if media_type == MEDIA_TYPE_PLAYLIST:
            response = self.client.play_playlist(media_id)
            self.update_state(response)


class AirPlayDevice(MediaPlayerDevice):
    """Representation an AirPlay device via an iTunes API instance."""

    # pylint: disable=too-many-public-methods
    def __init__(self, device_id, client):
        """Initialize the AirPlay device."""
        self._id = device_id
        self.client = client
        self.device_name = "AirPlay"
        self.kind = None
        self.active = False
        self.selected = False
        self.volume = 0
        self.supports_audio = False
        self.supports_video = False
        self.player_state = None

    def update_state(self, state_hash):
        """Update all the state properties with the passed in dictionary."""
        if 'player_state' in state_hash:
            self.player_state = state_hash.get('player_state', None)

        if 'name' in state_hash:
            name = state_hash.get('name', '')
            self.device_name = (name + ' AirTunes Speaker').strip()

        if 'kind' in state_hash:
            self.kind = state_hash.get('kind', None)

        if 'active' in state_hash:
            self.active = state_hash.get('active', None)

        if 'selected' in state_hash:
            self.selected = state_hash.get('selected', None)

        if 'sound_volume' in state_hash:
            self.volume = state_hash.get('sound_volume', 0)

        if 'supports_audio' in state_hash:
            self.supports_audio = state_hash.get('supports_audio', None)

        if 'supports_video' in state_hash:
            self.supports_video = state_hash.get('supports_video', None)

    @property
    def name(self):
        """Return the name of the device."""
        return self.device_name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if self.selected is True:
            return "mdi:volume-high"
        else:
            return "mdi:volume-off"

    @property
    def state(self):
        """Return the state of the device."""
        if self.selected is True:
            return STATE_ON
        else:
            return STATE_OFF

    def update(self):
        """Retrieve latest state."""

    @property
    def volume_level(self):
        """Return the volume."""
        return float(self.volume)/100.0

    @property
    def media_content_type(self):
        """Flag of media content that is supported."""
        return MEDIA_TYPE_MUSIC

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_AIRPLAY

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        volume = int(volume * 100)
        response = self.client.set_volume_airplay_device(self._id, volume)
        self.update_state(response)

    def turn_on(self):
        """Select AirPlay."""
        self.update_state({"selected": True})
        self.update_ha_state()
        response = self.client.toggle_airplay_device(self._id, True)
        self.update_state(response)

    def turn_off(self):
        """Deselect AirPlay."""
        self.update_state({"selected": False})
        self.update_ha_state()
        response = self.client.toggle_airplay_device(self._id, False)
        self.update_state(response)
