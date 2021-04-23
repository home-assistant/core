"""Denon HEOS Media Player."""
from functools import reduce, wraps
import logging
from operator import ior
from typing import Sequence

from pyheos import HeosError, const as heos_const

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ENQUEUE,
    DOMAIN,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_URL,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_GROUPING,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_PAUSED, STATE_PLAYING
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.dt import utcnow

from .const import (
    DATA_CONTROLLER_MANAGER,
    DATA_SOURCE_MANAGER,
    DOMAIN as HEOS_DOMAIN,
    SIGNAL_HEOS_UPDATED,
)

BASE_SUPPORTED_FEATURES = (
    SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_GROUPING
)

PLAY_STATE_TO_STATE = {
    heos_const.PLAY_STATE_PLAY: STATE_PLAYING,
    heos_const.PLAY_STATE_STOP: STATE_IDLE,
    heos_const.PLAY_STATE_PAUSE: STATE_PAUSED,
}

CONTROL_TO_SUPPORT = {
    heos_const.CONTROL_PLAY: SUPPORT_PLAY,
    heos_const.CONTROL_PAUSE: SUPPORT_PAUSE,
    heos_const.CONTROL_STOP: SUPPORT_STOP,
    heos_const.CONTROL_PLAY_PREVIOUS: SUPPORT_PREVIOUS_TRACK,
    heos_const.CONTROL_PLAY_NEXT: SUPPORT_NEXT_TRACK,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
):
    """Add media players for a config entry."""
    players = hass.data[HEOS_DOMAIN][DOMAIN]
    devices = [HeosMediaPlayer(player) for player in players.values()]
    async_add_entities(devices, True)


def log_command_error(command: str):
    """Return decorator that logs command failure."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                await func(*args, **kwargs)
            except (HeosError, ValueError) as ex:
                _LOGGER.error("Unable to %s: %s", command, ex)

        return wrapper

    return decorator


class HeosMediaPlayer(MediaPlayerEntity):
    """The HEOS player."""

    def __init__(self, player):
        """Initialize."""
        self._media_position_updated_at = None
        self._player = player
        self._signals = []
        self._supported_features = BASE_SUPPORTED_FEATURES
        self._source_manager = None
        self._group = []

    async def _player_update(self, player_id, event):
        """Handle player attribute updated."""
        if self._player.player_id != player_id:
            return
        if event == heos_const.EVENT_PLAYER_NOW_PLAYING_PROGRESS:
            self._media_position_updated_at = utcnow()
        await self.async_update_ha_state(True)

    async def _heos_updated(self):
        """Handle sources changed."""
        await self.async_update_ha_state(True)

    async def async_added_to_hass(self):
        """Device added to hass."""
        # Update state when attributes of the player change
        self._signals.append(
            self._player.heos.dispatcher.connect(
                heos_const.SIGNAL_PLAYER_EVENT, self._player_update
            )
        )
        # Update state when heos changes
        self._signals.append(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_HEOS_UPDATED, self._heos_updated
            )
        )

    @log_command_error("clear playlist")
    async def async_clear_playlist(self):
        """Clear players playlist."""
        await self._player.clear_queue()

    async def async_get_group(self):
        """Build a dictionary with HEOS group membership information."""
        group_membership = []
        if not self.player_id:
            _LOGGER.info(
                "No player_id for %s yet, not returning group info", self.entity_id
            )
            return group_membership

        controller = self.hass.data[HEOS_DOMAIN][DATA_CONTROLLER_MANAGER].controller
        try:
            groups = await controller.get_groups(refresh=True)
        except HeosError as err:
            _LOGGER.error("HEOS Unable to get group info: %s", err)
            return group_membership

        for group in groups.values():
            member_player_ids = {member.player_id for member in group.members}
            if (
                self.player_id == group.leader.player_id
                or self.player_id in member_player_ids
            ):
                leader_entity_id = None

                for entity in self.hass.data[DOMAIN].entities:
                    if not isinstance(entity, HeosMediaPlayer):
                        continue
                    if entity.player_id == group.leader.player_id:
                        leader_entity_id = entity.entity_id
                    elif entity.player_id in member_player_ids:
                        group_membership.append(entity.entity_id)
                # Make sure the group leader is always the first element
                group_membership.insert(0, leader_entity_id)
                return group_membership
        return group_membership

    @log_command_error("join_players")
    async def async_join_players(self, group_members):
        """Join `group_members` as a player group with the current player."""
        player_ids = []
        for player_entity_id in group_members:
            for entity in self.hass.data[DOMAIN].entities:
                if (
                    isinstance(entity, HeosMediaPlayer)
                    and entity.entity_id == player_entity_id
                ):
                    player_ids.append(entity.player_id)

        controller = self.hass.data[HEOS_DOMAIN][DATA_CONTROLLER_MANAGER].controller
        try:
            await controller.create_group(self.player_id, player_ids)
        except HeosError as err:
            _LOGGER.error(
                "Failed to group %s with %s: %s",
                self.player_id,
                player_ids,
                err,
            )

    @log_command_error("pause")
    async def async_media_pause(self):
        """Send pause command."""
        await self._player.pause()

    @log_command_error("play")
    async def async_media_play(self):
        """Send play command."""
        await self._player.play()

    @log_command_error("move to previous track")
    async def async_media_previous_track(self):
        """Send previous track command."""
        await self._player.play_previous()

    @log_command_error("move to next track")
    async def async_media_next_track(self):
        """Send next track command."""
        await self._player.play_next()

    @log_command_error("stop")
    async def async_media_stop(self):
        """Send stop command."""
        await self._player.stop()

    @log_command_error("set mute")
    async def async_mute_volume(self, mute):
        """Mute the volume."""
        await self._player.set_mute(mute)

    @log_command_error("play media")
    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        if media_type in (MEDIA_TYPE_URL, MEDIA_TYPE_MUSIC):
            await self._player.play_url(media_id)
            return

        if media_type == "quick_select":
            # media_id may be an int or a str
            selects = await self._player.get_quick_selects()
            try:
                index = int(media_id)
            except ValueError:
                # Try finding index by name
                index = next(
                    (index for index, select in selects.items() if select == media_id),
                    None,
                )
            if index is None:
                raise ValueError(f"Invalid quick select '{media_id}'")
            await self._player.play_quick_select(index)
            return

        if media_type == MEDIA_TYPE_PLAYLIST:
            playlists = await self._player.heos.get_playlists()
            playlist = next((p for p in playlists if p.name == media_id), None)
            if not playlist:
                raise ValueError(f"Invalid playlist '{media_id}'")
            add_queue_option = (
                heos_const.ADD_QUEUE_ADD_TO_END
                if kwargs.get(ATTR_MEDIA_ENQUEUE)
                else heos_const.ADD_QUEUE_REPLACE_AND_PLAY
            )
            await self._player.add_to_queue(playlist, add_queue_option)
            return

        if media_type == "favorite":
            # media_id may be an int or str
            try:
                index = int(media_id)
            except ValueError:
                # Try finding index by name
                index = next(
                    (
                        index
                        for index, favorite in self._source_manager.favorites.items()
                        if favorite.name == media_id
                    ),
                    None,
                )
            if index is None:
                raise ValueError(f"Invalid favorite '{media_id}'")
            await self._player.play_favorite(index)
            return

        raise ValueError(f"Unsupported media type '{media_type}'")

    @log_command_error("select source")
    async def async_select_source(self, source):
        """Select input source."""
        await self._source_manager.play_source(source, self._player)

    @log_command_error("set shuffle")
    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        await self._player.set_play_mode(self._player.repeat, shuffle)

    @log_command_error("set volume level")
    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._player.set_volume(int(volume * 100))

    async def async_update(self):
        """Update supported features of the player."""
        controls = self._player.now_playing_media.supported_controls
        current_support = [CONTROL_TO_SUPPORT[control] for control in controls]
        self._supported_features = reduce(ior, current_support, BASE_SUPPORTED_FEATURES)
        self._group = await self.async_get_group()

        if self._source_manager is None:
            self._source_manager = self.hass.data[HEOS_DOMAIN][DATA_SOURCE_MANAGER]

    @log_command_error("unjoin_player")
    async def async_unjoin_player(self):
        """Remove this player from any group."""
        if self.group_members:
            controller = self.hass.data[HEOS_DOMAIN][DATA_CONTROLLER_MANAGER].controller
            try:
                await controller.remove_group(self.player_id)
            except HeosError as err:
                _LOGGER.error(
                    "HEOS create_group with arguments (%s %s) failed. Error: %s",
                    self.player_id,
                    [],
                    err,
                )

    async def async_will_remove_from_hass(self):
        """Disconnect the device when removed."""
        for signal_remove in self._signals:
            signal_remove()
        self._signals.clear()

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self._player.available

    @property
    def device_info(self) -> dict:
        """Get attributes about the device."""
        return {
            "identifiers": {(HEOS_DOMAIN, self._player.player_id)},
            "name": self._player.name,
            "model": self._player.model,
            "manufacturer": "HEOS",
            "sw_version": self._player.version,
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Get additional attribute about the state."""
        return {
            "media_album_id": self._player.now_playing_media.album_id,
            "media_queue_id": self._player.now_playing_media.queue_id,
            "media_source_id": self._player.now_playing_media.source_id,
            "media_station": self._player.now_playing_media.station,
            "media_type": self._player.now_playing_media.type,
        }

    @property
    def group_members(self) -> list:
        """List of players which are grouped together."""
        return self._group

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return self._player.is_muted

    @property
    def media_album_name(self) -> str:
        """Album name of current playing media, music track only."""
        return self._player.now_playing_media.album

    @property
    def media_artist(self) -> str:
        """Artist of current playing media, music track only."""
        return self._player.now_playing_media.artist

    @property
    def media_content_id(self) -> str:
        """Content ID of current playing media."""
        return self._player.now_playing_media.media_id

    @property
    def media_content_type(self) -> str:
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        duration = self._player.now_playing_media.duration
        if isinstance(duration, int):
            return duration / 1000
        return None

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        # Some media doesn't have duration but reports position, return None
        if not self._player.now_playing_media.duration:
            return None
        return self._player.now_playing_media.current_position / 1000

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        # Some media doesn't have duration but reports position, return None
        if not self._player.now_playing_media.duration:
            return None
        return self._media_position_updated_at

    @property
    def media_image_remotely_accessible(self) -> bool:
        """If the image url is remotely accessible."""
        return True

    @property
    def media_image_url(self) -> str:
        """Image url of current playing media."""
        # May be an empty string, if so, return None
        image_url = self._player.now_playing_media.image_url
        return image_url if image_url else None

    @property
    def media_title(self) -> str:
        """Title of current playing media."""
        return self._player.now_playing_media.song

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._player.name

    @property
    def should_poll(self) -> bool:
        """No polling needed for this device."""
        return False

    @property
    def shuffle(self) -> bool:
        """Boolean if shuffle is enabled."""
        return self._player.shuffle

    @property
    def source(self) -> str:
        """Name of the current input source."""
        return self._source_manager.get_current_source(self._player.now_playing_media)

    @property
    def source_list(self) -> Sequence[str]:
        """List of available input sources."""
        return self._source_manager.source_list

    @property
    def state(self) -> str:
        """State of the player."""
        return PLAY_STATE_TO_STATE[self._player.state]

    @property
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        return self._supported_features

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return str(self._player.player_id)

    @property
    def player_id(self) -> int:
        """Return the HEOS player ID."""
        return self._player.player_id

    @property
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        return self._player.volume / 100
