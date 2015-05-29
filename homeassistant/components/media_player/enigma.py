"""
homeassistant.components.media_player.enigma
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Beta implementation of the Enigma2 media player.
Currently only shows whats playing on the box.

You should have a recent version of OpenWebIf installed
on your E2 box.

There is no support for username/password authentication
at this time.

Configuration:

To use the media_player you will need to add something like the
following to your config/configuration.yaml

media_player:
    platform: enigma
    name: Vu Duo2
    host: 192.168.1.26
    port: 80

Variables:

host
*Required
This is the IP address of your Enigma2 box. Example: 192.168.1.32

port
*Optional
The port your Enigma2 box uses, defaults to 80. Example: 8080

name
*Optional
The name to use when displaying this Enigma2 switch instance.

"""
from homeassistant.components.media_player import (
    MediaPlayerDevice, STATE_NO_APP, ATTR_MEDIA_STATE,
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_TITLE, ATTR_MEDIA_DURATION,
    ATTR_MEDIA_VOLUME, MEDIA_STATE_PLAYING, MEDIA_STATE_STOPPED)

import logging
import requests
_LOGGING = logging.getLogger(__name__)

# pylint: disable=unused-argument


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the enigma media player platform. """

    host = config.get('host', None)
    port = config.get('port', "80")
    name = config.get('name', "Enigma2")

    if not host:
        _LOGGING.error('Missing config variable-host')
        return False

    add_devices([
        EnigmaMediaPlayer(name, host, port)
    ])


class EnigmaMediaPlayer(MediaPlayerDevice):

    """ An Enigma2 media player. """

    def __init__(self, name, host, port):
        self._name = name
        self._host = host
        # self._port = port
        self.state_attr = {ATTR_MEDIA_STATE: MEDIA_STATE_STOPPED}
        # self.update()

        self.is_playing = False
        self.media_title = None
        self.volume = 1.0
        self.channel_title = None

    @property
    def should_poll(self):
        """ Need to refresh ourselves. """
        return True

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return STATE_NO_APP if self.is_playing is False else self.channel_title

    @property
    def state_attributes(self):
        """ Returns the state attributes. """

        return self.state_attr

    def turn_off(self):
        """ turn_off media player. """
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
        self.media_title = 'Demo media title'
        self.is_playing = True

    def update(self):
        """ Update state of the media_player. """
        _LOGGING.info("updating status enigma media_player")

        url = 'http://%s/api/statusinfo' % self._host
        _LOGGING.info('url: %s', url)

        response = requests.get(url)

        _LOGGING.info('response: %s' % response)
        _LOGGING.info("status_code %s" % response.status_code)

        if response.status_code != 200:
            _LOGGING.error("There was an error connecting to %s" % url)
            _LOGGING.error("status_code %s" % response.status_code)
            _LOGGING.error("error %s" % response.error)

            return

        _LOGGING.info('r.json: %s' % response.json())

        in_standby = response.json()['inStandby']
        _LOGGING.info('r.json inStandby: %s' % in_standby)

        if in_standby == 'true':
            self.state_attr = {
                ATTR_MEDIA_STATE: MEDIA_STATE_STOPPED
            }
            self.is_playing = False
            self.media_title = None
        else:
            self.is_playing = True
            self.media_title = response.json()['currservice_name']
            self.channel_title = response.json()['currservice_station']

            self.state_attr = {
                ATTR_MEDIA_CONTENT_ID: self.channel_title,
                ATTR_MEDIA_TITLE: self.media_title,
                ATTR_MEDIA_DURATION: 100,
                ATTR_MEDIA_VOLUME: self.volume,
                ATTR_MEDIA_STATE: MEDIA_STATE_PLAYING
            }
