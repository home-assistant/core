"""
homeassistant.components.media_player.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demo implementation of the media player.

"""
from homeassistant.const import (
    STATE_PLAYING, STATE_PAUSED, STATE_OFF)

from homeassistant.components.media_player import (
    MediaPlayerDevice, YOUTUBE_COVER_URL_FORMAT, MEDIA_TYPE_VIDEO,
    SUPPORT_PAUSE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_MUTE, SUPPORT_YOUTUBE,
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the cast platform. """
    add_devices([
        DemoYoutubePlayer(
            'Living Room', 'eyU3bRy2x44',
            '♥♥ The Best Fireplace Video (3 hours)'),
        DemoYoutubePlayer('Bedroom', 'kxopViU98Xo', 'Epic sax guy 10 hours')
    ])


YOUTUBE_PLAYER_SUPPORT = \
    SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_YOUTUBE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF


class DemoYoutubePlayer(MediaPlayerDevice):
    """ A Demo media player that only supports YouTube. """
    # We only implement the methods that we support
    # pylint: disable=abstract-method

    def __init__(self, name, youtube_id=None, media_title=None):
        self._name = name
        self._player_state = STATE_PLAYING
        self.youtube_id = youtube_id
        self._media_title = media_title
        self._volume_level = 1.0
        self._volume_muted = False

    @property
    def should_poll(self):
        """ We will push an update after each command. """
        return False

    @property
    def name(self):
        """ Name of the media player. """
        return self._name

    @property
    def state(self):
        """ State of the player. """
        return self._player_state

    @property
    def volume_level(self):
        """ Volume level of the media player (0..1). """
        return self._volume_level

    @property
    def is_volume_muted(self):
        """ Boolean if volume is currently muted. """
        return self._volume_muted

    @property
    def media_content_id(self):
        """ Content ID of current playing media. """
        return self.youtube_id

    @property
    def media_content_type(self):
        """ Content type of current playing media. """
        return MEDIA_TYPE_VIDEO

    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        return 360

    @property
    def media_image_url(self):
        """ Image url of current playing media. """
        return YOUTUBE_COVER_URL_FORMAT.format(self.youtube_id)

    @property
    def media_title(self):
        """ Title of current playing media. """
        return self._media_title

    @property
    def app_name(self):
        """ Current running app. """
        return "YouTube"

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        return YOUTUBE_PLAYER_SUPPORT

    def turn_on(self):
        """ turn the media player on. """
        self._player_state = STATE_PLAYING
        self.update_ha_state()

    def turn_off(self):
        """ turn the media player off. """
        self._player_state = STATE_OFF
        self.update_ha_state()

    def mute_volume(self, mute):
        """ mute the volume. """
        self._volume_muted = mute
        self.update_ha_state()

    def set_volume_level(self, volume):
        """ set volume level, range 0..1. """
        self._volume_level = volume
        self.update_ha_state()

    def media_play(self):
        """ Send play commmand. """
        self._player_state = STATE_PLAYING
        self.update_ha_state()

    def media_pause(self):
        """ Send pause command. """
        self._player_state = STATE_PAUSED
        self.update_ha_state()

    def play_youtube(self, media_id):
        """ Plays a YouTube media. """
        self.youtube_id = media_id
        self._media_title = 'some YouTube video'
        self.update_ha_state()
