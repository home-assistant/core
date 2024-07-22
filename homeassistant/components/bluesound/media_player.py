"""Support for Bluesound devices."""

from __future__ import annotations

import asyncio
from asyncio import CancelledError
from contextlib import suppress
from datetime import datetime, timedelta
import logging
from typing import Any, NamedTuple

from aiohttp.client_exceptions import ClientError
from pyblu import Input, Player, Preset, Status, SyncStatus
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_HOSTS,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN,
    SERVICE_CLEAR_TIMER,
    SERVICE_JOIN,
    SERVICE_SET_TIMER,
    SERVICE_UNJOIN,
)

_LOGGER = logging.getLogger(__name__)

ATTR_BLUESOUND_GROUP = "bluesound_group"
ATTR_MASTER = "master"

DATA_BLUESOUND = "bluesound"
DEFAULT_PORT = 11000

NODE_OFFLINE_CHECK_TIMEOUT = 180
NODE_RETRY_INITIATION = timedelta(minutes=3)

SYNC_STATUS_INTERVAL = timedelta(minutes=5)

UPDATE_CAPTURE_INTERVAL = timedelta(minutes=30)
UPDATE_PRESETS_INTERVAL = timedelta(minutes=30)
UPDATE_SERVICES_INTERVAL = timedelta(minutes=30)

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOSTS): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                }
            ],
        )
    }
)


class ServiceMethodDetails(NamedTuple):
    """Details for SERVICE_TO_METHOD mapping."""

    method: str
    schema: vol.Schema


BS_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

BS_JOIN_SCHEMA = BS_SCHEMA.extend({vol.Required(ATTR_MASTER): cv.entity_id})

SERVICE_TO_METHOD = {
    SERVICE_JOIN: ServiceMethodDetails(method="async_join", schema=BS_JOIN_SCHEMA),
    SERVICE_UNJOIN: ServiceMethodDetails(method="async_unjoin", schema=BS_SCHEMA),
    SERVICE_SET_TIMER: ServiceMethodDetails(
        method="async_increase_timer", schema=BS_SCHEMA
    ),
    SERVICE_CLEAR_TIMER: ServiceMethodDetails(
        method="async_clear_timer", schema=BS_SCHEMA
    ),
}


def _add_player(hass: HomeAssistant, async_add_entities, host, port=None, name=None):
    """Add Bluesound players."""

    @callback
    def _init_player(event=None):
        """Start polling."""
        hass.async_create_task(player.async_init())

    @callback
    def _start_polling(event=None):
        """Start polling."""
        player.start_polling()

    @callback
    def _stop_polling(event=None):
        """Stop polling."""
        player.stop_polling()

    @callback
    def _add_player_cb():
        """Add player after first sync fetch."""
        if player.id in [x.id for x in hass.data[DATA_BLUESOUND]]:
            _LOGGER.warning("Player already added %s", player.id)
            return

        hass.data[DATA_BLUESOUND].append(player)
        async_add_entities([player])
        _LOGGER.info("Added device with name: %s", player.name)

        if hass.is_running:
            _start_polling()
        else:
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _start_polling)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_polling)

    player = BluesoundPlayer(hass, host, port, name, _add_player_cb)

    if hass.is_running:
        _init_player()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _init_player)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Bluesound platforms."""
    if DATA_BLUESOUND not in hass.data:
        hass.data[DATA_BLUESOUND] = []

    if discovery_info:
        _add_player(
            hass,
            async_add_entities,
            discovery_info.get(CONF_HOST),
            discovery_info.get(CONF_PORT),
        )
        return

    if hosts := config.get(CONF_HOSTS):
        for host in hosts:
            _add_player(
                hass,
                async_add_entities,
                host.get(CONF_HOST),
                host.get(CONF_PORT),
                host.get(CONF_NAME),
            )

    async def async_service_handler(service: ServiceCall) -> None:
        """Map services to method of Bluesound devices."""
        if not (method := SERVICE_TO_METHOD.get(service.service)):
            return

        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        if entity_ids := service.data.get(ATTR_ENTITY_ID):
            target_players = [
                player
                for player in hass.data[DATA_BLUESOUND]
                if player.entity_id in entity_ids
            ]
        else:
            target_players = hass.data[DATA_BLUESOUND]

        for player in target_players:
            await getattr(player, method.method)(**params)

    for service, method in SERVICE_TO_METHOD.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=method.schema
        )


class BluesoundPlayer(MediaPlayerEntity):
    """Representation of a Bluesound Player."""

    _attr_media_content_type = MediaType.MUSIC

    def __init__(
        self, hass: HomeAssistant, host, port=None, name=None, init_callback=None
    ) -> None:
        """Initialize the media player."""
        self.host = host
        self._hass = hass
        self.port = port
        self._polling_task = None  # The actual polling task.
        self._name = name
        self._id = None
        self._last_status_update = None
        self._sync_status: SyncStatus | None = None
        self._status: Status | None = None
        self._inputs: list[Input] = []
        self._presets: list[Preset] = []
        self._is_online = False
        self._retry_remove = None
        self._muted = False
        self._master: BluesoundPlayer | None = None
        self._is_master = False
        self._group_name = None
        self._group_list: list[str] = []
        self._bluesound_device_name = None
        self._player = Player(
            host, port, async_get_clientsession(hass), default_timeout=10
        )

        self._init_callback = init_callback

        if self.port is None:
            self.port = DEFAULT_PORT

    @staticmethod
    def _try_get_index(string, search_string):
        """Get the index."""
        try:
            return string.index(search_string)
        except ValueError:
            return -1

    async def force_update_sync_status(self, on_updated_cb=None) -> bool:
        """Update the internal status."""
        sync_status = await self._player.sync_status()

        self._sync_status = sync_status

        if not self._name:
            self._name = sync_status.name if sync_status.name else self.host
        if not self._id:
            self._id = sync_status.id
        if not self._bluesound_device_name:
            self._bluesound_device_name = self._name

        if sync_status.master is not None:
            self._is_master = False
            master_id = f"{sync_status.master.ip}:{sync_status.master.port}"
            master_device = [
                device
                for device in self._hass.data[DATA_BLUESOUND]
                if device.id == master_id
            ]

            if master_device and master_id != self.id:
                self._master = master_device[0]
            else:
                self._master = None
                _LOGGER.error("Master not found %s", master_id)
        else:
            if self._master is not None:
                self._master = None
            slaves = self._sync_status.slaves
            self._is_master = slaves is not None

        if on_updated_cb:
            on_updated_cb()
        return True

    async def _start_poll_command(self):
        """Loop which polls the status of the player."""
        try:
            while True:
                await self.async_update_status()

        except (TimeoutError, ClientError):
            _LOGGER.info("Node %s:%s is offline, retrying later", self.name, self.port)
            await asyncio.sleep(NODE_OFFLINE_CHECK_TIMEOUT)
            self.start_polling()

        except CancelledError:
            _LOGGER.debug("Stopping the polling of node %s:%s", self.name, self.port)
        except Exception:
            _LOGGER.exception("Unexpected error in %s:%s", self.name, self.port)
            raise

    def start_polling(self):
        """Start the polling task."""
        self._polling_task = self._hass.async_create_task(self._start_poll_command())

    def stop_polling(self):
        """Stop the polling task."""
        self._polling_task.cancel()

    async def async_init(self, triggered=None):
        """Initialize the player async."""
        try:
            if self._retry_remove is not None:
                self._retry_remove()
                self._retry_remove = None

            await self.force_update_sync_status(self._init_callback)
        except (TimeoutError, ClientError):
            _LOGGER.info("Node %s:%s is offline, retrying later", self.host, self.port)
            self._retry_remove = async_track_time_interval(
                self._hass, self.async_init, NODE_RETRY_INITIATION
            )
        except Exception:
            _LOGGER.exception(
                "Unexpected when initiating error in %s:%s", self.host, self.port
            )
            raise

    async def async_update(self) -> None:
        """Update internal status of the entity."""
        if not self._is_online:
            return

        with suppress(TimeoutError):
            await self.async_update_sync_status()
            await self.async_update_presets()
            await self.async_update_captures()

    async def async_update_status(self):
        """Use the poll session to always get the status of the player."""
        etag = None
        if self._status is not None:
            etag = self._status.etag

        try:
            status = await self._player.status(etag=etag, poll_timeout=120, timeout=125)

            self._is_online = True
            self._last_status_update = dt_util.utcnow()
            self._status = status

            group_name = status.group_name
            if group_name != self._group_name:
                _LOGGER.debug("Group name change detected on device: %s", self.id)
                self._group_name = group_name

                # rebuild ordered list of entity_ids that are in the group, master is first
                self._group_list = self.rebuild_bluesound_group()

                # the sleep is needed to make sure that the
                # devices is synced
                await asyncio.sleep(1)
                await self.async_trigger_sync_on_all()
            elif self.is_grouped:
                # when player is grouped we need to fetch volume from
                # sync_status. We will force an update if the player is
                # grouped this isn't a foolproof solution. A better
                # solution would be to fetch sync_status more often when
                # the device is playing. This would solve a lot of
                # problems. This change will be done when the
                # communication is moved to a separate library
                with suppress(TimeoutError):
                    await self.force_update_sync_status()

            self.async_write_ha_state()
        except (TimeoutError, ClientError):
            self._is_online = False
            self._last_status_update = None
            self._status = None
            self.async_write_ha_state()
            _LOGGER.info("Client connection error, marking %s as offline", self._name)
            raise

    @property
    def unique_id(self) -> str | None:
        """Return an unique ID."""
        assert self._sync_status is not None
        return f"{format_mac(self._sync_status.mac)}-{self.port}"

    async def async_trigger_sync_on_all(self):
        """Trigger sync status update on all devices."""
        _LOGGER.debug("Trigger sync status on all devices")

        for player in self._hass.data[DATA_BLUESOUND]:
            await player.force_update_sync_status()

    @Throttle(SYNC_STATUS_INTERVAL)
    async def async_update_sync_status(self, on_updated_cb=None):
        """Update sync status."""
        await self.force_update_sync_status(on_updated_cb)

    @Throttle(UPDATE_CAPTURE_INTERVAL)
    async def async_update_captures(self) -> list[Input] | None:
        """Update Capture sources."""
        inputs = await self._player.inputs()
        self._inputs = inputs

        return inputs

    @Throttle(UPDATE_PRESETS_INTERVAL)
    async def async_update_presets(self) -> list[Preset] | None:
        """Update Presets."""
        presets = await self._player.presets()
        self._presets = presets

        return presets

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        if self._status is None:
            return MediaPlayerState.OFF

        if self.is_grouped and not self.is_master:
            return MediaPlayerState.IDLE

        status = self._status.state
        if status in ("pause", "stop"):
            return MediaPlayerState.PAUSED
        if status in ("stream", "play"):
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if self._status is None or (self.is_grouped and not self.is_master):
            return None

        return self._status.name

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media (Music track only)."""
        if self._status is None:
            return None

        if self.is_grouped and not self.is_master:
            return self._group_name

        return self._status.artist

    @property
    def media_album_name(self) -> str | None:
        """Artist of current playing media (Music track only)."""
        if self._status is None or (self.is_grouped and not self.is_master):
            return None

        return self._status.album

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if self._status is None or (self.is_grouped and not self.is_master):
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
        if self._status is None or (self.is_grouped and not self.is_master):
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
        if self._status is None or (self.is_grouped and not self.is_master):
            return None

        duration = self._status.total_seconds
        if duration is None:
            return None

        return duration

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
        if self.is_grouped and self._sync_status is not None:
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
        if self.is_grouped and self._sync_status is not None:
            mute = self._sync_status.mute_volume is not None

        return mute

    @property
    def id(self) -> str | None:
        """Get id of device."""
        return self._id

    @property
    def name(self) -> str | None:
        """Return the name of the device."""
        return self._name

    @property
    def bluesound_device_name(self) -> str | None:
        """Return the device name as returned by the device."""
        return self._bluesound_device_name

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        if self._status is None or (self.is_grouped and not self.is_master):
            return None

        sources = [x.text for x in self._inputs]
        sources += [x.name for x in self._presets]

        return sources

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        if self._status is None or (self.is_grouped and not self.is_master):
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

        if self.is_grouped and not self.is_master:
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
    def is_master(self) -> bool:
        """Return true if player is a coordinator."""
        return self._is_master

    @property
    def is_grouped(self) -> bool:
        """Return true if player is a coordinator."""
        return self._master is not None or self._is_master

    @property
    def shuffle(self) -> bool:
        """Return true if shuffle is active."""
        shuffle = False
        if self._status is not None:
            shuffle = self._status.shuffle

        return shuffle

    async def async_join(self, master):
        """Join the player to a group."""
        master_device = [
            device
            for device in self.hass.data[DATA_BLUESOUND]
            if device.entity_id == master
        ]

        if len(master_device) > 0:
            if self.id == master_device[0].id:
                raise ServiceValidationError("Cannot join player to itself")

            _LOGGER.debug(
                "Trying to join player: %s to master: %s",
                self.id,
                master_device[0].id,
            )

            await master_device[0].async_add_slave(self)
        else:
            _LOGGER.error("Master not found %s", master_device)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """List members in group."""
        attributes: dict[str, Any] = {}
        if self._group_list:
            attributes = {ATTR_BLUESOUND_GROUP: self._group_list}

        attributes[ATTR_MASTER] = self._is_master

        return attributes

    def rebuild_bluesound_group(self) -> list[str]:
        """Rebuild the list of entities in speaker group."""
        if self._group_name is None:
            return []

        device_group = self._group_name.split("+")

        sorted_entities = sorted(
            self._hass.data[DATA_BLUESOUND],
            key=lambda entity: entity.is_master,
            reverse=True,
        )
        return [
            entity.name
            for entity in sorted_entities
            if entity.bluesound_device_name in device_group
        ]

    async def async_unjoin(self):
        """Unjoin the player from a group."""
        if self._master is None:
            return

        _LOGGER.debug("Trying to unjoin player: %s", self.id)
        await self._master.async_remove_slave(self)

    async def async_add_slave(self, slave_device: BluesoundPlayer):
        """Add slave to master."""
        await self._player.add_slave(slave_device.host, slave_device.port)

    async def async_remove_slave(self, slave_device: BluesoundPlayer):
        """Remove slave to master."""
        await self._player.remove_slave(slave_device.host, slave_device.port)

    async def async_increase_timer(self) -> int:
        """Increase sleep time on player."""
        return await self._player.sleep_timer()

    async def async_clear_timer(self):
        """Clear sleep timer on player."""
        sleep = 1
        while sleep > 0:
            sleep = await self._player.sleep_timer()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable or disable shuffle mode."""
        await self._player.shuffle(shuffle)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if self.is_grouped and not self.is_master:
            return

        # presets and inputs might have the same name; presets have priority
        url: str | None = None
        for input_ in self._inputs:
            if input_.text == source:
                url = input_.url
        for preset in self._presets:
            if preset.name == source:
                url = preset.url

        await self._player.play_url(url)

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        if self.is_grouped and not self.is_master:
            return

        await self._player.clear()

    async def async_media_next_track(self) -> None:
        """Send media_next command to media player."""
        if self.is_grouped and not self.is_master:
            return

        await self._player.skip()

    async def async_media_previous_track(self) -> None:
        """Send media_previous command to media player."""
        if self.is_grouped and not self.is_master:
            return

        await self._player.back()

    async def async_media_play(self) -> None:
        """Send media_play command to media player."""
        if self.is_grouped and not self.is_master:
            return

        await self._player.play()

    async def async_media_pause(self) -> None:
        """Send media_pause command to media player."""
        if self.is_grouped and not self.is_master:
            return

        await self._player.pause()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        if self.is_grouped and not self.is_master:
            return

        await self._player.stop()

    async def async_media_seek(self, position: float) -> None:
        """Send media_seek command to media player."""
        if self.is_grouped and not self.is_master:
            return

        await self._player.play(seek=int(position))

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play_media command to the media player."""
        if self.is_grouped and not self.is_master:
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
            return None

        new_volume = self.volume_level + 0.01
        new_volume = min(1, new_volume)
        return await self.async_set_volume_level(new_volume)

    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        if self.volume_level is None:
            return None

        new_volume = self.volume_level - 0.01
        new_volume = max(0, new_volume)
        return await self.async_set_volume_level(new_volume)

    async def async_set_volume_level(self, volume: float) -> None:
        """Send volume_up command to media player."""
        volume = int(volume * 100)
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
