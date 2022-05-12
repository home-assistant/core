"""Support for interface with an Aquos TV."""
from __future__ import annotations

import logging

import sharp_aquos_rc
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_USERNAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Sharp Aquos TV"
DEFAULT_PORT = 10002
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "password"
DEFAULT_TIMEOUT = 0.5
DEFAULT_RETRIES = 2

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.string,
        vol.Optional("retries", default=DEFAULT_RETRIES): cv.string,
        vol.Optional("power_on_enabled", default=False): cv.boolean,
    }
)

SOURCES = {
    0: "TV / Antenna",
    1: "HDMI_IN_1",
    2: "HDMI_IN_2",
    3: "HDMI_IN_3",
    4: "HDMI_IN_4",
    5: "COMPONENT IN",
    6: "VIDEO_IN_1",
    7: "VIDEO_IN_2",
    8: "PC_IN",
}


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Sharp Aquos TV platform."""

    name = config[CONF_NAME]
    port = config[CONF_PORT]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    power_on_enabled = config["power_on_enabled"]
    host = config[CONF_HOST]
    remote = sharp_aquos_rc.TV(host, port, username, password, 15, 1)

    add_entities([SharpAquosTVDevice(name, remote, power_on_enabled)])


def _retry(func):
    """Handle query retries."""

    def wrapper(obj, *args, **kwargs):
        """Wrap all query functions."""
        update_retries = 5
        while update_retries > 0:
            try:
                func(obj, *args, **kwargs)
                break
            except (OSError, TypeError, ValueError):
                update_retries -= 1
                if update_retries == 0:
                    obj.set_state(STATE_OFF)

    return wrapper


class SharpAquosTVDevice(MediaPlayerEntity):
    """Representation of a Aquos TV."""

    _attr_source_list = list(SOURCES.values())
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.PLAY
    )

    def __init__(
        self, name: str, remote: sharp_aquos_rc.TV, power_on_enabled: bool = False
    ) -> None:
        """Initialize the aquos device."""
        self._power_on_enabled = power_on_enabled
        if power_on_enabled:
            self._attr_supported_features |= MediaPlayerEntityFeature.TURN_ON
        # Save a reference to the imported class
        self._attr_name = name
        # Assume that the TV is not muted
        self._remote = remote

    def set_state(self, state):
        """Set TV state."""
        self._attr_state = state

    @_retry
    def update(self):
        """Retrieve the latest data."""
        if self._remote.power() == 1:
            self._attr_state = STATE_ON
        else:
            self._attr_state = STATE_OFF
        # Set TV to be able to remotely power on
        if self._power_on_enabled:
            self._remote.power_on_command_settings(2)
        else:
            self._remote.power_on_command_settings(0)
        # Get mute state
        if self._remote.mute() == 2:
            self._attr_is_volume_muted = False
        else:
            self._attr_is_volume_muted = True
        # Get source
        self._attr_source = SOURCES.get(self._remote.input())
        # Get volume
        self._attr_volume_level = self._remote.volume() / 60

    @_retry
    def turn_off(self):
        """Turn off tvplayer."""
        self._remote.power(0)

    @_retry
    def volume_up(self):
        """Volume up the media player."""
        self._remote.volume(int(self.volume_level * 60) + 2)

    @_retry
    def volume_down(self):
        """Volume down media player."""
        self._remote.volume(int(self.volume_level * 60) - 2)

    @_retry
    def set_volume_level(self, volume):
        """Set Volume media player."""
        self._remote.volume(int(volume * 60))

    @_retry
    def mute_volume(self, mute):
        """Send mute command."""
        self._remote.mute(0)

    @_retry
    def turn_on(self):
        """Turn the media player on."""
        self._remote.power(1)

    @_retry
    def media_play_pause(self):
        """Simulate play pause media player."""
        self._remote.remote_button(40)

    @_retry
    def media_play(self):
        """Send play command."""
        self._remote.remote_button(16)

    @_retry
    def media_pause(self):
        """Send pause command."""
        self._remote.remote_button(16)

    @_retry
    def media_next_track(self):
        """Send next track command."""
        self._remote.remote_button(21)

    @_retry
    def media_previous_track(self):
        """Send the previous track command."""
        self._remote.remote_button(19)

    def select_source(self, source):
        """Set the input source."""
        for key, value in SOURCES.items():
            if source == value:
                self._remote.input(key)
