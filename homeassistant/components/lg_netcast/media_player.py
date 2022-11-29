"""Support for LG TV running on NetCast 3 or 4."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pylgnetcast import LG_COMMAND, LgNetCastClient, LgNetCastError
from requests import RequestException
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

DEFAULT_NAME = "LG TV Remote"

CONF_ON_ACTION = "turn_on_action"

SUPPORT_LGTV = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_ACCESS_TOKEN): vol.All(cv.string, vol.Length(max=6)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the LG TV platform."""

    host = config.get(CONF_HOST)
    access_token = config.get(CONF_ACCESS_TOKEN)
    name = config[CONF_NAME]
    on_action = config.get(CONF_ON_ACTION)

    client = LgNetCastClient(host, access_token)
    on_action_script = Script(hass, on_action, name, DOMAIN) if on_action else None

    add_entities([LgTVDevice(client, name, on_action_script)], True)


class LgTVDevice(MediaPlayerEntity):
    """Representation of a LG TV."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_media_content_type = MediaType.CHANNEL

    def __init__(self, client, name, on_action_script):
        """Initialize the LG TV device."""
        self._client = client
        self._name = name
        self._muted = False
        self._on_action_script = on_action_script
        # Assume that the TV is in Play mode
        self._playing = True
        self._volume = 0
        self._channel_id = None
        self._channel_name = ""
        self._program_name = ""
        self._sources = {}
        self._source_names = []

    def send_command(self, command):
        """Send remote control commands to the TV."""

        try:
            with self._client as client:
                client.send_command(command)
        except (LgNetCastError, RequestException):
            self._attr_state = MediaPlayerState.OFF

    def update(self) -> None:
        """Retrieve the latest data from the LG TV."""

        try:
            with self._client as client:
                self._attr_state = MediaPlayerState.PLAYING

                self.__update_volume()

                channel_info = client.query_data("cur_channel")
                if channel_info:
                    channel_info = channel_info[0]
                    channel_id = channel_info.find("major")
                    self._channel_name = channel_info.find("chname").text
                    self._program_name = channel_info.find("progName").text
                    if channel_id is not None:
                        self._channel_id = int(channel_id.text)
                    if self._channel_name is None:
                        self._channel_name = channel_info.find("inputSourceName").text
                    if self._program_name is None:
                        self._program_name = channel_info.find("labelName").text

                channel_list = client.query_data("channel_list")
                if channel_list:
                    channel_names = []
                    for channel in channel_list:
                        channel_name = channel.find("chname")
                        if channel_name is not None:
                            channel_names.append(str(channel_name.text))
                    self._sources = dict(zip(channel_names, channel_list))
                    # sort source names by the major channel number
                    source_tuples = [
                        (k, source.find("major").text)
                        for k, source in self._sources.items()
                    ]
                    sorted_sources = sorted(
                        source_tuples, key=lambda channel: int(channel[1])
                    )
                    self._source_names = [n for n, k in sorted_sources]
        except (LgNetCastError, RequestException):
            self._attr_state = MediaPlayerState.OFF

    def __update_volume(self):
        volume_info = self._client.get_volume()
        if volume_info:
            (volume, muted) = volume_info
            self._volume = volume
            self._muted = muted

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume / 100.0

    @property
    def source(self):
        """Return the current input source."""
        return self._channel_name

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    @property
    def media_content_id(self):
        """Content id of current playing media."""
        return self._channel_id

    @property
    def media_channel(self):
        """Channel currently playing."""
        return self._channel_name

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._program_name

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self._on_action_script:
            return SUPPORT_LGTV | MediaPlayerEntityFeature.TURN_ON
        return SUPPORT_LGTV

    @property
    def media_image_url(self):
        """URL for obtaining a screen capture."""
        return (
            f"{self._client.url}data?target=screen_image&_={datetime.now().timestamp()}"
        )

    def turn_off(self) -> None:
        """Turn off media player."""
        self.send_command(LG_COMMAND.POWER)

    def turn_on(self) -> None:
        """Turn on the media player."""
        if self._on_action_script:
            self._on_action_script.run(context=self._context)

    def volume_up(self) -> None:
        """Volume up the media player."""
        self.send_command(LG_COMMAND.VOLUME_UP)

    def volume_down(self) -> None:
        """Volume down media player."""
        self.send_command(LG_COMMAND.VOLUME_DOWN)

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._client.set_volume(float(volume * 100))

    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self.send_command(LG_COMMAND.MUTE_TOGGLE)

    def select_source(self, source: str) -> None:
        """Select input source."""
        self._client.change_channel(self._sources[source])

    def media_play_pause(self) -> None:
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self) -> None:
        """Send play command."""
        self._playing = True
        self._attr_state = MediaPlayerState.PLAYING
        self.send_command(LG_COMMAND.PLAY)

    def media_pause(self) -> None:
        """Send media pause command to media player."""
        self._playing = False
        self._attr_state = MediaPlayerState.PAUSED
        self.send_command(LG_COMMAND.PAUSE)

    def media_next_track(self) -> None:
        """Send next track command."""
        self.send_command(LG_COMMAND.FAST_FORWARD)

    def media_previous_track(self) -> None:
        """Send the previous track command."""
        self.send_command(LG_COMMAND.REWIND)

    def play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Tune to channel."""
        if media_type != MediaType.CHANNEL:
            raise ValueError(f"Invalid media type: {media_type}")

        for name, channel in self._sources.items():
            channel_id = channel.find("major")
            if channel_id is not None and int(channel_id.text) == int(media_id):
                self.select_source(name)
                return

        raise ValueError(f"Invalid media id: {media_id}")
