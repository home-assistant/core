"""Support to interface with the Jellyfin API."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from functools import wraps
import logging
from typing import Any, TypeVar
from xml.dom import NotFoundErr

from jellyfin_apiclient_python import JellyfinClient
from typing_extensions import Concatenate, ParamSpec

import homeassistant
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.browse_media import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONTENT_TYPE_MAP,
    DATA_CLIENT,
    DOMAIN,
    EXPANDABLE_TYPES,
    ITEM_KEY_IMAGE_TAGS,
    MEDIA_CLASS_MAP,
    MEDIA_TYPE_NONE,
    SUPPORTED_LIBRARY_TYPES,
)

_LOGGER = logging.getLogger(__name__)


_JellyfinMediaPlayerT = TypeVar("_JellyfinMediaPlayerT", bound="JellyfinMediaPlayer")
_R = TypeVar("_R")
_P = ParamSpec("_P")


def needs_data(
    func: Callable[Concatenate[_JellyfinMediaPlayerT, _P], _R]
) -> Callable[Concatenate[_JellyfinMediaPlayerT, _P], _R | None]:
    """Ensure session is available for certain attributes."""

    @wraps(func)
    def get_data_value(
        self: _JellyfinMediaPlayerT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R | None:
        if self._data is None:  # pylint: disable=protected-access
            return None

        try:
            return func(self, *args, **kwargs)
        except KeyError:
            return None

    return get_data_value


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jellyfin media_player from a config entry."""
    client: JellyfinClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    user = await hass.async_add_executor_job(client.jellyfin.get_user)

    coord = JellyfinMediaPlayerCoordinator(hass, client, user, async_add_entities)
    await coord.async_config_entry_first_refresh()
    _LOGGER.debug("New entity listener created")


class JellyfinMediaPlayerCoordinator(DataUpdateCoordinator):
    """Bundles data retrieval for sessions form Jellyfin server."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: JellyfinClient,
        user: str,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize the UpdateCoordinator."""
        super().__init__(
            hass, _LOGGER, name="Jellyfin", update_interval=timedelta(seconds=5)
        )

        self._client = client
        self._hass = hass
        self.user = user
        self.sessions: Any | None = None

        self._known: set[str] = set()
        self._async_add_entities = async_add_entities

    async def _async_update_data(self) -> None:
        self.sessions = await self._hass.async_add_executor_job(
            self._client.jellyfin.get_sessions
        )

        if not self.sessions:
            return

        for session in self.sessions:
            if session["Id"] not in self._known:
                self._known.add(session["Id"])
                entity = JellyfinMediaPlayer(self, self._hass, self._client, session)
                self._async_add_entities([entity], False)


class JellyfinMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Represents a Jellyfin Player device."""

    def __init__(
        self,
        coordinator: JellyfinMediaPlayerCoordinator,
        hass: HomeAssistant,
        client: JellyfinClient,
        session: Any,
    ) -> None:
        """Initialize the MediaPlayer Entity.

        Pulls out the properties from the session object we need, even when unavailable.
        """
        super().__init__(coordinator)
        self._hass = hass
        self._client = client
        self._device_id = session["DeviceId"]
        self._id = session["Id"]

        self._data = session

        self._attr_unique_id = f"{self._data['ServerId']}:{self._id}"
        self._attr_name = self._data["DeviceName"]
        self._attr_media_position_updated_at = homeassistant.util.dt.utcnow()
        self._attr_media_content_type = "video"
        self._attr_media_image_remotely_accessible = True
        self._attr_should_poll = True

    def update(self) -> None:
        """Update the internal state from Coordinator state."""
        self._data = None
        for session in self.coordinator.sessions:
            if session["Id"] == self._id:
                self._data = session
                self._attr_media_position_updated_at = homeassistant.util.dt.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        self.update()
        super()._handle_coordinator_update()

    @property  # type: ignore[misc]
    @needs_data
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        # We always need the now playing item.
        # If there is none, there's also no url
        now_playing = self._data["NowPlayingItem"]

        # Priority here is a bit questionable.
        # If the item has a backdrop, that works well.
        if "Backdrop" in now_playing[ITEM_KEY_IMAGE_TAGS]:
            return str(
                self._client.jellyfin.artwork(now_playing["Id"], "Backdrop", 100)
            )

        # We can get parent backdrop (e.g. Season's splash) easyily
        try:
            backdrop_item_id = now_playing["ParentBackdropItemId"]

            return str(self._client.jellyfin.artwork(backdrop_item_id, "Backdrop", 100))
        except KeyError:
            pass

        # As sort of last resort, use the item's primary
        if "Primary" in now_playing[ITEM_KEY_IMAGE_TAGS]:
            return str(self._client.jellyfin.artwork(now_playing["Id"], "Primary", 100))

        # Bail with no image. Should we use parent primary?
        # pylint tricks itself with the formatting here...
        _LOGGER.warning(  # pylint: disable=logging-not-lazy
            "Could not get image for %s even though there's an item playing" % self.name
        )
        return None

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        ret = (
            MediaPlayerEntityFeature.BROWSE_MEDIA
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
        )
        try:
            if self._data and self._data["PlayState"]["CanSeek"]:
                ret |= MediaPlayerEntityFeature.SEEK
        except KeyError:
            pass

        try:
            if (
                self._data
                and self._data["Capabilities"]["SupportsMediaControl"]
                and self.state != STATE_IDLE
            ):
                ret |= (
                    MediaPlayerEntityFeature.PAUSE
                    | MediaPlayerEntityFeature.PLAY
                    | MediaPlayerEntityFeature.STOP
                )
        except KeyError:
            pass

        return ret

    @property
    def state(self) -> str:
        """State of the player."""
        if not self._data:
            return STATE_OFF

        if not ("NowPlayingItem" in self._data):
            return STATE_IDLE

        if self._data["PlayState"]["IsPaused"]:
            return STATE_PAUSED

        return STATE_PLAYING

    @property  # type: ignore[misc]
    @needs_data
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return bool(self._data["PlayState"]["IsMuted"])

    @property  # type: ignore[misc]
    @needs_data
    def media_episode(self) -> str | None:
        """Episode of current playing media, TV show only."""
        return str(self._data["NowPlayingItem"]["IndexNumber"])

    @property  # type: ignore[misc]
    @needs_data
    def media_season(self) -> str | None:
        """Season of current playing media, TV show only."""
        return str(self._data["NowPlayingItem"]["ParentIndexNumber"])

    @property  # type: ignore[misc]
    @needs_data
    def media_series_title(self) -> str | None:
        """Title of series of current playing media, TV show only."""
        return str(self._data["NowPlayingItem"]["SeriesName"])

    @property  # type: ignore[misc]
    @needs_data
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return str(self._data["NowPlayingItem"]["Name"])

    @property  # type: ignore[misc]
    @needs_data
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return int(self._data["PlayState"]["PositionTicks"] / 10000000)

    @property  # type: ignore[misc]
    @needs_data
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return int(self._data["NowPlayingItem"]["RunTimeTicks"] / 10000000)

    @property  # type: ignore[misc]
    @needs_data
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        return str(self._data["NowPlayingItem"]["Id"])

    @property  # type: ignore[misc]
    @needs_data
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return float(self._data["PlayState"]["VolumeLevel"] / 100)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return bool(self._data)

    def media_seek(self, position: int) -> None:
        """Send seek command."""
        self._client.jellyfin.remote_seek(self._id, int(position * 10000000))

    def media_pause(self) -> None:
        """Send pause command."""
        self._client.jellyfin.remote_pause(self._id)

    def media_play(self) -> None:
        """Send play command."""
        self._client.jellyfin.remote_unpause(self._id)

    def media_play_pause(self) -> None:
        """Send the PlayPause command to the session."""
        self._client.jellyfin.remote_playpause(self._id)

    def media_stop(self) -> None:
        """Send stop command."""
        self._client.jellyfin.remote_stop(self._id)

    def play_media(
        self, media_type: str, media_id: str, **kwargs: dict[str, Any]
    ) -> None:
        """Play a piece of media."""
        self._client.jellyfin.remote_play_media(self._id, [media_id])

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._client.jellyfin.remote_set_volume(self._id, int(volume * 100))

    def mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if mute:
            self._client.jellyfin.remote_mute(self._id)
        else:
            self._client.jellyfin.remote_unmute(self._id)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return a device description for device registry."""

        if not self._data["Capabilities"]["SupportsPersistentIdentifier"]:
            return DeviceInfo(
                identifiers={(DOMAIN, "Jellyfin-clients")},
                name="Jellyfin Client Service",
                manufacturer="Jellyfin",
                model="Jellyfin Clients",
                entry_type=DeviceEntryType.SERVICE,
            )

        return DeviceInfo(
            identifiers={(DOMAIN, self._data["DeviceId"])},
            manufacturer="Jellyfin",
            model=self._data["Client"],
            name=self.name,
            sw_version=self._data["ApplicationVersion"],
            via_device=(DOMAIN, self._data["ServerId"]),
        )

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Return a BrowseMedia instance.

        The BrowseMedia instance will be used by the "media_player/browse_media" websocket command.

        """

        def browse_media_from_item(media: Any) -> BrowseMedia:
            return BrowseMedia(
                title=media["Name"],
                media_content_id=media["Id"],
                media_content_type=CONTENT_TYPE_MAP.get(media["Type"], MEDIA_TYPE_NONE),
                media_class=MEDIA_CLASS_MAP.get(media["Type"], MEDIA_CLASS_DIRECTORY),
                can_play=True,
                can_expand=media["Type"] not in EXPANDABLE_TYPES,
                children_media_class="",
                thumbnail=str(
                    self._client.jellyfin.artwork(media["Id"], "Primary", 500)
                ),
                children=[],
            )

        async def create_item_children(
            hass: HomeAssistant, client: JellyfinClient, user: str, itemid: str
        ) -> list[BrowseMedia]:
            children = await hass.async_add_executor_job(
                lambda: dict(
                    client.jellyfin.items(params={"parentId": itemid, "userId": user})
                )
            )

            return [browse_media_from_item(item) for item in children["Items"]]

        async def create_item_response(
            hass: HomeAssistant, client: JellyfinClient, user: str, itemid: str
        ) -> BrowseMedia:
            items = await hass.async_add_executor_job(
                lambda: dict(
                    client.jellyfin.items(params={"ids": [itemid], "userId": user})
                )
            )

            if not items or "Items" not in items or len(items["Items"]) < 1:
                raise NotFoundErr()

            return browse_media_from_item(items["Items"][0])

        async def create_root_response(
            hass: HomeAssistant, client: JellyfinClient, user: str
        ) -> BrowseMedia:
            folders = await hass.async_add_executor_job(
                client.jellyfin.get_media_folders
            )

            children = [
                await create_item_response(hass, client, user, folder["Id"])
                for folder in folders["Items"]
                if folder["CollectionType"] in SUPPORTED_LIBRARY_TYPES
            ]

            ret = BrowseMedia(
                media_content_id="root",
                media_content_type="server",
                media_class=MEDIA_CLASS_DIRECTORY,
                children_media_class=MEDIA_CLASS_DIRECTORY,
                title="Jellyfin",
                can_play=False,
                can_expand=True,
                children=children,
            )

            return ret

        async def create_single_response(
            hass: HomeAssistant, client: JellyfinClient, user: str, itemid: str
        ) -> BrowseMedia:
            item = await create_item_response(hass, client, user, itemid)
            item.children = await create_item_children(hass, client, user, itemid)

            return item

        # media_content_id will be none, when HA asks for toplevel info
        # we give our toplevel object which houses that info the id root.
        # When HA browses via Media tab, the toplevel is called media-source://jellyfin
        if (
            media_content_id is None
            or media_content_id == "root"
            or media_content_id == "media-source://jellyfin"
        ):
            _LOGGER.debug("Creating root instance in browse_media")
            return await create_root_response(
                self.hass, self._client, self.coordinator.user["Id"]
            )

        _LOGGER.debug(  # pylint: disable=logging-not-lazy
            "Creating item instance in browse_media for %s" % media_content_id
        )
        return await create_single_response(
            self._hass, self._client, self.coordinator.user["Id"], media_content_id
        )
