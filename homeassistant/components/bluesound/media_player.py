"""Support for Bluesound devices."""

from __future__ import annotations

import asyncio
from asyncio import CancelledError, Task
from contextlib import suppress
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from pyblu import Input, Player, Preset, Status, SyncStatus
from pyblu.errors import PlayerUnreachableError
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import ATTR_BLUESOUND_GROUP, ATTR_MASTER, DOMAIN
from .utils import dispatcher_join_signal, dispatcher_unjoin_signal, format_unique_id

if TYPE_CHECKING:
    from . import BluesoundConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)

DATA_BLUESOUND = DOMAIN
DEFAULT_PORT = 11000

SERVICE_CLEAR_TIMER = "clear_sleep_timer"
SERVICE_JOIN = "join"
SERVICE_SET_TIMER = "set_sleep_timer"
SERVICE_UNJOIN = "unjoin"

NODE_OFFLINE_CHECK_TIMEOUT = 180
NODE_RETRY_INITIATION = timedelta(minutes=3)

SYNC_STATUS_INTERVAL = timedelta(minutes=5)

POLL_TIMEOUT = 120


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BluesoundConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Bluesound entry."""
    bluesound_player = BluesoundPlayer(
        config_entry.data[CONF_HOST],
        config_entry.data[CONF_PORT],
        config_entry.runtime_data.player,
        config_entry.runtime_data.sync_status,
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_TIMER, None, "async_increase_timer"
    )
    platform.async_register_entity_service(
        SERVICE_CLEAR_TIMER, None, "async_clear_timer"
    )
    platform.async_register_entity_service(
        SERVICE_JOIN, {vol.Required(ATTR_MASTER): cv.entity_id}, "async_join"
    )
    platform.async_register_entity_service(SERVICE_UNJOIN, None, "async_unjoin")

    hass.data[DATA_BLUESOUND].append(bluesound_player)
    async_add_entities([bluesound_player], update_before_add=True)


class BluesoundPlayer(MediaPlayerEntity):
    """Representation of a Bluesound Player."""

    _attr_media_content_type = MediaType.MUSIC
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        host: str,
        port: int,
        player: Player,
        sync_status: SyncStatus,
    ) -> None:
        """Initialize the media player."""
        self.host = host
        self.port = port
        self._poll_status_loop_task: Task[None] | None = None
        self._poll_sync_status_loop_task: Task[None] | None = None
        self._id = sync_status.id
        self._last_status_update: datetime | None = None
        self._sync_status = sync_status
        self._status: Status | None = None
        self._inputs: list[Input] = []
        self._presets: list[Preset] = []
        self._group_name: str | None = None
        self._group_list: list[str] = []
        self._bluesound_device_name = sync_status.name
        self._player = player
        self._is_leader = False
        self._leader: BluesoundPlayer | None = None

        self._attr_unique_id = format_unique_id(sync_status.mac, port)
        # there should always be one player with the default port per mac
        if port == DEFAULT_PORT:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, format_mac(sync_status.mac))},
                connections={(CONNECTION_NETWORK_MAC, format_mac(sync_status.mac))},
                name=sync_status.name,
                manufacturer=sync_status.brand,
                model=sync_status.model_name,
                model_id=sync_status.model,
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, format_unique_id(sync_status.mac, port))},
                name=sync_status.name,
                manufacturer=sync_status.brand,
                model=sync_status.model_name,
                model_id=sync_status.model,
                via_device=(DOMAIN, format_mac(sync_status.mac)),
            )

    async def _poll_status_loop(self) -> None:
        """Loop which polls the status of the player."""
        while True:
            try:
                await self.async_update_status()
            except PlayerUnreachableError:
                _LOGGER.error(
                    "Node %s:%s is offline, retrying later", self.host, self.port
                )
                await asyncio.sleep(NODE_OFFLINE_CHECK_TIMEOUT)
            except CancelledError:
                _LOGGER.debug(
                    "Stopping the polling of node %s:%s", self.host, self.port
                )
                return
            except:  # noqa: E722 - this loop should never stop
                _LOGGER.exception(
                    "Unexpected error for %s:%s, retrying later", self.host, self.port
                )
                await asyncio.sleep(NODE_OFFLINE_CHECK_TIMEOUT)

    async def _poll_sync_status_loop(self) -> None:
        """Loop which polls the sync status of the player."""
        while True:
            try:
                await self.update_sync_status()
            except PlayerUnreachableError:
                await asyncio.sleep(NODE_OFFLINE_CHECK_TIMEOUT)
            except CancelledError:
                raise
            except:  # noqa: E722 - all errors must be caught for this loop
                await asyncio.sleep(NODE_OFFLINE_CHECK_TIMEOUT)

    async def async_added_to_hass(self) -> None:
        """Start the polling task."""
        await super().async_added_to_hass()

        self._poll_status_loop_task = self.hass.async_create_background_task(
            self._poll_status_loop(),
            name=f"bluesound.poll_status_loop_{self.host}:{self.port}",
        )
        self._poll_sync_status_loop_task = self.hass.async_create_background_task(
            self._poll_sync_status_loop(),
            name=f"bluesound.poll_sync_status_loop_{self.host}:{self.port}",
        )

        assert self._sync_status.id is not None
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                dispatcher_join_signal(self.entity_id),
                self.async_add_follower,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                dispatcher_unjoin_signal(self._sync_status.id),
                self.async_remove_follower,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop the polling task."""
        await super().async_will_remove_from_hass()

        assert self._poll_status_loop_task is not None
        if self._poll_status_loop_task.cancel():
            # the sleeps in _poll_loop will raise CancelledError
            with suppress(CancelledError):
                await self._poll_status_loop_task

        assert self._poll_sync_status_loop_task is not None
        if self._poll_sync_status_loop_task.cancel():
            # the sleeps in _poll_sync_status_loop will raise CancelledError
            with suppress(CancelledError):
                await self._poll_sync_status_loop_task

        self.hass.data[DATA_BLUESOUND].remove(self)

    async def async_update(self) -> None:
        """Update internal status of the entity."""
        if not self.available:
            return

        with suppress(PlayerUnreachableError):
            await self.async_update_presets()
            await self.async_update_captures()

    async def async_update_status(self) -> None:
        """Use the poll session to always get the status of the player."""
        etag = None
        if self._status is not None:
            etag = self._status.etag

        try:
            status = await self._player.status(
                etag=etag, poll_timeout=POLL_TIMEOUT, timeout=POLL_TIMEOUT + 5
            )

            self._attr_available = True
            self._last_status_update = dt_util.utcnow()
            self._status = status

            self.async_write_ha_state()
        except PlayerUnreachableError:
            self._attr_available = False
            self._last_status_update = None
            self._status = None
            self.async_write_ha_state()
            _LOGGER.error(
                "Client connection error, marking %s as offline",
                self._bluesound_device_name,
            )
            raise

    async def update_sync_status(self) -> None:
        """Update the internal status."""
        etag = None
        if self._sync_status:
            etag = self._sync_status.etag
        sync_status = await self._player.sync_status(
            etag=etag, poll_timeout=POLL_TIMEOUT, timeout=POLL_TIMEOUT + 5
        )

        self._sync_status = sync_status

        self._group_list = self.rebuild_bluesound_group()

        if sync_status.leader is not None:
            self._is_leader = False
            leader_id = f"{sync_status.leader.ip}:{sync_status.leader.port}"
            leader_device = [
                device
                for device in self.hass.data[DATA_BLUESOUND]
                if device.id == leader_id
            ]

            if leader_device and leader_id != self.id:
                self._leader = leader_device[0]
            else:
                self._leader = None
                _LOGGER.error("Leader not found %s", leader_id)
        else:
            if self._leader is not None:
                self._leader = None
            followers = self._sync_status.followers
            self._is_leader = followers is not None

        self.async_write_ha_state()

    async def async_update_captures(self) -> None:
        """Update Capture sources."""
        inputs = await self._player.inputs()
        self._inputs = inputs

    async def async_update_presets(self) -> None:
        """Update Presets."""
        presets = await self._player.presets()
        self._presets = presets

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        if self._status is None:
            return MediaPlayerState.OFF

        if self.is_grouped and not self.is_leader:
            return MediaPlayerState.IDLE

        match self._status.state:
            case "pause":
                return MediaPlayerState.PAUSED
            case "stream" | "play":
                return MediaPlayerState.PLAYING
            case _:
                return MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if self._status is None or (self.is_grouped and not self.is_leader):
            return None

        return self._status.name

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media (Music track only)."""
        if self._status is None:
            return None

        if self.is_grouped and not self.is_leader:
            return self._group_name

        return self._status.artist

    @property
    def media_album_name(self) -> str | None:
        """Artist of current playing media (Music track only)."""
        if self._status is None or (self.is_grouped and not self.is_leader):
            return None

        return self._status.album

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if self._status is None or (self.is_grouped and not self.is_leader):
            return None

        url = self._status.image
        if url is None:
            return None

        if url[0] == "/":
            url = f"http://{self.host}:{self.port}{url}"

        return url

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if self._status is None or (self.is_grouped and not self.is_leader):
            return None

        mediastate = self.state
        if self._last_status_update is None or mediastate == MediaPlayerState.IDLE:
            return None

        position = self._status.seconds
        if position is None:
            return None

        if mediastate == MediaPlayerState.PLAYING:
            position += (dt_util.utcnow() - self._last_status_update).total_seconds()

        return int(position)

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if self._status is None or (self.is_grouped and not self.is_leader):
            return None

        duration = self._status.total_seconds
        if duration is None:
            return None

        return int(duration)

    @property
    def media_position_updated_at(self) -> datetime | None:
        """Last time status was updated."""
        return self._last_status_update

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        volume = None

        if self._status is not None:
            volume = self._status.volume
        if self.is_grouped:
            volume = self._sync_status.volume

        if volume is None:
            return None

        return volume / 100

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        mute = False

        if self._status is not None:
            mute = self._status.mute
        if self.is_grouped:
            mute = self._sync_status.mute_volume is not None

        return mute

    @property
    def id(self) -> str | None:
        """Get id of device."""
        return self._id

    @property
    def bluesound_device_name(self) -> str | None:
        """Return the device name as returned by the device."""
        return self._bluesound_device_name

    @property
    def sync_status(self) -> SyncStatus:
        """Return the sync status."""
        return self._sync_status

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        if self._status is None or (self.is_grouped and not self.is_leader):
            return None

        sources = [x.text for x in self._inputs]
        sources += [x.name for x in self._presets]

        return sources

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        if self._status is None or (self.is_grouped and not self.is_leader):
            return None

        if self._status.input_id is not None:
            for input_ in self._inputs:
                if input_.id == self._status.input_id:
                    return input_.text

        for preset in self._presets:
            if preset.url == self._status.stream_url:
                return preset.name

        return self._status.service

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag of media commands that are supported."""
        if self._status is None:
            return MediaPlayerEntityFeature(0)

        if self.is_grouped and not self.is_leader:
            return (
                MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_MUTE
            )

        supported = (
            MediaPlayerEntityFeature.CLEAR_PLAYLIST
            | MediaPlayerEntityFeature.BROWSE_MEDIA
        )

        if not self._status.indexing:
            supported = (
                supported
                | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
                | MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.SELECT_SOURCE
                | MediaPlayerEntityFeature.SHUFFLE_SET
            )

        current_vol = self.volume_level
        if current_vol is not None and current_vol >= 0:
            supported = (
                supported
                | MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_MUTE
            )

        if self._status.can_seek:
            supported = supported | MediaPlayerEntityFeature.SEEK

        return supported

    @property
    def is_leader(self) -> bool:
        """Return true if player is leader of a group."""
        return self._sync_status.followers is not None

    @property
    def is_grouped(self) -> bool:
        """Return true if player is member or leader of a group."""
        return (
            self._sync_status.followers is not None
            or self._sync_status.leader is not None
        )

    @property
    def shuffle(self) -> bool:
        """Return true if shuffle is active."""
        shuffle = False
        if self._status is not None:
            shuffle = self._status.shuffle

        return shuffle

    async def async_join(self, master: str) -> None:
        """Join the player to a group."""
        if master == self.entity_id:
            raise ServiceValidationError("Cannot join player to itself")

        _LOGGER.debug("Trying to join player: %s", self.id)
        async_dispatcher_send(
            self.hass, dispatcher_join_signal(master), self.host, self.port
        )

    async def async_unjoin(self) -> None:
        """Unjoin the player from a group."""
        if self._sync_status.leader is None:
            return

        leader_id = f"{self._sync_status.leader.ip}:{self._sync_status.leader.port}"

        _LOGGER.debug("Trying to unjoin player: %s", self.id)
        async_dispatcher_send(
            self.hass, dispatcher_unjoin_signal(leader_id), self.host, self.port
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """List members in group."""
        attributes: dict[str, Any] = {}
        if self._group_list:
            attributes = {ATTR_BLUESOUND_GROUP: self._group_list}

        attributes[ATTR_MASTER] = self.is_leader

        return attributes

    def rebuild_bluesound_group(self) -> list[str]:
        """Rebuild the list of entities in speaker group."""
        if self.sync_status.leader is None and self.sync_status.followers is None:
            return []

        player_entities: list[BluesoundPlayer] = self.hass.data[DATA_BLUESOUND]

        leader_sync_status: SyncStatus | None = None
        if self.sync_status.leader is None:
            leader_sync_status = self.sync_status
        else:
            required_id = f"{self.sync_status.leader.ip}:{self.sync_status.leader.port}"
            for x in player_entities:
                if x.sync_status.id == required_id:
                    leader_sync_status = x.sync_status
                    break

        if leader_sync_status is None or leader_sync_status.followers is None:
            return []

        follower_ids = [f"{x.ip}:{x.port}" for x in leader_sync_status.followers]
        follower_names = [
            x.sync_status.name
            for x in player_entities
            if x.sync_status.id in follower_ids
        ]
        follower_names.insert(0, leader_sync_status.name)
        return follower_names

    async def async_add_follower(self, host: str, port: int) -> None:
        """Add follower to leader."""
        await self._player.add_follower(host, port)

    async def async_remove_follower(self, host: str, port: int) -> None:
        """Remove follower to leader."""
        await self._player.remove_follower(host, port)

    async def async_increase_timer(self) -> int:
        """Increase sleep time on player."""
        return await self._player.sleep_timer()

    async def async_clear_timer(self) -> None:
        """Clear sleep timer on player."""
        sleep = 1
        while sleep > 0:
            sleep = await self._player.sleep_timer()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable or disable shuffle mode."""
        await self._player.shuffle(shuffle)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if self.is_grouped and not self.is_leader:
            return

        # presets and inputs might have the same name; presets have priority
        url: str | None = None
        for input_ in self._inputs:
            if input_.text == source:
                url = input_.url
        for preset in self._presets:
            if preset.name == source:
                url = preset.url

        if url is None:
            raise ServiceValidationError(f"Source {source} not found")

        await self._player.play_url(url)

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        if self.is_grouped and not self.is_leader:
            return

        await self._player.clear()

    async def async_media_next_track(self) -> None:
        """Send media_next command to media player."""
        if self.is_grouped and not self.is_leader:
            return

        await self._player.skip()

    async def async_media_previous_track(self) -> None:
        """Send media_previous command to media player."""
        if self.is_grouped and not self.is_leader:
            return

        await self._player.back()

    async def async_media_play(self) -> None:
        """Send media_play command to media player."""
        if self.is_grouped and not self.is_leader:
            return

        await self._player.play()

    async def async_media_pause(self) -> None:
        """Send media_pause command to media player."""
        if self.is_grouped and not self.is_leader:
            return

        await self._player.pause()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        if self.is_grouped and not self.is_leader:
            return

        await self._player.stop()

    async def async_media_seek(self, position: float) -> None:
        """Send media_seek command to media player."""
        if self.is_grouped and not self.is_leader:
            return

        await self._player.play(seek=int(position))

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play_media command to the media player."""
        if self.is_grouped and not self.is_leader:
            return

        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

        url = async_process_play_media_url(self.hass, media_id)

        await self._player.play_url(url)

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        if self.volume_level is None:
            return

        new_volume = self.volume_level + 0.01
        new_volume = min(1, new_volume)
        await self.async_set_volume_level(new_volume)

    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        if self.volume_level is None:
            return

        new_volume = self.volume_level - 0.01
        new_volume = max(0, new_volume)
        await self.async_set_volume_level(new_volume)

    async def async_set_volume_level(self, volume: float) -> None:
        """Send volume_up command to media player."""
        volume = int(round(volume * 100))
        volume = min(100, volume)
        volume = max(0, volume)

        await self._player.volume(level=volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command to media player."""
        await self._player.volume(mute=mute)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )
