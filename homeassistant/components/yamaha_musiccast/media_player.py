"""Implementation of the musiccast media player."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from aiomusiccast import MusicCastGroupException, MusicCastMediaContent
from aiomusiccast.features import ZoneFeature

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import uuid

from . import MusicCastDataUpdateCoordinator, MusicCastDeviceEntity
from .const import (
    ATTR_MAIN_SYNC,
    ATTR_MC_LINK,
    DEFAULT_ZONE,
    DOMAIN,
    HA_REPEAT_MODE_TO_MC_MAPPING,
    MC_REPEAT_MODE_TO_HA_MAPPING,
    MEDIA_CLASS_MAPPING,
    NULL_GROUP,
)

_LOGGER = logging.getLogger(__name__)

MUSIC_PLAYER_BASE_SUPPORT = (
    MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.GROUPING
    | MediaPlayerEntityFeature.PLAY_MEDIA
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MusicCast sensor based on a config entry."""
    coordinator: MusicCastDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    name = coordinator.data.network_name

    media_players: list[Entity] = []

    for zone in coordinator.data.zones:
        zone_name = name if zone == DEFAULT_ZONE else f"{name} {zone}"

        media_players.append(
            MusicCastMediaPlayer(zone, zone_name, entry.entry_id, coordinator)
        )

    async_add_entities(media_players)


class MusicCastMediaPlayer(MusicCastDeviceEntity, MediaPlayerEntity):
    """The musiccast media player."""

    _attr_media_content_type = MediaType.MUSIC
    _attr_should_poll = False

    def __init__(self, zone_id, name, entry_id, coordinator):
        """Initialize the musiccast device."""
        self._player_state = MediaPlayerState.PLAYING
        self._volume_muted = False
        self._shuffle = False
        self._zone_id = zone_id

        super().__init__(
            name=name,
            icon="mdi:speaker",
            coordinator=coordinator,
        )

        self._volume_min = self.coordinator.data.zones[self._zone_id].min_volume
        self._volume_max = self.coordinator.data.zones[self._zone_id].max_volume

        self._cur_track = 0
        self._repeat = RepeatMode.OFF

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        self.coordinator.entities.append(self)
        # Sensors should also register callbacks to HA when their state changes
        self.coordinator.musiccast.register_group_update_callback(
            self.update_all_mc_entities
        )
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_schedule_check_client_list)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        await super().async_will_remove_from_hass()
        self.coordinator.entities.remove(self)
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.coordinator.musiccast.remove_group_update_callback(
            self.update_all_mc_entities
        )

    @property
    def ip_address(self):
        """Return the ip address of the musiccast device."""
        return self.coordinator.musiccast.ip

    @property
    def zone_id(self):
        """Return the zone id of the musiccast device."""
        return self._zone_id

    @property
    def _is_netusb(self):
        return self.coordinator.data.netusb_input == self.source_id

    @property
    def _is_tuner(self):
        return self.source_id == "tuner"

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return None

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the player."""
        if self.coordinator.data.zones[self._zone_id].power == "on":
            if self._is_netusb and self.coordinator.data.netusb_playback == "pause":
                return MediaPlayerState.PAUSED
            if self._is_netusb and self.coordinator.data.netusb_playback == "stop":
                return MediaPlayerState.IDLE
            return MediaPlayerState.PLAYING
        return MediaPlayerState.OFF

    @property
    def source_mapping(self):
        """Return a mapping of the actual source names to their labels configured in the MusicCast App."""
        ret = {}
        for inp in self.coordinator.data.zones[self._zone_id].input_list:
            label = self.coordinator.data.input_names.get(inp, "")
            if inp != label and (
                label in self.coordinator.data.zones[self._zone_id].input_list
                or list(self.coordinator.data.input_names.values()).count(label) > 1
            ):
                label += f" ({inp})"
            if label == "":
                label = inp
            ret[inp] = label
        return ret

    @property
    def reverse_source_mapping(self):
        """Return a mapping from the source label to the source name."""
        return {v: k for k, v in self.source_mapping.items()}

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        if ZoneFeature.VOLUME in self.coordinator.data.zones[self._zone_id].features:
            volume = self.coordinator.data.zones[self._zone_id].current_volume
            return (volume - self._volume_min) / (self._volume_max - self._volume_min)
        return None

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        if ZoneFeature.VOLUME in self.coordinator.data.zones[self._zone_id].features:
            return self.coordinator.data.zones[self._zone_id].mute
        return None

    @property
    def shuffle(self):
        """Boolean if shuffling is enabled."""
        return (
            self.coordinator.data.netusb_shuffle == "on" if self._is_netusb else False
        )

    @property
    def sound_mode(self):
        """Return the current sound mode."""
        return self.coordinator.data.zones[self._zone_id].sound_program

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return self.coordinator.data.zones[self._zone_id].sound_program_list

    @property
    def zone(self):
        """Return the zone of the media player."""
        return self._zone_id

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this media_player."""
        return f"{self.coordinator.data.device_id}_{self._zone_id}"

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self.coordinator.musiccast.turn_on(self._zone_id)
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self.coordinator.musiccast.turn_off(self._zone_id)
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""

        await self.coordinator.musiccast.mute_volume(self._zone_id, mute)
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level, range 0..1."""
        await self.coordinator.musiccast.set_volume_level(self._zone_id, volume)
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        await self.coordinator.musiccast.volume_up(self._zone_id)

    async def async_volume_down(self) -> None:
        """Turn volume down for media player."""
        await self.coordinator.musiccast.volume_down(self._zone_id)

    async def async_media_play(self) -> None:
        """Send play command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_play()
        else:
            raise HomeAssistantError(
                "Service play is not supported for non NetUSB sources."
            )

    async def async_media_pause(self) -> None:
        """Send pause command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_pause()
        else:
            raise HomeAssistantError(
                "Service pause is not supported for non NetUSB sources."
            )

    async def async_media_stop(self) -> None:
        """Send stop command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_stop()
        else:
            raise HomeAssistantError(
                "Service stop is not supported for non NetUSB sources."
            )

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_shuffle(shuffle)
        else:
            raise HomeAssistantError(
                "Service shuffle is not supported for non NetUSB sources."
            )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media."""
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

        if self.state == MediaPlayerState.OFF:
            await self.async_turn_on()

        if media_id:
            parts = media_id.split(":")

            if parts[0] == "list":
                if (index := parts[3]) == "-1":
                    index = "0"

                await self.coordinator.musiccast.play_list_media(index, self._zone_id)
                return

            if parts[0] == "presets":
                index = parts[1]
                await self.coordinator.musiccast.recall_netusb_preset(
                    self._zone_id, index
                )
                return

            if parts[0] in ("http", "https") or media_id.startswith("/"):
                media_id = async_process_play_media_url(self.hass, media_id)

                await self.coordinator.musiccast.play_url_media(
                    self._zone_id, media_id, "HomeAssistant"
                )
                return

        raise HomeAssistantError(
            "Only presets, media from media browser and http URLs are supported"
        )

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        if media_content_id and media_source.is_media_source_id(media_content_id):
            return await media_source.async_browse_media(
                self.hass,
                media_content_id,
                content_filter=lambda item: item.media_content_type.startswith(
                    "audio/"
                ),
            )

        if self.state == MediaPlayerState.OFF:
            raise HomeAssistantError(
                "The device has to be turned on to be able to browse media."
            )

        if media_content_id:
            media_content_path = media_content_id.split(":")
            media_content_provider = await MusicCastMediaContent.browse_media(
                self.coordinator.musiccast, self._zone_id, media_content_path, 24
            )
            add_media_source = False

        else:
            media_content_provider = MusicCastMediaContent.categories(
                self.coordinator.musiccast, self._zone_id
            )
            add_media_source = True

        def get_content_type(item):
            if item.can_play:
                return MediaClass.TRACK
            return MediaClass.DIRECTORY

        children = [
            BrowseMedia(
                title=child.title,
                media_class=MEDIA_CLASS_MAPPING.get(child.content_type),
                media_content_id=child.content_id,
                media_content_type=get_content_type(child),
                can_play=child.can_play,
                can_expand=child.can_browse,
                thumbnail=child.thumbnail,
            )
            for child in media_content_provider.children
        ]

        if add_media_source:
            with contextlib.suppress(media_source.BrowseError):
                item = await media_source.async_browse_media(
                    self.hass,
                    None,
                    content_filter=lambda item: item.media_content_type.startswith(
                        "audio/"
                    ),
                )
                # If domain is None, it's overview of available sources
                if item.domain is None:
                    children.extend(item.children)
                else:
                    children.append(item)

        return BrowseMedia(
            title=media_content_provider.title,
            media_class=MEDIA_CLASS_MAPPING.get(media_content_provider.content_type),
            media_content_id=media_content_provider.content_id,
            media_content_type=get_content_type(media_content_provider),
            can_play=False,
            can_expand=media_content_provider.can_browse,
            children=children,
        )

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        await self.coordinator.musiccast.select_sound_mode(self._zone_id, sound_mode)

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        if self.is_client and self.group_server != self:
            return self.group_server.coordinator.musiccast.media_image_url
        return self.coordinator.musiccast.media_image_url if self._is_netusb else None

    @property
    def media_title(self):
        """Return the title of current playing media."""
        if self._is_netusb:
            return self.coordinator.data.netusb_track
        if self._is_tuner:
            return self.coordinator.musiccast.tuner_media_title

        return None

    @property
    def media_artist(self):
        """Return the artist of current playing media (Music track only)."""
        if self._is_netusb:
            return self.coordinator.data.netusb_artist
        if self._is_tuner:
            return self.coordinator.musiccast.tuner_media_artist

        return None

    @property
    def media_album_name(self):
        """Return the album of current playing media (Music track only)."""
        return self.coordinator.data.netusb_album if self._is_netusb else None

    @property
    def repeat(self):
        """Return current repeat mode."""
        return (
            MC_REPEAT_MODE_TO_HA_MAPPING.get(self.coordinator.data.netusb_repeat)
            if self._is_netusb
            else RepeatMode.OFF
        )

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        supported_features = MUSIC_PLAYER_BASE_SUPPORT
        zone = self.coordinator.data.zones[self._zone_id]

        if ZoneFeature.POWER in zone.features:
            supported_features |= (
                MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
            )
        if ZoneFeature.VOLUME in zone.features:
            supported_features |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if ZoneFeature.MUTE in zone.features:
            supported_features |= MediaPlayerEntityFeature.VOLUME_MUTE

        if self._is_netusb or self._is_tuner:
            supported_features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
            supported_features |= MediaPlayerEntityFeature.NEXT_TRACK

        if self._is_netusb:
            supported_features |= MediaPlayerEntityFeature.PAUSE
            supported_features |= MediaPlayerEntityFeature.PLAY
            supported_features |= MediaPlayerEntityFeature.STOP

        if self.state != MediaPlayerState.OFF:
            supported_features |= MediaPlayerEntityFeature.BROWSE_MEDIA

        return supported_features

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_previous_track()
        elif self._is_tuner:
            await self.coordinator.musiccast.tuner_previous_station()
        else:
            raise HomeAssistantError(
                "Service previous track is not supported for non NetUSB or Tuner"
                " sources."
            )

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_next_track()
        elif self._is_tuner:
            await self.coordinator.musiccast.tuner_next_station()
        else:
            raise HomeAssistantError(
                "Service next track is not supported for non NetUSB or Tuner sources."
            )

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Enable/disable repeat mode."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_repeat(
                HA_REPEAT_MODE_TO_MC_MAPPING.get(repeat, "off")
            )
        else:
            raise HomeAssistantError(
                "Service set repeat is not supported for non NetUSB sources."
            )

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.coordinator.musiccast.select_source(
            self._zone_id, self.reverse_source_mapping.get(source, source)
        )

    @property
    def source_id(self):
        """ID of the current input source."""
        return self.coordinator.data.zones[self._zone_id].input

    @property
    def source(self):
        """Name of the current input source."""
        return self.source_mapping.get(self.source_id)

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self.source_mapping.values())

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self._is_netusb:
            return self.coordinator.data.netusb_total_time

        return None

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._is_netusb:
            return self.coordinator.data.netusb_play_time

        return None

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        if self._is_netusb:
            return self.coordinator.data.netusb_play_time_updated

        return None

    # Group and MusicCast System specific functions/properties

    @property
    def is_network_server(self) -> bool:
        """Return only true if the current entity is a network server and not a main zone with an attached zone2."""
        return (
            self.coordinator.data.group_role == "server"
            and self.coordinator.data.group_id != NULL_GROUP
            and self._zone_id == self.coordinator.data.group_server_zone
        )

    @property
    def other_zones(self) -> list[MusicCastMediaPlayer]:
        """Return media player entities of the other zones of this device."""
        return [
            entity
            for entity in self.coordinator.entities
            if entity != self and isinstance(entity, MusicCastMediaPlayer)
        ]

    @property
    def is_server(self) -> bool:
        """Return whether the media player is the server/host of the group.

        If the media player is not part of a group, False is returned.
        """
        return self.is_network_server or (
            self._zone_id == DEFAULT_ZONE
            and len(
                [
                    entity
                    for entity in self.other_zones
                    if entity.source == ATTR_MAIN_SYNC
                ]
            )
            > 0
        )

    @property
    def is_network_client(self) -> bool:
        """Return True if the current entity is a network client and not just a main syncing entity."""
        return (
            self.coordinator.data.group_role == "client"
            and self.coordinator.data.group_id != NULL_GROUP
            and self.source_id == ATTR_MC_LINK
        )

    @property
    def is_client(self) -> bool:
        """Return whether the media player is the client of a group.

        If the media player is not part of a group, False is returned.
        """
        return self.is_network_client or self.source_id == ATTR_MAIN_SYNC

    def get_all_mc_entities(self) -> list[MusicCastMediaPlayer]:
        """Return all media player entities of the musiccast system."""
        entities = []
        for coordinator in self.hass.data[DOMAIN].values():
            entities += [
                entity
                for entity in coordinator.entities
                if isinstance(entity, MusicCastMediaPlayer)
            ]
        return entities

    def get_all_server_entities(self) -> list[MusicCastMediaPlayer]:
        """Return all media player entities in the musiccast system, which are in server mode."""
        entities = self.get_all_mc_entities()
        return [entity for entity in entities if entity.is_server]

    def get_distribution_num(self) -> int:
        """Return the distribution_num (number of clients in the whole musiccast system)."""
        return sum(
            len(server.coordinator.data.group_client_list)
            for server in self.get_all_server_entities()
        )

    def is_part_of_group(self, group_server) -> bool:
        """Return True if the given server is the server of self's group."""
        return group_server != self and (
            (
                self.ip_address in group_server.coordinator.data.group_client_list
                and self.coordinator.data.group_id
                == group_server.coordinator.data.group_id
                and self.ip_address != group_server.ip_address
                and self.source_id == ATTR_MC_LINK
            )
            or (
                self.ip_address == group_server.ip_address
                and self.source_id == ATTR_MAIN_SYNC
            )
        )

    @property
    def group_server(self):
        """Return the server of the own group if present, self else."""
        for entity in self.get_all_server_entities():
            if self.is_part_of_group(entity):
                return entity
        return self

    @property
    def group_members(self) -> list[str] | None:
        """Return a list of entity_ids, which belong to the group of self."""
        return [entity.entity_id for entity in self.musiccast_group]

    @property
    def musiccast_group(self) -> list[MusicCastMediaPlayer]:
        """Return all media players of the current group, if the media player is server."""
        if self.is_client:
            # If we are a client we can still share group information, but we will take them from the server.
            if (server := self.group_server) != self:
                return server.musiccast_group

            return [self]
        if not self.is_server:
            return [self]
        entities = self.get_all_mc_entities()
        clients = [entity for entity in entities if entity.is_part_of_group(self)]
        return [self, *clients]

    @property
    def musiccast_zone_entity(self) -> MusicCastMediaPlayer:
        """Return the entity of the zone, which is using MusicCast at the moment, if there is one, self else.

        It is possible that multiple zones use MusicCast as client at the same time. In this case the first one is
        returned.
        """
        for entity in self.other_zones:
            if entity.is_network_server or entity.is_network_client:
                return entity

        return self

    async def update_all_mc_entities(self, check_clients=False):
        """Update the whole musiccast system when group data change."""
        # First update all servers as they provide the group information for their clients
        for entity in self.get_all_server_entities():
            if check_clients or self.coordinator.musiccast.group_reduce_by_source:
                await entity.async_check_client_list()
            else:
                entity.async_write_ha_state()
        # Then update all other entities
        for entity in self.get_all_mc_entities():
            if not entity.is_server:
                entity.async_write_ha_state()

    # Services

    async def async_join_players(self, group_members: list[str]) -> None:
        """Add all clients given in entities to the group of the server.

        Creates a new group if necessary. Used for join service.
        """
        _LOGGER.debug(
            "%s wants to add the following entities %s",
            self.entity_id,
            str(group_members),
        )

        entities = [
            entity
            for entity in self.get_all_mc_entities()
            if entity.entity_id in group_members
        ]

        if self.state == MediaPlayerState.OFF:
            await self.async_turn_on()

        if not self.is_server and self.musiccast_zone_entity.is_server:
            # The MusicCast Distribution Module of this device is already in use. To use it as a server, we first
            # have to unjoin and wait until the servers are updated.
            await self.musiccast_zone_entity.async_server_close_group()
        elif self.musiccast_zone_entity.is_client:
            await self.async_client_leave_group(True)
        # Use existing group id if we are server, generate a new one else.
        group = (
            self.coordinator.data.group_id
            if self.is_server
            else uuid.random_uuid_hex().upper()
        )

        ip_addresses = set()
        # First let the clients join
        for client in entities:
            if client != self:
                try:
                    network_join = await client.async_client_join(group, self)
                except MusicCastGroupException:
                    _LOGGER.warning(
                        (
                            "%s is struggling to update its group data. Will retry"
                            " perform the update"
                        ),
                        client.entity_id,
                    )
                    network_join = await client.async_client_join(group, self)

                if network_join:
                    ip_addresses.add(client.ip_address)

        if ip_addresses:
            await self.coordinator.musiccast.mc_server_group_extend(
                self._zone_id,
                list(ip_addresses),
                group,
                self.get_distribution_num(),
            )
        _LOGGER.debug(
            "%s added the following entities %s", self.entity_id, str(entities)
        )
        _LOGGER.debug(
            "%s has now the following musiccast group %s",
            self.entity_id,
            str(self.musiccast_group),
        )

        await self.update_all_mc_entities(True)

    async def async_unjoin_player(self) -> None:
        """Leave the group.

        Stops the distribution if device is server. Used for unjoin service.
        """
        _LOGGER.debug("%s called service unjoin", self.entity_id)
        if self.is_server:
            await self.async_server_close_group()

        else:
            await self.async_client_leave_group()

        await self.update_all_mc_entities(True)

    # Internal client functions

    async def async_client_join(self, group_id, server) -> bool:
        """Let the client join a group.

        If this client is a server, the server will stop distributing.
        If the client is part of a different group,
        it will leave that group first. Returns True, if the server has to
        add the client on his side.
        """
        # If we should join the group, which is served by the main zone,
        # we can simply select main_sync as input.
        _LOGGER.debug("%s called service client join", self.entity_id)
        if self.state == MediaPlayerState.OFF:
            await self.async_turn_on()
        if self.ip_address == server.ip_address:
            if server.zone == DEFAULT_ZONE:
                await self.async_select_source(ATTR_MAIN_SYNC)
                server.async_write_ha_state()
                return False

            # It is not possible to join a group hosted by zone2 from main zone.
            raise HomeAssistantError(
                "Can not join a zone other than main of the same device."
            )

        if self.musiccast_zone_entity.is_server:
            # If one of the zones of the device is a server, we need to unjoin first.
            _LOGGER.debug(
                (
                    "%s is a server of a group and has to stop distribution "
                    "to use MusicCast for %s"
                ),
                self.musiccast_zone_entity.entity_id,
                self.entity_id,
            )
            await self.musiccast_zone_entity.async_server_close_group()

        elif self.is_client:
            if self.is_part_of_group(server):
                _LOGGER.warning("%s is already part of the group", self.entity_id)
                return False

            _LOGGER.debug(
                "%s is client in a different group, will unjoin first",
                self.entity_id,
            )
            await self.async_client_leave_group()

        elif (
            self.ip_address in server.coordinator.data.group_client_list
            and self.coordinator.data.group_id == server.coordinator.data.group_id
            and self.coordinator.data.group_role == "client"
        ):
            # The device is already part of this group (e.g. main zone is also a client of this group).
            # Just select mc_link as source
            await self.coordinator.musiccast.zone_join(self._zone_id)
            return False

        _LOGGER.debug("%s will now join as a client", self.entity_id)
        await self.coordinator.musiccast.mc_client_join(
            server.ip_address, group_id, self._zone_id
        )
        return True

    async def async_client_leave_group(self, force=False):
        """Make self leave the group.

        Should only be called for clients.
        """
        _LOGGER.debug("%s client leave called", self.entity_id)
        if not force and (
            self.source_id == ATTR_MAIN_SYNC
            or [
                entity
                for entity in self.other_zones
                if entity.source_id == ATTR_MC_LINK
            ]
        ):
            await self.coordinator.musiccast.zone_unjoin(self._zone_id)
        else:
            servers = [
                server
                for server in self.get_all_server_entities()
                if server.coordinator.data.group_id == self.coordinator.data.group_id
            ]
            await self.coordinator.musiccast.mc_client_unjoin()
            if servers:
                await servers[0].coordinator.musiccast.mc_server_group_reduce(
                    servers[0].zone_id, [self.ip_address], self.get_distribution_num()
                )

    # Internal server functions

    async def async_server_close_group(self):
        """Close group of self.

        Should only be called for servers.
        """
        _LOGGER.debug("%s closes his group", self.entity_id)
        for client in self.musiccast_group:
            if client != self:
                await client.async_client_leave_group()
        await self.coordinator.musiccast.mc_server_group_close()

    async def async_check_client_list(self):
        """Let the server check if all its clients are still part of his group."""
        if not self.is_server or self.coordinator.data.group_update_lock.locked():
            return

        _LOGGER.debug("%s updates his group members", self.entity_id)
        client_ips_for_removal = [
            expected_client_ip
            for expected_client_ip in self.coordinator.data.group_client_list
            # The client is no longer part of the group. Prepare removal.
            if expected_client_ip
            not in [entity.ip_address for entity in self.musiccast_group]
        ]

        if client_ips_for_removal:
            _LOGGER.debug(
                "%s says good bye to the following members %s",
                self.entity_id,
                str(client_ips_for_removal),
            )
            await self.coordinator.musiccast.mc_server_group_reduce(
                self._zone_id, client_ips_for_removal, self.get_distribution_num()
            )
        if len(self.musiccast_group) < 2:
            # The group is empty, stop distribution.
            await self.async_server_close_group()

        self.async_write_ha_state()

    @callback
    def async_schedule_check_client_list(self):
        """Schedule async_check_client_list."""
        self.hass.async_create_task(self.async_check_client_list(), eager_start=True)
