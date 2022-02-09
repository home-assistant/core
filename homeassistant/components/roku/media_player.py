"""Support for the Roku media player."""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any
from urllib.parse import quote

import voluptuous as vol
import yarl

from homeassistant.components import media_source
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_EXTRA,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_URL,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.components.stream.const import FORMAT_CONTENT_TYPE, HLS_PROVIDER
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    STATE_HOME,
    STATE_IDLE,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import get_url, is_hass_url

from . import roku_exception_handler
from .browse_media import async_browse_media
from .const import (
    ATTR_CONTENT_ID,
    ATTR_FORMAT,
    ATTR_KEYWORD,
    ATTR_MEDIA_TYPE,
    DOMAIN,
    SERVICE_SEARCH,
)
from .coordinator import RokuDataUpdateCoordinator
from .entity import RokuEntity

_LOGGER = logging.getLogger(__name__)

SUPPORT_ROKU = (
    SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_BROWSE_MEDIA
)

ATTRS_TO_LAUNCH_PARAMS = {
    ATTR_CONTENT_ID: "contentID",
    ATTR_MEDIA_TYPE: "MediaType",
}

PLAY_MEDIA_SUPPORTED_TYPES = (
    MEDIA_TYPE_APP,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_URL,
    FORMAT_CONTENT_TYPE[HLS_PROVIDER],
)

ATTRS_TO_PLAY_VIDEO_PARAMS = {
    ATTR_NAME: "videoName",
    ATTR_FORMAT: "videoFormat",
}

SEARCH_SCHEMA = {vol.Required(ATTR_KEYWORD): str}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Roku config entry."""
    coordinator: RokuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    unique_id = coordinator.data.info.serial_number
    async_add_entities([RokuMediaPlayer(unique_id, coordinator)], True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SEARCH,
        SEARCH_SCHEMA,
        "search",
    )


class RokuMediaPlayer(RokuEntity, MediaPlayerEntity):
    """Representation of a Roku media player on the network."""

    def __init__(
        self, unique_id: str | None, coordinator: RokuDataUpdateCoordinator
    ) -> None:
        """Initialize the Roku device."""
        super().__init__(
            coordinator=coordinator,
            device_id=unique_id,
        )

        self._attr_name = coordinator.data.info.name
        self._attr_unique_id = unique_id
        self._attr_supported_features = SUPPORT_ROKU

    def _media_playback_trackable(self) -> bool:
        """Detect if we have enough media data to track playback."""
        if self.coordinator.data.media is None or self.coordinator.data.media.live:
            return False

        return self.coordinator.data.media.duration > 0

    @property
    def device_class(self) -> str | None:
        """Return the class of this device."""
        if self.coordinator.data.info.device_type == "tv":
            return MediaPlayerDeviceClass.TV

        return MediaPlayerDeviceClass.RECEIVER

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        if self.coordinator.data.state.standby:
            return STATE_STANDBY

        if self.coordinator.data.app is None:
            return None

        if (
            self.coordinator.data.app.name == "Power Saver"
            or self.coordinator.data.app.screensaver
        ):
            return STATE_IDLE

        if self.coordinator.data.app.name == "Roku":
            return STATE_HOME

        if self.coordinator.data.media:
            if self.coordinator.data.media.paused:
                return STATE_PAUSED
            return STATE_PLAYING

        if self.coordinator.data.app.name:
            return STATE_ON

        return None

    @property
    def media_content_type(self) -> str | None:
        """Content type of current playing media."""
        if self.app_id is None or self.app_name in ("Power Saver", "Roku"):
            return None

        if self.app_id == "tvinput.dtv" and self.coordinator.data.channel is not None:
            return MEDIA_TYPE_CHANNEL

        return MEDIA_TYPE_APP

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

        if self.coordinator.data.channel.name is not None:
            return f"{self.coordinator.data.channel.name} ({self.coordinator.data.channel.number})"

        return self.coordinator.data.channel.number

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
    def source_list(self) -> list:
        """List of available input sources."""
        return ["Home"] + sorted(
            app.name for app in self.coordinator.data.apps if app.name is not None
        )

    @roku_exception_handler
    async def search(self, keyword: str) -> None:
        """Emulate opening the search screen and entering the search keyword."""
        await self.coordinator.roku.search(keyword)

    async def async_get_browse_image(
        self,
        media_content_type: str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Fetch media browser image to serve via proxy."""
        if media_content_type == MEDIA_TYPE_APP and media_content_id:
            image_url = self.coordinator.roku.app_icon_url(media_content_id)
            return await self._async_fetch_image(image_url)

        return (None, None)

    async def async_browse_media(
        self,
        media_content_type: str | None = None,
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

    @roku_exception_handler
    async def async_turn_on(self) -> None:
        """Turn on the Roku."""
        await self.coordinator.roku.remote("poweron")
        await self.coordinator.async_request_refresh()

    @roku_exception_handler
    async def async_turn_off(self) -> None:
        """Turn off the Roku."""
        await self.coordinator.roku.remote("poweroff")
        await self.coordinator.async_request_refresh()

    @roku_exception_handler
    async def async_media_pause(self) -> None:
        """Send pause command."""
        if self.state not in (STATE_STANDBY, STATE_PAUSED):
            await self.coordinator.roku.remote("play")
            await self.coordinator.async_request_refresh()

    @roku_exception_handler
    async def async_media_play(self) -> None:
        """Send play command."""
        if self.state not in (STATE_STANDBY, STATE_PLAYING):
            await self.coordinator.roku.remote("play")
            await self.coordinator.async_request_refresh()

    @roku_exception_handler
    async def async_media_play_pause(self) -> None:
        """Send play/pause command."""
        if self.state != STATE_STANDBY:
            await self.coordinator.roku.remote("play")
            await self.coordinator.async_request_refresh()

    @roku_exception_handler
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.roku.remote("reverse")
        await self.coordinator.async_request_refresh()

    @roku_exception_handler
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.roku.remote("forward")
        await self.coordinator.async_request_refresh()

    @roku_exception_handler
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.coordinator.roku.remote("volume_mute")
        await self.coordinator.async_request_refresh()

    @roku_exception_handler
    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self.coordinator.roku.remote("volume_up")

    @roku_exception_handler
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self.coordinator.roku.remote("volume_down")

    @roku_exception_handler
    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media from a URL or file, launch an application, or tune to a channel."""
        extra: dict[str, Any] = kwargs.get(ATTR_MEDIA_EXTRA) or {}

        # Handle media_source
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(self.hass, media_id)
            media_type = MEDIA_TYPE_URL
            media_id = sourced_media.url

        # Sign and prefix with URL if playing a relative URL
        if media_id[0] == "/" or is_hass_url(self.hass, media_id):
            parsed = yarl.URL(media_id)

            if parsed.query:
                _LOGGER.debug("Not signing path for content with query param")
            else:
                media_id = async_sign_path(
                    self.hass,
                    quote(media_id),
                    dt.timedelta(seconds=media_source.DEFAULT_EXPIRY_TIME),
                )

            # prepend external URL
            if media_id[0] == "/":
                media_id = f"{get_url(self.hass)}{media_id}"

        if media_type not in PLAY_MEDIA_SUPPORTED_TYPES:
            _LOGGER.error(
                "Invalid media type %s. Only %s, %s, %s, and camera HLS streams are supported",
                media_type,
                MEDIA_TYPE_APP,
                MEDIA_TYPE_CHANNEL,
                MEDIA_TYPE_URL,
            )
            return

        if media_type == MEDIA_TYPE_APP:
            params = {
                param: extra[attr]
                for attr, param in ATTRS_TO_LAUNCH_PARAMS.items()
                if attr in extra
            }

            await self.coordinator.roku.launch(media_id, params)
        elif media_type == MEDIA_TYPE_CHANNEL:
            await self.coordinator.roku.tune(media_id)
        elif media_type == MEDIA_TYPE_URL:
            params = {
                param: extra[attr]
                for (attr, param) in ATTRS_TO_PLAY_VIDEO_PARAMS.items()
                if attr in extra
            }

            await self.coordinator.roku.play_on_roku(media_id, params)
        elif media_type == FORMAT_CONTENT_TYPE[HLS_PROVIDER]:
            params = {
                "MediaType": "hls",
            }

            await self.coordinator.roku.play_on_roku(media_id, params)

        await self.coordinator.async_request_refresh()

    @roku_exception_handler
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
