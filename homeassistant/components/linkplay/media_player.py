"""Support for LinkPlay media players."""

from __future__ import annotations

import logging
from typing import Any

from linkplay.bridge import LinkPlayBridge, LinkPlayMultiroom
from linkplay.consts import LoopMode, PlayingStatus
from linkplay.controller import LinkPlayController
from linkplay.exceptions import LinkPlayException

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import (
    BRIDGE_DISCOVERED,
    CONTROLLER,
    DEFAULT_FEATURES,
    DOMAIN,
    EQUALIZER_MAP,
    EQUALIZER_MAP_INV,
    REPEAT_MAP,
    REPEAT_MAP_INV,
    SEEKABLE_FEATURES,
    SOURCE_MAP,
    SOURCE_MAP_INV,
    STATE_MAP,
)
from .utils import get_active_multiroom, get_info_from_project

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a media player from a config entry."""

    @callback
    def add_entity(bridge: LinkPlayBridge):
        async_add_entities([LinkPlayMediaPlayerEntity(bridge)])

    entry.async_on_unload(async_dispatcher_connect(hass, BRIDGE_DISCOVERED, add_entity))


class LinkPlayMediaPlayerEntity(MediaPlayerEntity):
    """Representation of a LinkPlay media player."""

    _bridge: LinkPlayBridge

    def __init__(self, bridge: LinkPlayBridge) -> None:
        """Initialize the LinkPlay media player."""
        self._bridge = bridge

        self._attr_unique_id = self.entity_id = f"{DOMAIN}.{self._bridge.device.uuid}"
        self._attr_name = self._bridge.device.name
        self._attr_sound_mode_list = list(EQUALIZER_MAP.values())
        self._attr_should_poll = True
        self._attr_device_class = MediaPlayerDeviceClass.RECEIVER
        self._attr_source_list = [
            SOURCE_MAP[playing_mode]
            for playing_mode in self._bridge.device.playmode_support
        ]
        self._attr_media_content_type = MediaType.MUSIC

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return the device info."""
        manufacturer, model = get_info_from_project(
            self._bridge.device.properties["project"]
        )
        return dr.DeviceInfo(
            configuration_url=self._bridge.endpoint,
            connections={
                (dr.CONNECTION_NETWORK_MAC, self._bridge.device.properties["MAC"])
            },
            entry_type=None,
            hw_version=self._bridge.device.properties["hardware"],
            identifiers={(DOMAIN, self._bridge.device.uuid)},
            manufacturer=manufacturer,
            model=model,
            name=self._bridge.device.name,
            suggested_area=None,
            sw_version=self._bridge.device.properties["firmware"],
            via_device=(DOMAIN, DOMAIN),
        )

    @property
    def group_members(self) -> list[str]:
        """List of members which are currently grouped together."""

        multiroom = get_active_multiroom(self.hass, self._bridge)
        if multiroom is None:
            return []

        uuids = [multiroom.leader.device.uuid] + [
            follower.device.uuid for follower in multiroom.followers
        ]

        uuids.remove(self._bridge.device.uuid)

        return uuids

    async def async_update(self) -> None:
        """Update the state of the media player."""
        try:
            await self._bridge.player.update_status()
            self._update_properties()
        except LinkPlayException as e:
            _LOGGER.error(e)
            self._attr_available = False

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._bridge.player.set_play_mode(SOURCE_MAP_INV[source])

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        await self._bridge.player.set_equalizer_mode(EQUALIZER_MAP_INV[sound_mode])

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if mute:
            await self._bridge.player.mute()
        else:
            await self._bridge.player.unmute()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._bridge.player.set_volume(int(volume * 100))

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._bridge.player.pause()

    async def async_media_play(self) -> None:
        """Send play command."""
        if self._bridge.player.status == PlayingStatus.PAUSED:
            await self._bridge.player.resume()

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self._bridge.player.set_loop_mode(REPEAT_MAP_INV[repeat])

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Return a BrowseMedia instance.

        The BrowseMedia instance will be used by the
        "media_player/browse_media" websocket command.
        """
        # If your media player has no own media sources to browse, route all browse commands
        # to the media source integration.
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            # This allows filtering content. In this case it will only show audio sources.
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        ab = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
        await self._bridge.player.play(ab.url)

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        controller: LinkPlayController = self.hass.data[DOMAIN][CONTROLLER]
        multiroom = get_active_multiroom(self.hass, self._bridge)
        if multiroom is None:
            multiroom = LinkPlayMultiroom(self._bridge)

        for group_member in group_members:
            bridge = next(
                (
                    bridge
                    for bridge in controller.bridges
                    if bridge.device.uuid == group_member
                ),
                None,
            )
            await multiroom.add_follower(bridge)

        await controller.discover_multirooms()

    async def async_unjoin_player(self) -> None:
        """Remove this player from any group."""
        multiroom = get_active_multiroom(self.hass, self._bridge)
        if multiroom is not None:
            multiroom.remove_follower(self._bridge)

    def _update_properties(self) -> None:
        """Update the properties of the media player."""
        self._attr_available = True
        self._attr_state = STATE_MAP[self._bridge.player.status]
        self._attr_volume_level = self._bridge.player.volume / 100
        self._attr_is_volume_muted = self._bridge.player.muted
        self._attr_repeat = REPEAT_MAP[self._bridge.player.loop_mode]
        self._attr_shuffle = self._bridge.player.loop_mode == LoopMode.RANDOM_PLAYBACK
        self._attr_sound_mode = EQUALIZER_MAP[self._bridge.player.equalizer_mode]
        self._attr_supported_features = DEFAULT_FEATURES

        if self._bridge.player.status == PlayingStatus.PLAYING:
            if self._bridge.player.total_length != 0:
                self._attr_supported_features = (
                    self._attr_supported_features | SEEKABLE_FEATURES
                )

            self._attr_source = SOURCE_MAP.get(self._bridge.player.play_mode, "other")
            self._attr_media_position = self._bridge.player.current_position / 1000
            self._attr_media_position_updated_at = utcnow()
            self._attr_media_duration = self._bridge.player.total_length / 1000
            self._attr_media_artist = self._bridge.player.artist
            self._attr_media_title = self._bridge.player.title
            self._attr_media_album_name = self._bridge.player.album
        elif self._bridge.player.status == PlayingStatus.STOPPED:
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
            self._attr_media_artist = None
            self._attr_media_title = None
            self._attr_media_album_name = None
            self._attr_media_content_type = None
