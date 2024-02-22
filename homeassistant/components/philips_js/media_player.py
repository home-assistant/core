"""Media Player component to integrate TVs exposing the Joint Space API."""
from __future__ import annotations

from typing import Any

from haphilipsjs import ConnectionFailure

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.trigger import PluggableAction

from . import LOGGER as _LOGGER, PhilipsTVDataUpdateCoordinator
from .const import DOMAIN
from .entity import PhilipsJsEntity
from .helpers import async_get_turn_on_trigger

SUPPORT_PHILIPS_JS = (
    MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
)


def _inverted(data):
    return {v: k for k, v in data.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the configuration entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            PhilipsTVMediaPlayer(
                coordinator,
            )
        ]
    )


class PhilipsTVMediaPlayer(PhilipsJsEntity, MediaPlayerEntity):
    """Representation of a Philips TV exposing the JointSpace API."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_name = None

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize the Philips TV."""
        self._tv = coordinator.api
        self._sources: dict[str, str] = {}
        self._attr_unique_id = coordinator.unique_id
        self._attr_state = MediaPlayerState.OFF

        self._turn_on = PluggableAction(self.async_write_ha_state)
        super().__init__(coordinator)
        self._update_from_coordinator()

    async def async_added_to_hass(self) -> None:
        """Handle being added to hass."""
        await super().async_added_to_hass()

        if (entry := self.registry_entry) and entry.device_id:
            self.async_on_remove(
                self._turn_on.async_register(
                    self.hass, async_get_turn_on_trigger(entry.device_id)
                )
            )

    async def _async_update_soon(self):
        """Reschedule update task."""
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        supports = SUPPORT_PHILIPS_JS
        if self._turn_on or (self._tv.on and self._tv.powerstate is not None):
            supports |= MediaPlayerEntityFeature.TURN_ON
        return supports

    async def async_select_source(self, source: str) -> None:
        """Set the input source."""
        if source_id := _inverted(self._sources).get(source):
            await self._tv.setSource(source_id)
        await self._async_update_soon()

    async def async_turn_on(self) -> None:
        """Turn on the device."""
        if self._tv.on and self._tv.powerstate:
            await self._tv.setPowerState("On")
            self._attr_state = MediaPlayerState.ON
        else:
            await self._turn_on.async_run(self.hass, self._context)
        await self._async_update_soon()

    async def async_turn_off(self) -> None:
        """Turn off the device."""
        if self._attr_state == MediaPlayerState.ON:
            await self._tv.sendKey("Standby")
            self._attr_state = MediaPlayerState.OFF
            await self._async_update_soon()
        else:
            _LOGGER.debug("Ignoring turn off when already in expected state")

    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._tv.sendKey("VolumeUp")
        await self._async_update_soon()

    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._tv.sendKey("VolumeDown")
        await self._async_update_soon()

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        if self._tv.muted != mute:
            await self._tv.sendKey("Mute")
            await self._async_update_soon()
        else:
            _LOGGER.debug("Ignoring request when already in expected state")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._tv.setVolume(volume, self._tv.muted)
        await self._async_update_soon()

    async def async_media_previous_track(self) -> None:
        """Send rewind command."""
        if self._tv.channel_active:
            await self._tv.sendKey("ChannelStepDown")
        else:
            await self._tv.sendKey("Previous")
        await self._async_update_soon()

    async def async_media_next_track(self) -> None:
        """Send fast forward command."""
        if self._tv.channel_active:
            await self._tv.sendKey("ChannelStepUp")
        else:
            await self._tv.sendKey("Next")
        await self._async_update_soon()

    async def async_media_play_pause(self) -> None:
        """Send pause command to media player."""
        if self._tv.quirk_playpause_spacebar:
            await self._tv.sendKey("Confirm")
        else:
            await self._tv.sendKey("PlayPause")
        await self._async_update_soon()

    async def async_media_play(self) -> None:
        """Send pause command to media player."""
        await self._tv.sendKey("Play")
        await self._async_update_soon()

    async def async_media_pause(self) -> None:
        """Send play command to media player."""
        await self._tv.sendKey("Pause")
        await self._async_update_soon()

    async def async_media_stop(self) -> None:
        """Send play command to media player."""
        await self._tv.sendKey("Stop")
        await self._async_update_soon()

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if self._attr_media_content_id and self._attr_media_content_type in (
            MediaType.APP,
            MediaType.CHANNEL,
        ):
            return self.get_browse_image_url(
                self._attr_media_content_type,
                self._attr_media_content_id,
                media_image_id=None,
            )
        return None

    async def async_play_media_channel(self, media_id: str):
        """Play a channel."""
        list_id, _, channel_id = media_id.partition("/")
        if channel_id:
            await self._tv.setChannel(channel_id, list_id)
            await self._async_update_soon()
            return

        for channel in self._tv.channels_current:
            if channel.get("preset") == media_id:
                await self._tv.setChannel(channel["ccid"], self._tv.channel_list_id)
                await self._async_update_soon()
                return

        raise HomeAssistantError(f"Unable to find channel {media_id}")

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        _LOGGER.debug("Call play media type <%s>, Id <%s>", media_type, media_id)

        if media_type == MediaType.CHANNEL:
            await self.async_play_media_channel(media_id)
        elif media_type == MediaType.APP:
            if app := self._tv.applications.get(media_id):
                await self._tv.setApplication(app["intent"])
                await self._async_update_soon()
            else:
                raise HomeAssistantError(f"Unable to find application {media_id}")
        else:
            raise HomeAssistantError(f"Unsupported media type {media_type}")

    async def async_browse_media_channels(self, expanded: bool) -> BrowseMedia:
        """Return channel media objects."""
        if expanded:
            children = [
                BrowseMedia(
                    title=channel.get("name", f"Channel: {channel['ccid']}"),
                    media_class=MediaClass.CHANNEL,
                    media_content_id=f"{self._tv.channel_list_id}/{channel['ccid']}",
                    media_content_type=MediaType.CHANNEL,
                    can_play=True,
                    can_expand=False,
                )
                for channel in self._tv.channels_current
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

    async def async_browse_media_favorites(
        self, list_id: str, expanded: bool
    ) -> BrowseMedia:
        """Return channel media objects."""
        if expanded:
            favorites = self._tv.favorite_lists.get(list_id)
            if favorites:

                def get_name(channel):
                    channel_data = self._tv.channels.get(str(channel["ccid"]))
                    if channel_data:
                        return channel_data["name"]
                    return f"Channel: {channel['ccid']}"

                children = [
                    BrowseMedia(
                        title=get_name(channel),
                        media_class=MediaClass.CHANNEL,
                        media_content_id=f"{list_id}/{channel['ccid']}",
                        media_content_type=MediaType.CHANNEL,
                        can_play=True,
                        can_expand=False,
                    )
                    for channel in favorites.get("channels", [])
                ]
            else:
                children = None
        else:
            children = None

        favorite = self._tv.favorite_lists[list_id]
        return BrowseMedia(
            title=favorite.get("name", f"Favorites {list_id}"),
            media_class=MediaClass.DIRECTORY,
            media_content_id=f"favorites/{list_id}",
            media_content_type=MediaType.CHANNELS,
            children_media_class=MediaClass.CHANNEL,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def async_browse_media_applications(self, expanded):
        """Return application media objects."""
        if expanded:
            children = [
                BrowseMedia(
                    title=application["label"],
                    media_class=MediaClass.APP,
                    media_content_id=application_id,
                    media_content_type=MediaType.APP,
                    can_play=True,
                    can_expand=False,
                    thumbnail=self.get_browse_image_url(
                        MediaType.APP, application_id, media_image_id=None
                    ),
                )
                for application_id, application in self._tv.applications.items()
            ]
        else:
            children = None

        return BrowseMedia(
            title="Applications",
            media_class=MediaClass.DIRECTORY,
            media_content_id="applications",
            media_content_type=MediaType.APPS,
            children_media_class=MediaClass.APP,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def async_browse_media_favorite_lists(self, expanded):
        """Return favorite media objects."""
        if self._tv.favorite_lists and expanded:
            children = [
                await self.async_browse_media_favorites(list_id, False)
                for list_id in self._tv.favorite_lists
            ]
        else:
            children = None

        return BrowseMedia(
            title="Favorites",
            media_class=MediaClass.DIRECTORY,
            media_content_id="favorite_lists",
            media_content_type=MediaType.CHANNELS,
            children_media_class=MediaClass.CHANNEL,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def async_browse_media_root(self):
        """Return root media objects."""

        return BrowseMedia(
            title="Philips TV",
            media_class=MediaClass.DIRECTORY,
            media_content_id="",
            media_content_type="",
            can_play=False,
            can_expand=True,
            children=[
                await self.async_browse_media_channels(False),
                await self.async_browse_media_applications(False),
                await self.async_browse_media_favorite_lists(False),
            ],
        )

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        if not self._tv.on:
            raise BrowseError("Can't browse when tv is turned off")

        if media_content_id is None or media_content_id == "":
            return await self.async_browse_media_root()
        path = media_content_id.partition("/")
        if path[0] == "channels":
            return await self.async_browse_media_channels(True)
        if path[0] == "applications":
            return await self.async_browse_media_applications(True)
        if path[0] == "favorite_lists":
            return await self.async_browse_media_favorite_lists(True)
        if path[0] == "favorites":
            return await self.async_browse_media_favorites(path[2], True)

        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")

    async def async_get_browse_image(
        self,
        media_content_type: MediaType | str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Serve album art. Returns (content, content_type)."""
        try:
            if media_content_type == MediaType.APP and media_content_id:
                return await self._tv.getApplicationIcon(media_content_id)
            if media_content_type == MediaType.CHANNEL and media_content_id:
                return await self._tv.getChannelLogo(media_content_id)
        except ConnectionFailure:
            _LOGGER.warning("Failed to fetch image")
        return None, None

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Serve album art. Returns (content, content_type)."""
        if self.media_content_type is None or self.media_content_id is None:
            return None, None
        return await self.async_get_browse_image(
            self.media_content_type, self.media_content_id, None
        )

    @callback
    def _update_from_coordinator(self):
        if self._tv.on:
            if self._tv.powerstate in ("Standby", "StandbyKeep"):
                self._attr_state = MediaPlayerState.OFF
            else:
                self._attr_state = MediaPlayerState.ON
        else:
            self._attr_state = MediaPlayerState.OFF

        self._sources = {
            srcid: source.get("name") or f"Source {srcid}"
            for srcid, source in (self._tv.sources or {}).items()
        }

        self._attr_source = self._sources.get(self._tv.source_id)
        self._attr_source_list = list(self._sources.values())

        self._attr_app_id = self._tv.application_id
        if app := self._tv.applications.get(self._tv.application_id):
            self._attr_app_name = app.get("label")
        else:
            self._attr_app_name = None

        self._attr_volume_level = self._tv.volume
        self._attr_is_volume_muted = self._tv.muted

        if self._tv.channel_active:
            self._attr_media_content_type = MediaType.CHANNEL
            self._attr_media_content_id = f"all/{self._tv.channel_id}"
            self._attr_media_title = self._tv.channels.get(self._tv.channel_id, {}).get(
                "name"
            )
            self._attr_media_channel = self._attr_media_title
        elif self._tv.application_id:
            self._attr_media_content_type = MediaType.APP
            self._attr_media_content_id = self._tv.application_id
            self._attr_media_title = self._tv.applications.get(
                self._tv.application_id, {}
            ).get("label")
            self._attr_media_channel = None
        else:
            self._attr_media_content_type = None
            self._attr_media_content_id = None
            self._attr_media_title = self._sources.get(self._tv.source_id)
            self._attr_media_channel = None

        self._attr_assumed_state = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()
