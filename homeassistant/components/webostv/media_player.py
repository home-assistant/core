"""Support for interface with an LG webOS Smart TV."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from contextlib import suppress
from datetime import timedelta
from functools import wraps
import logging
from typing import Any, TypeVar, cast

from aiowebostv import WebOsClient, WebOsTvPairError
from typing_extensions import Concatenate, ParamSpec

from homeassistant import util
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import WebOsClientWrapper
from .const import (
    ATTR_PAYLOAD,
    ATTR_SOUND_OUTPUT,
    CONF_SOURCES,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    LIVE_TV_APP_ID,
    WEBOSTV_EXCEPTIONS,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEBOSTV = (
    SUPPORT_TURN_OFF
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_STOP
)

SUPPORT_WEBOSTV_VOLUME = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the LG webOS Smart TV platform."""
    unique_id = config_entry.unique_id
    assert unique_id
    name = config_entry.title
    sources = config_entry.options.get(CONF_SOURCES)
    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id]

    async_add_entities([LgWebOSMediaPlayerEntity(wrapper, name, sources, unique_id)])


_T = TypeVar("_T", bound="LgWebOSMediaPlayerEntity")
_P = ParamSpec("_P")


def cmd(
    func: Callable[Concatenate[_T, _P], Awaitable[None]]  # type: ignore[misc]
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:  # type: ignore[misc]
    """Catch command exceptions."""

    @wraps(func)
    async def cmd_wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Wrap all command methods."""
        try:
            await func(self, *args, **kwargs)
        except WEBOSTV_EXCEPTIONS as exc:
            if self.state != STATE_OFF:
                raise HomeAssistantError(
                    f"Error calling {func.__name__} on entity {self.entity_id}, state:{self.state}"
                ) from exc
            _LOGGER.warning(
                "Error calling %s on entity %s, state:%s, error: %r",
                func.__name__,
                self.entity_id,
                self.state,
                exc,
            )

    return cmd_wrapper


class LgWebOSMediaPlayerEntity(RestoreEntity, MediaPlayerEntity):
    """Representation of a LG webOS Smart TV."""

    def __init__(
        self,
        wrapper: WebOsClientWrapper,
        name: str,
        sources: list[str] | None,
        unique_id: str,
    ) -> None:
        """Initialize the webos device."""
        self._wrapper = wrapper
        self._client: WebOsClient = wrapper.client
        self._name = name
        self._unique_id = unique_id
        self._sources = sources

        # Assume that the TV is not paused
        self._paused = False

        self._current_source = None
        self._source_list: dict = {}

        self._supported_features: int | None = None

    async def async_added_to_hass(self) -> None:
        """Connect and subscribe to dispatcher signals and state updates."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_signal_handler)
        )

        await self._client.register_state_update_callback(
            self.async_handle_state_update
        )

        if self._supported_features is not None:
            return

        if (state := await self.async_get_last_state()) is not None:
            self._supported_features = state.attributes.get(ATTR_SUPPORTED_FEATURES)

    async def async_will_remove_from_hass(self) -> None:
        """Call disconnect on removal."""
        self._client.unregister_state_update_callback(self.async_handle_state_update)

    async def async_signal_handler(self, data: dict[str, Any]) -> None:
        """Handle domain-specific signal by calling appropriate method."""
        if (entity_ids := data[ATTR_ENTITY_ID]) == ENTITY_MATCH_NONE:
            return

        if entity_ids == ENTITY_MATCH_ALL or self.entity_id in entity_ids:
            params = {
                key: value
                for key, value in data.items()
                if key not in ["entity_id", "method"]
            }
            await getattr(self, data["method"])(**params)

    async def async_handle_state_update(self, _client: WebOsClient) -> None:
        """Update state from WebOsClient."""
        self.update_sources()
        self.async_write_ha_state()

    def update_sources(self) -> None:
        """Update list of sources from current source, apps, inputs and configured list."""
        source_list = self._source_list
        self._source_list = {}
        conf_sources = self._sources

        found_live_tv = False
        for app in self._client.apps.values():
            if app["id"] == LIVE_TV_APP_ID:
                found_live_tv = True
            if app["id"] == self._client.current_app_id:
                self._current_source = app["title"]
                self._source_list[app["title"]] = app
            elif (
                not conf_sources
                or app["id"] in conf_sources
                or any(word in app["title"] for word in conf_sources)
                or any(word in app["id"] for word in conf_sources)
            ):
                self._source_list[app["title"]] = app

        for source in self._client.inputs.values():
            if source["appId"] == LIVE_TV_APP_ID:
                found_live_tv = True
            if source["appId"] == self._client.current_app_id:
                self._current_source = source["label"]
                self._source_list[source["label"]] = source
            elif (
                not conf_sources
                or source["label"] in conf_sources
                or any(source["label"].find(word) != -1 for word in conf_sources)
            ):
                self._source_list[source["label"]] = source

        # empty list, TV may be off, keep previous list
        if not self._source_list and source_list:
            self._source_list = source_list
        # special handling of live tv since this might
        # not appear in the app or input lists in some cases
        elif not found_live_tv:
            app = {"id": LIVE_TV_APP_ID, "title": "Live TV"}
            if LIVE_TV_APP_ID == self._client.current_app_id:
                self._current_source = app["title"]
                self._source_list["Live TV"] = app
            elif (
                not conf_sources
                or app["id"] in conf_sources
                or any(word in app["title"] for word in conf_sources)
                or any(word in app["id"] for word in conf_sources)
            ):
                self._source_list["Live TV"] = app

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    async def async_update(self) -> None:
        """Connect."""
        if self._client.is_connected():
            return

        with suppress(*WEBOSTV_EXCEPTIONS, WebOsTvPairError):
            await self._client.connect()

    @property
    def unique_id(self) -> str:
        """Return the unique id of the device."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def device_class(self) -> MediaPlayerDeviceClass:
        """Return the device class of the device."""
        return MediaPlayerDeviceClass.TV

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if self._client.is_on:
            return STATE_ON

        return STATE_OFF

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return cast(bool, self._client.muted)

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if self._client.volume is not None:
            return cast(float, self._client.volume / 100.0)

        return None

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._current_source

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return sorted(self._source_list)

    @property
    def media_content_type(self) -> str | None:
        """Content type of current playing media."""
        if self._client.current_app_id == LIVE_TV_APP_ID:
            return MEDIA_TYPE_CHANNEL

        return None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if (self._client.current_app_id == LIVE_TV_APP_ID) and (
            self._client.current_channel is not None
        ):
            return cast(str, self._client.current_channel.get("channelName"))
        return None

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if self._client.current_app_id in self._client.apps:
            icon: str = self._client.apps[self._client.current_app_id]["largeIcon"]
            if not icon.startswith("http"):
                icon = self._client.apps[self._client.current_app_id]["icon"]
            return icon
        return None

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        if self.state == STATE_OFF and self._supported_features is not None:
            if self._wrapper.turn_on:
                return self._supported_features | SUPPORT_TURN_ON

            return self._supported_features & ~SUPPORT_TURN_ON

        supported = SUPPORT_WEBOSTV

        if self._client.sound_output in ("external_arc", "external_speaker"):
            supported = supported | SUPPORT_WEBOSTV_VOLUME
        elif self._client.sound_output != "lineout":
            supported = supported | SUPPORT_WEBOSTV_VOLUME | SUPPORT_VOLUME_SET

        if self._wrapper.turn_on:
            supported |= SUPPORT_TURN_ON

        if self.state != STATE_OFF:
            self._supported_features = supported

        return supported

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            manufacturer="LG",
            name=self._name,
        )

        if self._client.system_info is None and self.state == STATE_OFF:
            return device_info

        maj_v = self._client.software_info.get("major_ver")
        min_v = self._client.software_info.get("minor_ver")
        if maj_v and min_v:
            device_info["sw_version"] = f"{maj_v}.{min_v}"

        model = self._client.system_info.get("modelName")
        if model:
            device_info["model"] = model

        return device_info

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return device specific state attributes."""
        if self._client.sound_output is None and self.state == STATE_OFF:
            return None
        return {ATTR_SOUND_OUTPUT: self._client.sound_output}

    @cmd
    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self._client.power_off()

    async def async_turn_on(self) -> None:
        """Turn on media player."""
        self._wrapper.turn_on.async_run(self.hass, self._context)

    @cmd
    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self._client.volume_up()

    @cmd
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._client.volume_down()

    @cmd
    async def async_set_volume_level(self, volume: int) -> None:
        """Set volume level, range 0..1."""
        tv_volume = int(round(volume * 100))
        await self._client.set_volume(tv_volume)

    @cmd
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._client.set_mute(mute)

    @cmd
    async def async_select_sound_output(self, sound_output: str) -> None:
        """Select the sound output."""
        await self._client.change_sound_output(sound_output)

    @cmd
    async def async_media_play_pause(self) -> None:
        """Simulate play pause media player."""
        if self._paused:
            await self.async_media_play()
        else:
            await self.async_media_pause()

    @cmd
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if (source_dict := self._source_list.get(source)) is None:
            _LOGGER.warning("Source %s not found for %s", source, self.name)
            return
        if source_dict.get("title"):
            await self._client.launch_app(source_dict["id"])
        elif source_dict.get("label"):
            await self._client.set_input(source_dict["id"])

    @cmd
    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Call play media type <%s>, Id <%s>", media_type, media_id)

        if media_type == MEDIA_TYPE_CHANNEL:
            _LOGGER.debug("Searching channel")
            partial_match_channel_id = None
            perfect_match_channel_id = None

            for channel in self._client.channels:
                if media_id == channel["channelNumber"]:
                    perfect_match_channel_id = channel["channelId"]
                    continue

                if media_id.lower() == channel["channelName"].lower():
                    perfect_match_channel_id = channel["channelId"]
                    continue

                if media_id.lower() in channel["channelName"].lower():
                    partial_match_channel_id = channel["channelId"]

            if perfect_match_channel_id is not None:
                _LOGGER.info(
                    "Switching to channel <%s> with perfect match",
                    perfect_match_channel_id,
                )
                await self._client.set_channel(perfect_match_channel_id)
            elif partial_match_channel_id is not None:
                _LOGGER.info(
                    "Switching to channel <%s> with partial match",
                    partial_match_channel_id,
                )
                await self._client.set_channel(partial_match_channel_id)

    @cmd
    async def async_media_play(self) -> None:
        """Send play command."""
        self._paused = False
        await self._client.play()

    @cmd
    async def async_media_pause(self) -> None:
        """Send media pause command to media player."""
        self._paused = True
        await self._client.pause()

    @cmd
    async def async_media_stop(self) -> None:
        """Send stop command to media player."""
        await self._client.stop()

    @cmd
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if self._client.current_app_id == LIVE_TV_APP_ID:
            await self._client.channel_up()
        else:
            await self._client.fast_forward()

    @cmd
    async def async_media_previous_track(self) -> None:
        """Send the previous track command."""
        if self._client.current_app_id == LIVE_TV_APP_ID:
            await self._client.channel_down()
        else:
            await self._client.rewind()

    @cmd
    async def async_button(self, button: str) -> None:
        """Send a button press."""
        await self._client.button(button)

    @cmd
    async def async_command(self, command: str, **kwargs: Any) -> None:
        """Send a command."""
        await self._client.request(command, payload=kwargs.get(ATTR_PAYLOAD))
