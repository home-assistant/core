"""Media Player component to integrate TVs exposing the Joint Space API."""
from __future__ import annotations

from haphilipsjs import ConnectionFailure

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_APP,
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_APPS,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_CHANNELS,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LOGGER as _LOGGER, PhilipsTVDataUpdateCoordinator
from .const import DOMAIN

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

CONF_ON_ACTION = "turn_on_action"


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


class PhilipsTVMediaPlayer(
    CoordinatorEntity[PhilipsTVDataUpdateCoordinator], MediaPlayerEntity
):
    """Representation of a Philips TV exposing the JointSpace API."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize the Philips TV."""
        self._tv = coordinator.api
        self._sources: dict[str, str] = {}
        self._supports = SUPPORT_PHILIPS_JS
        self._system = coordinator.system
        self._attr_unique_id = coordinator.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.unique_id),
            },
            manufacturer="Philips",
            model=coordinator.system.get("model"),
            sw_version=coordinator.system.get("softwareversion"),
            name=coordinator.system["name"],
        )
        self._state = STATE_OFF
        self._media_content_type: str | None = None
        self._media_content_id: str | None = None
        self._media_title: str | None = None
        self._media_channel: str | None = None

        super().__init__(coordinator)
        self._update_from_coordinator()

    async def _async_update_soon(self):
        """Reschedule update task."""
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        supports = self._supports
        if self.coordinator.turn_on or (
            self._tv.on and self._tv.powerstate is not None
        ):
            supports |= MediaPlayerEntityFeature.TURN_ON
        return supports

    @property
    def state(self):
        """Get the device state. An exception means OFF state."""
        if self._tv.on and (self._tv.powerstate == "On" or self._tv.powerstate is None):
            return STATE_ON
        return STATE_OFF

    @property
    def source(self):
        """Return the current input source."""
        return self._sources.get(self._tv.source_id)

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._sources.values())

    async def async_select_source(self, source):
        """Set the input source."""
        if source_id := _inverted(self._sources).get(source):
            await self._tv.setSource(source_id)
        await self._async_update_soon()

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._tv.volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._tv.muted

    async def async_turn_on(self):
        """Turn on the device."""
        if self._tv.on and self._tv.powerstate:
            await self._tv.setPowerState("On")
            self._state = STATE_ON
        else:
            await self.coordinator.turn_on.async_run(self.hass, self._context)
        await self._async_update_soon()

    async def async_turn_off(self):
        """Turn off the device."""
        if self._state == STATE_ON:
            await self._tv.sendKey("Standby")
            self._state = STATE_OFF
            await self._async_update_soon()
        else:
            _LOGGER.debug("Ignoring turn off when already in expected state")

    async def async_volume_up(self):
        """Send volume up command."""
        await self._tv.sendKey("VolumeUp")
        await self._async_update_soon()

    async def async_volume_down(self):
        """Send volume down command."""
        await self._tv.sendKey("VolumeDown")
        await self._async_update_soon()

    async def async_mute_volume(self, mute):
        """Send mute command."""
        if self._tv.muted != mute:
            await self._tv.sendKey("Mute")
            await self._async_update_soon()
        else:
            _LOGGER.debug("Ignoring request when already in expected state")

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._tv.setVolume(volume, self._tv.muted)
        await self._async_update_soon()

    async def async_media_previous_track(self):
        """Send rewind command."""
        await self._tv.sendKey("Previous")
        await self._async_update_soon()

    async def async_media_next_track(self):
        """Send fast forward command."""
        await self._tv.sendKey("Next")
        await self._async_update_soon()

    async def async_media_play_pause(self):
        """Send pause command to media player."""
        if self._tv.quirk_playpause_spacebar:
            await self._tv.sendUnicode(" ")
        else:
            await self._tv.sendKey("PlayPause")
        await self._async_update_soon()

    async def async_media_play(self):
        """Send pause command to media player."""
        await self._tv.sendKey("Play")
        await self._async_update_soon()

    async def async_media_pause(self):
        """Send play command to media player."""
        await self._tv.sendKey("Pause")
        await self._async_update_soon()

    async def async_media_stop(self):
        """Send play command to media player."""
        await self._tv.sendKey("Stop")
        await self._async_update_soon()

    @property
    def media_channel(self):
        """Get current channel if it's a channel."""
        return self._media_channel

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._media_title

    @property
    def media_content_type(self):
        """Return content type of playing media."""
        return self._media_content_type

    @property
    def media_content_id(self):
        """Content type of current playing media."""
        return self._media_content_id

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._media_content_id and self._media_content_type in (
            MEDIA_TYPE_APP,
            MEDIA_TYPE_CHANNEL,
        ):
            return self.get_browse_image_url(
                self._media_content_type, self._media_content_id, media_image_id=None
            )
        return None

    @property
    def app_id(self):
        """ID of the current running app."""
        return self._tv.application_id

    @property
    def app_name(self):
        """Name of the current running app."""
        if app := self._tv.applications.get(self._tv.application_id):
            return app.get("label")

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        _LOGGER.debug("Call play media type <%s>, Id <%s>", media_type, media_id)

        if media_type == MEDIA_TYPE_CHANNEL:
            list_id, _, channel_id = media_id.partition("/")
            if channel_id:
                await self._tv.setChannel(channel_id, list_id)
                await self._async_update_soon()
            else:
                _LOGGER.error("Unable to find channel <%s>", media_id)
        elif media_type == MEDIA_TYPE_APP:
            if app := self._tv.applications.get(media_id):
                await self._tv.setApplication(app["intent"])
                await self._async_update_soon()
            else:
                _LOGGER.error("Unable to find application <%s>", media_id)
        else:
            _LOGGER.error("Unsupported media type <%s>", media_type)

    async def async_browse_media_channels(self, expanded):
        """Return channel media objects."""
        if expanded:
            children = [
                BrowseMedia(
                    title=channel.get("name", f"Channel: {channel_id}"),
                    media_class=MEDIA_CLASS_CHANNEL,
                    media_content_id=f"alltv/{channel_id}",
                    media_content_type=MEDIA_TYPE_CHANNEL,
                    can_play=True,
                    can_expand=False,
                )
                for channel_id, channel in self._tv.channels.items()
            ]
        else:
            children = None

        return BrowseMedia(
            title="Channels",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="channels",
            media_content_type=MEDIA_TYPE_CHANNELS,
            children_media_class=MEDIA_CLASS_CHANNEL,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def async_browse_media_favorites(self, list_id, expanded):
        """Return channel media objects."""
        if expanded:
            favorites = await self._tv.getFavoriteList(list_id)
            if favorites:

                def get_name(channel):
                    channel_data = self._tv.channels.get(str(channel["ccid"]))
                    if channel_data:
                        return channel_data["name"]
                    return f"Channel: {channel['ccid']}"

                children = [
                    BrowseMedia(
                        title=get_name(channel),
                        media_class=MEDIA_CLASS_CHANNEL,
                        media_content_id=f"{list_id}/{channel['ccid']}",
                        media_content_type=MEDIA_TYPE_CHANNEL,
                        can_play=True,
                        can_expand=False,
                    )
                    for channel in favorites
                ]
            else:
                children = None
        else:
            children = None

        favorite = self._tv.favorite_lists[list_id]
        return BrowseMedia(
            title=favorite.get("name", f"Favorites {list_id}"),
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id=f"favorites/{list_id}",
            media_content_type=MEDIA_TYPE_CHANNELS,
            children_media_class=MEDIA_CLASS_CHANNEL,
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
                    media_class=MEDIA_CLASS_APP,
                    media_content_id=application_id,
                    media_content_type=MEDIA_TYPE_APP,
                    can_play=True,
                    can_expand=False,
                    thumbnail=self.get_browse_image_url(
                        MEDIA_TYPE_APP, application_id, media_image_id=None
                    ),
                )
                for application_id, application in self._tv.applications.items()
            ]
        else:
            children = None

        return BrowseMedia(
            title="Applications",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="applications",
            media_content_type=MEDIA_TYPE_APPS,
            children_media_class=MEDIA_CLASS_APP,
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
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="favorite_lists",
            media_content_type=MEDIA_TYPE_CHANNELS,
            children_media_class=MEDIA_CLASS_CHANNEL,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def async_browse_media_root(self):
        """Return root media objects."""

        return BrowseMedia(
            title="Philips TV",
            media_class=MEDIA_CLASS_DIRECTORY,
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

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        if not self._tv.on:
            raise BrowseError("Can't browse when tv is turned off")

        if media_content_id in (None, ""):
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
        media_content_type: str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Serve album art. Returns (content, content_type)."""
        try:
            if media_content_type == MEDIA_TYPE_APP and media_content_id:
                return await self._tv.getApplicationIcon(media_content_id)
            if media_content_type == MEDIA_TYPE_CHANNEL and media_content_id:
                return await self._tv.getChannelLogo(media_content_id)
        except ConnectionFailure:
            _LOGGER.warning("Failed to fetch image")
        return None, None

    async def async_get_media_image(self):
        """Serve album art. Returns (content, content_type)."""
        return await self.async_get_browse_image(
            self.media_content_type, self.media_content_id, None
        )

    @callback
    def _update_from_coordinator(self):

        if self._tv.on:
            if self._tv.powerstate in ("Standby", "StandbyKeep"):
                self._state = STATE_OFF
            else:
                self._state = STATE_ON
        else:
            self._state = STATE_OFF

        self._sources = {
            srcid: source.get("name") or f"Source {srcid}"
            for srcid, source in (self._tv.sources or {}).items()
        }

        if self._tv.channel_active:
            self._media_content_type = MEDIA_TYPE_CHANNEL
            self._media_content_id = f"all/{self._tv.channel_id}"
            self._media_title = self._tv.channels.get(self._tv.channel_id, {}).get(
                "name"
            )
            self._media_channel = self._media_title
        elif self._tv.application_id:
            self._media_content_type = MEDIA_TYPE_APP
            self._media_content_id = self._tv.application_id
            self._media_title = self._tv.applications.get(
                self._tv.application_id, {}
            ).get("label")
            self._media_channel = None
        else:
            self._media_content_type = None
            self._media_content_id = None
            self._media_title = self._sources.get(self._tv.source_id)
            self._media_channel = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()
