"""Media player support for Bravia TV integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    BrowseError,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.components.media_player.browse_media import BrowseMedia
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SourceType
from .entity import BraviaTVEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bravia TV Media Player from a config_entry."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    unique_id = config_entry.unique_id
    assert unique_id is not None

    async_add_entities(
        [BraviaTVMediaPlayer(coordinator, unique_id, config_entry.title)]
    )


class BraviaTVMediaPlayer(BraviaTVEntity, MediaPlayerEntity):
    """Representation of a Bravia TV Media Player."""

    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        if self.coordinator.is_on:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self.coordinator.source

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return self.coordinator.source_list

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self.coordinator.volume_level

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return self.coordinator.volume_muted

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.coordinator.media_title

    @property
    def media_channel(self) -> str | None:
        """Channel currently playing."""
        return self.coordinator.media_channel

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        return self.coordinator.media_content_id

    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        return self.coordinator.media_content_type

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self.coordinator.media_duration

    async def async_turn_on(self) -> None:
        """Turn the device on."""
        await self.coordinator.async_turn_on()

    async def async_turn_off(self) -> None:
        """Turn the device off."""
        await self.coordinator.async_turn_off()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.coordinator.async_set_volume_level(volume)

    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self.coordinator.async_volume_up()

    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self.coordinator.async_volume_down()

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self.coordinator.async_volume_mute(mute)

    async def async_browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse apps and channels."""
        if not media_content_id:
            await self.coordinator.async_update_sources()
            return await self.async_browse_media_root()

        path = media_content_id.partition("/")
        if path[0] == "apps":
            return await self.async_browse_media_apps(True)
        if path[0] == "channels":
            return await self.async_browse_media_channels(True)

        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")

    async def async_browse_media_root(self) -> BrowseMedia:
        """Return root media objects."""

        return BrowseMedia(
            title="Sony TV",
            media_class=MediaClass.DIRECTORY,
            media_content_id="",
            media_content_type="",
            can_play=False,
            can_expand=True,
            children=[
                await self.async_browse_media_apps(),
                await self.async_browse_media_channels(),
            ],
        )

    async def async_browse_media_apps(self, expanded: bool = False) -> BrowseMedia:
        """Return apps media objects."""
        if expanded:
            children = [
                BrowseMedia(
                    title=item["title"],
                    media_class=MediaClass.APP,
                    media_content_id=uri,
                    media_content_type=MediaType.APP,
                    can_play=False,
                    can_expand=False,
                    thumbnail=self.get_browse_image_url(
                        MediaType.APP, uri, media_image_id=None
                    ),
                )
                for uri, item in self.coordinator.source_map.items()
                if item["type"] == SourceType.APP
            ]
        else:
            children = None

        return BrowseMedia(
            title="Applications",
            media_class=MediaClass.DIRECTORY,
            media_content_id="apps",
            media_content_type=MediaType.APPS,
            children_media_class=MediaClass.APP,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def async_browse_media_channels(self, expanded: bool = False) -> BrowseMedia:
        """Return channels media objects."""
        if expanded:
            children = [
                BrowseMedia(
                    title=item["title"],
                    media_class=MediaClass.CHANNEL,
                    media_content_id=uri,
                    media_content_type=MediaType.CHANNEL,
                    can_play=False,
                    can_expand=False,
                )
                for uri, item in self.coordinator.source_map.items()
                if item["type"] == SourceType.CHANNEL
            ]
        else:
            children = None

        return BrowseMedia(
            title="Channels",
            media_class=MediaClass.DIRECTORY,
            media_content_id="channels",
            media_content_type=MediaType.CHANNELS,
            children_media_class=MediaClass.CHANNEL,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def async_get_browse_image(
        self,
        media_content_type: str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Serve album art. Returns (content, content_type)."""
        if media_content_type == MediaType.APP and media_content_id:
            if icon := self.coordinator.source_map[media_content_id].get("icon"):
                (content, content_type) = await self._async_fetch_image(icon)
                if content_type:
                    # Fix invalid Content-Type header returned by Bravia
                    content_type = content_type.replace("Content-Type: ", "")
                return (content, content_type)
        return None, None

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        await self.coordinator.async_play_media(media_type, media_id, **kwargs)

    async def async_select_source(self, source: str) -> None:
        """Set the input source."""
        await self.coordinator.async_select_source(source)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.coordinator.async_media_play()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.coordinator.async_media_pause()

    async def async_media_play_pause(self) -> None:
        """Send pause command that toggle play/pause."""
        await self.coordinator.async_media_pause()

    async def async_media_stop(self) -> None:
        """Send media stop command to media player."""
        await self.coordinator.async_media_stop()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.async_media_next_track()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.async_media_previous_track()
