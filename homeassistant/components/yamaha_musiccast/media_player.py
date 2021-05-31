"""Demo implementation of the media player."""
from typing import Callable, List

from aiomusiccast import MusicCastMediaContent
import voluptuous as vol

from homeassistant.components.media_player import BrowseMedia, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_TRACK,
    MEDIA_TYPE_MUSIC,
    REPEAT_MODE_ALL,
    REPEAT_MODE_OFF,
    REPEAT_MODE_ONE,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import uuid

from . import _LOGGER, MusicCastDataUpdateCoordinator, MusicCastDeviceEntity
from ...helpers import entity_platform
from .const import (
    ATTR_MAIN_SYNC,
    ATTR_MC_LINK,
    ATTR_MUSICCAST_GROUP,
    ATTR_SLEEP_TIME,
    DEFAULT_ZONE,
    DOMAIN,
    MEDIA_CLASS_MAPPING,
    NULL_GROUP,
    REPEAT_MODE_MAPPING,
    SERVICE_ALARM,
    SERVICE_RECALL_NETUSB_PRESET,
    SERVICE_SLEEP,
    SERVICE_STORE_NETUSB_PRESET,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up MusicCast sensor based on a config entry."""
    coordinator: MusicCastDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    name = coordinator.data.network_name

    media_players = []

    for zone in coordinator.data.zones:
        zone_name = name if zone == DEFAULT_ZONE else f"{name} {zone}"

        media_players.append(
            MusicCastMediaPlayer(zone, zone_name, entry.entry_id, coordinator)
        )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SLEEP,
        {
            vol.Optional(ATTR_SLEEP_TIME): vol.All(
                vol.Coerce(int), vol.Range(min=30, max=120)
            )
        },
        "set_sleep_timer",
    )

    platform.async_register_entity_service(
        SERVICE_ALARM,
        {
            vol.Optional("enable"): bool,
            vol.Optional("volume"): int,
            vol.Optional("alarm_time"): str,
            vol.Optional("source"): str,
        },
        "configure_alarm",
    )

    platform.async_register_entity_service(
        SERVICE_RECALL_NETUSB_PRESET,
        {
            vol.Required("preset"): int,
        },
        "recall_netusb_preset",
    )

    platform.async_register_entity_service(
        SERVICE_STORE_NETUSB_PRESET,
        {
            vol.Required("preset"): int,
        },
        "store_netusb_preset",
    )

    async_add_entities(media_players, True)


MUSIC_PLAYER_SUPPORT = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_PLAY
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_REPEAT_SET
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_STOP
    | SUPPORT_BROWSE_MEDIA
    | SUPPORT_PLAY_MEDIA
)


class MusicCastMediaPlayer(MediaPlayerEntity, MusicCastDeviceEntity):
    """A demo media players."""

    def __init__(self, zone_id, name, entry_id, coordinator, device_class=None):
        """Initialize the demo device."""
        self._name = name
        self._player_state = STATE_PLAYING
        self._volume_muted = False
        self._shuffle = False
        self._device_class = device_class
        self._zone_id = zone_id
        self.coordinator: MusicCastDataUpdateCoordinator = coordinator

        self._volume_min = self.coordinator.data.zones[self._zone_id].min_volume
        self._volume_max = self.coordinator.data.zones[self._zone_id].max_volume

        self._cur_track = 0
        self._repeat = REPEAT_MODE_OFF

        super().__init__(
            entry_id=entry_id,
            coordinator=coordinator,
            name=name,
            icon="mdi:speaker",
        )

        self.coordinator.entities.append(self)

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        # Sensors should also register callbacks to HA when their state changes
        self.coordinator.musiccast.register_callback(self.async_write_ha_state)
        self.coordinator.musiccast.register_group_update_callback(
            self.update_all_mc_entities
        )

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.coordinator.musiccast.remove_callback(self.async_write_ha_state)

    @property
    def zone_id(self):
        """Return the zone_id of the media_player."""
        return self._zone_id

    @property
    def ip_address(self):
        """Return the ip address of the musiccast device."""
        return self.coordinator.musiccast.ip

    @property
    def should_poll(self):
        """Push an update after each command."""
        return False

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
    def name(self):
        """Return the name of the media player."""
        return self._name

    @property
    def state(self):
        """Return the state of the player."""
        if self.coordinator.data.zones[self._zone_id].power == "on":
            if self._is_netusb and self.coordinator.data.netusb_playback == "pause":
                return STATE_PAUSED
            elif self._is_netusb and self.coordinator.data.netusb_playback == "stop":
                return STATE_IDLE
            return STATE_PLAYING
        return STATE_OFF

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        volume = self.coordinator.data.zones[self._zone_id].current_volume
        return (volume - self._volume_min) / (self._volume_max - self._volume_min)

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self.coordinator.data.zones[self._zone_id].mute

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
    def device_class(self):
        """Return the device class of the media player."""
        return self._device_class

    @property
    def zone(self):
        """Return the zone of the media player."""
        return self._zone_id

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this media_player."""
        macs = self.coordinator.data.mac_addresses
        return f"{macs}_{self._zone_id}"

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.coordinator.musiccast.turn_on(self._zone_id)
        self.schedule_update_ha_state()

    async def async_turn_off(self):
        """Turn the media player off."""
        await self.coordinator.musiccast.turn_off(self._zone_id)
        self.schedule_update_ha_state()

    async def async_mute_volume(self, mute):
        """Mute the volume."""

        await self.coordinator.musiccast.mute_volume(self._zone_id, mute)
        self.schedule_update_ha_state()

    async def async_set_volume_level(self, volume):
        """Set the volume level, range 0..1."""
        await self.coordinator.musiccast.set_volume_level(self._zone_id, volume)
        self.schedule_update_ha_state()

    async def async_media_play(self):
        """Send play command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_play()

    async def async_media_pause(self):
        """Send pause command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_pause()

    async def async_media_stop(self):
        """Send stop command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_pause()

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_shuffle(shuffle)

    async def async_select_sound_mode(self, sound_mode):
        """Select sound mode."""
        print(f'CHANGING TO SOUND MODE "{sound_mode}"')
        await self.coordinator.musiccast.select_sound_mode(self._zone_id, sound_mode)

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return None

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        return self.coordinator.musiccast.media_image_url if self._is_netusb else ""

    @property
    def media_title(self):
        """Return the title of current playing media."""
        if self._is_netusb:
            return self.coordinator.data.netusb_track
        elif self._is_tuner:
            return self.coordinator.musiccast.tuner_media_title

        return None

    @property
    def media_artist(self):
        """Return the artist of current playing media (Music track only)."""
        if self._is_netusb:
            return self.coordinator.data.netusb_artist
        elif self._is_tuner:
            return self.coordinator.musiccast.tuner_media_artist

        return None

    @property
    def media_album_name(self):
        """Return the album of current playing media (Music track only)."""
        return self.coordinator.data.netusb_album if self._is_netusb else None

    @property
    def media_track(self):
        """Return the track number of current media (Music track only)."""
        return -1

    @property
    def repeat(self):
        """Return current repeat mode."""
        return (
            {
                "off": REPEAT_MODE_OFF,
                "one": REPEAT_MODE_ONE,
                "all": REPEAT_MODE_ALL,
            }.get(self.coordinator.data.netusb_repeat)
            if self._is_netusb
            else REPEAT_MODE_OFF
        )

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return MUSIC_PLAYER_SUPPORT

    async def async_media_previous_track(self):
        """Send previous track command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_previous_track()
        elif self._is_tuner:
            await self.coordinator.musiccast.tuner_previous_station()

    async def async_media_next_track(self):
        """Send next track command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_next_track()
        elif self._is_tuner:
            await self.coordinator.musiccast.tuner_next_station()

    def clear_playlist(self):
        """Clear players playlist."""
        self._cur_track = 0
        self._player_state = STATE_OFF
        self.schedule_update_ha_state()

    async def async_set_repeat(self, repeat):
        """Enable/disable repeat mode."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_repeat(
                REPEAT_MODE_MAPPING.get(repeat, "off")
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

    async def async_play_media(self, media_type: str, media_id: str, **kwargs) -> None:
        """Play media."""
        if media_id:
            parts = media_id.split(":")

            if parts[0] == "list":
                index = parts[3]

                if index == "-1":
                    index = "0"

                await self.coordinator.musiccast.play_list_media(index, self._zone_id)

            elif parts[0] == "presets":
                index = parts[1]
                await self.recall_netusb_preset(index)

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""

        print(f"BROWSE MEDIA ({media_content_type} / {media_content_id})")

        media_content_provider = MusicCastMediaContent(
            self.coordinator.musiccast, self._zone_id
        )

        if media_content_id and media_content_type != "categories":
            media_content_path = media_content_id.split(":")
            media_content_provider = await MusicCastMediaContent.browse_media(
                self.coordinator.musiccast, self._zone_id, media_content_path, 24
            )

        else:
            media_content_provider = media_content_provider.categories(
                self.coordinator.musiccast, self._zone_id
            )

        children = [
            BrowseMedia(
                title=child.title,
                media_class=MEDIA_CLASS_MAPPING.get(child.content_type),
                media_content_id=child.content_id,
                media_content_type=MEDIA_CLASS_TRACK
                if child.can_play
                else MEDIA_CLASS_DIRECTORY,
                can_play=child.can_play,
                can_expand=child.can_browse,
                thumbnail=child.thumbnail,
            )
            for child in media_content_provider.children
        ]

        overview = BrowseMedia(
            title=media_content_provider.title,
            media_class=MEDIA_CLASS_MAPPING.get(media_content_provider.content_type),
            media_content_id=media_content_provider.content_id,
            media_content_type=MEDIA_CLASS_TRACK
            if media_content_provider.can_play
            else MEDIA_CLASS_DIRECTORY,
            can_play=False,
            can_expand=media_content_provider.can_browse,
            children=children,
        )

        return overview

    async def recall_netusb_preset(self, preset):
        """Play the selected preset."""
        await self.coordinator.musiccast.recall_netusb_preset(self._zone_id, preset)

    async def store_netusb_preset(self, preset):
        """Play the selected preset."""
        await self.coordinator.musiccast.store_netusb_preset(preset)

    async def set_sleep_timer(self, sleep_time=0):
        """Set sleep time."""
        if "sleep" not in self.coordinator.data.zones[self._zone_id].func_list:
            raise Exception(self.entity_id + " does not have a sleep timer.")
        await self.coordinator.musiccast.set_sleep_timer(self._zone_id, sleep_time)

    @property
    def alarm_input_list(self):
        """Return the inputs, which are available for alarm."""
        if not self.coordinator.data.has_alarm:
            return {}
        return self.coordinator.musiccast.alarm_input_list

    async def configure_alarm(
        self, enable=None, volume=None, alarm_time=None, source=""
    ):
        """Use this method to setup the alarm."""
        if not self.coordinator.data.has_alarm:
            raise Exception(self.entity_id + " does not have a alarm.")
        await self.coordinator.musiccast.configure_alarm(
            enable, volume, alarm_time, source
        )

    # Group and MusicCast System specific functions/properties

    @property
    def is_network_server(self):
        """Return only true if the current entity is a network server and not a main zone with an attached zone2."""
        return (
            self.coordinator.data.group_role == "server"
            and self.coordinator.data.group_id != NULL_GROUP
            and self._zone_id == self.coordinator.data.group_server_zone
        )

    @property
    def is_server(self):
        """Return whether the media player is the server/host of the group.

        If the media player is not part of a group, False is returned.
        """
        return self.is_network_server or (
            self._zone_id == DEFAULT_ZONE
            and len(
                [
                    entity
                    for entity in self.coordinator.entities
                    if entity.source == ATTR_MAIN_SYNC
                ]
            )
        )

    @property
    def is_network_client(self):
        """Return True if the current entity is a network client and not just a main syncing entity."""
        return (
            self.coordinator.data.group_role == "client"
            and self.coordinator.data.group_id != NULL_GROUP
            and self.source == ATTR_MC_LINK
        )

    @property
    def is_client(self):
        """Return whether the media player is the client of a group.

        If the media player is not part of a group, False is returned.
        """
        return self.is_network_client or self.source == ATTR_MAIN_SYNC

    def get_all_mc_entities(self):
        """Return all media player entities of the musiccast system."""
        entities = []
        for coordinator in self.hass.data[DOMAIN].values():
            entities += coordinator.entities
        return entities

    def get_all_server_entities(self):
        """Return all media player entities in the musiccast system, which are in server mode."""
        entities = self.get_all_mc_entities()
        return [entity for entity in entities if entity.is_server]

    def get_distribution_num(self):
        """Return the distribution_num (number of clients in the whole musiccast system)."""
        distribution_num = sum(
            [
                len(server.coordinator.data.group_client_list)
                for server in self.get_all_server_entities()
            ]
        )
        return distribution_num

    def is_part_of_group(self, group_server):
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
    def musiccast_group(self):
        """Return all media players of the current group, if the media player is server."""
        if self.is_client:
            # If we are a client we can still share group information, but we will take them from the server.
            for entity in self.get_all_server_entities():
                if self.is_part_of_group(entity):
                    return entity.musiccast_group

            return [self]
        elif not self.is_server:
            return [self]
        entities = self.get_all_mc_entities()
        clients = [entity for entity in entities if entity.is_part_of_group(self)]
        return [self] + clients

    @property
    def musiccast_zone_entity(self):
        """Return the the entity of the zone, which is using MusicCast at the moment, if there is one, self else.

        It is possible that multiple zones use MusicCast as client at the same time. In this case the first one is
        returned.
        """
        for entity in self.coordinator.entities:
            if entity.is_network_server or entity.is_network_client:
                return entity

        return self

    async def update_all_mc_entities(self):
        """Update the whole musiccast system when group data change."""
        for entity in self.get_all_mc_entities():
            entity.async_write_ha_state()

    # Services and state attributes

    async def async_server_join(self, entities):
        """Add all clients given in entities to the group of the server.

        Creates a new group if necessary. Used for join service.
        """
        _LOGGER.info(
            self.entity_id + " wants to add the following entities " + str(entities)
        )
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
        # First let the clients join
        for client in entities:
            if client != self:
                await client.async_client_join(group, self)

        distribution_num = self.get_distribution_num()
        await self.coordinator.musiccast.mc_server_group_extend(
            self._zone_id,
            [
                entity.ip_address
                for entity in entities
                if entity.ip_address != self.ip_address
            ],
            group,
            distribution_num,
        )
        _LOGGER.info(self.entity_id + " added the following entities " + str(entities))
        _LOGGER.info(
            self.entity_id
            + " has now the following musiccast group "
            + str(self.musiccast_group)
        )

        await self.update_all_mc_entities()

    async def async_unjoin(self):
        """Leave the group.

        Stops the distribution if device is server. Used for unjoin service.
        """
        _LOGGER.info(self.entity_id + " called service unjoin.")
        if self.is_server:
            await self.async_server_close_group()

        else:
            await self.async_client_leave_group()

        await self.update_all_mc_entities()

    @property
    def device_state_attributes(self):
        """Return entity specific state attributes."""
        attributes = {
            ATTR_MUSICCAST_GROUP: [e.entity_id for e in self.musiccast_group],
            "alarm_inputs": self.alarm_input_list,
            "alarm_time": self.coordinator.data.alarm_time,
            "alarm_volume": self.coordinator.data.alarm_volume,
            "alarm_volume_settings": {
                "min": self.coordinator.data.alarm_volume_range[0],
                "max": self.coordinator.data.alarm_volume_range[1],
                "step": self.coordinator.data.alarm_volume_step,
            },
            "alarm_enabled": self.coordinator.data.alarm_enabled,
            "alarm_input": "preset:netusb:" + str(self.coordinator.data.alarm_preset)
            if self.coordinator.data.alarm_playback_type == "preset"
            else "resume:" + str(self.coordinator.data.alarm_resume_input)
            if self.coordinator.data.alarm_playback_type == "resume"
            else None,
        }
        return attributes

    # Internal client functions

    async def async_client_join(self, group_id, server):
        """Let the client join a group.

        If this client is a server, the server will stop distributing. If the client is part of a different group,
        it will leave that group first.
        """
        # If we should join the group, which is served by the main zone, we can simply select main_sync as input.
        _LOGGER.info(self.entity_id + " called service client join.")
        if self.state == STATE_OFF:
            await self.async_turn_on()
        if self.ip_address == server.ip_address:
            if server.zone == DEFAULT_ZONE:
                await self.async_select_source(ATTR_MAIN_SYNC)
                server.async_write_ha_state()
                return
            else:
                # It is not possible to join a group hosted by zone2 from main zone.
                raise Exception(
                    "Can not join a zone other than main of the same device."
                )

        if self.musiccast_zone_entity.is_server:
            # If one of the zones of the device is a server, we need to unjoin first.
            _LOGGER.info(
                self.musiccast_zone_entity.entity_id
                + " is a server of a group and has to stop distribution "
                "to use MusicCast for " + self.entity_id
            )
            await self.musiccast_zone_entity.async_server_close_group()

        elif self.is_client:
            if self.coordinator.data.group_id == server.coordinator.data.group_id:
                _LOGGER.warning(self.entity_id + " is already part of the group.")
                return
            else:
                _LOGGER.info(self.entity_id + " is client in a different group.")
                await self.async_client_leave_group()

        elif (
            self.ip_address in server.coordinator.data.group_client_list
            and self.coordinator.data.group_id == server.coordinator.data.group_id
            and self.coordinator.data.group_role == "client"
        ):
            # The device is already part of this group (e.g. main zone is also a client of this group).
            # Just select mc_link as source
            await self.async_select_source(ATTR_MC_LINK)
            # As the musiccast group has changed, we need to trigger the servers ha state.
            # In other cases this happens due to the callback after the dist updated message.
            server.async_write_ha_state()
            return

        _LOGGER.info(self.entity_id + " will now join as a client.")
        await self.coordinator.musiccast.mc_client_join(
            server.ip_address, group_id, self._zone_id
        )

        # Ensure that mc link is selected. If main sync was selected previously, it's possible that this does not
        # happen automatically
        await self.async_select_source(ATTR_MC_LINK)

    async def async_client_leave_group(self, force=False):
        """Make self leave the group.

        Should only be called for clients.
        """
        _LOGGER.info(self.entity_id + " client leave called.")
        if not force and (
            self.source == ATTR_MAIN_SYNC
            or len(
                [
                    entity
                    for entity in self.coordinator.entities
                    if (entity.source == ATTR_MC_LINK and entity != self)
                ]
            )
        ):
            # If we are only syncing to main or another zone is also using the musiccast module as client, don't
            # kill the client session, just select a dummy source.
            save_inputs = self.coordinator.musiccast.get_save_inputs(self._zone_id)
            if len(save_inputs):
                await self.async_select_source(save_inputs[0])
            else:
                await self.async_turn_off()
        else:
            servers = [
                server
                for server in self.get_all_server_entities()
                if server.coordinator.data.group_id == self.coordinator.data.group_id
            ]
            await self.coordinator.musiccast.mc_client_unjoin()
            if len(servers):
                await servers[0].coordinator.musiccast.mc_server_group_reduce(
                    servers[0].zone_id, [self.ip_address], self.get_distribution_num()
                )

        for server in self.get_all_server_entities():
            await server.async_check_client_list()

    # Internal server functions

    async def async_server_close_group(self):
        """Close group of self.

        Should only be called for servers.
        """
        _LOGGER.info(self.entity_id + " closes his group.")
        for client in self.musiccast_group:
            if client != self:
                await client.async_client_leave_group()
        await self.coordinator.musiccast.mc_server_group_close()

    async def async_check_client_list(self):
        """Let the server check if all its clients are still part of his group."""
        _LOGGER.info(self.entity_id + " updates his group members.")
        client_ips_for_removal = []
        for expected_client_ip in self.coordinator.data.group_client_list:
            if expected_client_ip not in [
                entity.ip_address for entity in self.musiccast_group
            ]:
                # The client is no longer part of the group. Prepare removal.
                client_ips_for_removal.append(expected_client_ip)

        distribution_num = self.get_distribution_num()
        if len(client_ips_for_removal):
            _LOGGER.info(
                self.entity_id
                + " says good bye to the following members "
                + str(client_ips_for_removal)
            )
            await self.coordinator.musiccast.mc_server_group_reduce(
                self._zone_id, client_ips_for_removal, distribution_num
            )
        if len(self.musiccast_group) < 2:
            # The group is empty, stop distribution.
            await self.async_server_close_group()

        self.async_write_ha_state()
