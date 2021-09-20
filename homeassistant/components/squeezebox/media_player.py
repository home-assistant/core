"""Support for interfacing to the Logitech SqueezeBox API."""
import asyncio
import json
import logging

from pysqueezebox import Server, async_discover
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ENQUEUE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config_entries import SOURCE_DISCOVERY
from homeassistant.const import (
    ATTR_COMMAND,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_START,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.util.dt import utcnow

from .browse_media import build_item_response, generate_playlist, library_payload
from .const import (
    DEFAULT_PORT,
    DISCOVERY_TASK,
    DOMAIN,
    KNOWN_PLAYERS,
    PLAYER_DISCOVERY_UNSUB,
)

SERVICE_CALL_METHOD = "call_method"
SERVICE_CALL_QUERY = "call_query"
SERVICE_SYNC = "sync"
SERVICE_UNSYNC = "unsync"

ATTR_QUERY_RESULT = "query_result"
ATTR_SYNC_GROUP = "sync_group"

SIGNAL_PLAYER_REDISCOVERED = "squeezebox_player_rediscovered"

_LOGGER = logging.getLogger(__name__)

DISCOVERY_INTERVAL = 60

SUPPORT_SQUEEZEBOX = (
    SUPPORT_BROWSE_MEDIA
    | SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SEEK
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_STOP
)

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_HOST),
    cv.deprecated(CONF_PORT),
    cv.deprecated(CONF_PASSWORD),
    cv.deprecated(CONF_USERNAME),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_USERNAME): cv.string,
        }
    ),
)

KNOWN_SERVERS = "known_servers"
ATTR_PARAMETERS = "parameters"
ATTR_OTHER_PLAYER = "other_player"

ATTR_TO_PROPERTY = [
    ATTR_QUERY_RESULT,
    ATTR_SYNC_GROUP,
]

SQUEEZEBOX_MODE = {
    "pause": STATE_PAUSED,
    "play": STATE_PLAYING,
    "stop": STATE_IDLE,
}


async def start_server_discovery(hass):
    """Start a server discovery task."""

    def _discovered_server(server):
        asyncio.create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_DISCOVERY},
                data={
                    CONF_HOST: server.host,
                    CONF_PORT: int(server.port),
                    "uuid": server.uuid,
                },
            )
        )

    hass.data.setdefault(DOMAIN, {})
    if DISCOVERY_TASK not in hass.data[DOMAIN]:
        _LOGGER.debug("Adding server discovery task for squeezebox")
        hass.data[DOMAIN][DISCOVERY_TASK] = hass.async_create_task(
            async_discover(_discovered_server)
        )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up squeezebox platform from platform entry in configuration.yaml (deprecated)."""

    if config:
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up an LMS Server from a config entry."""
    config = config_entry.data
    _LOGGER.debug("Reached async_setup_entry for host=%s", config[CONF_HOST])

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(config_entry.entry_id, {})

    known_players = hass.data[DOMAIN].setdefault(KNOWN_PLAYERS, [])

    session = async_get_clientsession(hass)
    _LOGGER.debug("Creating LMS object for %s", host)
    lms = Server(session, host, port, username, password)

    async def _discovery(now=None):
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

        players = await lms.async_get_players()
        if players:
            for player in players:
                hass.async_create_task(_discovered_player(player))

        hass.data[DOMAIN][config_entry.entry_id][
            PLAYER_DISCOVERY_UNSUB
        ] = hass.helpers.event.async_call_later(DISCOVERY_INTERVAL, _discovery)

    _LOGGER.debug("Adding player discovery job for LMS server: %s", host)
    asyncio.create_task(_discovery())

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
    if hass.is_running:
        asyncio.create_task(start_server_discovery(hass))
    else:
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, start_server_discovery(hass)
        )

    return True


class SqueezeBoxEntity(MediaPlayerEntity):
    """
    Representation of a SqueezeBox device.

    Wraps a pysqueezebox.Player() object.
    """

    def __init__(self, player):
        """Initialize the SqueezeBox device."""
        self._player = player
        self._last_update = None
        self._query_result = {}
        self._available = True
        self._remove_dispatcher = None

    @property
    def extra_state_attributes(self):
        """Return device-specific attributes."""
        squeezebox_attr = {
            attr: getattr(self, attr)
            for attr in ATTR_TO_PROPERTY
            if getattr(self, attr) is not None
        }

        return squeezebox_attr

    @property
    def name(self):
        """Return the name of the device."""
        return self._player.name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._player.player_id

    @property
    def available(self):
        """Return True if device connected to LMS server."""
        return self._available

    @callback
    def rediscovered(self, unique_id, connected):
        """Make a player available again."""
        if unique_id == self.unique_id and connected:
            self._available = True
            _LOGGER.info("Player %s is available again", self.name)
            self._remove_dispatcher()

    @property
    def state(self):
        """Return the state of the device."""
        if not self._player.power:
            return STATE_OFF
        if self._player.mode:
            return SQUEEZEBOX_MODE.get(self._player.mode)
        return None

    async def async_update(self):
        """Update the Player() object."""
        # only update available players, newly available players will be rediscovered and marked available
        if self._available:
            last_media_position = self.media_position
            await self._player.async_update()
            if self.media_position != last_media_position:
                self._last_update = utcnow()
            if self._player.connected is False:
                _LOGGER.info("Player %s is not available", self.name)
                self._available = False

                # start listening for restored players
                self._remove_dispatcher = async_dispatcher_connect(
                    self.hass, SIGNAL_PLAYER_REDISCOVERED, self.rediscovered
                )

    async def async_will_remove_from_hass(self):
        """Remove from list of known players when removed from hass."""
        self.hass.data[DOMAIN][KNOWN_PLAYERS].remove(self)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._player.volume:
            return int(float(self._player.volume)) / 100.0

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
            return MEDIA_TYPE_PLAYLIST
        return MEDIA_TYPE_MUSIC

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
    def media_artist(self):
        """Artist of current playing media."""
        return self._player.artist

    @property
    def media_album_name(self):
        """Album of current playing media."""
        return self._player.album

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._player.shuffle

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_SQUEEZEBOX

    @property
    def sync_group(self):
        """List players we are synced with."""
        player_ids = {
            p.unique_id: p.entity_id for p in self.hass.data[DOMAIN][KNOWN_PLAYERS]
        }
        sync_group = []
        for player in self._player.sync_group:
            if player in player_ids:
                sync_group.append(player_ids[player])
        return sync_group

    @property
    def query_result(self):
        """Return the result from the call_query service."""
        return self._query_result

    async def async_turn_off(self):
        """Turn off media player."""
        await self._player.async_set_power(False)

    async def async_volume_up(self):
        """Volume up media player."""
        await self._player.async_set_volume("+5")

    async def async_volume_down(self):
        """Volume down media player."""
        await self._player.async_set_volume("-5")

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        volume_percent = str(int(volume * 100))
        await self._player.async_set_volume(volume_percent)

    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        await self._player.async_set_muting(mute)

    async def async_media_stop(self):
        """Send stop command to media player."""
        await self._player.async_stop()

    async def async_media_play_pause(self):
        """Send pause command to media player."""
        await self._player.async_toggle_pause()

    async def async_media_play(self):
        """Send play command to media player."""
        await self._player.async_play()

    async def async_media_pause(self):
        """Send pause command to media player."""
        await self._player.async_pause()

    async def async_media_next_track(self):
        """Send next track command."""
        await self._player.async_index("+1")

    async def async_media_previous_track(self):
        """Send next track command."""
        await self._player.async_index("-1")

    async def async_media_seek(self, position):
        """Send seek command."""
        await self._player.async_time(position)

    async def async_turn_on(self):
        """Turn the media player on."""
        await self._player.async_set_power(True)

    async def async_play_media(self, media_type, media_id, **kwargs):
        """
        Send the play_media command to the media player.

        If ATTR_MEDIA_ENQUEUE is True, add `media_id` to the current playlist.
        """
        cmd = "play"
        index = None

        if kwargs.get(ATTR_MEDIA_ENQUEUE):
            cmd = "add"

        if media_type == MEDIA_TYPE_MUSIC:
            await self._player.async_load_url(media_id, cmd)
            return

        if media_type == MEDIA_TYPE_PLAYLIST:
            try:
                # a saved playlist by number
                payload = {
                    "search_id": int(media_id),
                    "search_type": MEDIA_TYPE_PLAYLIST,
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

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        shuffle_mode = "song" if shuffle else "none"
        await self._player.async_set_shuffle(shuffle_mode)

    async def async_clear_playlist(self):
        """Send the media player the command for clear playlist."""
        await self._player.async_clear_playlist()

    async def async_call_method(self, command, parameters=None):
        """
        Call Squeezebox JSON/RPC method.

        Additional parameters are added to the command to form the list of
        positional parameters (p0, p1...,  pN) passed to JSON/RPC server.
        """
        all_params = [command]
        if parameters:
            for parameter in parameters:
                all_params.append(parameter)
        await self._player.async_query(*all_params)

    async def async_call_query(self, command, parameters=None):
        """
        Call Squeezebox JSON/RPC method where we care about the result.

        Additional parameters are added to the command to form the list of
        positional parameters (p0, p1...,  pN) passed to JSON/RPC server.
        """
        all_params = [command]
        if parameters:
            for parameter in parameters:
                all_params.append(parameter)
        self._query_result = await self._player.async_query(*all_params)
        _LOGGER.debug("call_query got result %s", self._query_result)

    async def async_sync(self, other_player):
        """
        Add another Squeezebox player to this player's sync group.

        If the other player is a member of a sync group, it will leave the current sync group
        without asking.
        """
        player_ids = {
            p.entity_id: p.unique_id for p in self.hass.data[DOMAIN][KNOWN_PLAYERS]
        }
        other_player_id = player_ids.get(other_player)
        if other_player_id:
            await self._player.async_sync(other_player_id)
        else:
            _LOGGER.info("Could not find player_id for %s. Not syncing", other_player)

    async def async_unsync(self):
        """Unsync this Squeezebox player."""
        await self._player.async_unsync()

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""

        _LOGGER.debug(
            "Reached async_browse_media with content_type %s and content_id %s",
            media_content_type,
            media_content_id,
        )

        if media_content_type in [None, "library"]:
            return await library_payload(self._player)

        payload = {
            "search_type": media_content_type,
            "search_id": media_content_id,
        }

        return await build_item_response(self, self._player, payload)

    async def async_get_browse_image(
        self, media_content_type, media_content_id, media_image_id=None
    ):
        """Get album art from Squeezebox server."""
        if media_image_id:
            image_url = self._player.generate_image_url_from_track_id(media_image_id)
            result = await self._async_fetch_image(image_url)
            if result == (None, None):
                _LOGGER.debug("Error retrieving proxied album art from %s", image_url)
            return result

        return (None, None)
