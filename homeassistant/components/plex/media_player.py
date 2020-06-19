"""Support to interface with the Plex API."""
import json
import logging

import plexapi.exceptions
import requests.exceptions

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_TVSHOW,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.util import dt as dt_util

from .const import (
    COMMON_PLAYERS,
    CONF_SERVER_IDENTIFIER,
    DISPATCHERS,
    DOMAIN as PLEX_DOMAIN,
    NAME_FORMAT,
    PLEX_NEW_MP_SIGNAL,
    PLEX_UPDATE_MEDIA_PLAYER_SIGNAL,
    SERVERS,
)

LIVE_TV_SECTION = "-4"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Plex media_player from a config entry."""
    server_id = config_entry.data[CONF_SERVER_IDENTIFIER]
    registry = await async_get_registry(hass)

    @callback
    def async_new_media_players(new_entities):
        _async_add_entities(
            hass, registry, config_entry, async_add_entities, server_id, new_entities
        )

    unsub = async_dispatcher_connect(
        hass, PLEX_NEW_MP_SIGNAL.format(server_id), async_new_media_players
    )
    hass.data[PLEX_DOMAIN][DISPATCHERS][server_id].append(unsub)
    _LOGGER.debug("New entity listener created")


@callback
def _async_add_entities(
    hass, registry, config_entry, async_add_entities, server_id, new_entities
):
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

    def __init__(self, plex_server, device, session=None):
        """Initialize the Plex device."""
        self.plex_server = plex_server
        self.device = device
        self.session = session
        self._app_name = ""
        self._available = False
        self._device_protocol_capabilities = None
        self._is_player_active = False
        self._machine_identifier = device.machineIdentifier
        self._make = ""
        self._device_platform = None
        self._device_product = None
        self._device_title = None
        self._device_version = None
        self._name = None
        self._player_state = "idle"
        self._previous_volume_level = 1  # Used in fake muting
        self._session_type = None
        self._session_username = None
        self._state = STATE_IDLE
        self._volume_level = 1  # since we can't retrieve remotely
        self._volume_muted = False  # since we can't retrieve remotely
        # General
        self._media_content_id = None
        self._media_content_rating = None
        self._media_content_type = None
        self._media_duration = None
        self._media_image_url = None
        self._media_summary = None
        self._media_title = None
        self._media_position = None
        self._media_position_updated_at = None
        # Music
        self._media_album_artist = None
        self._media_album_name = None
        self._media_artist = None
        self._media_track = None
        # TV Show
        self._media_episode = None
        self._media_season = None
        self._media_series_title = None

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        server_id = self.plex_server.machine_identifier

        _LOGGER.debug("Added %s [%s]", self.entity_id, self.unique_id)
        unsub = async_dispatcher_connect(
            self.hass,
            PLEX_UPDATE_MEDIA_PLAYER_SIGNAL.format(self.unique_id),
            self.async_refresh_media_player,
        )
        self.hass.data[PLEX_DOMAIN][DISPATCHERS][server_id].append(unsub)

    @callback
    def async_refresh_media_player(self, device, session):
        """Set instance objects and trigger an entity state update."""
        _LOGGER.debug("Refreshing %s [%s / %s]", self.entity_id, device, session)
        self.device = device
        self.session = session
        self.async_schedule_update_ha_state(True)

    def _clear_media_details(self):
        """Set all Media Items to None."""
        # General
        self._media_content_id = None
        self._media_content_rating = None
        self._media_content_type = None
        self._media_duration = None
        self._media_image_url = None
        self._media_summary = None
        self._media_title = None
        # Music
        self._media_album_artist = None
        self._media_album_name = None
        self._media_artist = None
        self._media_track = None
        # TV Show
        self._media_episode = None
        self._media_season = None
        self._media_series_title = None

        # Clear library Name
        self._app_name = ""

    def update(self):
        """Refresh key device data."""
        self._clear_media_details()

        self._available = self.device or self.session

        if self.device:
            try:
                device_url = self.device.url("/")
            except plexapi.exceptions.BadRequest:
                device_url = "127.0.0.1"
            if "127.0.0.1" in device_url:
                self.device.proxyThroughServer()
            self._device_platform = self.device.platform
            self._device_product = self.device.product
            self._device_title = self.device.title
            self._device_version = self.device.version
            self._device_protocol_capabilities = self.device.protocolCapabilities
            self._player_state = self.device.state

        if not self.session:
            self.force_idle()
        else:
            session_device = next(
                (
                    p
                    for p in self.session.players
                    if p.machineIdentifier == self.device.machineIdentifier
                ),
                None,
            )
            if session_device:
                self._make = session_device.device or ""
                self._player_state = session_device.state
                self._device_platform = self._device_platform or session_device.platform
                self._device_product = self._device_product or session_device.product
                self._device_title = self._device_title or session_device.title
                self._device_version = self._device_version or session_device.version
            else:
                _LOGGER.warning("No player associated with active session")

            if self.session.usernames:
                self._session_username = self.session.usernames[0]

            # Calculate throttled position for proper progress display.
            position = int(self.session.viewOffset / 1000)
            now = dt_util.utcnow()
            if self._media_position is not None:
                pos_diff = position - self._media_position
                time_diff = now - self._media_position_updated_at
                if pos_diff != 0 and abs(time_diff.total_seconds() - pos_diff) > 5:
                    self._media_position_updated_at = now
                    self._media_position = position
            else:
                self._media_position_updated_at = now
                self._media_position = position

            self._media_content_id = self.session.ratingKey
            self._media_content_rating = getattr(self.session, "contentRating", None)

        name_parts = [self._device_product, self._device_title or self._device_platform]
        if (self._device_product in COMMON_PLAYERS) and self.make:
            # Add more context in name for likely duplicates
            name_parts.append(self.make)
        if self.username and self.username != self.plex_server.owner:
            # Prepend username for shared/managed clients
            name_parts.insert(0, self.username)
        self._name = NAME_FORMAT.format(" - ".join(name_parts))
        self._set_player_state()

        if self._is_player_active and self.session is not None:
            self._session_type = self.session.type
            if self.session.duration:
                self._media_duration = int(self.session.duration / 1000)
            else:
                self._media_duration = None
            #  title (movie name, tv episode name, music song name)
            self._media_summary = self.session.summary
            self._media_title = self.session.title
            # media type
            self._set_media_type()
            if self.session.librarySectionID == LIVE_TV_SECTION:
                self._app_name = "Live TV"
            else:
                self._app_name = (
                    self.session.section().title
                    if self.session.section() is not None
                    else ""
                )
            self._set_media_image()
        else:
            self._session_type = None

    def _set_media_image(self):
        thumb_url = self.session.thumbUrl
        if (
            self.media_content_type is MEDIA_TYPE_TVSHOW
            and not self.plex_server.option_use_episode_art
        ):
            if self.session.librarySectionID == LIVE_TV_SECTION:
                thumb_url = self.session.grandparentThumb
            else:
                thumb_url = self.session.url(self.session.grandparentThumb)

        if thumb_url is None:
            _LOGGER.debug(
                "Using media art because media thumb was not found: %s", self.name
            )
            thumb_url = self.session.url(self.session.art)

        self._media_image_url = thumb_url

    def _set_player_state(self):
        if self._player_state == "playing":
            self._is_player_active = True
            self._state = STATE_PLAYING
        elif self._player_state == "paused":
            self._is_player_active = True
            self._state = STATE_PAUSED
        elif self.device:
            self._is_player_active = False
            self._state = STATE_IDLE
        else:
            self._is_player_active = False
            self._state = STATE_OFF

    def _set_media_type(self):
        if self._session_type in ["clip", "episode"]:
            self._media_content_type = MEDIA_TYPE_TVSHOW

            # season number (00)
            self._media_season = self.session.seasonNumber
            # show name
            self._media_series_title = self.session.grandparentTitle
            # episode number (00)
            if self.session.index is not None:
                self._media_episode = self.session.index

        elif self._session_type == "movie":
            self._media_content_type = MEDIA_TYPE_MOVIE
            if self.session.year is not None and self._media_title is not None:
                self._media_title += f" ({self.session.year!s})"

        elif self._session_type == "track":
            self._media_content_type = MEDIA_TYPE_MUSIC
            self._media_album_name = self.session.parentTitle
            self._media_album_artist = self.session.grandparentTitle
            self._media_track = self.session.index
            self._media_artist = self.session.originalTitle
            # use album artist if track artist is missing
            if self._media_artist is None:
                _LOGGER.debug(
                    "Using album artist because track artist was not found: %s",
                    self.name,
                )
                self._media_artist = self._media_album_artist

    def force_idle(self):
        """Force client to idle."""
        self._player_state = STATE_IDLE
        self._state = STATE_IDLE
        self.session = None
        self._clear_media_details()

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def unique_id(self):
        """Return the id of this plex client."""
        return f"{self.plex_server.machine_identifier}:{self._machine_identifier}"

    @property
    def machine_identifier(self):
        """Return the Plex-provided identifier of this plex client."""
        return self._machine_identifier

    @property
    def available(self):
        """Return the availability of the client."""
        return self._available

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def username(self):
        """Return the username of the client owner."""
        return self._session_username

    @property
    def app_name(self):
        """Return the library name of playing media."""
        return self._app_name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def _active_media_plexapi_type(self):
        """Get the active media type required by PlexAPI commands."""
        if self.media_content_type is MEDIA_TYPE_MUSIC:
            return "music"

        return "video"

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self._media_content_id

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        if self._session_type == "clip":
            _LOGGER.debug(
                "Clip content type detected, compatibility may vary: %s", self.name
            )
            return MEDIA_TYPE_TVSHOW
        if self._session_type == "episode":
            return MEDIA_TYPE_TVSHOW
        if self._session_type == "movie":
            return MEDIA_TYPE_MOVIE
        if self._session_type == "track":
            return MEDIA_TYPE_MUSIC

        return None

    @property
    def media_artist(self):
        """Return the artist of current playing media, music track only."""
        return self._media_artist

    @property
    def media_album_name(self):
        """Return the album name of current playing media, music track only."""
        return self._media_album_name

    @property
    def media_album_artist(self):
        """Return the album artist of current playing media, music only."""
        return self._media_album_artist

    @property
    def media_track(self):
        """Return the track number of current playing media, music only."""
        return self._media_track

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return self._media_duration

    @property
    def media_position(self):
        """Return the duration of current playing media in seconds."""
        return self._media_position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._media_position_updated_at

    @property
    def media_image_url(self):
        """Return the image URL of current playing media."""
        return self._media_image_url

    @property
    def media_summary(self):
        """Return the summary of current playing media."""
        return self._media_summary

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self._media_title

    @property
    def media_season(self):
        """Return the season of current playing media (TV Show only)."""
        return self._media_season

    @property
    def media_series_title(self):
        """Return the title of the series of current playing media."""
        return self._media_series_title

    @property
    def media_episode(self):
        """Return the episode of current playing media (TV Show only)."""
        return self._media_episode

    @property
    def make(self):
        """Return the make of the device (ex. SHIELD Android TV)."""
        return self._make

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self.device and "playback" in self._device_protocol_capabilities:
            return (
                SUPPORT_PAUSE
                | SUPPORT_PREVIOUS_TRACK
                | SUPPORT_NEXT_TRACK
                | SUPPORT_STOP
                | SUPPORT_VOLUME_SET
                | SUPPORT_PLAY
                | SUPPORT_PLAY_MEDIA
                | SUPPORT_VOLUME_MUTE
            )

        return SUPPORT_PLAY_MEDIA

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

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        if self._is_player_active and self.device:
            return self._volume_muted

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

        src = json.loads(media_id)
        if isinstance(src, int):
            src = {"plex_key": src}

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
    def device_state_attributes(self):
        """Return the scene state attributes."""
        attr = {
            "media_content_rating": self._media_content_rating,
            "session_username": self.username,
            "media_library_name": self._app_name,
            "summary": self.media_summary,
        }

        return attr

    @property
    def device_info(self):
        """Return a device description for device registry."""
        if self.machine_identifier is None:
            return None

        return {
            "identifiers": {(PLEX_DOMAIN, self.machine_identifier)},
            "manufacturer": self._device_platform or "Plex",
            "model": self._device_product or self.make,
            "name": self.name,
            "sw_version": self._device_version,
            "via_device": (PLEX_DOMAIN, self.plex_server.machine_identifier),
        }
