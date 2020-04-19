"""Support for interfacing to the Logitech SqueezeBox API."""
import asyncio
import json
import logging
import socket
import urllib.parse

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ENQUEUE,
    MEDIA_TYPE_MUSIC,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    HTTP_OK,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import utcnow

from .const import DOMAIN, SERVICE_CALL_METHOD

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 9000
TIMEOUT = 10

SUPPORT_SQUEEZEBOX = (
    SUPPORT_PAUSE
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
)

MEDIA_PLAYER_SCHEMA = vol.Schema({ATTR_ENTITY_ID: cv.comp_entity_ids})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_USERNAME): cv.string,
    }
)

DATA_SQUEEZEBOX = "squeezebox"

KNOWN_SERVERS = "squeezebox_known_servers"

ATTR_PARAMETERS = "parameters"

SQUEEZEBOX_CALL_METHOD_SCHEMA = MEDIA_PLAYER_SCHEMA.extend(
    {
        vol.Required(ATTR_COMMAND): cv.string,
        vol.Optional(ATTR_PARAMETERS): vol.All(
            cv.ensure_list, vol.Length(min=1), [cv.string]
        ),
    }
)

SERVICE_TO_METHOD = {
    SERVICE_CALL_METHOD: {
        "method": "async_call_method",
        "schema": SQUEEZEBOX_CALL_METHOD_SCHEMA,
    }
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the squeezebox platform."""

    known_servers = hass.data.get(KNOWN_SERVERS)
    if known_servers is None:
        hass.data[KNOWN_SERVERS] = known_servers = set()

    if DATA_SQUEEZEBOX not in hass.data:
        hass.data[DATA_SQUEEZEBOX] = []

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    if discovery_info is not None:
        host = discovery_info.get("host")
        port = discovery_info.get("port")
    else:
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)

    # In case the port is not discovered
    if port is None:
        port = DEFAULT_PORT

    # Get IP of host, to prevent duplication of same host (different DNS names)
    try:
        ipaddr = socket.gethostbyname(host)
    except OSError as error:
        _LOGGER.error("Could not communicate with %s:%d: %s", host, port, error)
        raise PlatformNotReady from error

    if ipaddr in known_servers:
        return

    _LOGGER.debug("Creating LMS object for %s", ipaddr)
    lms = LogitechMediaServer(hass, host, port, username, password)

    players = await lms.create_players()
    if players is None:
        raise PlatformNotReady

    known_servers.add(ipaddr)

    hass.data[DATA_SQUEEZEBOX].extend(players)
    async_add_entities(players)

    async def async_service_handler(service):
        """Map services to methods on MediaPlayerDevice."""
        method = SERVICE_TO_METHOD.get(service.service)
        if not method:
            return

        params = {
            key: value for key, value in service.data.items() if key != "entity_id"
        }
        entity_ids = service.data.get("entity_id")
        if entity_ids:
            target_players = [
                player
                for player in hass.data[DATA_SQUEEZEBOX]
                if player.entity_id in entity_ids
            ]
        else:
            target_players = hass.data[DATA_SQUEEZEBOX]

        update_tasks = []
        for player in target_players:
            await getattr(player, method["method"])(**params)
            update_tasks.append(player.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks)

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service]["schema"]
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=schema
        )

    return True


class LogitechMediaServer:
    """Representation of a Logitech media server."""

    def __init__(self, hass, host, port, username, password):
        """Initialize the Logitech device."""
        self.hass = hass
        self.host = host
        self.port = port
        self._username = username
        self._password = password

    async def create_players(self):
        """Create a list of devices connected to LMS."""
        result = []
        data = await self.async_query("players", "status")
        if data is False:
            return None
        for players in data.get("players_loop", []):
            player = SqueezeBoxDevice(self, players["playerid"], players["name"])
            await player.async_update()
            result.append(player)
        return result

    async def async_query(self, *command, player=""):
        """Abstract out the JSON-RPC connection."""
        auth = (
            None
            if self._username is None
            else aiohttp.BasicAuth(self._username, self._password)
        )
        url = f"http://{self.host}:{self.port}/jsonrpc.js"
        data = json.dumps(
            {"id": "1", "method": "slim.request", "params": [player, command]}
        )

        _LOGGER.debug("URL: %s Data: %s", url, data)

        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(TIMEOUT):
                response = await websession.post(url, data=data, auth=auth)

                if response.status != HTTP_OK:
                    _LOGGER.error(
                        "Query failed, response code: %s Full message: %s",
                        response.status,
                        response,
                    )
                    return False

                data = await response.json()

        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            _LOGGER.error("Failed communicating with LMS: %s", type(error))
            return False

        try:
            return data["result"]
        except AttributeError:
            _LOGGER.error("Received invalid response: %s", data)
            return False


class SqueezeBoxDevice(MediaPlayerDevice):
    """Representation of a SqueezeBox device."""

    def __init__(self, lms, player_id, name):
        """Initialize the SqueezeBox device."""
        super().__init__()
        self._lms = lms
        self._id = player_id
        self._status = {}
        self._name = name
        self._last_update = None
        _LOGGER.debug("Creating SqueezeBox object: %s, %s", name, player_id)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._id

    @property
    def state(self):
        """Return the state of the device."""
        if "power" in self._status and self._status["power"] == 0:
            return STATE_OFF
        if "mode" in self._status:
            if self._status["mode"] == "pause":
                return STATE_PAUSED
            if self._status["mode"] == "play":
                return STATE_PLAYING
            if self._status["mode"] == "stop":
                return STATE_IDLE
        return None

    async def async_query(self, *parameters):
        """Send a command to the LMS."""
        return await self._lms.async_query(*parameters, player=self._id)

    async def async_update(self):
        """Retrieve the current state of the player."""
        tags = "adKl"
        response = await self.async_query("status", "-", "1", f"tags:{tags}")

        if response is False:
            return

        last_media_position = self.media_position

        self._status = {}

        try:
            self._status.update(response["playlist_loop"][0])
        except KeyError:
            pass
        try:
            self._status.update(response["remoteMeta"])
        except KeyError:
            pass

        self._status.update(response)

        if self.media_position != last_media_position:
            _LOGGER.debug(
                "Media position updated for %s: %s", self, self.media_position
            )
            self._last_update = utcnow()

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if "mixer volume" in self._status:
            return int(float(self._status["mixer volume"])) / 100.0

    @property
    def is_volume_muted(self):
        """Return true if volume is muted."""
        if "mixer volume" in self._status:
            return str(self._status["mixer volume"]).startswith("-")

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        if "current_title" in self._status:
            return self._status["current_title"]

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if "duration" in self._status:
            return int(float(self._status["duration"]))

    @property
    def media_position(self):
        """Duration of current playing media in seconds."""
        if "time" in self._status:
            return int(float(self._status["time"]))

    @property
    def media_position_updated_at(self):
        """Last time status was updated."""
        return self._last_update

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if "artwork_url" in self._status:
            media_url = self._status["artwork_url"]
        elif "id" in self._status:
            media_url = ("/music/{track_id}/cover.jpg").format(
                track_id=self._status["id"]
            )
        else:
            media_url = ("/music/current/cover.jpg?player={player}").format(
                player=self._id
            )

        # pylint: disable=protected-access
        if self._lms._username:
            base_url = "http://{username}:{password}@{server}:{port}/".format(
                username=self._lms._username,
                password=self._lms._password,
                server=self._lms.host,
                port=self._lms.port,
            )
        else:
            base_url = "http://{server}:{port}/".format(
                server=self._lms.host, port=self._lms.port
            )

        url = urllib.parse.urljoin(base_url, media_url)

        return url

    @property
    def media_title(self):
        """Title of current playing media."""
        if "title" in self._status:
            return self._status["title"]

        if "current_title" in self._status:
            return self._status["current_title"]

    @property
    def media_artist(self):
        """Artist of current playing media."""
        if "artist" in self._status:
            return self._status["artist"]

    @property
    def media_album_name(self):
        """Album of current playing media."""
        if "album" in self._status:
            return self._status["album"]

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        if "playlist_shuffle" in self._status:
            return self._status["playlist_shuffle"] == 1

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_SQUEEZEBOX

    async def async_turn_off(self):
        """Turn off media player."""
        await self.async_query("power", "0")

    async def async_volume_up(self):
        """Volume up media player."""
        await self.async_query("mixer", "volume", "+5")

    async def async_volume_down(self):
        """Volume down media player."""
        await self.async_query("mixer", "volume", "-5")

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        volume_percent = str(int(volume * 100))
        await self.async_query("mixer", "volume", volume_percent)

    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        mute_numeric = "1" if mute else "0"
        await self.async_query("mixer", "muting", mute_numeric)

    async def async_media_play_pause(self):
        """Send pause command to media player."""
        await self.async_query("pause")

    async def async_media_play(self):
        """Send play command to media player."""
        await self.async_query("play")

    async def async_media_pause(self):
        """Send pause command to media player."""
        await self.async_query("pause", "1")

    async def async_media_next_track(self):
        """Send next track command."""
        await self.async_query("playlist", "index", "+1")

    async def async_media_previous_track(self):
        """Send next track command."""
        await self.async_query("playlist", "index", "-1")

    async def async_media_seek(self, position):
        """Send seek command."""
        await self.async_query("time", position)

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.async_query("power", "1")

    async def async_play_media(self, media_type, media_id, **kwargs):
        """
        Send the play_media command to the media player.

        If ATTR_MEDIA_ENQUEUE is True, add `media_id` to the current playlist.
        """
        if kwargs.get(ATTR_MEDIA_ENQUEUE):
            await self._add_uri_to_playlist(media_id)
            return

        await self._play_uri(media_id)

    async def _play_uri(self, media_id):
        """Replace the current play list with the uri."""
        await self.async_query("playlist", "play", media_id)

    async def _add_uri_to_playlist(self, media_id):
        """Add an item to the existing playlist."""
        await self.async_query("playlist", "add", media_id)

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        await self.async_query("playlist", "shuffle", int(shuffle))

    async def async_clear_playlist(self):
        """Send the media player the command for clear playlist."""
        await self.async_query("playlist", "clear")

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
        await self.async_query(*all_params)
