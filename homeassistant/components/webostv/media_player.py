"""Support for interface with an LG webOS TV."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from contextlib import suppress
from datetime import timedelta
from functools import wraps
from http import HTTPStatus
import logging
from typing import Any, Concatenate, cast

from aiowebostv import WebOsTvPairError, WebOsTvState
import voluptuous as vol

from homeassistant import util
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import ATTR_COMMAND, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.trigger import PluggableAction
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_BUTTON,
    ATTR_PAYLOAD,
    ATTR_SOUND_OUTPUT,
    CONF_SOURCES,
    DOMAIN,
    LIVE_TV_APP_ID,
    SERVICE_BUTTON,
    SERVICE_COMMAND,
    SERVICE_SELECT_SOUND_OUTPUT,
    WEBOSTV_EXCEPTIONS,
)
from .helpers import WebOsTvConfigEntry, update_client_key
from .triggers.turn_on import async_get_turn_on_trigger

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEBOSTV = (
    MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.STOP
)

SUPPORT_WEBOSTV_VOLUME = (
    MediaPlayerEntityFeature.VOLUME_MUTE | MediaPlayerEntityFeature.VOLUME_STEP
)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=10)

BUTTON_SCHEMA: VolDictType = {vol.Required(ATTR_BUTTON): cv.string}
COMMAND_SCHEMA: VolDictType = {
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_PAYLOAD): dict,
}
SOUND_OUTPUT_SCHEMA: VolDictType = {vol.Required(ATTR_SOUND_OUTPUT): cv.string}

SERVICES = (
    (
        SERVICE_BUTTON,
        BUTTON_SCHEMA,
        "async_button",
        SupportsResponse.NONE,
    ),
    (
        SERVICE_COMMAND,
        COMMAND_SCHEMA,
        "async_command",
        SupportsResponse.OPTIONAL,
    ),
    (
        SERVICE_SELECT_SOUND_OUTPUT,
        SOUND_OUTPUT_SCHEMA,
        "async_select_sound_output",
        SupportsResponse.OPTIONAL,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsTvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LG webOS TV platform."""
    platform = entity_platform.async_get_current_platform()

    for service_name, schema, method, supports_response in SERVICES:
        platform.async_register_entity_service(
            service_name, schema, method, supports_response=supports_response
        )

    async_add_entities([LgWebOSMediaPlayerEntity(entry)])


def cmd[_R, **_P](
    func: Callable[Concatenate[LgWebOSMediaPlayerEntity, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[LgWebOSMediaPlayerEntity, _P], Coroutine[Any, Any, _R]]:
    """Catch command exceptions."""

    @wraps(func)
    async def cmd_wrapper(
        self: LgWebOSMediaPlayerEntity, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        """Wrap all command methods."""
        if self.state is MediaPlayerState.OFF and func.__name__ != "async_turn_off":
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_off",
                translation_placeholders={
                    "name": str(self._entry.title),
                    "func": func.__name__,
                },
            )
        try:
            return await func(self, *args, **kwargs)
        except WEBOSTV_EXCEPTIONS as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={
                    "name": str(self._entry.title),
                    "func": func.__name__,
                    "error": str(error),
                },
            ) from error

    return cmd_wrapper


class LgWebOSMediaPlayerEntity(RestoreEntity, MediaPlayerEntity):
    """Representation of a LG webOS TV."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: WebOsTvConfigEntry) -> None:
        """Initialize the webos device."""
        self._entry = entry
        self._client = entry.runtime_data
        self._attr_assumed_state = True
        self._device_name = entry.title
        self._attr_unique_id = entry.unique_id
        self._sources = entry.options.get(CONF_SOURCES)

        # Assume that the TV is not paused
        self._paused = False
        self._turn_on = PluggableAction(self.async_write_ha_state)
        self._current_source = None
        self._source_list: dict = {}

        self._supported_features = MediaPlayerEntityFeature(0)
        self._update_states()

    async def async_added_to_hass(self) -> None:
        """Connect and subscribe to dispatcher signals and state updates."""
        await super().async_added_to_hass()

        if (entry := self.registry_entry) and entry.device_id:
            self.async_on_remove(
                self._turn_on.async_register(
                    self.hass, async_get_turn_on_trigger(entry.device_id)
                )
            )

        await self._client.register_state_update_callback(
            self.async_handle_state_update
        )

        if (
            self.state == MediaPlayerState.OFF
            and (state := await self.async_get_last_state()) is not None
        ):
            self._supported_features = (
                state.attributes.get(
                    ATTR_SUPPORTED_FEATURES, MediaPlayerEntityFeature(0)
                )
                & ~MediaPlayerEntityFeature.TURN_ON
            )

    async def async_will_remove_from_hass(self) -> None:
        """Call disconnect on removal."""
        self._client.unregister_state_update_callback(self.async_handle_state_update)

    async def async_handle_state_update(self, tv_state: WebOsTvState) -> None:
        """Update state from WebOsClient."""
        self._update_states()
        self.async_write_ha_state()

    def _update_states(self) -> None:
        """Update entity state attributes."""
        tv_state = self._client.tv_state
        self._update_sources()

        self._attr_state = (
            MediaPlayerState.ON if tv_state.is_on else MediaPlayerState.OFF
        )
        self._attr_is_volume_muted = cast(bool, tv_state.muted)

        self._attr_volume_level = None
        if tv_state.volume is not None:
            self._attr_volume_level = tv_state.volume / 100.0

        self._attr_source = self._current_source
        self._attr_source_list = sorted(self._source_list)

        self._attr_media_content_type = None
        if tv_state.current_app_id == LIVE_TV_APP_ID:
            self._attr_media_content_type = MediaType.CHANNEL

        self._attr_media_title = None
        if (tv_state.current_app_id == LIVE_TV_APP_ID) and (
            tv_state.current_channel is not None
        ):
            self._attr_media_title = cast(
                str, tv_state.current_channel.get("channelName")
            )

        self._attr_media_image_url = None
        if tv_state.current_app_id in tv_state.apps:
            icon: str = tv_state.apps[tv_state.current_app_id]["largeIcon"]
            if not icon.startswith("http"):
                icon = tv_state.apps[tv_state.current_app_id]["icon"]
            self._attr_media_image_url = icon

        if self.state != MediaPlayerState.OFF or not self._supported_features:
            supported = SUPPORT_WEBOSTV
            if tv_state.sound_output == "external_speaker":
                supported = supported | SUPPORT_WEBOSTV_VOLUME
            elif tv_state.sound_output != "lineout":
                supported = (
                    supported
                    | SUPPORT_WEBOSTV_VOLUME
                    | MediaPlayerEntityFeature.VOLUME_SET
                )

            self._supported_features = supported

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cast(str, self.unique_id))},
            manufacturer="LG",
            name=self._device_name,
        )

        self._attr_assumed_state = True
        if tv_state.is_on and tv_state.media_state:
            self._attr_assumed_state = False
            for entry in tv_state.media_state:
                if entry.get("playState") == "playing":
                    self._attr_state = MediaPlayerState.PLAYING
                elif entry.get("playState") == "paused":
                    self._attr_state = MediaPlayerState.PAUSED
                elif entry.get("playState") == "unloaded":
                    self._attr_state = MediaPlayerState.IDLE

        tv_info = self._client.tv_info
        if self.state != MediaPlayerState.OFF:
            maj_v = tv_info.software.get("major_ver")
            min_v = tv_info.software.get("minor_ver")
            if maj_v and min_v:
                self._attr_device_info["sw_version"] = f"{maj_v}.{min_v}"

            if model := tv_info.system.get("modelName"):
                self._attr_device_info["model"] = model

            if serial_number := tv_info.system.get("serialNumber"):
                self._attr_device_info["serial_number"] = serial_number

        self._attr_extra_state_attributes = {}
        if tv_state.sound_output is not None or self.state != MediaPlayerState.OFF:
            self._attr_extra_state_attributes = {
                ATTR_SOUND_OUTPUT: tv_state.sound_output
            }

    def _update_sources(self) -> None:
        """Update list of sources from current source, apps, inputs and configured list."""
        tv_state = self._client.tv_state
        source_list = self._source_list
        self._source_list = {}
        conf_sources = self._sources

        found_live_tv = False
        for app in tv_state.apps.values():
            if app["id"] == LIVE_TV_APP_ID:
                found_live_tv = True
            if app["id"] == tv_state.current_app_id:
                self._current_source = app["title"]
                self._source_list[app["title"]] = app
            elif (
                not conf_sources
                or app["id"] in conf_sources
                or any(word in app["title"] for word in conf_sources)
                or any(word in app["id"] for word in conf_sources)
            ):
                self._source_list[app["title"]] = app

        for source in tv_state.inputs.values():
            if source["appId"] == LIVE_TV_APP_ID:
                found_live_tv = True
            if source["appId"] == tv_state.current_app_id:
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
            if tv_state.current_app_id == LIVE_TV_APP_ID:
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

        with suppress(*WEBOSTV_EXCEPTIONS):
            try:
                await self._client.connect()
            except WebOsTvPairError:
                self._entry.async_start_reauth(self.hass)
            else:
                update_client_key(self.hass, self._entry)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self._turn_on:
            return self._supported_features | MediaPlayerEntityFeature.TURN_ON

        return self._supported_features

    @cmd
    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self._client.power_off()

    async def async_turn_on(self) -> None:
        """Turn on media player."""
        await self._turn_on.async_run(self.hass, self._context)

    @cmd
    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self._client.volume_up()

    @cmd
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._client.volume_down()

    @cmd
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        tv_volume = int(round(volume * 100))
        await self._client.set_volume(tv_volume)

    @cmd
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._client.set_mute(mute)

    @cmd
    async def async_select_sound_output(self, sound_output: str) -> ServiceResponse:
        """Select the sound output."""
        return await self._client.change_sound_output(sound_output)

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
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="source_not_found",
                translation_placeholders={
                    "source": source,
                    "name": str(self._friendly_name_internal()),
                },
            )
        if source_dict.get("title"):
            await self._client.launch_app(source_dict["id"])
        elif source_dict.get("label"):
            await self._client.set_input(source_dict["id"])

    @cmd
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Call play media type <%s>, Id <%s>", media_type, media_id)

        if media_type == MediaType.CHANNEL and self._client.tv_state.channels:
            _LOGGER.debug("Searching channel")
            partial_match_channel_id = None
            perfect_match_channel_id = None

            for channel in self._client.tv_state.channels:
                if media_id == channel["channelNumber"]:
                    perfect_match_channel_id = channel["channelId"]
                    continue

                if media_id.lower() == channel["channelName"].lower():
                    perfect_match_channel_id = channel["channelId"]
                    continue

                if media_id.lower() in channel["channelName"].lower():
                    partial_match_channel_id = channel["channelId"]

            if perfect_match_channel_id is not None:
                _LOGGER.debug(
                    "Switching to channel <%s> with perfect match",
                    perfect_match_channel_id,
                )
                await self._client.set_channel(perfect_match_channel_id)
            elif partial_match_channel_id is not None:
                _LOGGER.debug(
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
        if self._client.tv_state.current_app_id == LIVE_TV_APP_ID:
            await self._client.channel_up()
        else:
            await self._client.fast_forward()

    @cmd
    async def async_media_previous_track(self) -> None:
        """Send the previous track command."""
        if self._client.tv_state.current_app_id == LIVE_TV_APP_ID:
            await self._client.channel_down()
        else:
            await self._client.rewind()

    @cmd
    async def async_button(self, button: str) -> None:
        """Send a button press."""
        await self._client.button(button)

    @cmd
    async def async_command(self, command: str, **kwargs: Any) -> ServiceResponse:
        """Send a command."""
        return await self._client.request(command, payload=kwargs.get(ATTR_PAYLOAD))

    async def _async_fetch_image(self, url: str) -> tuple[bytes | None, str | None]:
        """Retrieve an image.

        webOS uses self-signed certificates, thus we need to use an empty
        SSLContext to bypass validation errors if url starts with https.
        """
        content = None

        websession = async_get_clientsession(self.hass)
        with suppress(TimeoutError):
            async with asyncio.timeout(10):
                response = await websession.get(url, ssl=False)
                if response.status == HTTPStatus.OK:
                    content = await response.read()

        if content is None:
            _LOGGER.warning("Error retrieving proxied image from %s", url)

        return content, None
