"""
homeassistant.components.media_player.denon
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides an interface to Denon Network Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.denon/
"""
import logging
import telnetlib

from homeassistant.components.media_player import (
    DOMAIN, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    MediaPlayerDevice)
from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON, STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)

SUPPORT_DENON = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Denon platform. """
    if not config.get(CONF_HOST):
        _LOGGER.error(
            "Missing required configuration items in %s: %s",
            DOMAIN,
            CONF_HOST)
        return False

    denon = DenonDevice(
        config.get("name", "Music station"),
        config.get("host")
    )
    if denon.update():
        add_devices([denon])
        return True
    else:
        return False


class DenonDevice(MediaPlayerDevice):
    """ Represents a Denon device. """

    # pylint: disable=too-many-public-methods, abstract-method

    def __init__(self, name, host):
        self._name = name
        self._host = host
        self._pwstate = "PWSTANDBY"
        self._volume = 0
        self._muted = False
        self._mediasource = ""

    @classmethod
    def telnet_request(cls, telnet, command):
        """ Executes `command` and returns the response. """
        telnet.write(command.encode("ASCII") + b"\r")
        return telnet.read_until(b"\r", timeout=0.2).decode("ASCII").strip()

    def telnet_command(self, command):
        """ Establishes a telnet connection and sends `command`. """
        telnet = telnetlib.Telnet(self._host)
        telnet.write(command.encode("ASCII") + b"\r")
        telnet.read_very_eager()  # skip response
        telnet.close()

    def update(self):
        try:
            telnet = telnetlib.Telnet(self._host)
        except ConnectionRefusedError:
            return False

        self._pwstate = self.telnet_request(telnet, "PW?")
        # PW? sends also SISTATUS, which is not interesting
        telnet.read_until(b"\r", timeout=0.2)

        volume_str = self.telnet_request(telnet, "MV?")[len("MV"):]
        self._volume = int(volume_str) / 60
        self._muted = (self.telnet_request(telnet, "MU?") == "MUON")
        self._mediasource = self.telnet_request(telnet, "SI?")[len("SI"):]

        telnet.close()
        return True

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        if self._pwstate == "PWSTANDBY":
            return STATE_OFF
        if self._pwstate == "PWON":
            return STATE_ON

        return STATE_UNKNOWN

    @property
    def volume_level(self):
        """ Volume level of the media player (0..1). """
        return self._volume

    @property
    def is_volume_muted(self):
        """ Boolean if volume is currently muted. """
        return self._muted

    @property
    def media_title(self):
        """ Current media source. """
        return self._mediasource

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        return SUPPORT_DENON

    def turn_off(self):
        """ turn_off media player. """
        self.telnet_command("PWSTANDBY")

    def volume_up(self):
        """ volume_up media player. """
        self.telnet_command("MVUP")

    def volume_down(self):
        """ volume_down media player. """
        self.telnet_command("MVDOWN")

    def set_volume_level(self, volume):
        """ set volume level, range 0..1. """
        # 60dB max
        self.telnet_command("MV" + str(round(volume * 60)).zfill(2))

    def mute_volume(self, mute):
        """ mute (true) or unmute (false) media player. """
        self.telnet_command("MU" + ("ON" if mute else "OFF"))

    def media_play(self):
        """ media_play media player. """
        self.telnet_command("NS9A")

    def media_pause(self):
        """ media_pause media player. """
        self.telnet_command("NS9B")

    def media_next_track(self):
        """ Send next track command. """
        self.telnet_command("NS9D")

    def media_previous_track(self):
        self.telnet_command("NS9E")

    def turn_on(self):
        """ turn the media player on. """
        self.telnet_command("PWON")
