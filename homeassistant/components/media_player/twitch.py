"""
homeassistant.components.media_player.twitch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Twitch stream status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.twitch/
"""

from homeassistant.const import STATE_PLAYING, STATE_OFF

from homeassistant.components.media_player import (
    MediaPlayerDevice, MEDIA_TYPE_CHANNEL)

REQUIREMENTS = ['python-twitch==1.2.0']
DOMAIN = 'twitch'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Twitch platform. """
    add_devices(
        [TwitchDevice(channel) for channel in config.get('channels', [])])


class TwitchDevice(MediaPlayerDevice):
    """ Represents an Twitch channel. """

    # pylint: disable=abstract-method
    def __init__(self, channel):
        self._channel = channel
        self._state = STATE_OFF
        self._preview = None
        self._game = None
        self._title = None

    @property
    def should_poll(self):
        """ Device should be polled. """
        return True

    @property
    def state(self):
        """ State of the player. """
        return self._state

    # pylint: disable=no-member
    def update(self):
        """ Update device state. """
        from twitch.api import v3 as twitch
        stream = twitch.streams.by_channel(self._channel).get('stream')
        if stream:
            self._game = stream.get('channel').get('game')
            self._title = stream.get('channel').get('status')
            self._preview = stream.get('preview').get('small')
            self._state = STATE_PLAYING
        else:
            self._state = STATE_OFF

    @property
    def name(self):
        """ Channel name. """
        return self._channel

    @property
    def media_title(self):
        """ Channel title. """
        return self._title

    @property
    def app_name(self):
        """ Game name. """
        return self._game

    @property
    def media_image_url(self):
        """ Image preview url of the live stream. """
        return self._preview

    @property
    def media_content_type(self):
        """ Media type (channel). """
        return MEDIA_TYPE_CHANNEL

    def media_pause(self):
        """ Must implement because UI can pause. """
        pass
