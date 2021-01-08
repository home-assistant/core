"""Demo implementation of the media player."""
from typing import Callable, List

from pyamaha import NetUSB, Tuner, Zone

from homeassistant.components.media_player import BrowseMedia, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_TRACK,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_TRACK,
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

from . import MusicCastDataUpdateCoordinator, MusicCastDeviceEntity, _LOGGER
from .const import ATTR_MUSICCAST_GROUP, DOMAIN, NULL_GROUP, ATTR_MC_LINK, ATTR_MAIN_SYNC
from .musiccast_device import MusicCastData

PARALLEL_UPDATES = 1

DEFAULT_ZONE = "main"

BROWSABLE_INPUTS = [
    "usb",
    "server",
    "net_radio",
    "rhapsody",
    "napster",
    "pandora",
    "siriusxm",
    "juke",
    "radiko",
    "qobuz",
    "deezer",
    "amazon_music",
]


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up MusicCast sensor based on a config entry."""
    coordinator: MusicCastDataUpdateCoordinator[MusicCastData] = hass.data[DOMAIN][
        entry.entry_id
    ]

    name = coordinator.data.network_name

    media_players = []

    for zone in coordinator.data.zones:
        zone_name = name if zone == DEFAULT_ZONE else f"{name} {zone}"

        media_players.append(
            MusicCastMediaPlayer(zone, zone_name, entry.entry_id, coordinator)
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
            self.async_check_if_client_status_changed
        )

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.coordinator.musiccast.remove_callback(self.async_write_ha_state)

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
        """Return the zone of the media player"""
        return self._zone_id

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this media_player."""
        macs = self.coordinator.data.mac_addresses
        return f"{macs}_{self._zone_id}"

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.coordinator.musiccast.device.request(
            Zone.set_power(self._zone_id, "on")
        )
        self.schedule_update_ha_state()

    async def async_turn_off(self):
        """Turn the media player off."""
        await self.coordinator.musiccast.device.request(
            Zone.set_power(self._zone_id, "standby")
        )
        self.schedule_update_ha_state()

    async def async_mute_volume(self, mute):
        """Mute the volume."""

        await self.coordinator.musiccast.device.request(
            Zone.set_mute(self._zone_id, mute)
        )

        self.schedule_update_ha_state()

    async def async_set_volume_level(self, volume):
        """Set the volume level, range 0..1."""
        vol = self._volume_min + (self._volume_max - self._volume_min) * volume

        await self.coordinator.musiccast.device.request(
            Zone.set_volume(self._zone_id, round(vol), 1)
        )

        self.schedule_update_ha_state()

    async def async_media_play(self):
        """Send play command."""

        if self._is_netusb:
            await self.coordinator.musiccast.device.request(NetUSB.set_playback("play"))

    async def async_media_pause(self):
        """Send pause command."""
        if self._is_netusb:
            await self.coordinator.musiccast.device.request(
                NetUSB.set_playback("pause")
            )

    async def async_media_stop(self):
        """Send stop command."""
        if self._is_netusb:
            await self.coordinator.musiccast.device.request(NetUSB.set_playback("stop"))

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        if self._is_netusb and self.shuffle != shuffle:
            await self.coordinator.musiccast.device.request(NetUSB.toggle_shuffle())

    async def async_select_sound_mode(self, sound_mode):
        """Select sound mode."""
        print(f'CHANGING TO SOUND MODE "{sound_mode}"')
        await self.coordinator.musiccast.device.request(
            Zone.set_sound_program(self._zone_id, sound_mode)
        )

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
        return (
            f"http://{self.ip_address}{self.coordinator.data.netusb_albumart_url}"
            if self._is_netusb and self.coordinator.data.netusb_albumart_url
            else ""
        )

    @property
    def media_title(self):
        """Return the title of current playing media."""
        if self._is_netusb:
            return self.coordinator.data.netusb_track
        elif self._is_tuner:
            if self.coordinator.data.band == "dab":
                return self.coordinator.data.dab_dls
            else:
                if (
                    self.coordinator.data.rds_text_a == ""
                    and self.coordinator.data.rds_text_b != ""
                ):
                    return self.coordinator.data.rds_text_b
                elif (
                    self.coordinator.data.rds_text_a != ""
                    and self.coordinator.data.rds_text_b == ""
                ):
                    return self.coordinator.data.rds_text_a
                elif (
                    self.coordinator.data.rds_text_a != ""
                    and self.coordinator.data.rds_text_b != ""
                ):
                    return f"{self.coordinator.data.rds_text_a} / {self.coordinator.data.rds_text_b}"

        return None

    @property
    def media_artist(self):
        """Return the artist of current playing media (Music track only)."""

        if self._is_netusb:
            return self.coordinator.data.netusb_artist
        elif self._is_tuner:
            if self.coordinator.data.band == "dab":
                return self.coordinator.data.dab_service_label
            elif self.coordinator.data.band == "fm":
                return self.coordinator.data.fm_freq
            elif self.coordinator.data.band == "am":
                return self.coordinator.data.am_freq

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
            await self.coordinator.musiccast.device.request(
                NetUSB.set_playback("previous")
            )
        elif self._is_tuner:
            if self.coordinator.data.band in ("fm", "am"):
                await self.coordinator.musiccast.device.request(
                    Tuner.set_freq(self.coordinator.data.band, "auto_down", 0)
                )
            elif self.coordinator.data.band == "dab":
                await self.coordinator.musiccast.device.request(
                    Tuner.set_dab_service("previous")
                )

    async def async_media_next_track(self):
        """Send next track command."""
        if self._is_netusb:
            await self.coordinator.musiccast.device.request(NetUSB.set_playback("next"))
        elif self._is_tuner:
            if self.coordinator.data.band in ("fm", "am"):
                await self.coordinator.musiccast.device.request(
                    Tuner.set_freq(self.coordinator.data.band, "auto_up", 0)
                )
            elif self.coordinator.data.band == "dab":
                await self.coordinator.musiccast.device.request(
                    Tuner.set_dab_service("next")
                )

    def clear_playlist(self):
        """Clear players playlist."""
        # TODO self.tracks is not defined in init. Do we want to add the current playlist and integrate it into the
        #  media browser?
        self.tracks = []
        self._cur_track = 0
        self._player_state = STATE_OFF
        self.schedule_update_ha_state()

    async def async_set_repeat(self, repeat):
        """Enable/disable repeat mode."""
        print([self.repeat, repeat])
        if self._is_netusb and self.repeat != repeat and self.repeat != REPEAT_MODE_ONE:
            await self.coordinator.musiccast.device.request(NetUSB.toggle_repeat())

    async def async_select_source(self, source):
        """Select input source."""
        # We need to set the new source data manually to ensure that the data are updated before they are requested
        # during the group update processes.
        self.coordinator.data.zones[self._zone_id].input = source
        await self.coordinator.musiccast.device.request(
            Zone.set_input(self._zone_id, source, "")
        )

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

        print(f"PLAY MEDIA ({media_type} / {media_id})")

        if media_id:
            parts = media_id.split(":")

            if parts[0] == "list":
                index = parts[3]

                if index == "-1":
                    index = "0"

                await self.coordinator.musiccast.device.request(
                    NetUSB.set_list_control("main", "play", index, self._zone_id)
                )

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""

        print(f"BROWSE MEDIA ({media_content_type} / {media_content_id})")

        inputs = list(set(BROWSABLE_INPUTS) & set(self.source_list))
        inputs.sort()

        menu_layer = None

        if media_content_id and media_content_type != "categories":
            parts = media_content_id.split(":")

            list_info = None

            if parts[0] == "input":
                input = parts[1]

                # reset list info

                while True:
                    list_info = await (
                        await self.coordinator.musiccast.device.request(
                            NetUSB.get_list_info(input, 0, 8, "en", "main")
                        )
                    ).json()

                    menu_layer = list_info.get("menu_layer")
                    if menu_layer == 0:
                        break
                    else:
                        await self.coordinator.musiccast.device.request(
                            NetUSB.set_list_control("main", "return", "", self._zone_id)
                        )

            elif parts[0] == "list":
                input = parts[1]

                if parts[3] == "-1":
                    await self.coordinator.musiccast.device.request(
                        NetUSB.set_list_control(
                            "main", "return", parts[3], self._zone_id
                        )
                    )
                else:
                    await self.coordinator.musiccast.device.request(
                        NetUSB.set_list_control(
                            "main", "select", parts[3], self._zone_id
                        )
                    )

                list_info = await (
                    await self.coordinator.musiccast.device.request(
                        NetUSB.get_list_info(input, 0, 8, "en", "main")
                    )
                ).json()

                menu_layer = list_info.get("menu_layer")

            # Show first layer of list_info

            children = []

            parent_is_directory = False

            for i, info in enumerate(list_info.get("list_info", [])):
                # b[1]     Capable of Select(common for all Net/USB sources
                # b[2]     Capable of Play(common for all Net/USB sources)

                is_selectable = info.get("attribute") & 0b10 == 0b10
                is_playable = info.get("attribute") & 0b100 == 0b100

                child = BrowseMedia(
                    title=info.get("text"),
                    media_class=MEDIA_CLASS_DIRECTORY
                    if is_selectable
                    else MEDIA_CLASS_TRACK,
                    media_content_id=f"list:{input}:{menu_layer + 1}:{i}",
                    media_content_type=MEDIA_CLASS_DIRECTORY
                    if is_selectable
                    else MEDIA_TYPE_TRACK,
                    can_play=is_playable,
                    can_expand=is_selectable,
                    thumbnail=info.get("thumbnail"),
                )
                children.append(child)

                parent_is_directory = parent_is_directory or is_selectable

            input_folder = BrowseMedia(
                title=list_info.get("menu_name"),
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_id=f"list:{input}:{menu_layer}:-1",
                media_content_type=MEDIA_CLASS_DIRECTORY,
                can_play=not parent_is_directory,
                can_expand=True,
                children=children,
                children_media_class=MEDIA_CLASS_DIRECTORY
                if parent_is_directory
                else MEDIA_CLASS_TRACK,
            )

            return input_folder

        # START MAIN CATEGORIES FOR INPUTS
        menu_layer = 0

        children = [
            BrowseMedia(
                title=self.coordinator.data.input_names.get(input, input),
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_id=f"input:{input}",
                media_content_type=MEDIA_CLASS_DIRECTORY,
                can_play=False,
                can_expand=True,
            )
            for input in inputs
        ]

        overview = BrowseMedia(
            title="Library",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="",
            media_content_type="categories",
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class=MEDIA_CLASS_DIRECTORY,
        )

        return overview

    async def async_client_join(self, group_id, server):
        """Let the client join a group. If this client is a server, the server will stop distributing."""
        # If we should join the group, which is served by the main zone, we can simply select main_sync as input.
        _LOGGER.info(self.entity_id + " called service client join.")
        if self.ip_address == server.ip_address:
            if server.zone == DEFAULT_ZONE:
                await self.async_select_source(ATTR_MAIN_SYNC)
                server.async_write_ha_state()
                return
            else:
                # It is not possible to join a group hosted by zone2 from main zone.
                raise Exception("Can not join a zone other than main of the same device.")

        if self.musiccast_zone_entity.is_server:
            # If one of the zones of the device is a server, we need to unjoin first.
            _LOGGER.info(self.musiccast_zone_entity.entity_id + " is a server of a group and has to stop distribution "
                                                                "to use MusicCast for " + self.entity_id)
            await self.musiccast_zone_entity.async_server_close_group()

        elif self.is_client:
            if self.coordinator.data.group_id == server.coordinator.data.group_id:
                _LOGGER.info(self.entity_id + " is already part of the group.")
                return
            else:
                _LOGGER.info(self.entity_id + " is client in a different group.")
                await self.async_client_leave_group()

        elif self.ip_address in server.coordinator.data.group_client_list and \
            self.coordinator.data.group_id == server.coordinator.data.group_id and \
                self.coordinator.data.group_role == "client":
            # The device is already part of this group (e.g. main zone is also a client of this group).
            # Just select mc_link as source
            await self.async_select_source(ATTR_MC_LINK)
            # As the musiccast group has changed, we need to trigger the servers ha state.
            # In other cases this happens due to the callback after the dist updated message.
            server.async_write_ha_state()
            return

        _LOGGER.info(self.entity_id + " will now join as a client.")
        await self.coordinator.musiccast.mc_client_join(server.ip_address, group_id, self._zone_id)

        # Ensure that mc link is selected. If main sync was selected previously, it's possible that this does not
        # happen automatically
        await self.async_select_source(ATTR_MC_LINK)

    async def lock_entities(self, entities, lock):
        """Lock all entities given in entities except self.

        Ensures that if multiple zones of the same device are provided as entities that the lock is only acquired for
        one time.
        """
        coordinators = set([entity.coordinator for entity in entities if entity.coordinator != self.coordinator])
        for coordinator in coordinators:
            if lock:
                await coordinator.data.group_update_lock.acquire()
            else:
                coordinator.data.group_update_lock.release()

    async def async_server_join(self, entities):
        """Add all clients given in entities to the group of the server. Creates a new group if necessary."""
        _LOGGER.info(self.entity_id + " wants to add the following entities " + str(entities))
        async with self.coordinator.data.group_update_lock:
            if not self.is_server and self.musiccast_zone_entity.is_server:
                # The MusicCast Distribution Module of this device is already in use. To use it as a server, we first
                # have to unjoin and wait until the servers are updated.
                entities = self.musiccast_zone_entity.musiccast_group
                await self.lock_entities(entities, True)
                try:
                    await self.musiccast_zone_entity.async_server_close_group()
                finally:
                    await self.lock_entities(entities, False)
            elif self.musiccast_zone_entity.is_client:
                await self.async_client_leave_group(True)
            # Use existing group id if we are server, generate a new one else.
            group = (
                self.coordinator.data.group_id
                if self.is_server
                else uuid.random_uuid_hex().upper()
            )
            # First let the clients join
            await self.lock_entities(entities, True)
            try:
                for client in entities:
                    if client != self:
                        await client.async_client_join(group, self)

                await self.coordinator.musiccast.mc_server_group_extend(self._zone_id,
                                                                        [entity.ip_address for entity in entities],
                                                                        group)
                _LOGGER.info(self.entity_id + " added the following entities " + str(entities))
            finally:
                await self.lock_entities(entities, False)
                _LOGGER.info(self.entity_id + " has now the following musiccast group " + str(self.musiccast_group))
                self.async_write_ha_state()

    async def async_unjoin(self):
        """Leave the group. Stops the distribution if device is server."""
        async with self.coordinator.data.group_update_lock:
            _LOGGER.info(self.entity_id + " called service unjoin.")
            if self.is_server:
                await self.async_server_close_group()

            else:
                await self.async_client_leave_group()

    async def async_client_leave_group(self, force=False):
        _LOGGER.info(self.entity_id + " client leave called.")
        if not force and (self.source == ATTR_MAIN_SYNC or
                          len([entity for entity in self.coordinator.entities if (entity.source == ATTR_MC_LINK
                                                                                  and entity != self)])):
            # If we are only syncing to main or another zone is also using the musiccast module as client, don't
            # kill the client session, just select a dummy source.
            save_inputs = self.coordinator.musiccast.get_save_inputs(self._zone_id)
            if len(save_inputs):
                await self.async_select_source(save_inputs[0])
            else:
                await self.async_turn_off()
        else:
            await self.coordinator.musiccast.mc_client_unjoin()

        for server in self.get_all_server_entities():
            await server.async_check_client_list()

    async def async_server_close_group(self):
        _LOGGER.info(self.entity_id + " closes his group.")
        for client in self.musiccast_group:
            if client != self:
                await client.async_client_leave_group()
        await self.coordinator.musiccast.mc_server_group_close()

    def is_part_of_group(self, group_server):
        if self.entity_id and group_server.entity_id:
            print("-----" + self.entity_id + " in " + group_server.entity_id + "-----")
            print(self.ip_address + " vs " + str(group_server.coordinator.data.group_client_list))
            print(self.coordinator.data.group_id + " vs " + group_server.coordinator.data.group_id)
            print(self.ip_address + " vs " + group_server.ip_address)
            print(self.source)
            print("--------------------------------")
        return group_server != self and (
            (
                self.ip_address in group_server.coordinator.data.group_client_list and
                self.coordinator.data.group_id == group_server.coordinator.data.group_id and
                self.ip_address != group_server.ip_address and
                self.source == ATTR_MC_LINK
            ) or
            (
                self.ip_address == group_server.ip_address and
                self.source == ATTR_MAIN_SYNC
            )
        )

    @property
    def musiccast_group(self):
        """Return all media players of the current group, if the media player is server."""
        if not self.is_server:
            return [self]
        entities = self.get_all_mc_enitities()
        clients = [
            entity
            for entity in entities
            if entity.is_part_of_group(self)
        ]
        return clients + [self]

    def get_all_mc_enitities(self):
        entities = []
        for coordinator in self.hass.data[DOMAIN].values():
            entities += coordinator.entities
        return entities

    def get_all_server_entities(self):
        entities = self.get_all_mc_enitities()
        return [entity for entity in entities if entity.is_server]

    @property
    def device_state_attributes(self):
        """Return entity specific state attributes."""
        attributes = {
            ATTR_MUSICCAST_GROUP: [e.entity_id for e in self.musiccast_group],
        }
        return attributes

    @property
    def is_server(self):
        """Return whether the media player is the server/host of the group.

        If the media player is not part of a group, False is returned.
        """
        return (
                self.is_network_server or (
                 self._zone_id == DEFAULT_ZONE
                 and len([entity for entity in self.coordinator.entities if entity.source == ATTR_MAIN_SYNC])
                )
        )

    @property
    def is_network_server(self):
        """Return only true if the current entity is a network server and not a main zone with an attached zone2."""
        return (self.coordinator.data.group_role == "server"
                and self.coordinator.data.group_id != NULL_GROUP
                and self._zone_id == self.coordinator.data.group_server_zone)

    @property
    def is_client(self):
        """Return whether the media player is the client of a group.

        If the media player is not part of a group, False is returned.
        """
        return (
                self.is_network_client or (
                 self.source == ATTR_MAIN_SYNC)
        )

    @property
    def is_network_client(self):
        return (self.coordinator.data.group_role == "client"
                and self.coordinator.data.group_id != NULL_GROUP
                and self.source == ATTR_MC_LINK)

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

    async def async_check_if_client_status_changed(self):
        """Handle an group update.

        If the client left the group, the server speakers have to update their client lists.
        If he joined, servers should trigger update hass
        """
        if self.coordinator.data.last_group_role != "server" and (
            (
                self.coordinator.data.last_group_id != NULL_GROUP
                and self.coordinator.data.group_id
                != self.coordinator.data.last_group_id
            )
            or (
                self.coordinator.data.last_group_role == "client"
                and self.coordinator.data.group_role == "none"
            )
        ):
            # The client left the group. The servers need to update their client lists.
            servers = self.get_all_server_entities()
            for server in servers:
                await server.async_check_client_list()

    async def async_check_client_list(self):
        """Let the server check if all its clients are still part of his group."""
        _LOGGER.info(self.entity_id + " updates his group members.")
        client_ips_for_removal = list()
        for expected_client_ip in self.coordinator.data.group_client_list:
            if expected_client_ip not in [entity.ip_address for entity in self.musiccast_group]:
                # The client is no longer part of the group. Prepare removal.
                client_ips_for_removal.append(expected_client_ip)

        if len(client_ips_for_removal):
            _LOGGER.info(self.entity_id + " says good bye to the following members " + str(client_ips_for_removal))
            await self.coordinator.musiccast.mc_server_group_reduce(self._zone_id, client_ips_for_removal)
        if len(self.musiccast_group) < 2:
            # The group is empty, stop distribution.
            await self.async_server_close_group()

        self.async_write_ha_state()
