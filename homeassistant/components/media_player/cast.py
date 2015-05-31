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

CAST_SPLASH = 'https://home-assistant.io/images/cast/splash.png'


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
        hosts = (host_port[0] for host_port
                 in pychromecast.discover_chromecasts())

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

        self.cast.socket_client.receiver_controller.register_status_listener(
            self)
        self.cast.socket_client.media_controller.register_status_listener(self)

        self.cast_status = self.cast.status
        self.media_status = self.cast.media_controller.status

    @property
    def should_poll(self):
        return False

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
        cast_status = self.cast_status
        media_status = self.media_status
        media_controller = self.cast.media_controller

        state_attr = {
            ATTR_MEDIA_STATE: self.media_state,
            'application_id': self.cast.app_id,
        }

        if cast_status:
            state_attr[ATTR_MEDIA_VOLUME] = cast_status.volume_level

        if media_status.content_id:
            state_attr[ATTR_MEDIA_CONTENT_ID] = media_status.content_id

        if media_status.duration:
            state_attr[ATTR_MEDIA_DURATION] = media_status.duration

        if media_controller.title:
            state_attr[ATTR_MEDIA_TITLE] = media_controller.title

        if media_controller.thumbnail:
            state_attr[ATTR_ENTITY_PICTURE] = media_controller.thumbnail

        return state_attr

    def turn_on(self):
        """ Turns on the ChromeCast. """
        # The only way we can turn the Chromecast is on is by launching an app
        if not self.cast.status or not self.cast.status.is_active_input:
            if self.cast.app_id:
                self.cast.quit_app()

            self.cast.play_media(
                CAST_SPLASH, pychromecast.STREAM_TYPE_BUFFERED)

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

    def volume_mute(self):
        """ Service to send the chromecast the command for volume up. """
        self.cast.set_volume(0)

    def volume_set(self, volume):
        """ Service to send the chromecast the command for volume down. """
        self.cast.set_volume(volume)

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

    def media_prev_track(self):
        """ media_prev_track media player. """
        self.cast.media_controller.rewind()

    def media_next_track(self):
        """ media_next_track media player. """
        self.cast.media_controller.skip()

    def play_youtube_video(self, video_id):
        """ Plays specified video_id on the Chromecast's YouTube channel. """
        self.youtube.play_video(video_id)

    def new_cast_status(self, status):
        """ Called when a new cast status is received. """
        self.cast_status = status
        self.update_ha_state()

    def new_media_status(self, status):
        """ Called when a new media status is received. """
        self.media_status = status
        self.update_ha_state()
