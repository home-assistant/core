"""
homeassistant.components.media_player.chromecast
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demo implementation of the media player.
"""

from homeassistant.components.media_player import (
    MediaPlayerDevice, STATE_NO_APP, ATTR_MEDIA_STATE,
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_TITLE, ATTR_MEDIA_DURATION,
    ATTR_MEDIA_VOLUME, MEDIA_STATE_PLAYING, MEDIA_STATE_STOPPED,
    YOUTUBE_COVER_URL_FORMAT)
from homeassistant.const import ATTR_ENTITY_PICTURE


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the cast platform. """
    add_devices([
        DemoMediaPlayer(
            'Living Room', 'eyU3bRy2x44',
            '♥♥ The Best Fireplace Video (3 hours)'),
        DemoMediaPlayer('Bedroom', 'kxopViU98Xo', 'Epic sax guy 10 hours')
    ])


class DemoMediaPlayer(MediaPlayerDevice):
    """ A Demo media player that only supports YouTube. """

    def __init__(self, name, youtube_id=None, media_title=None):
        self._name = name
        self.is_playing = youtube_id is not None
        self.youtube_id = youtube_id
        self.media_title = media_title
        self.volume = 1.0

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return STATE_NO_APP if self.youtube_id is None else "YouTube"

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        if self.youtube_id is None:
            return

        state_attr = {
            ATTR_MEDIA_CONTENT_ID: self.youtube_id,
            ATTR_MEDIA_TITLE: self.media_title,
            ATTR_MEDIA_DURATION: 100,
            ATTR_MEDIA_VOLUME: self.volume,
            ATTR_ENTITY_PICTURE:
            YOUTUBE_COVER_URL_FORMAT.format(self.youtube_id)
        }

        if self.is_playing:
            state_attr[ATTR_MEDIA_STATE] = MEDIA_STATE_PLAYING
        else:
            state_attr[ATTR_MEDIA_STATE] = MEDIA_STATE_STOPPED

        return state_attr

    def turn_off(self):
        """ turn_off media player. """
        self.youtube_id = None
        self.is_playing = False

    def volume_up(self):
        """ volume_up media player. """
        if self.volume < 1:
            self.volume += 0.1

    def volume_down(self):
        """ volume_down media player. """
        if self.volume > 0:
            self.volume -= 0.1

    def media_play_pause(self):
        """ media_play_pause media player. """
        self.is_playing = not self.is_playing

    def media_play(self):
        """ media_play media player. """
        self.is_playing = True

    def media_pause(self):
        """ media_pause media player. """
        self.is_playing = False

    def play_youtube(self, media_id):
        """ Plays a YouTube media. """
        self.youtube_id = media_id
        self.media_title = 'Demo media title'
        self.is_playing = True
