"""Implementation of the musiccast media player."""
from __future__ import annotations

import logging

from aiomusiccast import MusicCastGroupException
from aiomusiccast.features import ZoneFeature
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    REPEAT_MODE_OFF,
    SUPPORT_GROUPING,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.util import uuid

from . import MusicCastDataUpdateCoordinator, MusicCastDeviceEntity
from .const import (
    ATTR_MAIN_SYNC,
    ATTR_MC_LINK,
    DEFAULT_ZONE,
    DOMAIN,
    HA_REPEAT_MODE_TO_MC_MAPPING,
    INTERVAL_SECONDS,
    MC_REPEAT_MODE_TO_HA_MAPPING,
    NULL_GROUP,
)

_LOGGER = logging.getLogger(__name__)

MUSIC_PLAYER_BASE_SUPPORT = (
    SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_REPEAT_SET
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_STOP
    | SUPPORT_GROUPING
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=5000): cv.port,
        vol.Optional(INTERVAL_SECONDS, default=0): cv.positive_int,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config,
    async_add_devices: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import legacy configurations."""

    if hass.config_entries.async_entries(DOMAIN) and config[CONF_HOST] not in [
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    ]:
        _LOGGER.error(
            "Configuration in configuration.yaml is not supported anymore. "
            "Please add this device using the config flow: %s",
            config[CONF_HOST],
        )
    else:
        _LOGGER.warning(
            "Configuration in configuration.yaml is deprecated. Use the config flow instead"
        )

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config
            )
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

    def __init__(self, zone_id, name, entry_id, coordinator):
        """Initialize the musiccast device."""
        self._player_state = STATE_PLAYING
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
        self._repeat = REPEAT_MODE_OFF

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        self.coordinator.entities.append(self)
        # Sensors should also register callbacks to HA when their state changes
        self.coordinator.musiccast.register_callback(self.async_write_ha_state)
        self.coordinator.musiccast.register_group_update_callback(
            self.update_all_mc_entities
        )
        self.coordinator.async_add_listener(self.async_schedule_check_client_list)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        await super().async_will_remove_from_hass()
        self.coordinator.entities.remove(self)
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.coordinator.musiccast.remove_callback(self.async_write_ha_state)
        self.coordinator.musiccast.remove_group_update_callback(
            self.update_all_mc_entities
        )
        self.coordinator.async_remove_listener(self.async_schedule_check_client_list)

    @property
    def should_poll(self):
        """Push an update after each command."""
        return False

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
        return (
            self.coordinator.data.netusb_input
            == self.coordinator.data.zones[self._zone_id].input
        )

    @property
    def _is_tuner(self):
        return self.coordinator.data.zones[self._zone_id].input == "tuner"

    @property
    def state(self):
        """Return the state of the player."""
        if self.coordinator.data.zones[self._zone_id].power == "on":
            if self._is_netusb and self.coordinator.data.netusb_playback == "pause":
                return STATE_PAUSED
            if self._is_netusb and self.coordinator.data.netusb_playback == "stop":
                return STATE_IDLE
            return STATE_PLAYING
        return STATE_OFF

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

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.coordinator.musiccast.turn_on(self._zone_id)
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn the media player off."""
        await self.coordinator.musiccast.turn_off(self._zone_id)
        self.async_write_ha_state()

    async def async_mute_volume(self, mute):
        """Mute the volume."""

        await self.coordinator.musiccast.mute_volume(self._zone_id, mute)
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume):
        """Set the volume level, range 0..1."""
        await self.coordinator.musiccast.set_volume_level(self._zone_id, volume)
        self.async_write_ha_state()

    async def async_media_play(self):
        """Send play command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_play()
        else:
            raise HomeAssistantError(
                "Service play is not supported for non NetUSB sources."
            )

    async def async_media_pause(self):
        """Send pause command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_pause()
        else:
            raise HomeAssistantError(
                "Service pause is not supported for non NetUSB sources."
            )

    async def async_media_stop(self):
        """Send stop command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_pause()
        else:
            raise HomeAssistantError(
                "Service stop is not supported for non NetUSB sources."
            )

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_shuffle(shuffle)
        else:
            raise HomeAssistantError(
                "Service shuffle is not supported for non NetUSB sources."
            )

    async def async_select_sound_mode(self, sound_mode):
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
            else REPEAT_MODE_OFF
        )

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        supported_features = MUSIC_PLAYER_BASE_SUPPORT
        zone = self.coordinator.data.zones[self._zone_id]

        if ZoneFeature.POWER in zone.features:
            supported_features |= SUPPORT_TURN_ON | SUPPORT_TURN_OFF
        if ZoneFeature.VOLUME in zone.features:
            supported_features |= SUPPORT_VOLUME_SET
        if ZoneFeature.MUTE in zone.features:
            supported_features |= SUPPORT_VOLUME_MUTE

        return supported_features

    async def async_media_previous_track(self):
        """Send previous track command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_previous_track()
        elif self._is_tuner:
            await self.coordinator.musiccast.tuner_previous_station()
        else:
            raise HomeAssistantError(
                "Service previous track is not supported for non NetUSB or Tuner sources."
            )

    async def async_media_next_track(self):
        """Send next track command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_next_track()
        elif self._is_tuner:
            await self.coordinator.musiccast.tuner_next_station()
        else:
            raise HomeAssistantError(
                "Service next track is not supported for non NetUSB or Tuner sources."
            )

    async def async_set_repeat(self, repeat):
        """Enable/disable repeat mode."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_repeat(
                HA_REPEAT_MODE_TO_MC_MAPPING.get(repeat, "off")
            )
        else:
            raise HomeAssistantError(
                "Service set repeat is not supported for non NetUSB sources."
            )

    async def async_select_source(self, source):
        """Select input source."""
        await self.coordinator.musiccast.select_source(self._zone_id, source)

    @property
    def source(self):
        """Name of the current input source."""
        return self.coordinator.data.zones[self._zone_id].input

    @property
    def source_list(self):
        """List of available input sources."""
        return self.coordinator.data.zones[self._zone_id].input_list

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
            and self.source == ATTR_MC_LINK
        )

    @property
    def is_client(self) -> bool:
        """Return whether the media player is the client of a group.

        If the media player is not part of a group, False is returned.
        """
        return self.is_network_client or self.source == ATTR_MAIN_SYNC

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
                and self.source == ATTR_MC_LINK
            )
            or (
                self.ip_address == group_server.ip_address
                and self.source == ATTR_MAIN_SYNC
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
            server = self.group_server
            if server != self:
                return server.musiccast_group

            return [self]
        if not self.is_server:
            return [self]
        entities = self.get_all_mc_entities()
        clients = [entity for entity in entities if entity.is_part_of_group(self)]
        return [self] + clients

    @property
    def musiccast_zone_entity(self) -> MusicCastMediaPlayer:
        """Return the the entity of the zone, which is using MusicCast at the moment, if there is one, self else.

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

    async def async_join_players(self, group_members):
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

        if self.state == STATE_OFF:
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
                        "%s is struggling to update its group data. Will retry perform the update",
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

    async def async_unjoin_player(self):
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

        If this client is a server, the server will stop distributing. If the client is part of a different group,
        it will leave that group first. Returns True, if the server has to add the client on his side.
        """
        # If we should join the group, which is served by the main zone, we can simply select main_sync as input.
        _LOGGER.debug("%s called service client join", self.entity_id)
        if self.state == STATE_OFF:
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
                "%s is a server of a group and has to stop distribution "
                "to use MusicCast for %s",
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
            self.source == ATTR_MAIN_SYNC
            or [entity for entity in self.other_zones if entity.source == ATTR_MC_LINK]
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
        client_ips_for_removal = []
        for expected_client_ip in self.coordinator.data.group_client_list:
            if expected_client_ip not in [
                entity.ip_address for entity in self.musiccast_group
            ]:
                # The client is no longer part of the group. Prepare removal.
                client_ips_for_removal.append(expected_client_ip)

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
        self.hass.create_task(self.async_check_client_list())
