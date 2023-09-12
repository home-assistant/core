"""Support for the Roku media player."""
from __future__ import annotations

import datetime as dt
import logging
import mimetypes
from typing import Any

from rokuecp.helpers import guess_stream_format
import voluptuous as vol
import yarl

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_EXTRA,
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.components.stream import FORMAT_CONTENT_TYPE, HLS_PROVIDER
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .browse_media import async_browse_media
from .const import (
    ATTR_ARTIST_NAME,
    ATTR_CONTENT_ID,
    ATTR_FORMAT,
    ATTR_KEYWORD,
    ATTR_MEDIA_TYPE,
    ATTR_THUMBNAIL,
    DOMAIN,
    SERVICE_SEARCH,
)
from .coordinator import RokuDataUpdateCoordinator
from .entity import RokuEntity
from .helpers import format_channel_name, roku_exception_handler

_LOGGER = logging.getLogger(__name__)


STREAM_FORMAT_TO_MEDIA_TYPE = {
    "dash": MediaType.VIDEO,
    "hls": MediaType.VIDEO,
    "ism": MediaType.VIDEO,
    "m4a": MediaType.MUSIC,
    "m4v": MediaType.VIDEO,
    "mka": MediaType.MUSIC,
    "mkv": MediaType.VIDEO,
    "mks": MediaType.VIDEO,
    "mp3": MediaType.MUSIC,
    "mp4": MediaType.VIDEO,
}

ATTRS_TO_LAUNCH_PARAMS = {
    ATTR_CONTENT_ID: "contentID",
    ATTR_MEDIA_TYPE: "mediaType",
}

ATTRS_TO_PLAY_ON_ROKU_PARAMS = {
    ATTR_NAME: "videoName",
    ATTR_FORMAT: "videoFormat",
    ATTR_THUMBNAIL: "k",
}

ATTRS_TO_PLAY_ON_ROKU_AUDIO_PARAMS = {
    ATTR_NAME: "songName",
    ATTR_FORMAT: "songFormat",
    ATTR_ARTIST_NAME: "artistName",
    ATTR_THUMBNAIL: "albumArtUrl",
}

SEARCH_SCHEMA = {vol.Required(ATTR_KEYWORD): str}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Roku config entry."""
    coordinator: RokuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            RokuMediaPlayer(
                coordinator=coordinator,
            )
        ],
        True,
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SEARCH,
        SEARCH_SCHEMA,
        "search",
    )


class RokuMediaPlayer(RokuEntity, MediaPlayerEntity):
    """Representation of a Roku media player on the network."""

    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

    def _media_playback_trackable(self) -> bool:
        """Detect if we have enough media data to track playback."""
        if self.coordinator.data.media is None or self.coordinator.data.media.live:
            return False

        return self.coordinator.data.media.duration > 0

    @property
    def device_class(self) -> MediaPlayerDeviceClass:
        """Return the class of this device."""
        if self.coordinator.data.info.device_type == "tv":
            return MediaPlayerDeviceClass.TV

        return MediaPlayerDeviceClass.RECEIVER

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self.coordinator.data.state.standby:
            return MediaPlayerState.STANDBY

        if self.coordinator.data.app is None:
            return None

        if (
            self.coordinator.data.app.name == "Power Saver"
            or self.coordinator.data.app.name == "Roku"
            or self.coordinator.data.app.screensaver
        ):
            return MediaPlayerState.IDLE

        if self.coordinator.data.media:
            if self.coordinator.data.media.paused:
                return MediaPlayerState.PAUSED
            return MediaPlayerState.PLAYING

        if self.coordinator.data.app.name:
            return MediaPlayerState.ON

        return None

    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        if self.app_id is None or self.app_name in ("Power Saver", "Roku"):
            return None

        if self.app_id == "tvinput.dtv" and self.coordinator.data.channel is not None:
            return MediaType.CHANNEL

        return MediaType.APP

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if self.app_id is None or self.app_name in ("Power Saver", "Roku"):
            return None

        return self.coordinator.roku.app_icon_url(self.app_id)

    @property
    def app_name(self) -> str | None:
        """Name of the current running app."""
        if self.coordinator.data.app is not None:
            return self.coordinator.data.app.name

        return None

    @property
    def app_id(self) -> str | None:
        """Return the ID of the current running app."""
        if self.coordinator.data.app is not None:
            return self.coordinator.data.app.app_id

        return None

    @property
    def media_channel(self) -> str | None:
        """Return the TV channel currently tuned."""
        if self.app_id != "tvinput.dtv" or self.coordinator.data.channel is None:
            return None

        channel = self.coordinator.data.channel

        return format_channel_name(channel.number, channel.name)

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        if self.app_id != "tvinput.dtv" or self.coordinator.data.channel is None:
            return None

        if self.coordinator.data.channel.program_title is not None:
            return self.coordinator.data.channel.program_title

        return None

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if self.coordinator.data.media is not None and self._media_playback_trackable():
            return self.coordinator.data.media.duration

        return None

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if self.coordinator.data.media is not None and self._media_playback_trackable():
            return self.coordinator.data.media.position

        return None

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid."""
        if self.coordinator.data.media is not None and self._media_playback_trackable():
            return self.coordinator.data.media.at

        return None

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        if self.coordinator.data.app is not None:
            return self.coordinator.data.app.name

        return None

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return ["Home"] + sorted(
            app.name for app in self.coordinator.data.apps if app.name is not None
        )

    @roku_exception_handler()
    async def search(self, keyword: str) -> None:
        """Emulate opening the search screen and entering the search keyword."""
        await self.coordinator.roku.search(keyword)

    async def async_get_browse_image(
        self,
        media_content_type: MediaType | str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Fetch media browser image to serve via proxy."""
        if media_content_type == MediaType.APP and media_content_id:
            image_url = self.coordinator.roku.app_icon_url(media_content_id)
            return await self._async_fetch_image(image_url)

        return (None, None)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await async_browse_media(
            self.hass,
            self.coordinator,
            self.get_browse_image_url,
            media_content_id,
            media_content_type,
        )

    @roku_exception_handler()
    async def async_turn_on(self) -> None:
        """Turn on the Roku."""
        await self.coordinator.roku.remote("poweron")
        await self.coordinator.async_request_refresh()

    @roku_exception_handler(ignore_timeout=True)
    async def async_turn_off(self) -> None:
        """Turn off the Roku."""
        await self.coordinator.roku.remote("poweroff")
        await self.coordinator.async_request_refresh()

    @roku_exception_handler()
    async def async_media_pause(self) -> None:
        """Send pause command."""
        if self.state not in {MediaPlayerState.STANDBY, MediaPlayerState.PAUSED}:
            await self.coordinator.roku.remote("play")
            await self.coordinator.async_request_refresh()

    @roku_exception_handler()
    async def async_media_play(self) -> None:
        """Send play command."""
        if self.state not in {MediaPlayerState.STANDBY, MediaPlayerState.PLAYING}:
            await self.coordinator.roku.remote("play")
            await self.coordinator.async_request_refresh()

    @roku_exception_handler()
    async def async_media_play_pause(self) -> None:
        """Send play/pause command."""
        if self.state != MediaPlayerState.STANDBY:
            await self.coordinator.roku.remote("play")
            await self.coordinator.async_request_refresh()

    @roku_exception_handler()
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.roku.remote("reverse")
        await self.coordinator.async_request_refresh()

    @roku_exception_handler()
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.roku.remote("forward")
        await self.coordinator.async_request_refresh()

    @roku_exception_handler()
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.coordinator.roku.remote("volume_mute")
        await self.coordinator.async_request_refresh()

    @roku_exception_handler()
    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self.coordinator.roku.remote("volume_up")

    @roku_exception_handler()
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self.coordinator.roku.remote("volume_down")

    @roku_exception_handler()
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media from a URL or file, launch an application, or tune to a channel."""
        extra: dict[str, Any] = kwargs.get(ATTR_MEDIA_EXTRA) or {}
        original_media_type: str = media_type
        original_media_id: str = media_id
        mime_type: str | None = None
        stream_name: str | None = None
        stream_format: str | None = extra.get(ATTR_FORMAT)

        # Handle media_source
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_type = MediaType.URL
            media_id = sourced_media.url
            mime_type = sourced_media.mime_type
            stream_name = original_media_id
            stream_format = guess_stream_format(media_id, mime_type)

        if media_type == FORMAT_CONTENT_TYPE[HLS_PROVIDER]:
            media_type = MediaType.VIDEO
            mime_type = FORMAT_CONTENT_TYPE[HLS_PROVIDER]
            stream_name = "Camera Stream"
            stream_format = "hls"

        if media_type in {MediaType.MUSIC, MediaType.URL, MediaType.VIDEO}:
            # If media ID is a relative URL, we serve it from HA.
            media_id = async_process_play_media_url(self.hass, media_id)

            parsed = yarl.URL(media_id)

            if mime_type is None:
                mime_type, _ = mimetypes.guess_type(parsed.path)

            if stream_format is None:
                stream_format = guess_stream_format(media_id, mime_type)

            if extra.get(ATTR_FORMAT) is None:
                extra[ATTR_FORMAT] = stream_format

            if extra[ATTR_FORMAT] not in STREAM_FORMAT_TO_MEDIA_TYPE:
                _LOGGER.error(
                    "Media type %s is not supported with format %s (mime: %s)",
                    original_media_type,
                    extra[ATTR_FORMAT],
                    mime_type,
                )
                return

            if (
                media_type == MediaType.URL
                and STREAM_FORMAT_TO_MEDIA_TYPE[extra[ATTR_FORMAT]] == MediaType.MUSIC
            ):
                media_type = MediaType.MUSIC

            if media_type == MediaType.MUSIC and "tts_proxy" in media_id:
                stream_name = "Text to Speech"
            elif stream_name is None:
                if stream_format == "ism":
                    stream_name = parsed.parts[-2]
                else:
                    stream_name = parsed.name

            if extra.get(ATTR_NAME) is None:
                extra[ATTR_NAME] = stream_name

        if media_type == MediaType.APP:
            params = {
                param: extra[attr]
                for attr, param in ATTRS_TO_LAUNCH_PARAMS.items()
                if attr in extra
            }

            await self.coordinator.roku.launch(media_id, params)
        elif media_type == MediaType.CHANNEL:
            await self.coordinator.roku.tune(media_id)
        elif media_type == MediaType.MUSIC:
            if extra.get(ATTR_ARTIST_NAME) is None:
                extra[ATTR_ARTIST_NAME] = "Home Assistant"

            params = {
                param: extra[attr]
                for (attr, param) in ATTRS_TO_PLAY_ON_ROKU_AUDIO_PARAMS.items()
                if attr in extra
            }

            params = {"t": "a", **params}

            await self.coordinator.roku.play_on_roku(media_id, params)
        elif media_type in {MediaType.URL, MediaType.VIDEO}:
            params = {
                param: extra[attr]
                for (attr, param) in ATTRS_TO_PLAY_ON_ROKU_PARAMS.items()
                if attr in extra
            }

            await self.coordinator.roku.play_on_roku(media_id, params)
        else:
            _LOGGER.error("Media type %s is not supported", original_media_type)
            return

        await self.coordinator.async_request_refresh()

    @roku_exception_handler()
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if source == "Home":
            await self.coordinator.roku.remote("home")

        appl = next(
            (
                app
                for app in self.coordinator.data.apps
                if source in (app.name, app.app_id)
            ),
            None,
        )

        if appl is not None and appl.app_id is not None:
            await self.coordinator.roku.launch(appl.app_id)
            await self.coordinator.async_request_refresh()
