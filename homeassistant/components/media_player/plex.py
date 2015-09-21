"""
homeassistant.components.media_player.plex
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides an interface to the Plex API

Configuration:

To use Plex add something like this to your configuration:

media_player:
  platform: plex
  name: plex_server
  user: plex
  password: my_secure_password

Variables:

name
*Required
The name of the backend device (Under Plex Media Server > settings > server).

user
*Required
The Plex username

password
*Required
The Plex password
"""

import logging

from homeassistant.components.media_player import (
    MediaPlayerDevice, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_NEXT_TRACK, MEDIA_TYPE_TVSHOW, MEDIA_TYPE_VIDEO)
from homeassistant.const import (
    STATE_IDLE, STATE_PLAYING, STATE_PAUSED, STATE_UNKNOWN)
from plexapi.myplex import MyPlexUser

REQUIREMENTS = ['https://github.com/miniconfig/python-plexapi/archive/'
                '437e36dca3b7780dc0cb73941d662302c0cd2fa9.zip'
                '#python-plexapi==1.0.2']

_LOGGER = logging.getLogger(__name__)

SUPPORT_PLEX = SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK

# pylint: disable=abstract-method
# pylint: disable=unused-argument


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the plex platform. """
    name = config.get('name', '')
    user = config.get('user', '')
    password = config.get('password', '')
    plexuser = MyPlexUser.signin(user, password)
    plexserver = plexuser.getResource(name).connect()
    dev = plexserver.clients()
    for device in dev:
        if "PlayStation" not in device.name:
            add_devices([PlexClient(device.name, plexserver)])


class PlexClient(MediaPlayerDevice):
    """ Represents a Plex device. """

    # pylint: disable=too-many-public-methods

    def __init__(self, name, plexserver):
        self.client = plexserver.client(name)
        self._name = name
        self._media = None
        self.update()
        self.server = plexserver

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        if self._media is None:
            return STATE_IDLE
        else:
            state = self._media.get('state')
            if state == 'playing':
                return STATE_PLAYING
            elif state == 'paused':
                return STATE_PAUSED
        return STATE_UNKNOWN

    def update(self):
        timeline = self.client.timeline()
        for timeline_item in timeline:
            if timeline_item.get('state') in ('playing', 'paused'):
                self._media = timeline_item

    @property
    def media_content_id(self):
        """ Content ID of current playing media. """
        if self._media is not None:
            return self._media.get('ratingKey')

    @property
    def media_content_type(self):
        """ Content type of current playing media. """
        if self._media is None:
            return None
        media_type = self.server.library.getByKey(
            self.media_content_id).type
        if media_type == 'episode':
            return MEDIA_TYPE_TVSHOW
        elif media_type == 'movie':
            return MEDIA_TYPE_VIDEO
        return None

    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        if self._media is not None:
            total_time = self._media.get('duration')
            return total_time

    @property
    def media_image_url(self):
        """ Image url of current playing media. """
        if self._media is not None:
            return self.server.library.getByKey(self.media_content_id).thumbUrl
        return None

    @property
    def media_title(self):
        """ Title of current playing media. """
        # find a string we can use as a title
        if self._media is not None:
            return self.server.library.getByKey(self.media_content_id).title

    @property
    def media_season(self):
        """ Season of curent playing media. (TV Show only) """
        if self._media is not None:
            show_season = self.server.library.getByKey(
                self.media_content_id).season().index
            return show_season
        return None

    @property
    def media_series_title(self):
        """ Series title of current playing media. (TV Show only)"""
        if self._media is not None:
            series_title = self.server.library.getByKey(
                self.media_content_id).show().title
            return series_title
        return None

    @property
    def media_episode(self):
        """ Episode of current playing media. (TV Show only) """
        if self._media is not None:
            show_episode = self.server.library.getByKey(
                self.media_content_id).index
            return show_episode
        return None

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        return SUPPORT_PLEX

    def media_play(self):
        """ media_play media player. """
        self.client.play()

    def media_pause(self):
        """ media_pause media player. """
        self.client.pause()

    def media_next_track(self):
        """ Send next track command. """
        self.client.skipNext()

    def media_previous_track(self):
        """ Send previous track command. """
        self.client.skipPrevious()
