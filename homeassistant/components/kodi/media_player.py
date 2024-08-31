"""Support for interfacing with the XBMC/Kodi JSON-RPC API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from datetime import timedelta
from functools import wraps
import logging
import re
from typing import Any, Concatenate

from jsonrpc_base.jsonrpc import ProtocolError, TransportError
from pykodi import CannotConnectError
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    BrowseError,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROXY_SSL,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_platform,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.network import is_internal_request
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, VolDictType
import homeassistant.util.dt as dt_util

from .browse_media import (
    build_item_response,
    get_media_info,
    library_payload,
    media_source_content_filter,
)
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
    "music": MediaType.MUSIC,
    "artist": MediaType.MUSIC,
    "album": MediaType.MUSIC,
    "song": MediaType.MUSIC,
    "video": MediaType.VIDEO,
    "set": MediaType.PLAYLIST,
    "musicvideo": MediaType.VIDEO,
    "movie": MediaType.MOVIE,
    "tvshow": MediaType.TVSHOW,
    "season": MediaType.TVSHOW,
    "episode": MediaType.TVSHOW,
    # Type 'channel' is used for radio or tv streams from pvr
    "channel": MediaType.CHANNEL,
    # Type 'audio' is used for audio media, that Kodi couldn't scroblle
    "audio": MediaType.MUSIC,
}

MAP_KODI_MEDIA_TYPES: dict[MediaType | str, str] = {
    MediaType.MOVIE: "movieid",
    MediaType.EPISODE: "episodeid",
    MediaType.SEASON: "seasonid",
    MediaType.TVSHOW: "tvshowid",
}


PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
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


KODI_ADD_MEDIA_SCHEMA: VolDictType = {
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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Kodi media player platform."""
    platform = entity_platform.async_get_current_platform()
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
    if (uid := config_entry.unique_id) is None:
        uid = config_entry.entry_id

    entity = KodiEntity(connection, kodi, name, uid)
    async_add_entities([entity])


def cmd[_KodiEntityT: KodiEntity, **_P](
    func: Callable[Concatenate[_KodiEntityT, _P], Awaitable[Any]],
) -> Callable[Concatenate[_KodiEntityT, _P], Coroutine[Any, Any, None]]:
    """Catch command exceptions."""

    @wraps(func)
    async def wrapper(obj: _KodiEntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Wrap all command methods."""
        try:
            await func(obj, *args, **kwargs)
        except (TransportError, ProtocolError) as exc:
            # If Kodi is off, we expect calls to fail.
            if obj.state == MediaPlayerState.OFF:
                log_function = _LOGGER.debug
            else:
                log_function = _LOGGER.error
            log_function(
                "Error calling %s on entity %s: %r",
                func.__name__,
                obj.entity_id,
                exc,
            )

    return wrapper


class KodiEntity(MediaPlayerEntity):
    """Representation of a XBMC/Kodi device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "media_player"
    _attr_supported_features = (
        MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.SHUFFLE_SET
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    def __init__(self, connection, kodi, name, uid):
        """Initialize the Kodi entity."""
        self._connection = connection
        self._kodi = kodi
        self._attr_unique_id = uid
        self._device_id = None
        self._players = None
        self._properties = {}
        self._item = {}
        self._app_properties = {}
        self._media_position_updated_at = None
        self._media_position = None
        self._connect_error = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uid)},
            manufacturer="Kodi",
            name=name,
        )

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

    @callback
    def async_on_key_press(self, sender, data):
        """Handle a incoming key press notification."""
        self.hass.bus.async_fire(
            f"{DOMAIN}_keypress",
            {
                CONF_TYPE: "keypress",
                CONF_DEVICE_ID: self._device_id,
                ATTR_ENTITY_ID: self.entity_id,
                "sender": sender,
                "data": data,
            },
        )

    async def async_on_quit(self, sender, data):
        """Reset the player state on quit action."""
        await self._clear_connection()

    async def _clear_connection(self, close=True):
        self._reset_state()
        self.async_write_ha_state()
        if close:
            await self._connection.close()

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        if self._kodi_is_off:
            return MediaPlayerState.OFF

        if self._no_active_players:
            return MediaPlayerState.IDLE

        if self._properties["speed"] == 0:
            return MediaPlayerState.PAUSED

        return MediaPlayerState.PLAYING

    async def async_added_to_hass(self) -> None:
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
        if self.hass.state is CoreState.running:
            await start_watchdog()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, start_watchdog)

    async def _on_ws_connected(self):
        """Call after ws is connected."""
        self._connect_error = False
        self._register_ws_callbacks()

        version = (await self._kodi.get_application_properties(["version"]))["version"]
        sw_version = f"{version['major']}.{version['minor']}"
        dev_reg = dr.async_get(self.hass)
        device = dev_reg.async_get_device(identifiers={(DOMAIN, self.unique_id)})
        dev_reg.async_update_device(device.id, sw_version=sw_version)
        self._device_id = device.id

        self.async_schedule_update_ha_state(True)

    async def _async_ws_connect(self):
        """Connect to Kodi via websocket protocol."""
        try:
            await self._connection.connect()
            await self._on_ws_connected()
        except (TransportError, CannotConnectError):
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.warning("Unable to connect to Kodi via websocket")
            await self._clear_connection(False)
        else:
            self._connect_error = False

    async def _ping(self):
        try:
            await self._kodi.ping()
        except (TransportError, CannotConnectError):
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.warning("Unable to ping Kodi via websocket")
            await self._clear_connection()
        else:
            self._connect_error = False

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
        self._connection.server.Other.OnKeyPress = self.async_on_key_press
        self._connection.server.System.OnQuit = self.async_on_quit
        self._connection.server.System.OnRestart = self.async_on_quit
        self._connection.server.System.OnSleep = self.async_on_quit

    @cmd
    async def async_update(self) -> None:
        """Retrieve latest state."""
        if not self._connection.connected:
            self._reset_state()
            return

        try:
            self._players = await self._kodi.get_players()
        except (TransportError, ProtocolError):
            if not self._connection.can_subscribe:
                self._reset_state()
                return
            raise

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
                    "streamdetails",
                ],
            )
        else:
            self._reset_state([])

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return not self._connection.can_subscribe

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if "volume" in self._app_properties:
            return int(self._app_properties["volume"]) / 100.0
        return None

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

        if (total_time := self._properties.get("totaltime")) is None:
            return None

        return (
            total_time["hours"] * 3600
            + total_time["minutes"] * 60
            + total_time["seconds"]
        )

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if (time := self._properties.get("time")) is None:
            return None

        return time["hours"] * 3600 + time["minutes"] * 60 + time["seconds"]

    @property
    def media_position_updated_at(self):
        """Last valid time of media position."""
        return self._media_position_updated_at

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if (thumbnail := self._item.get("thumbnail")) is None:
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
        if artists := self._item.get("artist"):
            return artists[0]

        return None

    @property
    def media_album_artist(self):
        """Album artist of current playing media, music track only."""
        if artists := self._item.get("albumartist"):
            return artists[0]

        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the state attributes."""
        state_attr: dict[str, str | None] = {}
        if self.state == MediaPlayerState.OFF:
            return state_attr

        state_attr["dynamic_range"] = "sdr"
        if (video_details := self._item.get("streamdetails", {}).get("video")) and (
            hdr_type := video_details[0].get("hdrtype")
        ):
            state_attr["dynamic_range"] = hdr_type

        return state_attr

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        _LOGGER.debug("Firing event to turn on device")
        self.hass.bus.async_fire(EVENT_TURN_ON, {ATTR_ENTITY_ID: self.entity_id})

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        _LOGGER.debug("Firing event to turn off device")
        self.hass.bus.async_fire(EVENT_TURN_OFF, {ATTR_ENTITY_ID: self.entity_id})

    @cmd
    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self._kodi.volume_up()

    @cmd
    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        await self._kodi.volume_down()

    @cmd
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._kodi.set_volume_level(int(volume * 100))

    @cmd
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._kodi.mute(mute)

    @cmd
    async def async_media_play_pause(self) -> None:
        """Pause media on media player."""
        await self._kodi.play_pause()

    @cmd
    async def async_media_play(self) -> None:
        """Play media."""
        await self._kodi.play()

    @cmd
    async def async_media_pause(self) -> None:
        """Pause the media player."""
        await self._kodi.pause()

    @cmd
    async def async_media_stop(self) -> None:
        """Stop the media player."""
        await self._kodi.stop()

    @cmd
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._kodi.next_track()

    @cmd
    async def async_media_previous_track(self) -> None:
        """Send next track command."""
        await self._kodi.previous_track()

    @cmd
    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self._kodi.media_seek(position)

    @cmd
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play_media command to the media player."""
        if media_source.is_media_source_id(media_id):
            media_type = MediaType.URL
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

        media_type_lower = media_type.lower()

        if media_type_lower == MediaType.CHANNEL:
            await self._kodi.play_channel(int(media_id))
        elif media_type_lower == MediaType.PLAYLIST:
            await self._kodi.play_playlist(int(media_id))
        elif media_type_lower == "file":
            await self._kodi.play_file(media_id)
        elif media_type_lower == "directory":
            await self._kodi.play_directory(media_id)
        elif media_type_lower in [
            MediaType.ARTIST,
            MediaType.ALBUM,
            MediaType.TRACK,
        ]:
            await self.async_clear_playlist()
            await self.async_add_to_playlist(media_type_lower, media_id)
            await self._kodi.play_playlist(0)
        elif media_type_lower in [
            MediaType.MOVIE,
            MediaType.EPISODE,
            MediaType.SEASON,
            MediaType.TVSHOW,
        ]:
            await self._kodi.play_item(
                {MAP_KODI_MEDIA_TYPES[media_type_lower]: int(media_id)}
            )
        else:
            media_id = async_process_play_media_url(self.hass, media_id)

            await self._kodi.play_file(media_id)

    @cmd
    async def async_set_shuffle(self, shuffle: bool) -> None:
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
        except ProtocolError as exc:
            result = exc.args[2]["error"]
            _LOGGER.error(
                "Run API method %s.%s(%s) error: %s",
                self.entity_id,
                method,
                kwargs,
                result,
            )
        except TransportError:
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

    async def async_clear_playlist(self) -> None:
        """Clear default playlist (i.e. playlistid=0)."""
        await self._kodi.clear_playlist()

    async def async_add_to_playlist(self, media_type, media_id):
        """Add media item to default playlist (i.e. playlistid=0)."""
        if media_type == MediaType.ARTIST:
            await self._kodi.add_artist_to_playlist(int(media_id))
        elif media_type == MediaType.ALBUM:
            await self._kodi.add_album_to_playlist(int(media_id))
        elif media_type == MediaType.TRACK:
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

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
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
                media_content_id,
                media_image_id,
            )

        if media_content_type in [None, "library"]:
            return await library_payload(self.hass)

        if media_content_id and media_source.is_media_source_id(media_content_id):
            return await media_source.async_browse_media(
                self.hass, media_content_id, content_filter=media_source_content_filter
            )

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
        self,
        media_content_type: MediaType | str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
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
