"""Support for interfacing with the XBMC/Kodi JSON-RPC API."""
from datetime import timedelta
from functools import wraps
import logging
import re
import urllib.parse

import jsonrpc_base
from jsonrpc_base.jsonrpc import ProtocolError, TransportError
from pykodi import CannotConnectError
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_SEASON,
    MEDIA_TYPE_TRACK,
    MEDIA_TYPE_TVSHOW,
    MEDIA_TYPE_VIDEO,
    SUPPORT_BROWSE_MEDIA,
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
    SUPPORT_VOLUME_STEP,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROXY_SSL,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import CoreState, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry,
    entity_platform,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.network import is_internal_request
import homeassistant.util.dt as dt_util

from .browse_media import build_item_response, get_media_info, library_payload
from .const import (
    CONF_WS_PORT,
    DATA_CONNECTION,
    DATA_KODI,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_WS_PORT,
    DOMAIN,
    EVENT_TURN_OFF,
    EVENT_TURN_ON,
)

_LOGGER = logging.getLogger(__name__)

EVENT_KODI_CALL_METHOD_RESULT = "kodi_call_method_result"

CONF_TCP_PORT = "tcp_port"
CONF_TURN_ON_ACTION = "turn_on_action"
CONF_TURN_OFF_ACTION = "turn_off_action"
CONF_ENABLE_WEBSOCKET = "enable_websocket"

DEPRECATED_TURN_OFF_ACTIONS = {
    None: None,
    "quit": "Application.Quit",
    "hibernate": "System.Hibernate",
    "suspend": "System.Suspend",
    "reboot": "System.Reboot",
    "shutdown": "System.Shutdown",
}

WEBSOCKET_WATCHDOG_INTERVAL = timedelta(seconds=10)

# https://github.com/xbmc/xbmc/blob/master/xbmc/media/MediaType.h
MEDIA_TYPES = {
    "music": MEDIA_TYPE_MUSIC,
    "artist": MEDIA_TYPE_MUSIC,
    "album": MEDIA_TYPE_MUSIC,
    "song": MEDIA_TYPE_MUSIC,
    "video": MEDIA_TYPE_VIDEO,
    "set": MEDIA_TYPE_PLAYLIST,
    "musicvideo": MEDIA_TYPE_VIDEO,
    "movie": MEDIA_TYPE_MOVIE,
    "tvshow": MEDIA_TYPE_TVSHOW,
    "season": MEDIA_TYPE_TVSHOW,
    "episode": MEDIA_TYPE_TVSHOW,
    # Type 'channel' is used for radio or tv streams from pvr
    "channel": MEDIA_TYPE_CHANNEL,
    # Type 'audio' is used for audio media, that Kodi couldn't scroblle
    "audio": MEDIA_TYPE_MUSIC,
}

MAP_KODI_MEDIA_TYPES = {
    MEDIA_TYPE_MOVIE: "movieid",
    MEDIA_TYPE_EPISODE: "episodeid",
    MEDIA_TYPE_SEASON: "seasonid",
    MEDIA_TYPE_TVSHOW: "tvshowid",
}

SUPPORT_KODI = (
    SUPPORT_BROWSE_MEDIA
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SEEK
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_STOP
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TCP_PORT, default=DEFAULT_WS_PORT): cv.port,
        vol.Optional(CONF_PROXY_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_TURN_ON_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_TURN_OFF_ACTION): vol.Any(
            cv.SCRIPT_SCHEMA, vol.In(DEPRECATED_TURN_OFF_ACTIONS)
        ),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Inclusive(CONF_USERNAME, "auth"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "auth"): cv.string,
        vol.Optional(CONF_ENABLE_WEBSOCKET, default=True): cv.boolean,
    }
)


SERVICE_ADD_MEDIA = "add_to_playlist"
SERVICE_CALL_METHOD = "call_method"

ATTR_MEDIA_TYPE = "media_type"
ATTR_MEDIA_NAME = "media_name"
ATTR_MEDIA_ARTIST_NAME = "artist_name"
ATTR_MEDIA_ID = "media_id"
ATTR_METHOD = "method"


KODI_ADD_MEDIA_SCHEMA = {
    vol.Required(ATTR_MEDIA_TYPE): cv.string,
    vol.Optional(ATTR_MEDIA_ID): cv.string,
    vol.Optional(ATTR_MEDIA_NAME): cv.string,
    vol.Optional(ATTR_MEDIA_ARTIST_NAME): cv.string,
}

KODI_CALL_METHOD_SCHEMA = cv.make_entity_service_schema(
    {vol.Required(ATTR_METHOD): cv.string}, extra=vol.ALLOW_EXTRA
)


def find_matching_config_entries_for_host(hass, host):
    """Search existing config entries for one matching the host."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_HOST] == host:
            return entry
    return None


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Kodi platform."""
    if discovery_info:
        # Now handled by zeroconf in the config flow
        return

    host = config[CONF_HOST]
    if find_matching_config_entries_for_host(hass, host):
        return

    websocket = config.get(CONF_ENABLE_WEBSOCKET)
    ws_port = config.get(CONF_TCP_PORT) if websocket else None

    entry_data = {
        CONF_NAME: config.get(CONF_NAME, host),
        CONF_HOST: host,
        CONF_PORT: config.get(CONF_PORT),
        CONF_WS_PORT: ws_port,
        CONF_USERNAME: config.get(CONF_USERNAME),
        CONF_PASSWORD: config.get(CONF_PASSWORD),
        CONF_SSL: config.get(CONF_PROXY_SSL),
        CONF_TIMEOUT: config.get(CONF_TIMEOUT),
    }

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_data
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Kodi media player platform."""
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_ADD_MEDIA, KODI_ADD_MEDIA_SCHEMA, "async_add_media_to_playlist"
    )
    platform.async_register_entity_service(
        SERVICE_CALL_METHOD, KODI_CALL_METHOD_SCHEMA, "async_call_method"
    )

    data = hass.data[DOMAIN][config_entry.entry_id]
    connection = data[DATA_CONNECTION]
    kodi = data[DATA_KODI]
    name = config_entry.data[CONF_NAME]
    uid = config_entry.unique_id
    if uid is None:
        uid = config_entry.entry_id

    entity = KodiEntity(connection, kodi, name, uid)
    async_add_entities([entity])


def cmd(func):
    """Catch command exceptions."""

    @wraps(func)
    async def wrapper(obj, *args, **kwargs):
        """Wrap all command methods."""
        try:
            await func(obj, *args, **kwargs)
        except jsonrpc_base.jsonrpc.TransportError as exc:
            # If Kodi is off, we expect calls to fail.
            if obj.state == STATE_OFF:
                log_function = _LOGGER.info
            else:
                log_function = _LOGGER.error
            log_function(
                "Error calling %s on entity %s: %r", func.__name__, obj.entity_id, exc
            )

    return wrapper


class KodiEntity(MediaPlayerEntity):
    """Representation of a XBMC/Kodi device."""

    def __init__(self, connection, kodi, name, uid):
        """Initialize the Kodi entity."""
        self._connection = connection
        self._kodi = kodi
        self._name = name
        self._unique_id = uid
        self._players = None
        self._properties = {}
        self._item = {}
        self._app_properties = {}
        self._media_position_updated_at = None
        self._media_position = None

    def _reset_state(self, players=None):
        self._players = players
        self._properties = {}
        self._item = {}
        self._app_properties = {}
        self._media_position_updated_at = None
        self._media_position = None

    @property
    def _kodi_is_off(self):
        return self._players is None

    @property
    def _no_active_players(self):
        return not self._players

    @callback
    def async_on_speed_event(self, sender, data):
        """Handle player changes between playing and paused."""
        self._properties["speed"] = data["player"]["speed"]

        if not hasattr(data["item"], "id"):
            # If no item id is given, perform a full update
            force_refresh = True
        else:
            # If a new item is playing, force a complete refresh
            force_refresh = data["item"]["id"] != self._item.get("id")

        self.async_schedule_update_ha_state(force_refresh)

    @callback
    def async_on_stop(self, sender, data):
        """Handle the stop of the player playback."""
        # Prevent stop notifications which are sent after quit notification
        if self._kodi_is_off:
            return

        self._reset_state([])
        self.async_write_ha_state()

    @callback
    def async_on_volume_changed(self, sender, data):
        """Handle the volume changes."""
        self._app_properties["volume"] = data["volume"]
        self._app_properties["muted"] = data["muted"]
        self.async_write_ha_state()

    async def async_on_quit(self, sender, data):
        """Reset the player state on quit action."""
        await self._clear_connection()

    async def _clear_connection(self, close=True):
        self._reset_state()
        self.async_write_ha_state()
        if close:
            await self._connection.close()

    @property
    def unique_id(self):
        """Return the unique id of the device."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device info for this device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Kodi",
        }

    @property
    def state(self):
        """Return the state of the device."""
        if self._kodi_is_off:
            return STATE_OFF

        if self._no_active_players:
            return STATE_IDLE

        if self._properties["speed"] == 0:
            return STATE_PAUSED

        return STATE_PLAYING

    async def async_added_to_hass(self):
        """Connect the websocket if needed."""
        if not self._connection.can_subscribe:
            return

        if self._connection.connected:
            await self._on_ws_connected()

        async def start_watchdog(event=None):
            """Start websocket watchdog."""
            await self._async_connect_websocket_if_disconnected()
            self.async_on_remove(
                async_track_time_interval(
                    self.hass,
                    self._async_connect_websocket_if_disconnected,
                    WEBSOCKET_WATCHDOG_INTERVAL,
                )
            )

        # If Home Assistant is already in a running state, start the watchdog
        # immediately, else trigger it after Home Assistant has finished starting.
        if self.hass.state == CoreState.running:
            await start_watchdog()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_watchdog)

    async def _on_ws_connected(self):
        """Call after ws is connected."""
        self._register_ws_callbacks()

        version = (await self._kodi.get_application_properties(["version"]))["version"]
        sw_version = f"{version['major']}.{version['minor']}"
        dev_reg = await device_registry.async_get_registry(self.hass)
        device = dev_reg.async_get_device({(DOMAIN, self.unique_id)})
        dev_reg.async_update_device(device.id, sw_version=sw_version)

        self.async_schedule_update_ha_state(True)

    async def _async_ws_connect(self):
        """Connect to Kodi via websocket protocol."""
        try:
            await self._connection.connect()
            await self._on_ws_connected()
        except (jsonrpc_base.jsonrpc.TransportError, CannotConnectError):
            _LOGGER.debug("Unable to connect to Kodi via websocket", exc_info=True)
            await self._clear_connection(False)

    async def _ping(self):
        try:
            await self._kodi.ping()
        except (jsonrpc_base.jsonrpc.TransportError, CannotConnectError):
            _LOGGER.debug("Unable to ping Kodi via websocket", exc_info=True)
            await self._clear_connection()

    async def _async_connect_websocket_if_disconnected(self, *_):
        """Reconnect the websocket if it fails."""
        if not self._connection.connected:
            await self._async_ws_connect()
        else:
            await self._ping()

    @callback
    def _register_ws_callbacks(self):
        self._connection.server.Player.OnPause = self.async_on_speed_event
        self._connection.server.Player.OnPlay = self.async_on_speed_event
        self._connection.server.Player.OnAVStart = self.async_on_speed_event
        self._connection.server.Player.OnAVChange = self.async_on_speed_event
        self._connection.server.Player.OnResume = self.async_on_speed_event
        self._connection.server.Player.OnSpeedChanged = self.async_on_speed_event
        self._connection.server.Player.OnSeek = self.async_on_speed_event
        self._connection.server.Player.OnStop = self.async_on_stop
        self._connection.server.Application.OnVolumeChanged = (
            self.async_on_volume_changed
        )
        self._connection.server.System.OnQuit = self.async_on_quit
        self._connection.server.System.OnRestart = self.async_on_quit
        self._connection.server.System.OnSleep = self.async_on_quit

    @cmd
    async def async_update(self):
        """Retrieve latest state."""
        if not self._connection.connected:
            self._reset_state()
            return

        self._players = await self._kodi.get_players()

        if self._kodi_is_off:
            self._reset_state()
            return

        if self._players:
            self._app_properties = await self._kodi.get_application_properties(
                ["volume", "muted"]
            )

            self._properties = await self._kodi.get_player_properties(
                self._players[0], ["time", "totaltime", "speed", "live"]
            )

            position = self._properties["time"]
            if self._media_position != position:
                self._media_position_updated_at = dt_util.utcnow()
                self._media_position = position

            self._item = await self._kodi.get_playing_item_properties(
                self._players[0],
                [
                    "title",
                    "file",
                    "uniqueid",
                    "thumbnail",
                    "artist",
                    "albumartist",
                    "showtitle",
                    "album",
                    "season",
                    "episode",
                ],
            )
        else:
            self._reset_state([])

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return not self._connection.can_subscribe

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if "volume" in self._app_properties:
            return int(self._app_properties["volume"]) / 100.0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._app_properties.get("muted")

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._item.get("uniqueid", None)

    @property
    def media_content_type(self):
        """Content type of current playing media.

        If the media type cannot be detected, the player type is used.
        """
        item_type = MEDIA_TYPES.get(self._item.get("type"))
        if (item_type is None or item_type == "channel") and self._players:
            return MEDIA_TYPES.get(self._players[0]["type"])
        return item_type

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self._properties.get("live"):
            return None

        total_time = self._properties.get("totaltime")

        if total_time is None:
            return None

        return (
            total_time["hours"] * 3600
            + total_time["minutes"] * 60
            + total_time["seconds"]
        )

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        time = self._properties.get("time")

        if time is None:
            return None

        return time["hours"] * 3600 + time["minutes"] * 60 + time["seconds"]

    @property
    def media_position_updated_at(self):
        """Last valid time of media position."""
        return self._media_position_updated_at

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        thumbnail = self._item.get("thumbnail")
        if thumbnail is None:
            return None

        return self._kodi.thumbnail_url(thumbnail)

    @property
    def media_title(self):
        """Title of current playing media."""
        # find a string we can use as a title
        item = self._item
        return item.get("title") or item.get("label") or item.get("file")

    @property
    def media_series_title(self):
        """Title of series of current playing media, TV show only."""
        return self._item.get("showtitle")

    @property
    def media_season(self):
        """Season of current playing media, TV show only."""
        return self._item.get("season")

    @property
    def media_episode(self):
        """Episode of current playing media, TV show only."""
        return self._item.get("episode")

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._item.get("album")

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        artists = self._item.get("artist", [])
        if artists:
            return artists[0]

        return None

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        artists = self._item.get("albumartist", [])
        if artists:
            return artists[0]

        return None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_KODI

    async def async_turn_on(self):
        """Turn the media player on."""
        _LOGGER.debug("Firing event to turn on device")
        self.hass.bus.async_fire(EVENT_TURN_ON, {ATTR_ENTITY_ID: self.entity_id})

    async def async_turn_off(self):
        """Turn the media player off."""
        _LOGGER.debug("Firing event to turn off device")
        self.hass.bus.async_fire(EVENT_TURN_OFF, {ATTR_ENTITY_ID: self.entity_id})

    @cmd
    async def async_volume_up(self):
        """Volume up the media player."""
        await self._kodi.volume_up()

    @cmd
    async def async_volume_down(self):
        """Volume down the media player."""
        await self._kodi.volume_down()

    @cmd
    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._kodi.set_volume_level(int(volume * 100))

    @cmd
    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        await self._kodi.mute(mute)

    @cmd
    async def async_media_play_pause(self):
        """Pause media on media player."""
        await self._kodi.play_pause()

    @cmd
    async def async_media_play(self):
        """Play media."""
        await self._kodi.play()

    @cmd
    async def async_media_pause(self):
        """Pause the media player."""
        await self._kodi.pause()

    @cmd
    async def async_media_stop(self):
        """Stop the media player."""
        await self._kodi.stop()

    @cmd
    async def async_media_next_track(self):
        """Send next track command."""
        await self._kodi.next_track()

    @cmd
    async def async_media_previous_track(self):
        """Send next track command."""
        await self._kodi.previous_track()

    @cmd
    async def async_media_seek(self, position):
        """Send seek command."""
        await self._kodi.media_seek(position)

    @cmd
    async def async_play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player."""
        media_type_lower = media_type.lower()

        if media_type_lower == MEDIA_TYPE_CHANNEL:
            await self._kodi.play_channel(int(media_id))
        elif media_type_lower == MEDIA_TYPE_PLAYLIST:
            await self._kodi.play_playlist(int(media_id))
        elif media_type_lower == "directory":
            await self._kodi.play_directory(str(media_id))
        elif media_type_lower in [
            MEDIA_TYPE_ARTIST,
            MEDIA_TYPE_ALBUM,
            MEDIA_TYPE_TRACK,
        ]:
            await self.async_clear_playlist()
            await self.async_add_to_playlist(media_type_lower, media_id)
            await self._kodi.play_playlist(0)
        elif media_type_lower in [
            MEDIA_TYPE_MOVIE,
            MEDIA_TYPE_EPISODE,
            MEDIA_TYPE_SEASON,
            MEDIA_TYPE_TVSHOW,
        ]:
            await self._kodi.play_item(
                {MAP_KODI_MEDIA_TYPES[media_type_lower]: int(media_id)}
            )
        else:
            await self._kodi.play_file(str(media_id))

    @cmd
    async def async_set_shuffle(self, shuffle):
        """Set shuffle mode, for the first player."""
        if self._no_active_players:
            raise RuntimeError("Error: No active player.")
        await self._kodi.set_shuffle(shuffle)

    async def async_call_method(self, method, **kwargs):
        """Run Kodi JSONRPC API method with params."""
        _LOGGER.debug("Run API method %s, kwargs=%s", method, kwargs)
        result_ok = False
        try:
            result = await self._kodi.call_method(method, **kwargs)
            result_ok = True
        except jsonrpc_base.jsonrpc.ProtocolError as exc:
            result = exc.args[2]["error"]
            _LOGGER.error(
                "Run API method %s.%s(%s) error: %s",
                self.entity_id,
                method,
                kwargs,
                result,
            )
        except jsonrpc_base.jsonrpc.TransportError:
            result = None
            _LOGGER.warning(
                "TransportError trying to run API method %s.%s(%s)",
                self.entity_id,
                method,
                kwargs,
            )

        if isinstance(result, dict):
            event_data = {
                "entity_id": self.entity_id,
                "result": result,
                "result_ok": result_ok,
                "input": {"method": method, "params": kwargs},
            }
            _LOGGER.debug("EVENT kodi_call_method_result: %s", event_data)
            self.hass.bus.async_fire(
                EVENT_KODI_CALL_METHOD_RESULT, event_data=event_data
            )
        return result

    async def async_clear_playlist(self):
        """Clear default playlist (i.e. playlistid=0)."""
        await self._kodi.clear_playlist()

    async def async_add_to_playlist(self, media_type, media_id):
        """Add media item to default playlist (i.e. playlistid=0)."""
        if media_type == MEDIA_TYPE_ARTIST:
            await self._kodi.add_artist_to_playlist(int(media_id))
        elif media_type == MEDIA_TYPE_ALBUM:
            await self._kodi.add_album_to_playlist(int(media_id))
        elif media_type == MEDIA_TYPE_TRACK:
            await self._kodi.add_song_to_playlist(int(media_id))

    async def async_add_media_to_playlist(
        self, media_type, media_id=None, media_name="ALL", artist_name=""
    ):
        """Add a media to default playlist.

        First the media type must be selected, then
        the media can be specified in terms of id or
        name and optionally artist name.
        All the albums of an artist can be added with
        media_name="ALL"
        """
        if media_type == "SONG":
            if media_id is None:
                media_id = await self._async_find_song(media_name, artist_name)
            if media_id:
                await self._kodi.add_song_to_playlist(int(media_id))

        elif media_type == "ALBUM":
            if media_id is None:
                if media_name == "ALL":
                    await self._async_add_all_albums(artist_name)
                    return

                media_id = await self._async_find_album(media_name, artist_name)
            if media_id:
                await self._kodi.add_album_to_playlist(int(media_id))

        else:
            raise RuntimeError("Unrecognized media type.")

        if media_id is None:
            _LOGGER.warning("No media detected for Playlist.Add")

    async def _async_add_all_albums(self, artist_name):
        """Add all albums of an artist to default playlist (i.e. playlistid=0).

        The artist is specified in terms of name.
        """
        artist_id = await self._async_find_artist(artist_name)

        albums = await self._kodi.get_albums(artist_id)

        for alb in albums["albums"]:
            await self._kodi.add_album_to_playlist(int(alb["albumid"]))

    async def _async_find_artist(self, artist_name):
        """Find artist by name."""
        artists = await self._kodi.get_artists()
        try:
            out = self._find(artist_name, [a["artist"] for a in artists["artists"]])
            return artists["artists"][out[0][0]]["artistid"]
        except KeyError:
            _LOGGER.warning("No artists were found: %s", artist_name)
            return None

    async def _async_find_song(self, song_name, artist_name=""):
        """Find song by name and optionally artist name."""
        artist_id = None
        if artist_name != "":
            artist_id = await self._async_find_artist(artist_name)

        songs = await self._kodi.get_songs(artist_id)
        if songs["limits"]["total"] == 0:
            return None

        out = self._find(song_name, [a["label"] for a in songs["songs"]])
        return songs["songs"][out[0][0]]["songid"]

    async def _async_find_album(self, album_name, artist_name=""):
        """Find album by name and optionally artist name."""
        artist_id = None
        if artist_name != "":
            artist_id = await self._async_find_artist(artist_name)

        albums = await self._kodi.get_albums(artist_id)
        try:
            out = self._find(album_name, [a["label"] for a in albums["albums"]])
            return albums["albums"][out[0][0]]["albumid"]
        except KeyError:
            _LOGGER.warning(
                "No albums were found with artist: %s, album: %s",
                artist_name,
                album_name,
            )
            return None

    @staticmethod
    def _find(key_word, words):
        key_word = key_word.split(" ")
        patt = [re.compile(f"(^| ){k}( |$)", re.IGNORECASE) for k in key_word]

        out = [[i, 0] for i in range(len(words))]
        for i in range(len(words)):
            mtc = [p.search(words[i]) for p in patt]
            rate = [m is not None for m in mtc].count(True)
            out[i][1] = rate

        return sorted(out, key=lambda out: out[1], reverse=True)

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        is_internal = is_internal_request(self.hass)

        async def _get_thumbnail_url(
            media_content_type,
            media_content_id,
            media_image_id=None,
            thumbnail_url=None,
        ):
            if is_internal:
                return self._kodi.thumbnail_url(thumbnail_url)

            return self.get_browse_image_url(
                media_content_type,
                urllib.parse.quote_plus(media_content_id),
                media_image_id,
            )

        if media_content_type in [None, "library"]:
            return await library_payload()

        payload = {
            "search_type": media_content_type,
            "search_id": media_content_id,
        }

        response = await build_item_response(self._kodi, payload, _get_thumbnail_url)
        if response is None:
            raise BrowseError(
                f"Media not found: {media_content_type} / {media_content_id}"
            )
        return response

    async def async_get_browse_image(
        self, media_content_type, media_content_id, media_image_id=None
    ):
        """Get media image from kodi server."""
        try:
            image_url, _, _ = await get_media_info(
                self._kodi, media_content_id, media_content_type
            )
        except (ProtocolError, TransportError):
            return (None, None)

        if image_url:
            return await self._async_fetch_image(image_url)

        return (None, None)
