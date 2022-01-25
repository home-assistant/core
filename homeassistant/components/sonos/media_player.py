"""Support to interface with Sonos players."""
from __future__ import annotations

from asyncio import run_coroutine_threadsafe
import datetime
from datetime import timedelta
import logging
from typing import Any
from urllib.parse import quote

from soco import alarms
from soco.core import (
    MUSIC_SRC_LINE_IN,
    MUSIC_SRC_RADIO,
    PLAY_MODE_BY_MEANING,
    PLAY_MODES,
)
from soco.data_structures import DidlFavorite
import voluptuous as vol

from homeassistant.components import media_source, spotify
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ENQUEUE,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_TRACK,
    REPEAT_MODE_ALL,
    REPEAT_MODE_OFF,
    REPEAT_MODE_ONE,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_GROUPING,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.components.plex.const import PLEX_URI_SCHEME
from homeassistant.components.plex.services import play_on_sonos
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TIME, STATE_IDLE, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform, service
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import get_url

from . import media_browser
from .const import (
    DATA_SONOS,
    DOMAIN as SONOS_DOMAIN,
    MEDIA_TYPES_TO_SONOS,
    PLAYABLE_MEDIA_TYPES,
    SONOS_CREATE_MEDIA_PLAYER,
    SONOS_STATE_PLAYING,
    SONOS_STATE_TRANSITIONING,
    SOURCE_LINEIN,
    SOURCE_TV,
)
from .entity import SonosEntity
from .helpers import soco_error
from .speaker import SonosMedia, SonosSpeaker

_LOGGER = logging.getLogger(__name__)

SUPPORT_SONOS = (
    SUPPORT_BROWSE_MEDIA
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_GROUPING
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_REPEAT_SET
    | SUPPORT_SEEK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_STOP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
)

VOLUME_INCREMENT = 2

REPEAT_TO_SONOS = {
    REPEAT_MODE_OFF: False,
    REPEAT_MODE_ALL: True,
    REPEAT_MODE_ONE: "ONE",
}

SONOS_TO_REPEAT = {meaning: mode for mode, meaning in REPEAT_TO_SONOS.items()}

ATTR_SONOS_GROUP = "sonos_group"

UPNP_ERRORS_TO_IGNORE = ["701", "711", "712"]

SERVICE_JOIN = "join"
SERVICE_UNJOIN = "unjoin"
SERVICE_SNAPSHOT = "snapshot"
SERVICE_RESTORE = "restore"
SERVICE_SET_TIMER = "set_sleep_timer"
SERVICE_CLEAR_TIMER = "clear_sleep_timer"
SERVICE_UPDATE_ALARM = "update_alarm"
SERVICE_PLAY_QUEUE = "play_queue"
SERVICE_REMOVE_FROM_QUEUE = "remove_from_queue"

ATTR_SLEEP_TIME = "sleep_time"
ATTR_ALARM_ID = "alarm_id"
ATTR_VOLUME = "volume"
ATTR_ENABLED = "enabled"
ATTR_INCLUDE_LINKED_ZONES = "include_linked_zones"
ATTR_MASTER = "master"
ATTR_WITH_GROUP = "with_group"
ATTR_QUEUE_POSITION = "queue_position"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonos from a config entry."""
    platform = entity_platform.async_get_current_platform()

    @callback
    def async_create_entities(speaker: SonosSpeaker) -> None:
        """Handle device discovery and create entities."""
        _LOGGER.debug("Creating media_player on %s", speaker.zone_name)
        async_add_entities([SonosMediaPlayerEntity(speaker)])

    @service.verify_domain_control(hass, SONOS_DOMAIN)
    async def async_service_handle(service_call: ServiceCall) -> None:
        """Handle dispatched services."""
        assert platform is not None
        entities = await platform.async_extract_from_service(service_call)

        if not entities:
            return

        speakers = []
        for entity in entities:
            assert isinstance(entity, SonosMediaPlayerEntity)
            speakers.append(entity.speaker)

        if service_call.service == SERVICE_JOIN:
            master = platform.entities.get(service_call.data[ATTR_MASTER])
            if master:
                await SonosSpeaker.join_multi(hass, master.speaker, speakers)  # type: ignore[arg-type]
            else:
                _LOGGER.error(
                    "Invalid master specified for join service: %s",
                    service_call.data[ATTR_MASTER],
                )
        elif service_call.service == SERVICE_UNJOIN:
            await SonosSpeaker.unjoin_multi(hass, speakers)  # type: ignore[arg-type]
        elif service_call.service == SERVICE_SNAPSHOT:
            await SonosSpeaker.snapshot_multi(
                hass, speakers, service_call.data[ATTR_WITH_GROUP]  # type: ignore[arg-type]
            )
        elif service_call.service == SERVICE_RESTORE:
            await SonosSpeaker.restore_multi(
                hass, speakers, service_call.data[ATTR_WITH_GROUP]  # type: ignore[arg-type]
            )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_MEDIA_PLAYER, async_create_entities)
    )

    hass.services.async_register(
        SONOS_DOMAIN,
        SERVICE_JOIN,
        async_service_handle,
        cv.make_entity_service_schema({vol.Required(ATTR_MASTER): cv.entity_id}),
    )

    hass.services.async_register(
        SONOS_DOMAIN,
        SERVICE_UNJOIN,
        async_service_handle,
        cv.make_entity_service_schema({}),
    )

    join_unjoin_schema = cv.make_entity_service_schema(
        {vol.Optional(ATTR_WITH_GROUP, default=True): cv.boolean}
    )

    hass.services.async_register(
        SONOS_DOMAIN, SERVICE_SNAPSHOT, async_service_handle, join_unjoin_schema
    )

    hass.services.async_register(
        SONOS_DOMAIN, SERVICE_RESTORE, async_service_handle, join_unjoin_schema
    )

    platform.async_register_entity_service(  # type: ignore
        SERVICE_SET_TIMER,
        {
            vol.Required(ATTR_SLEEP_TIME): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=86399)
            )
        },
        "set_sleep_timer",
    )

    platform.async_register_entity_service(SERVICE_CLEAR_TIMER, {}, "clear_sleep_timer")  # type: ignore

    platform.async_register_entity_service(  # type: ignore
        SERVICE_UPDATE_ALARM,
        {
            vol.Required(ATTR_ALARM_ID): cv.positive_int,
            vol.Optional(ATTR_TIME): cv.time,
            vol.Optional(ATTR_VOLUME): cv.small_float,
            vol.Optional(ATTR_ENABLED): cv.boolean,
            vol.Optional(ATTR_INCLUDE_LINKED_ZONES): cv.boolean,
        },
        "set_alarm",
    )

    platform.async_register_entity_service(  # type: ignore
        SERVICE_PLAY_QUEUE,
        {vol.Optional(ATTR_QUEUE_POSITION): cv.positive_int},
        "play_queue",
    )

    platform.async_register_entity_service(  # type: ignore
        SERVICE_REMOVE_FROM_QUEUE,
        {vol.Optional(ATTR_QUEUE_POSITION): cv.positive_int},
        "remove_from_queue",
    )


class SonosMediaPlayerEntity(SonosEntity, MediaPlayerEntity):
    """Representation of a Sonos entity."""

    _attr_supported_features = SUPPORT_SONOS
    _attr_media_content_type = MEDIA_TYPE_MUSIC

    def __init__(self, speaker: SonosSpeaker) -> None:
        """Initialize the media player entity."""
        super().__init__(speaker)
        self._attr_unique_id = self.soco.uid
        self._attr_name = self.speaker.zone_name

    @property
    def coordinator(self) -> SonosSpeaker:
        """Return the current coordinator SonosSpeaker."""
        return self.speaker.coordinator or self.speaker

    def __hash__(self) -> int:
        """Return a hash of self."""
        return hash(self.unique_id)

    @property  # type: ignore[misc]
    def state(self) -> str:
        """Return the state of the entity."""
        if self.media.playback_status in (
            "PAUSED_PLAYBACK",
            "STOPPED",
        ):
            # Sonos can consider itself "paused" but without having media loaded
            # (happens if playing Spotify and via Spotify app you pick another device to play on)
            if self.media.title is None:
                return STATE_IDLE
            return STATE_PAUSED
        if self.media.playback_status in (
            SONOS_STATE_PLAYING,
            SONOS_STATE_TRANSITIONING,
        ):
            return STATE_PLAYING
        return STATE_IDLE

    async def _async_poll(self) -> None:
        """Retrieve latest state by polling."""
        await self.hass.data[DATA_SONOS].favorites[
            self.speaker.household_id
        ].async_poll()
        await self.hass.async_add_executor_job(self._update)

    def _update(self) -> None:
        """Retrieve latest state by polling."""
        self.speaker.update_groups()
        self.speaker.update_volume()
        if self.speaker.is_coordinator:
            self.speaker.update_media()

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self.speaker.volume and self.speaker.volume / 100

    @property
    def is_volume_muted(self) -> bool | None:
        """Return true if volume is muted."""
        return self.speaker.muted

    @property  # type: ignore[misc]
    def shuffle(self) -> str | None:
        """Shuffling state."""
        shuffle: str = PLAY_MODES[self.media.play_mode][0]
        return shuffle

    @property  # type: ignore[misc]
    def repeat(self) -> str | None:
        """Return current repeat mode."""
        sonos_repeat = PLAY_MODES[self.media.play_mode][1]
        return SONOS_TO_REPEAT[sonos_repeat]

    @property
    def media(self) -> SonosMedia:
        """Return the SonosMedia object from the coordinator speaker."""
        return self.coordinator.media

    @property  # type: ignore[misc]
    def media_content_id(self) -> str | None:
        """Content id of current playing media."""
        return self.media.uri

    @property  # type: ignore[misc]
    def media_duration(self) -> float | None:
        """Duration of current playing media in seconds."""
        return self.media.duration

    @property  # type: ignore[misc]
    def media_position(self) -> float | None:
        """Position of current playing media in seconds."""
        return self.media.position

    @property  # type: ignore[misc]
    def media_position_updated_at(self) -> datetime.datetime | None:
        """When was the position of the current playing media valid."""
        return self.media.position_updated_at

    @property  # type: ignore[misc]
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self.media.image_url or None

    @property  # type: ignore[misc]
    def media_channel(self) -> str | None:
        """Channel currently playing."""
        return self.media.channel or None

    @property
    def media_playlist(self) -> str | None:
        """Title of playlist currently playing."""
        return self.media.playlist_name

    @property  # type: ignore[misc]
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self.media.artist or None

    @property  # type: ignore[misc]
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self.media.album_name or None

    @property  # type: ignore[misc]
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.media.title or None

    @property  # type: ignore[misc]
    def source(self) -> str | None:
        """Name of the current input source."""
        return self.media.source_name or None

    @soco_error()
    def volume_up(self) -> None:
        """Volume up media player."""
        self.soco.volume += VOLUME_INCREMENT

    @soco_error()
    def volume_down(self) -> None:
        """Volume down media player."""
        self.soco.volume -= VOLUME_INCREMENT

    @soco_error()
    def set_volume_level(self, volume: str) -> None:
        """Set volume level, range 0..1."""
        self.soco.volume = str(int(volume * 100))

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    def set_shuffle(self, shuffle: str) -> None:
        """Enable/Disable shuffle mode."""
        sonos_shuffle = shuffle
        sonos_repeat = PLAY_MODES[self.media.play_mode][1]
        self.coordinator.soco.play_mode = PLAY_MODE_BY_MEANING[
            (sonos_shuffle, sonos_repeat)
        ]

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    def set_repeat(self, repeat: str) -> None:
        """Set repeat mode."""
        sonos_shuffle = PLAY_MODES[self.media.play_mode][0]
        sonos_repeat = REPEAT_TO_SONOS[repeat]
        self.coordinator.soco.play_mode = PLAY_MODE_BY_MEANING[
            (sonos_shuffle, sonos_repeat)
        ]

    @soco_error()
    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        self.soco.mute = mute

    @soco_error()
    def select_source(self, source: str) -> None:
        """Select input source."""
        soco = self.coordinator.soco
        if source == SOURCE_LINEIN:
            soco.switch_to_line_in()
            return

        if source == SOURCE_TV:
            soco.switch_to_tv()
            return

        self._play_favorite_by_name(source)

    def _play_favorite_by_name(self, name: str) -> None:
        """Play a favorite by name."""
        fav = [fav for fav in self.speaker.favorites if fav.title == name]

        if len(fav) != 1:
            return

        src = fav.pop()
        self._play_favorite(src)

    def _play_favorite(self, favorite: DidlFavorite) -> None:
        """Play a favorite."""
        uri = favorite.reference.get_uri()
        soco = self.coordinator.soco
        if soco.music_source_from_uri(uri) in [
            MUSIC_SRC_RADIO,
            MUSIC_SRC_LINE_IN,
        ]:
            soco.play_uri(uri, title=favorite.title)
        else:
            soco.clear_queue()
            soco.add_to_queue(favorite.reference)
            soco.play_from_queue(0)

    @property  # type: ignore[misc]
    def source_list(self) -> list[str]:
        """List of available input sources."""
        sources = [fav.title for fav in self.speaker.favorites]

        model = self.coordinator.model_name.upper()
        if "PLAY:5" in model or "CONNECT" in model:
            sources += [SOURCE_LINEIN]
        elif "PLAYBAR" in model:
            sources += [SOURCE_LINEIN, SOURCE_TV]
        elif "BEAM" in model or "PLAYBASE" in model:
            sources += [SOURCE_TV]

        return sources

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    def media_play(self) -> None:
        """Send play command."""
        self.coordinator.soco.play()

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    def media_stop(self) -> None:
        """Send stop command."""
        self.coordinator.soco.stop()

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    def media_pause(self) -> None:
        """Send pause command."""
        self.coordinator.soco.pause()

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    def media_next_track(self) -> None:
        """Send next track command."""
        self.coordinator.soco.next()

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    def media_previous_track(self) -> None:
        """Send next track command."""
        self.coordinator.soco.previous()

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    def media_seek(self, position: str) -> None:
        """Send seek command."""
        self.coordinator.soco.seek(str(datetime.timedelta(seconds=int(position))))

    @soco_error()
    def clear_playlist(self) -> None:
        """Clear players playlist."""
        self.coordinator.soco.clear_queue()

    @soco_error()
    def play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """
        Send the play_media command to the media player.

        If media_id is a Plex payload, attempt Plex->Sonos playback.

        If media_id is an Apple Music, Deezer, Sonos, or Tidal share link,
        attempt playback using the respective service.

        If media_type is "playlist", media_id should be a Sonos
        Playlist name.  Otherwise, media_id should be a URI.

        If ATTR_MEDIA_ENQUEUE is True, add `media_id` to the queue.
        """
        if spotify.is_spotify_media_type(media_type):
            media_type = spotify.resolve_spotify_media_type(media_type)

        if media_source.is_media_source_id(media_id):
            media_type = MEDIA_TYPE_MUSIC
            media_id = (
                run_coroutine_threadsafe(
                    media_source.async_resolve_media(self.hass, media_id),
                    self.hass.loop,
                )
                .result()
                .url
            )

        if media_type == "favorite_item_id":
            favorite = self.speaker.favorites.lookup_by_item_id(media_id)
            if favorite is None:
                raise ValueError(f"Missing favorite for media_id: {media_id}")
            self._play_favorite(favorite)
            return

        soco = self.coordinator.soco
        if media_id and media_id.startswith(PLEX_URI_SCHEME):
            media_id = media_id[len(PLEX_URI_SCHEME) :]
            play_on_sonos(self.hass, media_type, media_id, self.name)  # type: ignore[no-untyped-call]
            return

        share_link = self.speaker.share_link
        if share_link.is_share_link(media_id):
            if kwargs.get(ATTR_MEDIA_ENQUEUE):
                share_link.add_share_link_to_queue(media_id)
            else:
                soco.clear_queue()
                share_link.add_share_link_to_queue(media_id)
                soco.play_from_queue(0)
        elif media_type in (MEDIA_TYPE_MUSIC, MEDIA_TYPE_TRACK):
            # If media ID is a relative URL, we serve it from HA.
            # Create a signed path.
            if media_id[0] == "/":
                media_id = async_sign_path(
                    self.hass,
                    quote(media_id),
                    timedelta(seconds=media_source.DEFAULT_EXPIRY_TIME),
                )

                # prepend external URL
                hass_url = get_url(self.hass, prefer_external=True)
                media_id = f"{hass_url}{media_id}"

            if kwargs.get(ATTR_MEDIA_ENQUEUE):
                soco.add_uri_to_queue(media_id)
            else:
                soco.play_uri(media_id)
        elif media_type == MEDIA_TYPE_PLAYLIST:
            if media_id.startswith("S:"):
                item = media_browser.get_media(self.media.library, media_id, media_type)  # type: ignore[no-untyped-call]
                soco.play_uri(item.get_uri())
                return
            try:
                playlists = soco.get_sonos_playlists()
                playlist = next(p for p in playlists if p.title == media_id)
            except StopIteration:
                _LOGGER.error('Could not find a Sonos playlist named "%s"', media_id)
            else:
                soco.clear_queue()
                soco.add_to_queue(playlist)
                soco.play_from_queue(0)
        elif media_type in PLAYABLE_MEDIA_TYPES:
            item = media_browser.get_media(self.media.library, media_id, media_type)  # type: ignore[no-untyped-call]

            if not item:
                _LOGGER.error('Could not find "%s" in the library', media_id)
                return

            soco.play_uri(item.get_uri())
        else:
            _LOGGER.error('Sonos does not support a media type of "%s"', media_type)

    @soco_error()
    def set_sleep_timer(self, sleep_time: int) -> None:
        """Set the timer on the player."""
        self.coordinator.soco.set_sleep_timer(sleep_time)

    @soco_error()
    def clear_sleep_timer(self) -> None:
        """Clear the timer on the player."""
        self.coordinator.soco.set_sleep_timer(None)

    @soco_error()
    def set_alarm(
        self,
        alarm_id: int,
        time: datetime.datetime | None = None,
        volume: float | None = None,
        enabled: bool | None = None,
        include_linked_zones: bool | None = None,
    ) -> None:
        """Set the alarm clock on the player."""
        alarm = None
        for one_alarm in alarms.get_alarms(self.coordinator.soco):
            if one_alarm.alarm_id == str(alarm_id):
                alarm = one_alarm
        if alarm is None:
            _LOGGER.warning("Did not find alarm with id %s", alarm_id)
            return
        if time is not None:
            alarm.start_time = time
        if volume is not None:
            alarm.volume = int(volume * 100)
        if enabled is not None:
            alarm.enabled = enabled
        if include_linked_zones is not None:
            alarm.include_linked_zones = include_linked_zones
        alarm.save()

    @soco_error()
    def play_queue(self, queue_position: int = 0) -> None:
        """Start playing the queue."""
        self.soco.play_from_queue(queue_position)

    @soco_error()
    def remove_from_queue(self, queue_position: int = 0) -> None:
        """Remove item from the queue."""
        self.coordinator.soco.remove_from_queue(queue_position)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: dict[str, Any] = {
            ATTR_SONOS_GROUP: self.speaker.sonos_group_entities
        }

        if self.media.queue_position is not None:
            attributes[ATTR_QUEUE_POSITION] = self.media.queue_position

        return attributes

    async def async_get_browse_image(
        self,
        media_content_type: str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Fetch media browser image to serve via proxy."""
        if (
            media_content_type in [MEDIA_TYPE_ALBUM, MEDIA_TYPE_ARTIST]
            and media_content_id
        ):
            item = await self.hass.async_add_executor_job(
                media_browser.get_media,
                self.media.library,
                media_content_id,
                MEDIA_TYPES_TO_SONOS[media_content_type],
            )
            if image_url := getattr(item, "album_art_uri", None):
                result = await self._async_fetch_image(image_url)  # type: ignore[no-untyped-call]
                return result  # type: ignore

        return (None, None)

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> Any:
        """Implement the websocket media browsing helper."""
        return await media_browser.async_browse_media(
            self.hass,
            self.speaker,
            self.media,
            self.get_browse_image_url,
            media_content_id,
            media_content_type,
        )

    def join_players(self, group_members):
        """Join `group_members` as a player group with the current player."""
        speakers = []
        for entity_id in group_members:
            if speaker := self.hass.data[DATA_SONOS].entity_id_mappings.get(entity_id):
                speakers.append(speaker)
            else:
                raise HomeAssistantError(f"Not a known Sonos entity_id: {entity_id}")

        self.speaker.join(speakers)

    def unjoin_player(self):
        """Remove this player from any group."""
        self.speaker.unjoin()
