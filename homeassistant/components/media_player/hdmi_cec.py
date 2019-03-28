"""
Support for HDMI CEC devices as media players.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
import logging

from homeassistant.components.hdmi_cec import ATTR_NEW, CecDevice
from homeassistant.components.media_player import (
    DOMAIN, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP, MediaPlayerDevice)
from homeassistant.const import (
    STATE_IDLE, STATE_OFF, STATE_ON, STATE_PAUSED, STATE_PLAYING)

DEPENDENCIES = ['hdmi_cec']

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + '.{}'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Find and return HDMI devices as +switches."""
    if ATTR_NEW in discovery_info:
        _LOGGER.info("Setting up HDMI devices %s", discovery_info[ATTR_NEW])
        entities = []
        for device in discovery_info[ATTR_NEW]:
            hdmi_device = hass.data.get(device)
            entities.append(CecPlayerDevice(
                hdmi_device, hdmi_device.logical_address,
            ))
        add_entities(entities, True)


class CecPlayerDevice(CecDevice, MediaPlayerDevice):
    """Representation of a HDMI device as a Media player."""

    def __init__(self, device, logical) -> None:
        """Initialize the HDMI device."""
        CecDevice.__init__(self, device, logical)
        self.entity_id = "%s.%s_%s" % (
            DOMAIN, 'hdmi', hex(self._logical_address)[2:])

    def send_keypress(self, key):
        """Send keypress to CEC adapter."""
        from pycec.commands import KeyPressCommand, KeyReleaseCommand
        _LOGGER.debug("Sending keypress %s to device %s", hex(key),
                      hex(self._logical_address))
        self._device.send_command(
            KeyPressCommand(key, dst=self._logical_address))
        self._device.send_command(
            KeyReleaseCommand(dst=self._logical_address))

    def send_playback(self, key):
        """Send playback status to CEC adapter."""
        from pycec.commands import CecCommand
        self._device.async_send_command(
            CecCommand(key, dst=self._logical_address))

    def mute_volume(self, mute):
        """Mute volume."""
        from pycec.const import KEY_MUTE_TOGGLE
        self.send_keypress(KEY_MUTE_TOGGLE)

    def media_previous_track(self):
        """Go to previous track."""
        from pycec.const import KEY_BACKWARD
        self.send_keypress(KEY_BACKWARD)

    def turn_on(self):
        """Turn device on."""
        self._device.turn_on()
        self._state = STATE_ON

    def clear_playlist(self):
        """Clear players playlist."""
        raise NotImplementedError()

    def turn_off(self):
        """Turn device off."""
        self._device.turn_off()
        self._state = STATE_OFF

    def media_stop(self):
        """Stop playback."""
        from pycec.const import KEY_STOP
        self.send_keypress(KEY_STOP)
        self._state = STATE_IDLE

    def play_media(self, media_type, media_id, **kwargs):
        """Not supported."""
        raise NotImplementedError()

    def media_next_track(self):
        """Skip to next track."""
        from pycec.const import KEY_FORWARD
        self.send_keypress(KEY_FORWARD)

    def media_seek(self, position):
        """Not supported."""
        raise NotImplementedError()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        raise NotImplementedError()

    def media_pause(self):
        """Pause playback."""
        from pycec.const import KEY_PAUSE
        self.send_keypress(KEY_PAUSE)
        self._state = STATE_PAUSED

    def select_source(self, source):
        """Not supported."""
        raise NotImplementedError()

    def media_play(self):
        """Start playback."""
        from pycec.const import KEY_PLAY
        self.send_keypress(KEY_PLAY)
        self._state = STATE_PLAYING

    def volume_up(self):
        """Increase volume."""
        from pycec.const import KEY_VOLUME_UP
        _LOGGER.debug("%s: volume up", self._logical_address)
        self.send_keypress(KEY_VOLUME_UP)

    def volume_down(self):
        """Decrease volume."""
        from pycec.const import KEY_VOLUME_DOWN
        _LOGGER.debug("%s: volume down", self._logical_address)
        self.send_keypress(KEY_VOLUME_DOWN)

    @property
    def state(self) -> str:
        """Cache state of device."""
        return self._state

    def update(self):
        """Update device status."""
        device = self._device
        from pycec.const import STATUS_PLAY, STATUS_STOP, STATUS_STILL, \
            POWER_OFF, POWER_ON
        if device.power_status in [POWER_OFF, 3]:
            self._state = STATE_OFF
        elif not self.support_pause:
            if device.power_status in [POWER_ON, 4]:
                self._state = STATE_ON
        elif device.status == STATUS_PLAY:
            self._state = STATE_PLAYING
        elif device.status == STATUS_STOP:
            self._state = STATE_IDLE
        elif device.status == STATUS_STILL:
            self._state = STATE_PAUSED
        else:
            _LOGGER.warning("Unknown state: %s", device.status)

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        from pycec.const import TYPE_RECORDER, TYPE_PLAYBACK, TYPE_TUNER, \
            TYPE_AUDIO
        if self.type_id == TYPE_RECORDER or self.type == TYPE_PLAYBACK:
            return (SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PLAY_MEDIA |
                    SUPPORT_PAUSE | SUPPORT_STOP | SUPPORT_PREVIOUS_TRACK |
                    SUPPORT_NEXT_TRACK)
        if self.type == TYPE_TUNER:
            return (SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PLAY_MEDIA |
                    SUPPORT_PAUSE | SUPPORT_STOP)
        if self.type_id == TYPE_AUDIO:
            return (SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP |
                    SUPPORT_VOLUME_MUTE)
        return SUPPORT_TURN_ON | SUPPORT_TURN_OFF
