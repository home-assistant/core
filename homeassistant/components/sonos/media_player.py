"""Support to interface with Sonos players."""
from __future__ import annotations

import datetime
import logging
from typing import Any
import urllib.parse

from soco import alarms
from soco.core import (
    MUSIC_SRC_LINE_IN,
    MUSIC_SRC_RADIO,
    PLAY_MODE_BY_MEANING,
    PLAY_MODES,
)
import voluptuous as vol

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
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.plex.const import PLEX_URI_SCHEME
from homeassistant.components.plex.services import play_on_sonos
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TIME, STATE_IDLE, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, entity_platform, service
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import is_internal_request

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
from .media_browser import build_item_response, get_media, library_payload
from .speaker import SonosMedia, SonosSpeaker

_LOGGER = logging.getLogger(__name__)

SUPPORT_SONOS = (
    SUPPORT_BROWSE_MEDIA
    | SUPPORT_CLEAR_PLAYLIST
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
SERVICE_SET_OPTION = "set_option"
SERVICE_PLAY_QUEUE = "play_queue"
SERVICE_REMOVE_FROM_QUEUE = "remove_from_queue"

ATTR_SLEEP_TIME = "sleep_time"
ATTR_ALARM_ID = "alarm_id"
ATTR_VOLUME = "volume"
ATTR_ENABLED = "enabled"
ATTR_INCLUDE_LINKED_ZONES = "include_linked_zones"
ATTR_MASTER = "master"
ATTR_WITH_GROUP = "with_group"
ATTR_BUTTONS_ENABLED = "buttons_enabled"
ATTR_CROSSFADE = "crossfade"
ATTR_NIGHT_SOUND = "night_sound"
ATTR_SPEECH_ENHANCE = "speech_enhance"
ATTR_QUEUE_POSITION = "queue_position"
ATTR_STATUS_LIGHT = "status_light"


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
        SERVICE_SET_OPTION,
        {
            vol.Optional(ATTR_BUTTONS_ENABLED): cv.boolean,
            vol.Optional(ATTR_CROSSFADE): cv.boolean,
            vol.Optional(ATTR_NIGHT_SOUND): cv.boolean,
            vol.Optional(ATTR_SPEECH_ENHANCE): cv.boolean,
            vol.Optional(ATTR_STATUS_LIGHT): cv.boolean,
        },
        "set_option",
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

    @property
    def coordinator(self) -> SonosSpeaker:
        """Return the current coordinator SonosSpeaker."""
        return self.speaker.coordinator or self.speaker

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.soco.uid  # type: ignore[no-any-return]

    def __hash__(self) -> int:
        """Return a hash of self."""
        return hash(self.unique_id)

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.speaker.zone_name  # type: ignore[no-any-return]

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

    async def async_update(self) -> None:
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

    @property
    def media_content_type(self) -> str:
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

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

    @property  # type: ignore[misc]
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        return SUPPORT_SONOS

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
        elif source == SOURCE_TV:
            soco.switch_to_tv()
        else:
            fav = [fav for fav in self.speaker.favorites if fav.title == source]
            if len(fav) == 1:
                src = fav.pop()
                uri = src.reference.get_uri()
                if soco.music_source_from_uri(uri) in [
                    MUSIC_SRC_RADIO,
                    MUSIC_SRC_LINE_IN,
                ]:
                    soco.play_uri(uri, title=source)
                else:
                    soco.clear_queue()
                    soco.add_to_queue(src.reference)
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

        If media_id is a Sonos or Tidal share link, attempt playback
        using the respective service.

        If media_type is "playlist", media_id should be a Sonos
        Playlist name.  Otherwise, media_id should be a URI.

        If ATTR_MEDIA_ENQUEUE is True, add `media_id` to the queue.
        """
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
            if kwargs.get(ATTR_MEDIA_ENQUEUE):
                soco.add_uri_to_queue(media_id)
            else:
                soco.play_uri(media_id)
        elif media_type == MEDIA_TYPE_PLAYLIST:
            if media_id.startswith("S:"):
                item = get_media(self.media.library, media_id, media_type)  # type: ignore[no-untyped-call]
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
            item = get_media(self.media.library, media_id, media_type)  # type: ignore[no-untyped-call]

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
    def set_option(
        self,
        buttons_enabled: bool | None = None,
        crossfade: bool | None = None,
        night_sound: bool | None = None,
        speech_enhance: bool | None = None,
        status_light: bool | None = None,
    ) -> None:
        """Modify playback options."""
        if buttons_enabled is not None:
            self.soco.buttons_enabled = buttons_enabled

        if crossfade is not None:
            self.soco.cross_fade = crossfade

        if night_sound is not None and self.speaker.night_mode is not None:
            self.soco.night_mode = night_sound

        if speech_enhance is not None and self.speaker.dialog_mode is not None:
            self.soco.dialog_mode = speech_enhance

        if status_light is not None:
            self.soco.status_light = status_light

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

        if self.speaker.night_mode is not None:
            attributes[ATTR_NIGHT_SOUND] = self.speaker.night_mode

        if self.speaker.dialog_mode is not None:
            attributes[ATTR_SPEECH_ENHANCE] = self.speaker.dialog_mode

        if self.media.queue_position is not None:
            attributes[ATTR_QUEUE_POSITION] = self.media.queue_position

        return attributes

    async def async_get_browse_image(
        self,
        media_content_type: str | None,
        media_content_id: str | None,
        media_image_id: str | None = None,
    ) -> tuple[None | str, None | str]:
        """Fetch media browser image to serve via proxy."""
        if (
            media_content_type in [MEDIA_TYPE_ALBUM, MEDIA_TYPE_ARTIST]
            and media_content_id
        ):
            item = await self.hass.async_add_executor_job(
                get_media,
                self.media.library,
                media_content_id,
                MEDIA_TYPES_TO_SONOS[media_content_type],
            )
            image_url = getattr(item, "album_art_uri", None)
            if image_url:
                result = await self._async_fetch_image(image_url)  # type: ignore[no-untyped-call]
                return result  # type: ignore

        return (None, None)

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> Any:
        """Implement the websocket media browsing helper."""
        is_internal = is_internal_request(self.hass)

        def _get_thumbnail_url(
            media_content_type: str,
            media_content_id: str,
            media_image_id: str | None = None,
        ) -> str | None:
            if is_internal:
                item = get_media(  # type: ignore[no-untyped-call]
                    self.media.library,
                    media_content_id,
                    media_content_type,
                )
                return getattr(item, "album_art_uri", None)  # type: ignore[no-any-return]

            return self.get_browse_image_url(
                media_content_type,
                urllib.parse.quote_plus(media_content_id),
                media_image_id,
            )

        if media_content_type in [None, "library"]:
            return await self.hass.async_add_executor_job(
                library_payload, self.media.library, _get_thumbnail_url
            )

        payload = {
            "search_type": media_content_type,
            "idstring": media_content_id,
        }
        response = await self.hass.async_add_executor_job(
            build_item_response, self.media.library, payload, _get_thumbnail_url
        )
        if response is None:
            raise BrowseError(
                f"Media not found: {media_content_type} / {media_content_id}"
            )
        return response
