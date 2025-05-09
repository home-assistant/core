"""Support for interfacing to the SqueezeBox API."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json
import logging
from typing import TYPE_CHECKING, Any

from pysqueezebox import Server, async_discover
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EXTRA,
    BrowseError,
    BrowseMedia,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import ATTR_COMMAND, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    discovery_flow,
    entity_platform,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.start import async_at_start
from homeassistant.util.dt import utcnow

from .browse_media import (
    BrowseData,
    build_item_response,
    generate_playlist,
    library_payload,
    media_source_content_filter,
)
from .const import (
    ATTR_ANNOUNCE_TIMEOUT,
    ATTR_ANNOUNCE_VOLUME,
    CONF_BROWSE_LIMIT,
    CONF_VOLUME_STEP,
    DEFAULT_BROWSE_LIMIT,
    DEFAULT_VOLUME_STEP,
    DISCOVERY_TASK,
    DOMAIN,
    KNOWN_PLAYERS,
    KNOWN_SERVERS,
    SIGNAL_PLAYER_DISCOVERED,
    SQUEEZEBOX_SOURCE_STRINGS,
)
from .coordinator import SqueezeBoxPlayerUpdateCoordinator
from .entity import SqueezeboxEntity

if TYPE_CHECKING:
    from . import SqueezeboxConfigEntry

SERVICE_CALL_METHOD = "call_method"
SERVICE_CALL_QUERY = "call_query"

ATTR_QUERY_RESULT = "query_result"

_LOGGER = logging.getLogger(__name__)


ATTR_PARAMETERS = "parameters"
ATTR_OTHER_PLAYER = "other_player"

ATTR_TO_PROPERTY = [
    ATTR_QUERY_RESULT,
]

SQUEEZEBOX_MODE = {
    "pause": MediaPlayerState.PAUSED,
    "play": MediaPlayerState.PLAYING,
    "stop": MediaPlayerState.IDLE,
}


async def start_server_discovery(hass: HomeAssistant) -> None:
    """Start a server discovery task."""

    def _discovered_server(server: Server) -> None:
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data={
                CONF_HOST: server.host,
                CONF_PORT: int(server.port),
                "uuid": server.uuid,
            },
        )

    hass.data.setdefault(DOMAIN, {})
    if DISCOVERY_TASK not in hass.data[DOMAIN]:
        _LOGGER.debug("Adding server discovery task for squeezebox")
        hass.data[DOMAIN][DISCOVERY_TASK] = hass.async_create_background_task(
            async_discover(_discovered_server),
            name="squeezebox server discovery",
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SqueezeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Squeezebox media_player platform from a server config entry."""

    # Add media player entities when discovered
    async def _player_discovered(player: SqueezeBoxPlayerUpdateCoordinator) -> None:
        _LOGGER.debug("Setting up media_player entity for player %s", player)
        async_add_entities([SqueezeBoxMediaPlayerEntity(player)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PLAYER_DISCOVERED, _player_discovered)
    )

    # Register entity services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CALL_METHOD,
        {
            vol.Required(ATTR_COMMAND): cv.string,
            vol.Optional(ATTR_PARAMETERS): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
        },
        "async_call_method",
    )
    platform.async_register_entity_service(
        SERVICE_CALL_QUERY,
        {
            vol.Required(ATTR_COMMAND): cv.string,
            vol.Optional(ATTR_PARAMETERS): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
        },
        "async_call_query",
    )

    # Start server discovery task if not already running
    entry.async_on_unload(async_at_start(hass, start_server_discovery))


def get_announce_volume(extra: dict) -> float | None:
    """Get announce volume from extra service data."""
    if ATTR_ANNOUNCE_VOLUME not in extra:
        return None
    announce_volume = float(extra[ATTR_ANNOUNCE_VOLUME])
    if not (0 < announce_volume <= 1):
        raise ValueError
    return announce_volume * 100


def get_announce_timeout(extra: dict) -> int | None:
    """Get announce volume from extra service data."""
    if ATTR_ANNOUNCE_TIMEOUT not in extra:
        return None
    announce_timeout = int(extra[ATTR_ANNOUNCE_TIMEOUT])
    if announce_timeout < 1:
        raise ValueError
    return announce_timeout


class SqueezeBoxMediaPlayerEntity(SqueezeboxEntity, MediaPlayerEntity):
    """Representation of the media player features of a SqueezeBox device.

    Wraps a pysqueezebox.Player() object.
    """

    _attr_supported_features = (
        MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.REPEAT_SET
        | MediaPlayerEntityFeature.SHUFFLE_SET
        | MediaPlayerEntityFeature.CLEAR_PLAYLIST
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.GROUPING
        | MediaPlayerEntityFeature.MEDIA_ENQUEUE
        | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
    )
    _attr_has_entity_name = True
    _attr_name = None
    _last_update: datetime | None = None

    def __init__(self, coordinator: SqueezeBoxPlayerUpdateCoordinator) -> None:
        """Initialize the SqueezeBox device."""
        super().__init__(coordinator)
        self._query_result: bool | dict = {}
        self._remove_dispatcher: Callable | None = None
        self._previous_media_position = 0
        self._attr_unique_id = format_mac(self._player.player_id)
        self._browse_data = BrowseData()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._previous_media_position != self.media_position:
            self._previous_media_position = self.media_position
            self._last_update = utcnow()
        self.async_write_ha_state()

    @property
    def volume_step(self) -> float:
        """Return the step to be used for volume up down."""
        return float(
            self.coordinator.config_entry.options.get(
                CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
            )
            / 100
        )

    @property
    def browse_limit(self) -> int:
        """Return the step to be used for volume up down."""
        return self.coordinator.config_entry.options.get(
            CONF_BROWSE_LIMIT, DEFAULT_BROWSE_LIMIT
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.available and super().available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device-specific attributes."""
        return {
            attr: getattr(self, attr)
            for attr in ATTR_TO_PROPERTY
            if getattr(self, attr) is not None
        }

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if not self._player.power:
            return MediaPlayerState.OFF
        if self._player.mode and self._player.mode in SQUEEZEBOX_MODE:
            return SQUEEZEBOX_MODE[self._player.mode]
        _LOGGER.error(
            "Received unknown mode %s from player %s", self._player.mode, self.name
        )
        return None

    async def async_will_remove_from_hass(self) -> None:
        """Remove from list of known players when removed from hass."""
        known_servers = self.hass.data[DOMAIN][KNOWN_SERVERS]
        known_players = known_servers[self.coordinator.server_uuid][KNOWN_PLAYERS]
        known_players.remove(self.coordinator.player.player_id)

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if self._player.volume:
            return int(float(self._player.volume)) / 100.0

        return None

    @property
    def is_volume_muted(self) -> bool:
        """Return true if volume is muted."""
        return bool(self._player.muting)

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        if not self._player.playlist:
            return None
        if len(self._player.playlist) > 1:
            urls = [{"url": track["url"]} for track in self._player.playlist]
            return json.dumps({"index": self._player.current_index, "urls": urls})
        return str(self._player.url)

    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        if not self._player.playlist:
            return None
        if len(self._player.playlist) > 1:
            return MediaType.PLAYLIST
        return MediaType.MUSIC

    @property
    def media_duration(self) -> int:
        """Duration of current playing media in seconds."""
        return int(self._player.duration) if self._player.duration else 0

    @property
    def media_position(self) -> int:
        """Position of current playing media in seconds."""
        return int(self._player.time) if self._player.time else 0

    @property
    def media_position_updated_at(self) -> datetime | None:
        """Last time status was updated."""
        return self._last_update

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return str(self._player.image_url) if self._player.image_url else None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return str(self._player.title)

    @property
    def media_channel(self) -> str | None:
        """Channel (e.g. webradio name) of current playing media."""
        return str(self._player.remote_title)

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media."""
        return str(self._player.artist)

    @property
    def media_album_name(self) -> str | None:
        """Album of current playing media."""
        return str(self._player.album)

    @property
    def repeat(self) -> RepeatMode:
        """Repeat setting."""
        if self._player.repeat == "song":
            return RepeatMode.ONE
        if self._player.repeat == "playlist":
            return RepeatMode.ALL
        return RepeatMode.OFF

    @property
    def shuffle(self) -> bool:
        """Boolean if shuffle is enabled."""
        # Squeezebox has a third shuffle mode (album) not recognized by Home Assistant
        return bool(self._player.shuffle == "song")

    @property
    def group_members(self) -> list[str]:
        """List players we are synced with."""
        ent_reg = er.async_get(self.hass)
        return [
            entity_id
            for player in self._player.sync_group
            if (
                entity_id := ent_reg.async_get_entity_id(
                    Platform.MEDIA_PLAYER, DOMAIN, player
                )
            )
        ]

    @property
    def query_result(self) -> dict | bool:
        """Return the result from the call_query service."""
        return self._query_result

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self._player.async_set_power(False)
        await self.coordinator.async_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        volume_percent = str(int(volume * 100))
        await self._player.async_set_volume(volume_percent)
        await self.coordinator.async_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._player.async_set_muting(mute)
        await self.coordinator.async_refresh()

    async def async_media_stop(self) -> None:
        """Send stop command to media player."""
        await self._player.async_stop()
        await self.coordinator.async_refresh()

    async def async_media_play_pause(self) -> None:
        """Send pause command to media player."""
        await self._player.async_toggle_pause()
        await self.coordinator.async_refresh()

    async def async_media_play(self) -> None:
        """Send play command to media player."""
        await self._player.async_play()
        await self.coordinator.async_refresh()

    async def async_media_pause(self) -> None:
        """Send pause command to media player."""
        await self._player.async_pause()
        await self.coordinator.async_refresh()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._player.async_index("+1")
        await self.coordinator.async_refresh()

    async def async_media_previous_track(self) -> None:
        """Send next track command."""
        await self._player.async_index("-1")
        await self.coordinator.async_refresh()

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self._player.async_time(position)
        await self.coordinator.async_refresh()

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._player.async_set_power(True)
        await self.coordinator.async_refresh()

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Send the play_media command to the media player."""
        index = None

        if media_type:
            media_type = media_type.lower()

        enqueue: MediaPlayerEnqueue | None = kwargs.get(ATTR_MEDIA_ENQUEUE)

        if enqueue == MediaPlayerEnqueue.ADD:
            cmd = "add"
        elif enqueue == MediaPlayerEnqueue.NEXT:
            cmd = "insert"
        elif enqueue == MediaPlayerEnqueue.PLAY:
            cmd = "play_now"
        else:
            cmd = "play"

        if media_source.is_media_source_id(media_id):
            media_type = MediaType.MUSIC
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

        if announce:
            if media_type not in MediaType.MUSIC:
                raise ServiceValidationError(
                    "Announcements must have media type of 'music'.  Playlists are not supported"
                )

            extra = kwargs.get(ATTR_MEDIA_EXTRA, {})
            cmd = "announce"
            try:
                announce_volume = get_announce_volume(extra)
            except ValueError:
                raise ServiceValidationError(
                    f"{ATTR_ANNOUNCE_VOLUME} must be a number greater than 0 and less than or equal to 1"
                ) from None
            else:
                self._player.set_announce_volume(announce_volume)

            try:
                announce_timeout = get_announce_timeout(extra)
            except ValueError:
                raise ServiceValidationError(
                    f"{ATTR_ANNOUNCE_TIMEOUT} must be a whole number greater than 0"
                ) from None
            else:
                self._player.set_announce_timeout(announce_timeout)

        if media_type in MediaType.MUSIC:
            if not media_id.startswith(SQUEEZEBOX_SOURCE_STRINGS):
                # do not process special squeezebox "source" media ids
                media_id = async_process_play_media_url(self.hass, media_id)

            await self._player.async_load_url(media_id, cmd)
            return

        if media_type == MediaType.PLAYLIST:
            try:
                # a saved playlist by number
                payload = {
                    "search_id": media_id,
                    "search_type": MediaType.PLAYLIST,
                }
                playlist = await generate_playlist(
                    self._player, payload, self.browse_limit, self._browse_data
                )
            except BrowseError:
                # a list of urls
                content = json.loads(media_id)
                playlist = content["urls"]
                index = content["index"]
        else:
            payload = {
                "search_id": media_id,
                "search_type": media_type,
            }
            playlist = await generate_playlist(
                self._player, payload, self.browse_limit, self._browse_data
            )

            _LOGGER.debug("Generated playlist: %s", playlist)

        await self._player.async_load_playlist(playlist, cmd)
        if index is not None:
            await self._player.async_index(index)
        await self.coordinator.async_refresh()

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set the repeat mode."""
        if repeat == RepeatMode.ALL:
            repeat_mode = "playlist"
        elif repeat == RepeatMode.ONE:
            repeat_mode = "song"
        else:
            repeat_mode = "none"

        await self._player.async_set_repeat(repeat_mode)
        await self.coordinator.async_refresh()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        shuffle_mode = "song" if shuffle else "none"
        await self._player.async_set_shuffle(shuffle_mode)
        await self.coordinator.async_refresh()

    async def async_clear_playlist(self) -> None:
        """Send the media player the command for clear playlist."""
        await self._player.async_clear_playlist()
        await self.coordinator.async_refresh()

    async def async_call_method(
        self, command: str, parameters: list[str] | None = None
    ) -> None:
        """Call Squeezebox JSON/RPC method.

        Additional parameters are added to the command to form the list of
        positional parameters (p0, p1...,  pN) passed to JSON/RPC server.
        """
        all_params = [command]
        if parameters:
            all_params.extend(parameters)
        await self._player.async_query(*all_params)

    async def async_call_query(
        self, command: str, parameters: list[str] | None = None
    ) -> None:
        """Call Squeezebox JSON/RPC method where we care about the result.

        Additional parameters are added to the command to form the list of
        positional parameters (p0, p1...,  pN) passed to JSON/RPC server.
        """
        all_params = [command]
        if parameters:
            all_params.extend(parameters)
        self._query_result = await self._player.async_query(*all_params)
        _LOGGER.debug("call_query got result %s", self._query_result)
        self.async_write_ha_state()

    async def async_join_players(self, group_members: list[str]) -> None:
        """Add other Squeezebox players to this player's sync group.

        If the other player is a member of a sync group, it will leave the current sync group
        without asking.
        """
        ent_reg = er.async_get(self.hass)
        for other_player_entity_id in group_members:
            other_player = ent_reg.async_get(other_player_entity_id)
            if other_player is None:
                raise ServiceValidationError(
                    f"Could not find player with entity_id {other_player_entity_id}"
                )
            if other_player_id := other_player.unique_id:
                await self._player.async_sync(other_player_id)
            else:
                raise ServiceValidationError(
                    f"Could not join unknown player {other_player_entity_id}"
                )

    async def async_unjoin_player(self) -> None:
        """Unsync this Squeezebox player."""
        await self._player.async_unsync()
        await self.coordinator.async_refresh()

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        _LOGGER.debug(
            "Reached async_browse_media with content_type %s and content_id %s",
            media_content_type,
            media_content_id,
        )

        if media_content_type:
            media_content_type = media_content_type.lower()

        if media_content_type in [None, "library"]:
            return await library_payload(self.hass, self._player, self._browse_data)

        if media_content_id and media_source.is_media_source_id(media_content_id):
            return await media_source.async_browse_media(
                self.hass, media_content_id, content_filter=media_source_content_filter
            )

        payload = {
            "search_type": media_content_type,
            "search_id": media_content_id,
        }

        return await build_item_response(
            self,
            self._player,
            payload,
            self.browse_limit,
            self._browse_data,
        )

    async def async_get_browse_image(
        self,
        media_content_type: MediaType | str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Get album art from Squeezebox server."""
        if media_image_id:
            image_url = self._player.generate_image_url_from_track_id(media_image_id)
            result = await self._async_fetch_image(image_url)
            if result == (None, None):
                _LOGGER.debug("Error retrieving proxied album art from %s", image_url)
            return result

        return (None, None)
