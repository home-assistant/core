"""Support to interface with the Plex API."""
from functools import wraps
import json
import logging

import plexapi.exceptions
import requests.exceptions

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import STATE_IDLE, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.network import is_internal_request

from .const import (
    COMMON_PLAYERS,
    CONF_SERVER_IDENTIFIER,
    DISPATCHERS,
    DOMAIN as PLEX_DOMAIN,
    NAME_FORMAT,
    PLEX_NEW_MP_SIGNAL,
    PLEX_UPDATE_MEDIA_PLAYER_SESSION_SIGNAL,
    PLEX_UPDATE_MEDIA_PLAYER_SIGNAL,
    PLEX_UPDATE_SENSOR_SIGNAL,
    SERVERS,
    TRANSIENT_DEVICE_MODELS,
)
from .media_browser import browse_media

_LOGGER = logging.getLogger(__name__)


def needs_session(func):
    """Ensure session is available for certain attributes."""

    @wraps(func)
    def get_session_attribute(self, *args):
        if self.session is None:
            return None
        return func(self, *args)

    return get_session_attribute


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Plex media_player from a config entry."""
    server_id = config_entry.data[CONF_SERVER_IDENTIFIER]
    registry = await async_get_registry(hass)

    @callback
    def async_new_media_players(new_entities):
        _async_add_entities(hass, registry, async_add_entities, server_id, new_entities)

    unsub = async_dispatcher_connect(
        hass, PLEX_NEW_MP_SIGNAL.format(server_id), async_new_media_players
    )
    hass.data[PLEX_DOMAIN][DISPATCHERS][server_id].append(unsub)
    _LOGGER.debug("New entity listener created")


@callback
def _async_add_entities(hass, registry, async_add_entities, server_id, new_entities):
    """Set up Plex media_player entities."""
    _LOGGER.debug("New entities: %s", new_entities)
    entities = []
    plexserver = hass.data[PLEX_DOMAIN][SERVERS][server_id]
    for entity_params in new_entities:
        plex_mp = PlexMediaPlayer(plexserver, **entity_params)
        entities.append(plex_mp)

        # Migration to per-server unique_ids
        old_entity_id = registry.async_get_entity_id(
            MP_DOMAIN, PLEX_DOMAIN, plex_mp.machine_identifier
        )
        if old_entity_id is not None:
            new_unique_id = f"{server_id}:{plex_mp.machine_identifier}"
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                plex_mp.machine_identifier,
                new_unique_id,
            )
            registry.async_update_entity(old_entity_id, new_unique_id=new_unique_id)

    async_add_entities(entities, True)


class PlexMediaPlayer(MediaPlayerEntity):
    """Representation of a Plex device."""

    def __init__(self, plex_server, device, player_source, session=None):
        """Initialize the Plex device."""
        self.plex_server = plex_server
        self.device = device
        self.player_source = player_source

        self.device_make = None
        self.device_platform = None
        self.device_product = None
        self.device_title = None
        self.device_version = None
        self.machine_identifier = device.machineIdentifier
        self.session_device = None

        self._available = False
        self._device_protocol_capabilities = None
        self._name = None
        self._previous_volume_level = 1  # Used in fake muting
        self._state = STATE_IDLE
        self._volume_level = 1  # since we can't retrieve remotely
        self._volume_muted = False  # since we can't retrieve remotely

        # Initializes other attributes
        self.session = session

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        _LOGGER.debug("Added %s [%s]", self.entity_id, self.unique_id)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                PLEX_UPDATE_MEDIA_PLAYER_SIGNAL.format(self.unique_id),
                self.async_refresh_media_player,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                PLEX_UPDATE_MEDIA_PLAYER_SESSION_SIGNAL.format(self.unique_id),
                self.async_update_from_websocket,
            )
        )

    @callback
    def async_refresh_media_player(self, device, session, source):
        """Set instance objects and trigger an entity state update."""
        _LOGGER.debug("Refreshing %s [%s / %s]", self.entity_id, device, session)
        self.device = device
        self.session = session
        if source:
            self.player_source = source
        self.async_schedule_update_ha_state(True)

        async_dispatcher_send(
            self.hass,
            PLEX_UPDATE_SENSOR_SIGNAL.format(self.plex_server.machine_identifier),
        )

    @callback
    def async_update_from_websocket(self, state):
        """Update the entity based on new websocket data."""
        self.update_state(state)
        self.async_write_ha_state()

        async_dispatcher_send(
            self.hass,
            PLEX_UPDATE_SENSOR_SIGNAL.format(self.plex_server.machine_identifier),
        )

    def update(self):
        """Refresh key device data."""
        if not self.session:
            self.force_idle()
            if not self.device:
                self._available = False
                return

        self._available = True

        try:
            device_url = self.device.url("/")
        except plexapi.exceptions.BadRequest:
            device_url = "127.0.0.1"
        if "127.0.0.1" in device_url:
            self.device.proxyThroughServer()
        self._device_protocol_capabilities = self.device.protocolCapabilities

        for device in filter(None, [self.device, self.session_device]):
            self.device_make = self.device_make or device.device
            self.device_platform = self.device_platform or device.platform
            self.device_product = self.device_product or device.product
            self.device_title = self.device_title or device.title
            self.device_version = self.device_version or device.version

        name_parts = [self.device_product, self.device_title or self.device_platform]
        if (self.device_product in COMMON_PLAYERS) and self.device_make:
            # Add more context in name for likely duplicates
            name_parts.append(self.device_make)
        if self.username and self.username != self.plex_server.owner:
            # Prepend username for shared/managed clients
            name_parts.insert(0, self.username)
        self._name = NAME_FORMAT.format(" - ".join(name_parts))

    def force_idle(self):
        """Force client to idle."""
        self._state = STATE_IDLE
        if self.player_source == "session":
            self.device = None
            self.session_device = None
            self._available = False

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def unique_id(self):
        """Return the id of this plex client."""
        return f"{self.plex_server.machine_identifier}:{self.machine_identifier}"

    @property
    def session(self):
        """Return the active session for this player."""
        return self._session

    @session.setter
    def session(self, session):
        self._session = session
        if session:
            self.session_device = self.session.player
            self.update_state(self.session.state)
        else:
            self._state = STATE_IDLE

    @property
    def available(self):
        """Return the availability of the client."""
        return self._available

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    @needs_session
    def username(self):
        """Return the username of the client owner."""
        return self.session.username

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update_state(self, state):
        """Set the state of the device, handle session termination."""
        if state == "playing":
            self._state = STATE_PLAYING
        elif state == "paused":
            self._state = STATE_PAUSED
        elif state == "stopped":
            self.session = None
            self.force_idle()
        else:
            self._state = STATE_IDLE

    @property
    def _is_player_active(self):
        """Report if the client is playing media."""
        return self.state in [STATE_PLAYING, STATE_PAUSED]

    @property
    def _active_media_plexapi_type(self):
        """Get the active media type required by PlexAPI commands."""
        if self.media_content_type is MEDIA_TYPE_MUSIC:
            return "music"

        return "video"

    @property
    @needs_session
    def session_key(self):
        """Return current session key."""
        return self.session.sessionKey

    @property
    @needs_session
    def media_library_title(self):
        """Return the library name of playing media."""
        return self.session.media_library_title

    @property
    @needs_session
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self.session.media_content_id

    @property
    @needs_session
    def media_content_type(self):
        """Return the content type of current playing media."""
        return self.session.media_content_type

    @property
    @needs_session
    def media_content_rating(self):
        """Return the content rating of current playing media."""
        return self.session.media_content_rating

    @property
    @needs_session
    def media_artist(self):
        """Return the artist of current playing media, music track only."""
        return self.session.media_artist

    @property
    @needs_session
    def media_album_name(self):
        """Return the album name of current playing media, music track only."""
        return self.session.media_album_name

    @property
    @needs_session
    def media_album_artist(self):
        """Return the album artist of current playing media, music only."""
        return self.session.media_album_artist

    @property
    @needs_session
    def media_track(self):
        """Return the track number of current playing media, music only."""
        return self.session.media_track

    @property
    @needs_session
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return self.session.media_duration

    @property
    @needs_session
    def media_position(self):
        """Return the duration of current playing media in seconds."""
        return self.session.media_position

    @property
    @needs_session
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self.session.media_position_updated_at

    @property
    @needs_session
    def media_image_url(self):
        """Return the image URL of current playing media."""
        return self.session.media_image_url

    @property
    @needs_session
    def media_summary(self):
        """Return the summary of current playing media."""
        return self.session.media_summary

    @property
    @needs_session
    def media_title(self):
        """Return the title of current playing media."""
        return self.session.media_title

    @property
    @needs_session
    def media_season(self):
        """Return the season of current playing media (TV Show only)."""
        return self.session.media_season

    @property
    @needs_session
    def media_series_title(self):
        """Return the title of the series of current playing media."""
        return self.session.media_series_title

    @property
    @needs_session
    def media_episode(self):
        """Return the episode of current playing media (TV Show only)."""
        return self.session.media_episode

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self.device and "playback" in self._device_protocol_capabilities:
            return (
                SUPPORT_PAUSE
                | SUPPORT_PREVIOUS_TRACK
                | SUPPORT_NEXT_TRACK
                | SUPPORT_STOP
                | SUPPORT_SEEK
                | SUPPORT_VOLUME_SET
                | SUPPORT_PLAY
                | SUPPORT_PLAY_MEDIA
                | SUPPORT_VOLUME_MUTE
                | SUPPORT_BROWSE_MEDIA
            )

        return SUPPORT_BROWSE_MEDIA | SUPPORT_PLAY_MEDIA

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.setVolume(int(volume * 100), self._active_media_plexapi_type)
            self._volume_level = volume  # store since we can't retrieve

    @property
    def volume_level(self):
        """Return the volume level of the client (0..1)."""
        if (
            self._is_player_active
            and self.device
            and "playback" in self._device_protocol_capabilities
        ):
            return self._volume_level
        return None

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        if self._is_player_active and self.device:
            return self._volume_muted
        return None

    def mute_volume(self, mute):
        """Mute the volume.

        Since we can't actually mute, we'll:
        - On mute, store volume and set volume to 0
        - On unmute, set volume to previously stored volume
        """
        if not (self.device and "playback" in self._device_protocol_capabilities):
            return

        self._volume_muted = mute
        if mute:
            self._previous_volume_level = self._volume_level
            self.set_volume_level(0)
        else:
            self.set_volume_level(self._previous_volume_level)

    def media_play(self):
        """Send play command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.play(self._active_media_plexapi_type)

    def media_pause(self):
        """Send pause command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.pause(self._active_media_plexapi_type)

    def media_stop(self):
        """Send stop command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.stop(self._active_media_plexapi_type)

    def media_seek(self, position):
        """Send the seek command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.seekTo(position * 1000, self._active_media_plexapi_type)

    def media_next_track(self):
        """Send next track command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.skipNext(self._active_media_plexapi_type)

    def media_previous_track(self):
        """Send previous track command."""
        if self.device and "playback" in self._device_protocol_capabilities:
            self.device.skipPrevious(self._active_media_plexapi_type)

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        if not (self.device and "playback" in self._device_protocol_capabilities):
            _LOGGER.debug(
                "Client is not currently accepting playback controls: %s", self.name
            )
            return
        if not self.plex_server.has_token:
            _LOGGER.warning(
                "Plex integration configured without a token, playback may fail"
            )

        src = json.loads(media_id)
        if isinstance(src, int):
            src = {"plex_key": src}

        playqueue_id = src.pop("playqueue_id", None)

        if playqueue_id:
            try:
                playqueue = self.plex_server.get_playqueue(playqueue_id)
            except plexapi.exceptions.NotFound as err:
                raise HomeAssistantError(
                    f"PlayQueue '{playqueue_id}' could not be found"
                ) from err
        else:
            shuffle = src.pop("shuffle", 0)
            media = self.plex_server.lookup_media(media_type, **src)

            if media is None:
                _LOGGER.error("Media could not be found: %s", media_id)
                return

            _LOGGER.debug("Attempting to play %s on %s", media, self.name)
            playqueue = self.plex_server.create_playqueue(media, shuffle=shuffle)

        try:
            self.device.playMedia(playqueue)
        except requests.exceptions.ConnectTimeout:
            _LOGGER.error("Timed out playing on %s", self.name)

    @property
    def extra_state_attributes(self):
        """Return the scene state attributes."""
        attributes = {}
        for attr in [
            "media_content_rating",
            "media_library_title",
            "player_source",
            "media_summary",
            "username",
        ]:
            value = getattr(self, attr, None)
            if value:
                attributes[attr] = value

        return attributes

    @property
    def device_info(self):
        """Return a device description for device registry."""
        if self.machine_identifier is None:
            return None

        if self.device_product in TRANSIENT_DEVICE_MODELS:
            return {
                "identifiers": {(PLEX_DOMAIN, "plex.tv-clients")},
                "name": "Plex Client Service",
                "manufacturer": "Plex",
                "model": "Plex Clients",
                "entry_type": "service",
            }

        return {
            "identifiers": {(PLEX_DOMAIN, self.machine_identifier)},
            "manufacturer": self.device_platform or "Plex",
            "model": self.device_product or self.device_make,
            "name": self.name,
            "sw_version": self.device_version,
            "via_device": (PLEX_DOMAIN, self.plex_server.machine_identifier),
        }

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        is_internal = is_internal_request(self.hass)
        return await self.hass.async_add_executor_job(
            browse_media,
            self,
            is_internal,
            media_content_type,
            media_content_id,
        )

    async def async_get_browse_image(
        self, media_content_type, media_content_id, media_image_id=None
    ):
        """Get media image from Plex server."""
        image_url = self.plex_server.thumbnail_cache.get(media_content_id)
        if image_url:
            result = await self._async_fetch_image(image_url)
            return result

        return (None, None)
