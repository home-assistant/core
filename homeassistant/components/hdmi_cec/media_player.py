"""Support for HDMI CEC devices as media players."""

from __future__ import annotations

import logging
from typing import Any

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

from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_NEW, DOMAIN
from .entity import CecEntity

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = MP_DOMAIN + ".{}"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Find and return HDMI devices as +switches."""
    if discovery_info and ATTR_NEW in discovery_info:
        _LOGGER.debug("Setting up HDMI devices %s", discovery_info[ATTR_NEW])
        entities = []
        for device in discovery_info[ATTR_NEW]:
            hdmi_device = hass.data[DOMAIN][device]
            entities.append(CecPlayerEntity(hdmi_device, hdmi_device.logical_address))
        add_entities(entities, True)


class CecPlayerEntity(CecEntity, MediaPlayerEntity):
    """Representation of a HDMI device as a Media player."""

    def __init__(self, device, logical) -> None:
        """Initialize the HDMI device."""
        CecEntity.__init__(self, device, logical)
        self.entity_id = f"{MP_DOMAIN}.hdmi_{hex(self._logical_address)[2:]}"

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

    def mute_volume(self, mute: bool) -> None:
        """Mute volume."""
        self.send_keypress(KEY_MUTE_TOGGLE)

    def media_previous_track(self) -> None:
        """Go to previous track."""
        self.send_keypress(KEY_BACKWARD)

    def turn_on(self) -> None:
        """Turn device on."""
        self._device.turn_on()
        self._attr_state = MediaPlayerState.ON

    def clear_playlist(self) -> None:
        """Clear players playlist."""
        raise NotImplementedError

    def turn_off(self) -> None:
        """Turn device off."""
        self._device.turn_off()
        self._attr_state = MediaPlayerState.OFF

    def media_stop(self) -> None:
        """Stop playback."""
        self.send_keypress(KEY_STOP)
        self._attr_state = MediaPlayerState.IDLE

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Not supported."""
        raise NotImplementedError

    def media_next_track(self) -> None:
        """Skip to next track."""
        self.send_keypress(KEY_FORWARD)

    def media_seek(self, position: float) -> None:
        """Not supported."""
        raise NotImplementedError

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        raise NotImplementedError

    def media_pause(self) -> None:
        """Pause playback."""
        self.send_keypress(KEY_PAUSE)
        self._attr_state = MediaPlayerState.PAUSED

    def select_source(self, source: str) -> None:
        """Not supported."""
        raise NotImplementedError

    def media_play(self) -> None:
        """Start playback."""
        self.send_keypress(KEY_PLAY)
        self._attr_state = MediaPlayerState.PLAYING

    def volume_up(self) -> None:
        """Increase volume."""
        _LOGGER.debug("%s: volume up", self._logical_address)
        self.send_keypress(KEY_VOLUME_UP)

    def volume_down(self) -> None:
        """Decrease volume."""
        _LOGGER.debug("%s: volume down", self._logical_address)
        self.send_keypress(KEY_VOLUME_DOWN)

    def update(self) -> None:
        """Update device status."""
        device = self._device
        if device.power_status in [POWER_OFF, 3]:
            self._attr_state = MediaPlayerState.OFF
        elif not self.support_pause:
            if device.power_status in [POWER_ON, 4]:
                self._attr_state = MediaPlayerState.ON
        elif device.status == STATUS_PLAY:
            self._attr_state = MediaPlayerState.PLAYING
        elif device.status == STATUS_STOP:
            self._attr_state = MediaPlayerState.IDLE
        elif device.status == STATUS_STILL:
            self._attr_state = MediaPlayerState.PAUSED
        else:
            _LOGGER.warning("Unknown state: %s", device.status)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self.type_id == TYPE_RECORDER or self.type == TYPE_PLAYBACK:
            return (
                MediaPlayerEntityFeature.TURN_ON
                | MediaPlayerEntityFeature.TURN_OFF
                | MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
                | MediaPlayerEntityFeature.NEXT_TRACK
            )
        if self.type == TYPE_TUNER:
            return (
                MediaPlayerEntityFeature.TURN_ON
                | MediaPlayerEntityFeature.TURN_OFF
                | MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.STOP
            )
        if self.type_id == TYPE_AUDIO:
            return (
                MediaPlayerEntityFeature.TURN_ON
                | MediaPlayerEntityFeature.TURN_OFF
                | MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.VOLUME_MUTE
            )
        return MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
