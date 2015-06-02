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
try:
    import openwebif.api
    from openwebif.error import OpenWebIfError, MissingParamError
except ImportError:
    openwebif.api = None

_LOGGING = logging.getLogger(__name__)

# pylint: disable=unused-argument


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the enigma media player platform. """

    if openwebif.api is None:
        _LOGGING.error((
            "Failed to import openwebif. Did you maybe not install the "
            "'openwebif.py' dependency?"))

        return False

    host = config.get('host', None)
    port = config.get('port', "80")
    name = config.get('name', "Enigma2")

    try:
        e2_box = openwebif.api.CreateDevice(host, port=port)
    except MissingParamError as param_err:
        _LOGGING.error("Missing required param: %s", param_err)
        return False
    except OpenWebIfError as conn_err:
        _LOGGING.error("Unable to connect: %s", conn_err)
        return False

    add_devices([
        EnigmaMediaPlayer(name, e2_box)
    ])


class EnigmaMediaPlayer(MediaPlayerDevice):

    """ An Enigma2 media player. """

    def __init__(self, name, e2_box):
        self._name = name
        self._e2_box = e2_box
        self.is_playing = False
        self.media_title = None
        self.volume = 1.0
        self.channel_title = None

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self.channel_title if self.is_playing else STATE_NO_APP

    @property
    def state_attributes(self):
        """ Returns the state attributes. """

        status_info = self._e2_box.get_status_info()
        _LOGGING.info('status_info: %s', status_info)

        in_standby = status_info['inStandby']
        _LOGGING.info('inStandby: %s', in_standby)

        if in_standby == 'true':
            state_attr = {
                ATTR_MEDIA_STATE: MEDIA_STATE_STOPPED
            }
            self.is_playing = False
            self.media_title = None
        else:
            self.is_playing = True
            self.media_title = status_info['currservice_name']
            self.channel_title = status_info['currservice_station']

            state_attr = {
                ATTR_MEDIA_CONTENT_ID: self.channel_title,
                ATTR_MEDIA_TITLE: self.media_title,
                ATTR_MEDIA_DURATION: 100,
                ATTR_MEDIA_VOLUME: self.volume,
                ATTR_MEDIA_STATE: MEDIA_STATE_PLAYING
            }

        return state_attr

    def update(self):
        """ Update state of the media_player. """
        _LOGGING.info("updating status enigma media_player")
