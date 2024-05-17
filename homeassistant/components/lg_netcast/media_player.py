"""Support for LG TV running on NetCast 3 or 4."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

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
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.trigger import PluggableAction
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_MANUFACTURER, DOMAIN
from .triggers.turn_on import async_get_turn_on_trigger

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
    | MediaPlayerEntityFeature.STOP
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_ACCESS_TOKEN): vol.All(cv.string, vol.Length(max=6)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a LG Netcast Media Player from a config_entry."""

    host = config_entry.data[CONF_HOST]
    access_token = config_entry.data[CONF_ACCESS_TOKEN]
    unique_id = config_entry.unique_id
    name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)
    model = config_entry.data[CONF_MODEL]

    client = LgNetCastClient(host, access_token)

    hass.data[DOMAIN][config_entry.entry_id] = client

    async_add_entities([LgTVDevice(client, name, model, unique_id=unique_id)])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the LG TV platform."""

    host = config.get(CONF_HOST)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )

    if (
        result.get("type") == FlowResultType.ABORT
        and result.get("reason") == "cannot_connect"
    ):
        raise PlatformNotReady(f"Connection error while connecting to {host}")


class LgTVDevice(MediaPlayerEntity):
    """Representation of a LG TV."""

    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_media_content_type = MediaType.CHANNEL
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, client, name, model, unique_id):
        """Initialize the LG TV device."""
        self._client = client
        self._muted = False
        self._turn_on = PluggableAction(self.async_write_ha_state)
        self._volume = 0
        self._channel_id = None
        self._channel_name = ""
        self._program_name = ""
        self._sources = {}
        self._source_names = []
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=ATTR_MANUFACTURER,
            name=name,
            model=model,
        )

    async def async_added_to_hass(self) -> None:
        """Connect and subscribe to dispatcher signals and state updates."""
        await super().async_added_to_hass()

        entry = self.registry_entry

        if TYPE_CHECKING:
            assert entry is not None and entry.device_id is not None

        self.async_on_remove(
            self._turn_on.async_register(
                self.hass, async_get_turn_on_trigger(entry.device_id)
            )
        )

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
                self._attr_state = MediaPlayerState.ON

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
                    self._sources = dict(zip(channel_names, channel_list, strict=False))
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
        if self._turn_on:
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

    async def async_turn_on(self) -> None:
        """Turn on the media player."""
        await self._turn_on.async_run(self.hass, self._context)

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

    def media_play(self) -> None:
        """Send play command."""
        self.send_command(LG_COMMAND.PLAY)

    def media_pause(self) -> None:
        """Send media pause command to media player."""
        self.send_command(LG_COMMAND.PAUSE)

    def media_stop(self) -> None:
        """Send media stop command to media player."""
        self.send_command(LG_COMMAND.STOP)

    def media_next_track(self) -> None:
        """Send next track command."""
        self.send_command(LG_COMMAND.FAST_FORWARD)

    def media_previous_track(self) -> None:
        """Send the previous track command."""
        self.send_command(LG_COMMAND.REWIND)

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Tune to channel."""
        if media_type != MediaType.CHANNEL:
            raise ValueError(f"Invalid media type: {media_type}")

        for name, channel in self._sources.items():
            channel_id = channel.find("major")
            if channel_id is not None and int(channel_id.text) == int(media_id):
                self.select_source(name)
                return

        raise ValueError(f"Invalid media id: {media_id}")
