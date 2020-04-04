"""Support for HDMI CEC devices as media players."""
import logging

from pycec.commands import CecCommand, KeyPressCommand, KeyReleaseCommand
from pycec.const import (
    KEY_BACKWARD,
    KEY_FORWARD,
    KEY_MUTE_TOGGLE,
    KEY_PAUSE,
    KEY_PLAY,
    KEY_STOP,
    KEY_VOLUME_DOWN,
    KEY_VOLUME_UP,
    POWER_OFF,
    POWER_ON,
    STATUS_PLAY,
    STATUS_STILL,
    STATUS_STOP,
    TYPE_AUDIO,
    TYPE_PLAYBACK,
    TYPE_RECORDER,
    TYPE_TUNER,
)

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.components.media_player.const import (
    DOMAIN,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)

from . import ATTR_NEW, CecDevice

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Find and return HDMI devices as +switches."""
    if ATTR_NEW in discovery_info:
        _LOGGER.debug("Setting up HDMI devices %s", discovery_info[ATTR_NEW])
        entities = []
        for device in discovery_info[ATTR_NEW]:
            hdmi_device = hass.data.get(device)
            entities.append(CecPlayerDevice(hdmi_device, hdmi_device.logical_address))
        add_entities(entities, True)


class CecPlayerDevice(CecDevice, MediaPlayerDevice):
    """Representation of a HDMI device as a Media player."""

    def __init__(self, device, logical) -> None:
        """Initialize the HDMI device."""
        CecDevice.__init__(self, device, logical)
        self.entity_id = "{}.{}_{}".format(
            DOMAIN, "hdmi", hex(self._logical_address)[2:]
        )

    def send_keypress(self, key):
        """Send keypress to CEC adapter."""
        _LOGGER.debug(
            "Sending keypress %s to device %s", hex(key), hex(self._logical_address)
        )
        self._device.send_command(KeyPressCommand(key, dst=self._logical_address))
        self._device.send_command(KeyReleaseCommand(dst=self._logical_address))

    def send_playback(self, key):
        """Send playback status to CEC adapter."""
        self._device.async_send_command(CecCommand(key, dst=self._logical_address))

    def mute_volume(self, mute):
        """Mute volume."""
        self.send_keypress(KEY_MUTE_TOGGLE)

    def media_previous_track(self):
        """Go to previous track."""
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
        self.send_keypress(KEY_STOP)
        self._state = STATE_IDLE

    def play_media(self, media_type, media_id, **kwargs):
        """Not supported."""
        raise NotImplementedError()

    def media_next_track(self):
        """Skip to next track."""
        self.send_keypress(KEY_FORWARD)

    def media_seek(self, position):
        """Not supported."""
        raise NotImplementedError()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        raise NotImplementedError()

    def media_pause(self):
        """Pause playback."""
        self.send_keypress(KEY_PAUSE)
        self._state = STATE_PAUSED

    def select_source(self, source):
        """Not supported."""
        raise NotImplementedError()

    def media_play(self):
        """Start playback."""
        self.send_keypress(KEY_PLAY)
        self._state = STATE_PLAYING

    def volume_up(self):
        """Increase volume."""
        _LOGGER.debug("%s: volume up", self._logical_address)
        self.send_keypress(KEY_VOLUME_UP)

    def volume_down(self):
        """Decrease volume."""
        _LOGGER.debug("%s: volume down", self._logical_address)
        self.send_keypress(KEY_VOLUME_DOWN)

    @property
    def state(self) -> str:
        """Cache state of device."""
        return self._state

    def update(self):
        """Update device status."""
        device = self._device
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
        if self.type_id == TYPE_RECORDER or self.type == TYPE_PLAYBACK:
            return (
                SUPPORT_TURN_ON
                | SUPPORT_TURN_OFF
                | SUPPORT_PLAY_MEDIA
                | SUPPORT_PAUSE
                | SUPPORT_STOP
                | SUPPORT_PREVIOUS_TRACK
                | SUPPORT_NEXT_TRACK
            )
        if self.type == TYPE_TUNER:
            return (
                SUPPORT_TURN_ON
                | SUPPORT_TURN_OFF
                | SUPPORT_PLAY_MEDIA
                | SUPPORT_PAUSE
                | SUPPORT_STOP
            )
        if self.type_id == TYPE_AUDIO:
            return (
                SUPPORT_TURN_ON
                | SUPPORT_TURN_OFF
                | SUPPORT_VOLUME_STEP
                | SUPPORT_VOLUME_MUTE
            )
        return SUPPORT_TURN_ON | SUPPORT_TURN_OFF
