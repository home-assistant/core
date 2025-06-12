"""Support to interface with Sonos players."""

from __future__ import annotations

import datetime
from functools import partial
import logging
from typing import Any

from soco import SoCo, alarms
from soco.core import (
    MUSIC_SRC_LINE_IN,
    MUSIC_SRC_RADIO,
    PLAY_MODE_BY_MEANING,
    PLAY_MODES,
)
from soco.data_structures import DidlFavorite, DidlMusicTrack
from soco.ms_data_structures import MusicServiceItem
from sonos_websocket.exception import SonosWebsocketError
import voluptuous as vol

from homeassistant.components import media_source, spotify
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_TITLE,
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.components.plex import PLEX_URI_SCHEME
from homeassistant.components.plex.services import process_plex_payload
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TIME
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform, service
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import UnjoinData, media_browser
from .const import (
    DATA_SONOS,
    DOMAIN,
    MEDIA_TYPE_DIRECTORY,
    MEDIA_TYPES_TO_SONOS,
    MODELS_LINEIN_AND_TV,
    MODELS_LINEIN_ONLY,
    MODELS_TV_ONLY,
    PLAYABLE_MEDIA_TYPES,
    SONOS_CREATE_MEDIA_PLAYER,
    SONOS_MEDIA_UPDATED,
    SONOS_STATE_PLAYING,
    SONOS_STATE_TRANSITIONING,
    SOURCE_LINEIN,
    SOURCE_TV,
)
from .entity import SonosEntity
from .helpers import soco_error
from .speaker import SonosMedia, SonosSpeaker

_LOGGER = logging.getLogger(__name__)

LONG_SERVICE_TIMEOUT = 30.0
UNJOIN_SERVICE_TIMEOUT = 0.1
VOLUME_INCREMENT = 2

REPEAT_TO_SONOS = {
    RepeatMode.OFF: False,
    RepeatMode.ALL: True,
    RepeatMode.ONE: "ONE",
}

SONOS_TO_REPEAT = {meaning: mode for mode, meaning in REPEAT_TO_SONOS.items()}

UPNP_ERRORS_TO_IGNORE = ["701", "711", "712"]
ANNOUNCE_NOT_SUPPORTED_ERRORS: list[str] = ["globalError"]

SERVICE_SNAPSHOT = "snapshot"
SERVICE_RESTORE = "restore"
SERVICE_SET_TIMER = "set_sleep_timer"
SERVICE_CLEAR_TIMER = "clear_sleep_timer"
SERVICE_UPDATE_ALARM = "update_alarm"
SERVICE_PLAY_QUEUE = "play_queue"
SERVICE_REMOVE_FROM_QUEUE = "remove_from_queue"
SERVICE_GET_QUEUE = "get_queue"

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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sonos from a config entry."""
    platform = entity_platform.async_get_current_platform()

    @callback
    def async_create_entities(speaker: SonosSpeaker) -> None:
        """Handle device discovery and create entities."""
        _LOGGER.debug("Creating media_player on %s", speaker.zone_name)
        async_add_entities([SonosMediaPlayerEntity(speaker)])

    @service.verify_domain_control(hass, DOMAIN)
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

        if service_call.service == SERVICE_SNAPSHOT:
            await SonosSpeaker.snapshot_multi(
                hass, speakers, service_call.data[ATTR_WITH_GROUP]
            )
        elif service_call.service == SERVICE_RESTORE:
            await SonosSpeaker.restore_multi(
                hass, speakers, service_call.data[ATTR_WITH_GROUP]
            )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_MEDIA_PLAYER, async_create_entities)
    )

    join_unjoin_schema = cv.make_entity_service_schema(
        {vol.Optional(ATTR_WITH_GROUP, default=True): cv.boolean}
    )

    hass.services.async_register(
        DOMAIN, SERVICE_SNAPSHOT, async_service_handle, join_unjoin_schema
    )

    hass.services.async_register(
        DOMAIN, SERVICE_RESTORE, async_service_handle, join_unjoin_schema
    )

    platform.async_register_entity_service(
        SERVICE_SET_TIMER,
        {
            vol.Required(ATTR_SLEEP_TIME): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=86399)
            )
        },
        "set_sleep_timer",
    )

    platform.async_register_entity_service(
        SERVICE_CLEAR_TIMER, None, "clear_sleep_timer"
    )

    platform.async_register_entity_service(
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

    platform.async_register_entity_service(
        SERVICE_PLAY_QUEUE,
        {vol.Optional(ATTR_QUEUE_POSITION): cv.positive_int},
        "play_queue",
    )

    platform.async_register_entity_service(
        SERVICE_REMOVE_FROM_QUEUE,
        {vol.Optional(ATTR_QUEUE_POSITION): cv.positive_int},
        "remove_from_queue",
    )

    platform.async_register_entity_service(
        SERVICE_GET_QUEUE,
        None,
        "get_queue",
        supports_response=SupportsResponse.ONLY,
    )


class SonosMediaPlayerEntity(SonosEntity, MediaPlayerEntity):
    """Representation of a Sonos entity."""

    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.CLEAR_PLAYLIST
        | MediaPlayerEntityFeature.GROUPING
        | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
        | MediaPlayerEntityFeature.MEDIA_ENQUEUE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.REPEAT_SET
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SHUFFLE_SET
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
    )
    _attr_media_content_type = MediaType.MUSIC
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    def __init__(self, speaker: SonosSpeaker) -> None:
        """Initialize the media player entity."""
        super().__init__(speaker)
        self._attr_unique_id = self.soco.uid

    async def async_added_to_hass(self) -> None:
        """Handle common setup when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SONOS_MEDIA_UPDATED,
                self.async_write_media_state,
            )
        )

    @callback
    def async_write_media_state(self, uid: str) -> None:
        """Write media state if the provided UID is coordinator of this speaker."""
        if self.coordinator.uid == uid:
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if the media_player is available."""
        return (
            self.speaker.available
            and bool(self.speaker.sonos_group_entities)
            and self.media.playback_status is not None
        )

    @property
    def coordinator(self) -> SonosSpeaker:
        """Return the current coordinator SonosSpeaker."""
        return self.speaker.coordinator or self.speaker

    @property
    def group_members(self) -> list[str] | None:
        """List of entity_ids which are currently grouped together."""
        return self.speaker.sonos_group_entities

    def __hash__(self) -> int:
        """Return a hash of self."""
        return hash(self.unique_id)

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the entity."""
        if self.media.playback_status in (
            "PAUSED_PLAYBACK",
            "STOPPED",
        ):
            # Sonos can consider itself "paused" but without having media loaded
            # (happens if playing Spotify and via Spotify app
            # you pick another device to play on)
            if self.media.title is None:
                return MediaPlayerState.IDLE
            return MediaPlayerState.PAUSED
        if self.media.playback_status in (
            SONOS_STATE_PLAYING,
            SONOS_STATE_TRANSITIONING,
        ):
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    async def _async_fallback_poll(self) -> None:
        """Retrieve latest state by polling."""
        await (
            self.hass.data[DATA_SONOS].favorites[self.speaker.household_id].async_poll()
        )
        await self.hass.async_add_executor_job(self._update)

    def _update(self) -> None:
        """Retrieve latest state by polling."""
        self.speaker.update_groups()
        self.speaker.update_volume()
        if self.speaker.is_coordinator:
            self.media.poll_media()

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self.speaker.volume and self.speaker.volume / 100

    @property
    def is_volume_muted(self) -> bool | None:
        """Return true if volume is muted."""
        return self.speaker.muted

    @property
    def shuffle(self) -> bool | None:
        """Shuffling state."""
        return PLAY_MODES[self.media.play_mode][0]

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        sonos_repeat = PLAY_MODES[self.media.play_mode][1]
        return SONOS_TO_REPEAT[sonos_repeat]

    @property
    def media(self) -> SonosMedia:
        """Return the SonosMedia object from the coordinator speaker."""
        return self.coordinator.media

    @property
    def media_content_id(self) -> str | None:
        """Content id of current playing media."""
        return self.media.uri

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return int(self.media.duration) if self.media.duration else None

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self.media.position

    @property
    def media_position_updated_at(self) -> datetime.datetime | None:
        """When was the position of the current playing media valid."""
        return self.media.position_updated_at

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self.media.image_url or None

    @property
    def media_channel(self) -> str | None:
        """Channel currently playing."""
        return self.media.channel or None

    @property
    def media_playlist(self) -> str | None:
        """Title of playlist currently playing."""
        return self.media.playlist_name

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self.media.artist or None

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self.media.album_name or None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.media.title or None

    @property
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
    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self.soco.volume = int(volume * 100)

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    def set_shuffle(self, shuffle: bool) -> None:
        """Enable/Disable shuffle mode."""
        sonos_shuffle = shuffle
        sonos_repeat = PLAY_MODES[self.media.play_mode][1]
        self.coordinator.soco.play_mode = PLAY_MODE_BY_MEANING[
            (sonos_shuffle, sonos_repeat)
        ]

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    def set_repeat(self, repeat: RepeatMode) -> None:
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
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_favorite",
                translation_placeholders={
                    "name": name,
                },
            )

        src = fav.pop()
        self._play_favorite(src)

    def _play_favorite(self, favorite: DidlFavorite) -> None:
        """Play a favorite."""
        uri = favorite.reference.get_uri()
        soco = self.coordinator.soco
        if (
            soco.music_source_from_uri(uri)
            in [
                MUSIC_SRC_RADIO,
                MUSIC_SRC_LINE_IN,
            ]
            or favorite.reference.item_class == "object.item.audioItem.audioBook"
        ):
            soco.play_uri(
                uri,
                title=favorite.title,
                meta=favorite.resource_meta_data,
                timeout=LONG_SERVICE_TIMEOUT,
            )
        else:
            soco.clear_queue()
            soco.add_to_queue(favorite.reference, timeout=LONG_SERVICE_TIMEOUT)
            soco.play_from_queue(0)

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        model = self.coordinator.model_name.split()[-1].upper()
        if model in MODELS_LINEIN_ONLY:
            return [SOURCE_LINEIN]
        if model in MODELS_TV_ONLY:
            return [SOURCE_TV]
        if model in MODELS_LINEIN_AND_TV:
            return [SOURCE_LINEIN, SOURCE_TV]
        return []

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
    def media_seek(self, position: float) -> None:
        """Send seek command."""
        self.coordinator.soco.seek(str(datetime.timedelta(seconds=int(position))))

    @soco_error()
    def clear_playlist(self) -> None:
        """Clear players playlist."""
        self.coordinator.soco.clear_queue()

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play_media command to the media player.

        If media_id is a Plex payload, attempt Plex->Sonos playback.

        If media_id is an Apple Music, Deezer, Sonos, or Tidal share link,
        attempt playback using the respective service.

        If media_type is "playlist", media_id should be a Sonos
        Playlist name.  Otherwise, media_id should be a URI.
        """
        is_radio = False

        if media_source.is_media_source_id(media_id):
            is_radio = media_id.startswith("media-source://radio_browser/")
            media_type = MediaType.MUSIC
            media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, media.url)

        if kwargs.get(ATTR_MEDIA_ANNOUNCE):
            volume = kwargs.get("extra", {}).get("volume")
            _LOGGER.debug("Playing %s using websocket audioclip", media_id)
            try:
                assert self.speaker.websocket
                response, _ = await self.speaker.websocket.play_clip(
                    async_process_play_media_url(self.hass, media_id),
                    volume=volume,
                )
            except SonosWebsocketError as exc:
                raise HomeAssistantError(
                    f"Error when calling Sonos websocket: {exc}"
                ) from exc
            if response.get("success"):
                return
            if response.get("type") in ANNOUNCE_NOT_SUPPORTED_ERRORS:
                # If the speaker does not support announce do not raise and
                # fall through to_play_media to play the clip directly.
                _LOGGER.debug(
                    "Speaker %s does not support announce, media_id %s response %s",
                    self.speaker.zone_name,
                    media_id,
                    response,
                )
            else:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="announce_media_error",
                    translation_placeholders={
                        "media_id": media_id,
                        "response": response,
                    },
                )

        if spotify.is_spotify_media_type(media_type):
            media_type = spotify.resolve_spotify_media_type(media_type)
            media_id = spotify.spotify_uri_from_media_browser_url(media_id)

        await self.hass.async_add_executor_job(
            partial(self._play_media, media_type, media_id, is_radio, **kwargs)
        )

    @soco_error()
    def _play_media(
        self, media_type: MediaType | str, media_id: str, is_radio: bool, **kwargs: Any
    ) -> None:
        """Wrap sync calls to async_play_media."""
        _LOGGER.debug("_play_media media_type %s media_id %s", media_type, media_id)
        enqueue = kwargs.get(ATTR_MEDIA_ENQUEUE, MediaPlayerEnqueue.REPLACE)

        if media_type == "favorite_item_id":
            favorite = self.speaker.favorites.lookup_by_item_id(media_id)
            if favorite is None:
                raise ValueError(f"Missing favorite for media_id: {media_id}")
            self._play_favorite(favorite)
            return

        soco = self.coordinator.soco
        if media_id and media_id.startswith(PLEX_URI_SCHEME):
            plex_plugin = self.speaker.plex_plugin
            result = process_plex_payload(
                self.hass, media_type, media_id, supports_playqueues=False
            )
            if result.shuffle:
                self.set_shuffle(True)
            if enqueue == MediaPlayerEnqueue.ADD:
                plex_plugin.add_to_queue(result.media, timeout=LONG_SERVICE_TIMEOUT)
            elif enqueue in (
                MediaPlayerEnqueue.NEXT,
                MediaPlayerEnqueue.PLAY,
            ):
                pos = (self.media.queue_position or 0) + 1
                new_pos = plex_plugin.add_to_queue(
                    result.media, position=pos, timeout=LONG_SERVICE_TIMEOUT
                )
                if enqueue == MediaPlayerEnqueue.PLAY:
                    soco.play_from_queue(new_pos - 1)
            elif enqueue == MediaPlayerEnqueue.REPLACE:
                soco.clear_queue()
                plex_plugin.add_to_queue(result.media, timeout=LONG_SERVICE_TIMEOUT)
                soco.play_from_queue(0)
            return

        share_link = self.coordinator.share_link
        if share_link.is_share_link(media_id):
            if enqueue == MediaPlayerEnqueue.ADD:
                share_link.add_share_link_to_queue(
                    media_id, timeout=LONG_SERVICE_TIMEOUT
                )
            elif enqueue in (
                MediaPlayerEnqueue.NEXT,
                MediaPlayerEnqueue.PLAY,
            ):
                pos = (self.media.queue_position or 0) + 1
                new_pos = share_link.add_share_link_to_queue(
                    media_id, position=pos, timeout=LONG_SERVICE_TIMEOUT
                )
                if enqueue == MediaPlayerEnqueue.PLAY:
                    soco.play_from_queue(new_pos - 1)
            elif enqueue == MediaPlayerEnqueue.REPLACE:
                soco.clear_queue()
                share_link.add_share_link_to_queue(
                    media_id, timeout=LONG_SERVICE_TIMEOUT
                )
                soco.play_from_queue(0)
        elif media_type == MEDIA_TYPE_DIRECTORY:
            self._play_media_directory(
                soco=soco, media_type=media_type, media_id=media_id, enqueue=enqueue
            )
        elif media_type in {MediaType.MUSIC, MediaType.TRACK}:
            # If media ID is a relative URL, we serve it from HA.
            media_id = async_process_play_media_url(self.hass, media_id)

            if enqueue == MediaPlayerEnqueue.ADD:
                soco.add_uri_to_queue(media_id, timeout=LONG_SERVICE_TIMEOUT)
            elif enqueue in (
                MediaPlayerEnqueue.NEXT,
                MediaPlayerEnqueue.PLAY,
            ):
                pos = (self.media.queue_position or 0) + 1
                new_pos = soco.add_uri_to_queue(
                    media_id, position=pos, timeout=LONG_SERVICE_TIMEOUT
                )
                if enqueue == MediaPlayerEnqueue.PLAY:
                    soco.play_from_queue(new_pos - 1)
            elif enqueue == MediaPlayerEnqueue.REPLACE:
                soco.play_uri(media_id, force_radio=is_radio)
        elif media_type == MediaType.PLAYLIST:
            if media_id.startswith("S:"):
                playlist = media_browser.get_media(
                    self.media.library, media_id, media_type
                )
            else:
                playlists = soco.get_sonos_playlists(complete_result=True)
                playlist = next((p for p in playlists if p.title == media_id), None)
            if not playlist:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_sonos_playlist",
                    translation_placeholders={
                        "name": media_id,
                    },
                )
            soco.clear_queue()
            soco.add_to_queue(playlist, timeout=LONG_SERVICE_TIMEOUT)
            soco.play_from_queue(0)
        elif media_type in PLAYABLE_MEDIA_TYPES:
            item = media_browser.get_media(self.media.library, media_id, media_type)
            if not item:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_media",
                    translation_placeholders={
                        "media_id": media_id,
                    },
                )
            self._play_media_queue(soco, item, enqueue)
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_content_type",
                translation_placeholders={
                    "media_type": media_type,
                },
            )

    def _play_media_queue(
        self, soco: SoCo, item: MusicServiceItem, enqueue: MediaPlayerEnqueue
    ):
        """Manage adding, replacing, playing items onto the sonos queue."""
        _LOGGER.debug(
            "_play_media_queue item_id [%s] title [%s] enqueue [%s]",
            item.item_id,
            item.title,
            enqueue,
        )
        if enqueue == MediaPlayerEnqueue.REPLACE:
            soco.clear_queue()

        if enqueue in (MediaPlayerEnqueue.ADD, MediaPlayerEnqueue.REPLACE):
            soco.add_to_queue(item, timeout=LONG_SERVICE_TIMEOUT)
            if enqueue == MediaPlayerEnqueue.REPLACE:
                soco.play_from_queue(0)
        else:
            pos = (self.media.queue_position or 0) + 1
            new_pos = soco.add_to_queue(
                item, position=pos, timeout=LONG_SERVICE_TIMEOUT
            )
            if enqueue == MediaPlayerEnqueue.PLAY:
                soco.play_from_queue(new_pos - 1)

    def _play_media_directory(
        self,
        soco: SoCo,
        media_type: MediaType | str,
        media_id: str,
        enqueue: MediaPlayerEnqueue,
    ):
        """Play a directory from a music library share."""
        item = media_browser.get_media(self.media.library, media_id, media_type)
        if not item:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_media",
                translation_placeholders={
                    "media_id": media_id,
                },
            )
        self._play_media_queue(soco, item, enqueue)

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
        alarm: alarms.Alarm | None = None
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

    @soco_error()
    def get_queue(self) -> list[dict]:
        """Get the queue."""
        queue: list[DidlMusicTrack] = self.coordinator.soco.get_queue(max_items=0)
        return [
            {
                ATTR_MEDIA_TITLE: getattr(track, "title", None),
                ATTR_MEDIA_ALBUM_NAME: getattr(track, "album", None),
                ATTR_MEDIA_ARTIST: getattr(track, "creator", None),
                ATTR_MEDIA_CONTENT_ID: track.get_uri(),
            }
            for track in queue
        ]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: dict[str, Any] = {}

        if self.media.queue_position is not None:
            attributes[ATTR_QUEUE_POSITION] = self.media.queue_position

        if self.media.queue_size:
            attributes["queue_size"] = self.media.queue_size

        if self.source:
            attributes[ATTR_INPUT_SOURCE] = self.source

        return attributes

    async def async_get_browse_image(
        self,
        media_content_type: MediaType | str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Fetch media browser image to serve via proxy."""
        if (
            media_content_type in {MediaType.ALBUM, MediaType.ARTIST}
            and media_content_id
        ):
            item = await self.hass.async_add_executor_job(
                media_browser.get_media,
                self.media.library,
                media_content_id,
                MEDIA_TYPES_TO_SONOS[media_content_type],
            )
            if image_url := getattr(item, "album_art_uri", None):
                return await self._async_fetch_image(image_url)

        return (None, None)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_browser.async_browse_media(
            self.hass,
            self.speaker,
            self.media,
            self.get_browse_image_url,
            media_content_id,
            media_content_type,
        )

    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        speakers = []
        for entity_id in group_members:
            if speaker := self.hass.data[DATA_SONOS].entity_id_mappings.get(entity_id):
                speakers.append(speaker)
            else:
                raise HomeAssistantError(f"Not a known Sonos entity_id: {entity_id}")

        await SonosSpeaker.join_multi(self.hass, self.speaker, speakers)

    async def async_unjoin_player(self) -> None:
        """Remove this player from any group.

        Coalesces all calls within UNJOIN_SERVICE_TIMEOUT to allow use of SonosSpeaker.unjoin_multi()
        which optimizes the order in which speakers are removed from their groups.
        Removing coordinators last better preserves playqueues on the speakers.
        """
        sonos_data = self.hass.data[DATA_SONOS]
        household_id = self.speaker.household_id

        async def async_process_unjoin(now: datetime.datetime) -> None:
            """Process the unjoin with all remove requests within the coalescing period."""
            unjoin_data = sonos_data.unjoin_data.pop(household_id)
            _LOGGER.debug(
                "Processing unjoins for %s", [x.zone_name for x in unjoin_data.speakers]
            )
            await SonosSpeaker.unjoin_multi(self.hass, unjoin_data.speakers)
            unjoin_data.event.set()

        if unjoin_data := sonos_data.unjoin_data.get(household_id):
            unjoin_data.speakers.append(self.speaker)
        else:
            unjoin_data = sonos_data.unjoin_data[household_id] = UnjoinData(
                speakers=[self.speaker]
            )
            async_call_later(self.hass, UNJOIN_SERVICE_TIMEOUT, async_process_unjoin)

        _LOGGER.debug("Requesting unjoin for %s", self.speaker.zone_name)
        await unjoin_data.event.wait()
