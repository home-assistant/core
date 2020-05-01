"""Support for interfacing to the Logitech SqueezeBox API."""
import asyncio
import logging
import socket

from pysqueezebox import Server
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
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
    STATE_OFF,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import utcnow

from .const import DOMAIN, SERVICE_CALL_METHOD, SQUEEZEBOX_MODE

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
        ipaddr = await hass.async_add_executor_job(socket.gethostbyname, host)
    except OSError as error:
        _LOGGER.error("Could not communicate with %s:%d: %s", host, port, error)
        raise PlatformNotReady from error

    if ipaddr in known_servers:
        return

    _LOGGER.debug("Creating LMS object for %s", ipaddr)
    lms = Server(async_get_clientsession(hass), host, port, username, password)
    known_servers.add(ipaddr)

    players = await lms.async_get_players()
    if players is None:
        raise PlatformNotReady
    media_players = []
    for player in players:
        media_players.append(SqueezeBoxDevice(player))

    hass.data[DATA_SQUEEZEBOX].extend(media_players)
    async_add_entities(media_players)

    async def async_service_handler(service):
        """Map services to methods on MediaPlayerEntity."""
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


class SqueezeBoxDevice(MediaPlayerEntity):
    """
    Representation of a SqueezeBox device.

    Wraps a pysqueezebox.Player() object.
    """

    def __init__(self, player):
        """Initialize the SqueezeBox device."""
        self._player = player
        self._last_update = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._player.name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._player.player_id

    @property
    def state(self):
        """Return the state of the device."""
        if self._player.power is not None and not self._player.power:
            return STATE_OFF
        if self._player.mode:
            return SQUEEZEBOX_MODE.get(self._player.mode)
        return None

    async def async_update(self):
        """Update the Player() object."""
        last_media_position = self.media_position
        await self._player.async_update()
        if self.media_position != last_media_position:
            _LOGGER.debug(
                "Media position updated for %s: %s", self, self.media_position
            )
            self._last_update = utcnow()

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
        return self._player.url

    @property
    def media_content_type(self):
        """Content type of current playing media."""
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
        if kwargs.get(ATTR_MEDIA_ENQUEUE):
            cmd = "add"

        await self._player.async_load_url(media_id, cmd)

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
