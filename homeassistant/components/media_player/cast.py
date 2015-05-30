"""
homeassistant.components.media_player.chromecast
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to interact with Cast devices on the network.

WARNING: This platform is currently not working due to a changed Cast API
"""
import logging

try:
    import pychromecast
    import pychromecast.controllers.youtube as youtube
except ImportError:
    pychromecast = None

from homeassistant.const import ATTR_ENTITY_PICTURE

# ATTR_MEDIA_ALBUM, ATTR_MEDIA_IMAGE_URL,
# ATTR_MEDIA_ARTIST,
from homeassistant.components.media_player import (
    MediaPlayerDevice, STATE_NO_APP, ATTR_MEDIA_STATE, ATTR_MEDIA_TITLE,
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_DURATION, ATTR_MEDIA_VOLUME,
    MEDIA_STATE_PLAYING, MEDIA_STATE_PAUSED, MEDIA_STATE_STOPPED,
    MEDIA_STATE_UNKNOWN)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the cast platform. """
    logger = logging.getLogger(__name__)

    if pychromecast is None:
        logger.error((
            "Failed to import pychromecast. Did you maybe not install the "
            "'pychromecast' dependency?"))

        return False

    if discovery_info:
        hosts = [discovery_info[0]]

    else:
        hosts = pychromecast.discover_chromecasts()

    casts = []

    for host in hosts:
        try:
            casts.append(CastDevice(host))
        except pychromecast.ChromecastConnectionError:
            pass

    add_devices(casts)


class CastDevice(MediaPlayerDevice):
    """ Represents a Cast device on the network. """

    def __init__(self, host):
        self.cast = pychromecast.Chromecast(host)
        self.youtube = youtube.YouTubeController()
        self.cast.register_handler(self.youtube)

    @property
    def name(self):
        """ Returns the name of the device. """
        return self.cast.device.friendly_name

    @property
    def state(self):
        """ Returns the state of the device. """
        if self.cast.is_idle:
            return STATE_NO_APP
        else:
            return self.cast.app_display_name

    @property
    def media_state(self):
        """ Returns the media state. """
        media_controller = self.cast.media_controller

        if media_controller.is_playing:
            return MEDIA_STATE_PLAYING
        elif media_controller.is_paused:
            return MEDIA_STATE_PAUSED
        elif media_controller.is_idle:
            return MEDIA_STATE_STOPPED
        else:
            return MEDIA_STATE_UNKNOWN

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        cast_status = self.cast.status
        media_controller = self.cast.media_controller
        media_status = media_controller.status

        state_attr = {
            ATTR_MEDIA_STATE: self.media_state,
            'application_id': self.cast.app_id,
        }

        if cast_status:
            state_attr[ATTR_MEDIA_VOLUME] = cast_status.volume_level,

        if media_status.content_id:
            state_attr[ATTR_MEDIA_CONTENT_ID] = media_status.content_id

        if media_status.duration:
            state_attr[ATTR_MEDIA_DURATION] = media_status.duration

        if media_controller.title:
            state_attr[ATTR_MEDIA_TITLE] = media_controller.title

        if media_controller.thumbnail:
            state_attr[ATTR_ENTITY_PICTURE] = media_controller.thumbnail

        return state_attr

    def turn_off(self):
        """ Service to exit any running app on the specimedia player ChromeCast and
        shows idle screen. Will quit all ChromeCasts if nothing specified.
        """
        self.cast.quit_app()

    def volume_up(self):
        """ Service to send the chromecast the command for volume up. """
        self.cast.volume_up()

    def volume_down(self):
        """ Service to send the chromecast the command for volume down. """
        self.cast.volume_down()

    def media_play_pause(self):
        """ Service to send the chromecast the command for play/pause. """
        media_state = self.media_state

        if media_state in (MEDIA_STATE_STOPPED, MEDIA_STATE_PAUSED):
            self.cast.media_controller.play()
        elif media_state == MEDIA_STATE_PLAYING:
            self.cast.media_controller.pause()

    def media_play(self):
        """ Service to send the chromecast the command for play/pause. """
        if self.media_state in (MEDIA_STATE_STOPPED, MEDIA_STATE_PAUSED):
            self.cast.media_controller.play()

    def media_pause(self):
        """ Service to send the chromecast the command for play/pause. """
        if self.media_state == MEDIA_STATE_PLAYING:
            self.cast.media_controller.pause()

    def play_youtube_video(self, video_id):
        """ Plays specified video_id on the Chromecast's YouTube channel. """
        self.youtube.play_video(video_id)
