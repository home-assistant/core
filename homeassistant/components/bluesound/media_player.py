"""Support for Bluesound devices."""

from __future__ import annotations

import asyncio
from asyncio import CancelledError, Task
from contextlib import suppress
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, NamedTuple

from pyblu import Input, Player, Preset, Status, SyncStatus
from pyblu.errors import PlayerUnreachableError
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
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_HOSTS,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    ServiceCall,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_BLUESOUND_GROUP,
    ATTR_MASTER,
    DOMAIN,
    INTEGRATION_TITLE,
    SERVICE_CLEAR_TIMER,
    SERVICE_JOIN,
    SERVICE_SET_TIMER,
    SERVICE_UNJOIN,
)
from .utils import format_unique_id

if TYPE_CHECKING:
    from . import BluesoundConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)

DATA_BLUESOUND = DOMAIN
DEFAULT_PORT = 11000

NODE_OFFLINE_CHECK_TIMEOUT = 180
NODE_RETRY_INITIATION = timedelta(minutes=3)

SYNC_STATUS_INTERVAL = timedelta(minutes=5)

POLL_TIMEOUT = 120

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

BS_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

BS_JOIN_SCHEMA = BS_SCHEMA.extend({vol.Required(ATTR_MASTER): cv.entity_id})


class ServiceMethodDetails(NamedTuple):
    """Details for SERVICE_TO_METHOD mapping."""

    method: str
    schema: vol.Schema


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


async def _async_import(hass: HomeAssistant, config: ConfigType) -> None:
    """Import config entry from configuration.yaml."""
    if not hass.config_entries.async_entries(DOMAIN):
        # Start import flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
        if (
            result["type"] == FlowResultType.ABORT
            and result["reason"] == "cannot_connect"
        ):
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{result['reason']}",
                breaks_in_ha_version="2025.2.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": INTEGRATION_TITLE,
                },
            )
            return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2025.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


def setup_services(hass: HomeAssistant) -> None:
    """Set up services for Bluesound component."""

    async def async_service_handler(service: ServiceCall) -> None:
        """Map services to method of Bluesound devices."""
        if not (method := SERVICE_TO_METHOD.get(service.service)):
            return

        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        if entity_ids := service.data.get(ATTR_ENTITY_ID):
            target_players = [
                player for player in hass.data[DOMAIN] if player.entity_id in entity_ids
            ]
        else:
            target_players = hass.data[DOMAIN]

        for player in target_players:
            await getattr(player, method.method)(**params)

    for service, method in SERVICE_TO_METHOD.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=method.schema
        )


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

    hass.data[DATA_BLUESOUND].append(bluesound_player)
    async_add_entities([bluesound_player], update_before_add=True)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Trigger import flows."""
    hosts = config.get(CONF_HOSTS, [])
    for host in hosts:
        import_data = {
            CONF_HOST: host[CONF_HOST],
            CONF_PORT: host.get(CONF_PORT, 11000),
        }
        hass.async_create_task(_async_import(hass, import_data))


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
        self._muted = False
        self._master: BluesoundPlayer | None = None
        self._is_master = False
        self._group_name: str | None = None
        self._group_list: list[str] = []
        self._bluesound_device_name = sync_status.name
        self._player = player

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

            group_name = status.group_name
            if group_name != self._group_name:
                _LOGGER.debug("Group name change detected on device: %s", self.id)
                self._group_name = group_name

                # rebuild ordered list of entity_ids that are in the group, master is first
                self._group_list = self.rebuild_bluesound_group()

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

        if sync_status.master is not None:
            self._is_master = False
            master_id = f"{sync_status.master.ip}:{sync_status.master.port}"
            master_device = [
                device
                for device in self.hass.data[DATA_BLUESOUND]
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

    async def async_join(self, master: str) -> None:
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

        sorted_entities: list[BluesoundPlayer] = sorted(
            self.hass.data[DATA_BLUESOUND],
            key=lambda entity: entity.is_master,
            reverse=True,
        )
        return [
            entity.sync_status.name
            for entity in sorted_entities
            if entity.bluesound_device_name in device_group
        ]

    async def async_unjoin(self) -> None:
        """Unjoin the player from a group."""
        if self._master is None:
            return

        _LOGGER.debug("Trying to unjoin player: %s", self.id)
        await self._master.async_remove_slave(self)

    async def async_add_slave(self, slave_device: BluesoundPlayer) -> None:
        """Add slave to master."""
        await self._player.add_slave(slave_device.host, slave_device.port)

    async def async_remove_slave(self, slave_device: BluesoundPlayer) -> None:
        """Remove slave to master."""
        await self._player.remove_slave(slave_device.host, slave_device.port)

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

        if url is None:
            raise ServiceValidationError(f"Source {source} not found")

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
