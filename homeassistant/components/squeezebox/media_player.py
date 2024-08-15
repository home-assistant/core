"""Support for interfacing to the SqueezeBox API."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json
import logging
from typing import Any

from pysqueezebox import Player, async_discover
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import ATTR_COMMAND, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    discovery_flow,
    entity_platform,
)
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
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_start
from homeassistant.util.dt import utcnow

from . import SqueezeboxConfigEntry
from .browse_media import (
    build_item_response,
    generate_playlist,
    library_payload,
    media_source_content_filter,
)
from .const import DISCOVERY_TASK, DOMAIN, KNOWN_PLAYERS, SQUEEZEBOX_SOURCE_STRINGS

SERVICE_CALL_METHOD = "call_method"
SERVICE_CALL_QUERY = "call_query"
SERVICE_SYNC = "sync"
SERVICE_UNSYNC = "unsync"

ATTR_QUERY_RESULT = "query_result"
ATTR_SYNC_GROUP = "sync_group"

SIGNAL_PLAYER_REDISCOVERED = "squeezebox_player_rediscovered"

_LOGGER = logging.getLogger(__name__)

DISCOVERY_INTERVAL = 60


KNOWN_SERVERS = "known_servers"
ATTR_PARAMETERS = "parameters"
ATTR_OTHER_PLAYER = "other_player"

ATTR_TO_PROPERTY = [
    ATTR_QUERY_RESULT,
    ATTR_SYNC_GROUP,
]

SQUEEZEBOX_MODE = {
    "pause": MediaPlayerState.PAUSED,
    "play": MediaPlayerState.PLAYING,
    "stop": MediaPlayerState.IDLE,
}


async def start_server_discovery(hass: HomeAssistant) -> None:
    """Start a server discovery task."""

    def _discovered_server(server):
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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an player discovery from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    known_players = hass.data[DOMAIN].setdefault(KNOWN_PLAYERS, [])
    lms = entry.runtime_data

    async def _player_discovery(now=None):
        """Discover squeezebox players by polling server."""

        async def _discovered_player(player):
            """Handle a (re)discovered player."""
            entity = next(
                (
                    known
                    for known in known_players
                    if known.unique_id == player.player_id
                ),
                None,
            )
            if entity:
                await player.async_update()
                async_dispatcher_send(
                    hass, SIGNAL_PLAYER_REDISCOVERED, player.player_id, player.connected
                )

            if not entity:
                _LOGGER.debug("Adding new entity: %s", player)
                entity = SqueezeBoxEntity(player)
                known_players.append(entity)
                async_add_entities([entity])

        if players := await lms.async_get_players():
            for player in players:
                hass.async_create_task(_discovered_player(player))

        entry.async_on_unload(
            async_call_later(hass, DISCOVERY_INTERVAL, _player_discovery)
        )

    _LOGGER.debug(
        "Adding player discovery job for LMS server: %s", entry.data[CONF_HOST]
    )
    entry.async_create_background_task(
        hass, _player_discovery(), "squeezebox.media_player.player_discovery"
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
    platform.async_register_entity_service(
        SERVICE_SYNC,
        {vol.Required(ATTR_OTHER_PLAYER): cv.string},
        "async_sync",
    )
    platform.async_register_entity_service(SERVICE_UNSYNC, None, "async_unsync")

    # Start server discovery task if not already running
    entry.async_on_unload(async_at_start(hass, start_server_discovery))


class SqueezeBoxEntity(MediaPlayerEntity):
    """Representation of a SqueezeBox device.

    Wraps a pysqueezebox.Player() object.
    """

    _attr_supported_features = (
        MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
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
    )
    _attr_has_entity_name = True
    _attr_name = None
    _last_update: datetime | None = None
    _attr_available = True

    def __init__(self, player: Player) -> None:
        """Initialize the SqueezeBox device."""
        self._player = player
        self._query_result: bool | dict = {}
        self._remove_dispatcher: Callable | None = None
        self._attr_unique_id = format_mac(player.player_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=player.name,
            connections={(CONNECTION_NETWORK_MAC, self._attr_unique_id)},
        )

    @property
    def extra_state_attributes(self):
        """Return device-specific attributes."""
        return {
            attr: getattr(self, attr)
            for attr in ATTR_TO_PROPERTY
            if getattr(self, attr) is not None
        }

    @callback
    def rediscovered(self, unique_id, connected):
        """Make a player available again."""
        if unique_id == self.unique_id and connected:
            self._attr_available = True
            _LOGGER.debug("Player %s is available again", self.name)
            self._remove_dispatcher()

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if not self._player.power:
            return MediaPlayerState.OFF
        if self._player.mode:
            return SQUEEZEBOX_MODE.get(self._player.mode)
        return None

    async def async_update(self) -> None:
        """Update the Player() object."""
        # only update available players, newly available players will be rediscovered and marked available
        if self._attr_available:
            last_media_position = self.media_position
            await self._player.async_update()
            if self.media_position != last_media_position:
                self._last_update = utcnow()
            if self._player.connected is False:
                _LOGGER.debug("Player %s is not available", self.name)
                self._attr_available = False

                # start listening for restored players
                self._remove_dispatcher = async_dispatcher_connect(
                    self.hass, SIGNAL_PLAYER_REDISCOVERED, self.rediscovered
                )

    async def async_will_remove_from_hass(self) -> None:
        """Remove from list of known players when removed from hass."""
        self.hass.data[DOMAIN][KNOWN_PLAYERS].remove(self)

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if self._player.volume:
            return int(float(self._player.volume)) / 100.0
        return None

    @property
    def is_volume_muted(self):
        """Return true if volume is muted."""
        return self._player.muting

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        if not self._player.playlist:
            return None
        if len(self._player.playlist) > 1:
            urls = [{"url": track["url"]} for track in self._player.playlist]
            return json.dumps({"index": self._player.current_index, "urls": urls})
        return self._player.url

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if not self._player.playlist:
            return None
        if len(self._player.playlist) > 1:
            return MediaType.PLAYLIST
        return MediaType.MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._player.duration

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._player.time

    @property
    def media_position_updated_at(self):
        """Last time status was updated."""
        return self._last_update

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._player.image_url

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._player.title

    @property
    def media_channel(self):
        """Channel (e.g. webradio name) of current playing media."""
        return self._player.remote_title

    @property
    def media_artist(self):
        """Artist of current playing media."""
        return self._player.artist

    @property
    def media_album_name(self):
        """Album of current playing media."""
        return self._player.album

    @property
    def repeat(self):
        """Repeat setting."""
        if self._player.repeat == "song":
            return RepeatMode.ONE
        if self._player.repeat == "playlist":
            return RepeatMode.ALL
        return RepeatMode.OFF

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        # Squeezebox has a third shuffle mode (album) not recognized by Home Assistant
        return self._player.shuffle == "song"

    @property
    def group_members(self):
        """List players we are synced with."""
        player_ids = {
            p.unique_id: p.entity_id for p in self.hass.data[DOMAIN][KNOWN_PLAYERS]
        }
        return [
            player_ids[player]
            for player in self._player.sync_group
            if player in player_ids
        ]

    @property
    def sync_group(self):
        """List players we are synced with. Deprecated."""
        return self.group_members

    @property
    def query_result(self):
        """Return the result from the call_query service."""
        return self._query_result

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self._player.async_set_power(False)

    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self._player.async_set_volume("+5")

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._player.async_set_volume("-5")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        volume_percent = str(int(volume * 100))
        await self._player.async_set_volume(volume_percent)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._player.async_set_muting(mute)

    async def async_media_stop(self) -> None:
        """Send stop command to media player."""
        await self._player.async_stop()

    async def async_media_play_pause(self) -> None:
        """Send pause command to media player."""
        await self._player.async_toggle_pause()

    async def async_media_play(self) -> None:
        """Send play command to media player."""
        await self._player.async_play()

    async def async_media_pause(self) -> None:
        """Send pause command to media player."""
        await self._player.async_pause()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._player.async_index("+1")

    async def async_media_previous_track(self) -> None:
        """Send next track command."""
        await self._player.async_index("-1")

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self._player.async_time(position)

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._player.async_set_power(True)

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play_media command to the media player."""
        index = None

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
                    "search_id": int(media_id),
                    "search_type": MediaType.PLAYLIST,
                }
                playlist = await generate_playlist(self._player, payload)
            except ValueError:
                # a list of urls
                content = json.loads(media_id)
                playlist = content["urls"]
                index = content["index"]
        else:
            payload = {
                "search_id": media_id,
                "search_type": media_type,
            }
            playlist = await generate_playlist(self._player, payload)

            _LOGGER.debug("Generated playlist: %s", playlist)

        await self._player.async_load_playlist(playlist, cmd)
        if index is not None:
            await self._player.async_index(index)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set the repeat mode."""
        if repeat == RepeatMode.ALL:
            repeat_mode = "playlist"
        elif repeat == RepeatMode.ONE:
            repeat_mode = "song"
        else:
            repeat_mode = "none"

        await self._player.async_set_repeat(repeat_mode)

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        shuffle_mode = "song" if shuffle else "none"
        await self._player.async_set_shuffle(shuffle_mode)

    async def async_clear_playlist(self) -> None:
        """Send the media player the command for clear playlist."""
        await self._player.async_clear_playlist()

    async def async_call_method(self, command, parameters=None):
        """Call Squeezebox JSON/RPC method.

        Additional parameters are added to the command to form the list of
        positional parameters (p0, p1...,  pN) passed to JSON/RPC server.
        """
        all_params = [command]
        if parameters:
            all_params.extend(parameters)
        await self._player.async_query(*all_params)

    async def async_call_query(self, command, parameters=None):
        """Call Squeezebox JSON/RPC method where we care about the result.

        Additional parameters are added to the command to form the list of
        positional parameters (p0, p1...,  pN) passed to JSON/RPC server.
        """
        all_params = [command]
        if parameters:
            all_params.extend(parameters)
        self._query_result = await self._player.async_query(*all_params)
        _LOGGER.debug("call_query got result %s", self._query_result)

    async def async_join_players(self, group_members: list[str]) -> None:
        """Add other Squeezebox players to this player's sync group.

        If the other player is a member of a sync group, it will leave the current sync group
        without asking.
        """
        player_ids = {
            p.entity_id: p.unique_id for p in self.hass.data[DOMAIN][KNOWN_PLAYERS]
        }

        for other_player in group_members:
            if other_player_id := player_ids.get(other_player):
                await self._player.async_sync(other_player_id)
            else:
                _LOGGER.debug(
                    "Could not find player_id for %s. Not syncing", other_player
                )

    async def async_sync(self, other_player):
        """Sync this Squeezebox player to another. Deprecated."""
        _LOGGER.warning(
            "Service squeezebox.sync is deprecated; use media_player.join_players"
            " instead"
        )
        await self.async_join_players([other_player])

    async def async_unjoin_player(self) -> None:
        """Unsync this Squeezebox player."""
        await self._player.async_unsync()

    async def async_unsync(self):
        """Unsync this Squeezebox player. Deprecated."""
        _LOGGER.warning(
            "Service squeezebox.unsync is deprecated; use media_player.unjoin_player"
            " instead"
        )
        await self.async_unjoin_player()

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        _LOGGER.debug(
            "Reached async_browse_media with content_type %s and content_id %s",
            media_content_type,
            media_content_id,
        )

        if media_content_type in [None, "library"]:
            return await library_payload(self.hass, self._player)

        if media_source.is_media_source_id(media_content_id):
            return await media_source.async_browse_media(
                self.hass, media_content_id, content_filter=media_source_content_filter
            )

        payload = {
            "search_type": media_content_type,
            "search_id": media_content_id,
        }

        return await build_item_response(self, self._player, payload)

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
