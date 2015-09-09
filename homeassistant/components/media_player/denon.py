"""
homeassistant.components.media_player.denon
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides an interface to Denon Network Receivers.
Developed for a Denon DRA-N5, see
http://www.denon.co.uk/chg/product/compactsystems/networkmusicsystems/ceolpiccolo

A few notes:
    - As long as this module is active and connected, the receiver does
      not seem to accept additional telnet connections.

    - Be careful with the volume. 50% or even 100% are very loud.

    - To be able to wake up the receiver, activate the "remote" setting
      in the receiver's settings.

    - Play and pause are supported, toggling is not possible.

    - Seeking cannot be implemented as the UI sends absolute positions.
      Only seeking via simulated button presses is possible.

Configuration:

To use your Denon you will need to add something like the following to
your config/configuration.yaml:

media_player:
  platform: denon
  name: Music station
  host: 192.168.0.123

Variables:

host
*Required
The ip of the player. Example: 192.168.0.123

name
*Optional
The name of the device.
"""
import telnetlib
import logging

from homeassistant.components.media_player import (
    MediaPlayerDevice, SUPPORT_PAUSE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_MUTE, SUPPORT_PREVIOUS_TRACK, SUPPORT_NEXT_TRACK,
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF,
    DOMAIN)
from homeassistant.const import (
    CONF_HOST, STATE_OFF, STATE_ON, STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

SUPPORT_DENON = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Denon platform. """
    if not config.get(CONF_HOST):
        _LOGGER.error(
            "Missing required configuration items in %s: %s",
            DOMAIN,
            CONF_HOST)
        return False

    add_devices([
        DenonDevice(
            config.get('name', 'Music station'),
            config.get('host'))
    ])

    return True


class DenonDevice(MediaPlayerDevice):
    """ Represents a Denon device. """

    # pylint: disable=too-many-public-methods

    def __init__(self, name, host):
        self._name = name
        self._host = host
        self._telnet = telnetlib.Telnet(self._host)

    def query(self, message):
        """ Send request and await response from server """
        try:
            # unspecified command, should be ignored
            self._telnet.write("?".encode('UTF-8') + b'\r')
        except (EOFError, BrokenPipeError, ConnectionResetError):
            self._telnet.open(self._host)

        self._telnet.read_very_eager()  # skip what is not requested

        self._telnet.write(message.encode('ASCII') + b'\r')
        # timeout 200ms, defined by protocol
        resp = self._telnet.read_until(b'\r', timeout=0.2)\
            .decode('UTF-8').strip()

        if message == "PW?":
            # workaround; PW? sends also SISTATUS
            self._telnet.read_until(b'\r', timeout=0.2)

        return resp

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        pwstate = self.query('PW?')
        if pwstate == "PWSTANDBY":
            return STATE_OFF
        if pwstate == "PWON":
            return STATE_ON

        return STATE_UNKNOWN

    @property
    def volume_level(self):
        """ Volume level of the media player (0..1). """
        return int(self.query('MV?')[len('MV'):]) / 60

    @property
    def is_volume_muted(self):
        """ Boolean if volume is currently muted. """
        return self.query('MU?') == "MUON"

    @property
    def media_title(self):
        """ Current media source. """
        return self.query('SI?')[len('SI'):]

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        return SUPPORT_DENON

    def turn_off(self):
        """ turn_off media player. """
        self.query('PWSTANDBY')

    def volume_up(self):
        """ volume_up media player. """
        self.query('MVUP')

    def volume_down(self):
        """ volume_down media player. """
        self.query('MVDOWN')

    def set_volume_level(self, volume):
        """ set volume level, range 0..1. """
        # 60dB max
        self.query('MV' + str(round(volume * 60)).zfill(2))

    def mute_volume(self, mute):
        """ mute (true) or unmute (false) media player. """
        self.query('MU' + ('ON' if mute else 'OFF'))

    def media_play_pause(self):
        """ media_play_pause media player. """
        raise NotImplementedError()

    def media_play(self):
        """ media_play media player. """
        self.query('NS9A')

    def media_pause(self):
        """ media_pause media player. """
        self.query('NS9B')

    def media_next_track(self):
        """ Send next track command. """
        self.query('NS9D')

    def media_previous_track(self):
        self.query('NS9E')

    def media_seek(self, position):
        raise NotImplementedError()

    def turn_on(self):
        """ turn the media player on. """
        self.query('PWON')
