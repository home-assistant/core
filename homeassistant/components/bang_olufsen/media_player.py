"""Media player entity for the Bang & Olufsen integration."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import TYPE_CHECKING, Any, cast

from mozart_api import __version__ as MOZART_API_VERSION
from mozart_api.exceptions import ApiException
from mozart_api.models import (
    Action,
    Art,
    BeolinkLeader,
    ListeningModeProps,
    ListeningModeRef,
    OverlayPlayRequest,
    OverlayPlayRequestTextToSpeechTextToSpeech,
    PlaybackContentMetadata,
    PlaybackError,
    PlaybackProgress,
    PlayQueueItem,
    PlayQueueItemType,
    RenderingState,
    SceneProperties,
    SoftwareUpdateState,
    SoftwareUpdateStatus,
    Source,
    Uri,
    UserFlow,
    VolumeLevel,
    VolumeMute,
    VolumeState,
)
from mozart_api.mozart_client import MozartClient, get_highest_resolution_artwork

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_EXTRA,
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from . import BangOlufsenData
from .const import (
    BANG_OLUFSEN_STATES,
    CONF_BEOLINK_JID,
    CONNECTION_STATUS,
    DOMAIN,
    FALLBACK_SOURCES,
    HIDDEN_SOURCE_IDS,
    VALID_MEDIA_TYPES,
    BangOlufsenMediaType,
    BangOlufsenSource,
    WebsocketNotification,
)
from .entity import BangOlufsenEntity
from .util import get_serial_number_from_jid

_LOGGER = logging.getLogger(__name__)

BANG_OLUFSEN_FEATURES = (
    MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.CLEAR_PLAYLIST
    | MediaPlayerEntityFeature.GROUPING
    | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Media Player entity from config entry."""
    data: BangOlufsenData = hass.data[DOMAIN][config_entry.entry_id]

    # Add MediaPlayer entity
    async_add_entities(new_entities=[BangOlufsenMediaPlayer(config_entry, data.client)])


class BangOlufsenMediaPlayer(BangOlufsenEntity, MediaPlayerEntity):
    """Representation of a media player."""

    _attr_icon = "mdi:speaker-wireless"
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_supported_features = BANG_OLUFSEN_FEATURES

    def __init__(self, entry: ConfigEntry, client: MozartClient) -> None:
        """Initialize the media player."""
        super().__init__(entry, client)

        self._beolink_jid: str = self.entry.data[CONF_BEOLINK_JID]
        self._model: str = self.entry.data[CONF_MODEL]

        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{self._host}/#/",
            identifiers={(DOMAIN, self._unique_id)},
            manufacturer="Bang & Olufsen",
            model=self._model,
            serial_number=self._unique_id,
        )
        self._attr_unique_id = self._unique_id

        # Misc. variables.
        self._audio_sources: dict[str, str] = {}
        self._media_image: Art = Art()
        self._software_status: SoftwareUpdateStatus = SoftwareUpdateStatus(
            software_version="",
            state=SoftwareUpdateState(seconds_remaining=0, value="idle"),
        )
        self._sources: dict[str, str] = {}
        self._state: str = MediaPlayerState.IDLE
        self._video_sources: dict[str, str] = {}
        self._sound_modes: dict[str, int] = {}

        # Beolink compatible sources
        self._beolink_sources: dict[str, bool] = {}
        self._remote_leader: BeolinkLeader | None = None

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        await self._initialize()

        signal_handlers: dict[str, Callable] = {
            CONNECTION_STATUS: self._async_update_connection_state,
            WebsocketNotification.ACTIVE_LISTENING_MODE: self._async_update_sound_modes,
            WebsocketNotification.BEOLINK: self._async_update_beolink,
            WebsocketNotification.PLAYBACK_ERROR: self._async_update_playback_error,
            WebsocketNotification.PLAYBACK_METADATA: self._async_update_playback_metadata_and_beolink,
            WebsocketNotification.PLAYBACK_PROGRESS: self._async_update_playback_progress,
            WebsocketNotification.PLAYBACK_STATE: self._async_update_playback_state,
            WebsocketNotification.REMOTE_MENU_CHANGED: self._async_update_sources,
            WebsocketNotification.SOURCE_CHANGE: self._async_update_source_change,
            WebsocketNotification.VOLUME: self._async_update_volume,
        }

        for signal, signal_handler in signal_handlers.items():
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"{self._unique_id}_{signal}",
                    signal_handler,
                )
            )

    async def _initialize(self) -> None:
        """Initialize connection dependent variables."""

        # Get software version.
        self._software_status = await self._client.get_softwareupdate_status()

        _LOGGER.debug(
            "Connected to: %s %s running SW %s",
            self._model,
            self._unique_id,
            self._software_status.software_version,
        )

        # Get overall device state once. This is handled by WebSocket events the rest of the time.
        product_state = await self._client.get_product_state()

        # Get volume information.
        if product_state.volume:
            self._volume = product_state.volume

        # Get all playback information.
        # Ensure that the metadata is not None upon startup
        if product_state.playback:
            if product_state.playback.metadata:
                self._playback_metadata = product_state.playback.metadata
                self._remote_leader = product_state.playback.metadata.remote_leader
            if product_state.playback.progress:
                self._playback_progress = product_state.playback.progress
            if product_state.playback.source:
                self._source_change = product_state.playback.source
            if product_state.playback.state:
                self._playback_state = product_state.playback.state
                # Set initial state
                if self._playback_state.value:
                    self._state = self._playback_state.value

        self._attr_media_position_updated_at = utcnow()

        # Get the highest resolution available of the given images.
        self._media_image = get_highest_resolution_artwork(self._playback_metadata)

        # If the device has been updated with new sources, then the API will fail here.
        await self._async_update_sources()

        await self._async_update_sound_modes()

    async def _async_update_sources(self) -> None:
        """Get sources for the specific product."""

        # Audio sources
        try:
            # Get all available sources.
            sources = await self._client.get_available_sources(target_remote=False)

        # Use a fallback list of sources
        except ValueError:
            # Try to get software version from device
            if self.device_info:
                sw_version = self.device_info.get("sw_version")
            if not sw_version:
                sw_version = self._software_status.software_version

            _LOGGER.warning(
                "The API is outdated compared to the device software version %s and %s. Using fallback sources",
                MOZART_API_VERSION,
                sw_version,
            )
            sources = FALLBACK_SOURCES

        # Save all of the relevant enabled sources, both the ID and the friendly name for displaying in a dict.
        self._audio_sources = {
            source.id: source.name
            for source in cast(list[Source], sources.items)
            if source.is_enabled
            and source.id
            and source.name
            and source.id not in HIDDEN_SOURCE_IDS
        }

        # Some sources are not Beolink expandable, meaning that they can't be joined by
        # or expand to other Bang & Olufsen devices for a multi-room experience.
        # _source_change, which is used throughout the entity for current source
        # information, lacks this information, so source ID's and their expandability is
        # stored in the self._beolink_sources variable.
        self._beolink_sources = {
            source.id: (
                source.is_multiroom_available
                if source.is_multiroom_available is not None
                else False
            )
            for source in cast(list[Source], sources.items)
            if source.id
        }

        # Video sources from remote menu
        menu_items = await self._client.get_remote_menu()

        for key in menu_items:
            menu_item = menu_items[key]

            if not menu_item.available:
                continue

            # TV SOURCES
            if (
                menu_item.content is not None
                and menu_item.content.categories
                and len(menu_item.content.categories) > 0
                and "music" not in menu_item.content.categories
                and menu_item.label
                and menu_item.label != "TV"
            ):
                self._video_sources[key] = menu_item.label

        # Combine the source dicts
        self._sources = self._audio_sources | self._video_sources

        self._attr_source_list = list(self._sources.values())

        # HASS won't necessarily be running the first time this method is run
        if self.hass.is_running:
            self.async_write_ha_state()

    async def _async_update_playback_metadata_and_beolink(
        self, data: PlaybackContentMetadata
    ) -> None:
        """Update _playback_metadata and related."""
        self._playback_metadata = data

        # Update current artwork and remote_leader.
        self._media_image = get_highest_resolution_artwork(self._playback_metadata)
        await self._async_update_beolink()

    @callback
    def _async_update_playback_error(self, data: PlaybackError) -> None:
        """Show playback error."""
        raise HomeAssistantError(data.error)

    @callback
    def _async_update_playback_progress(self, data: PlaybackProgress) -> None:
        """Update _playback_progress and last update."""
        self._playback_progress = data
        self._attr_media_position_updated_at = utcnow()

        self.async_write_ha_state()

    @callback
    def _async_update_playback_state(self, data: RenderingState) -> None:
        """Update _playback_state and related."""
        self._playback_state = data

        # Update entity state based on the playback state.
        if self._playback_state.value:
            self._state = self._playback_state.value

            self.async_write_ha_state()

    @callback
    def _async_update_source_change(self, data: Source) -> None:
        """Update _source_change and related."""
        self._source_change = data

        # Check if source is line-in or optical and progress should be updated
        if self._source_change.id in (
            BangOlufsenSource.LINE_IN.id,
            BangOlufsenSource.SPDIF.id,
        ):
            self._playback_progress = PlaybackProgress(progress=0)

        self.async_write_ha_state()

    @callback
    def _async_update_volume(self, data: VolumeState) -> None:
        """Update _volume."""
        self._volume = data

        self.async_write_ha_state()

    async def _async_update_beolink(self) -> None:
        """Update the current Beolink leader, listeners, peers and self."""

        # Add Beolink listeners / leader
        self._remote_leader = self._playback_metadata.remote_leader

        # Create group members list
        group_members = []

        # If the device is a listener.
        if self._remote_leader is not None:
            # Add leader if available in Home Assistant
            leader = self._get_entity_id_from_jid(self._remote_leader.jid)
            group_members.append(
                leader
                if leader is not None
                else f"leader_not_in_hass-{self._remote_leader.friendly_name}"
            )

            # Add self
            group_members.append(self.entity_id)

        # If not listener, check if leader.
        else:
            beolink_listeners = await self._client.get_beolink_listeners()

            # Check if the device is a leader.
            if len(beolink_listeners) > 0:
                # Add self
                group_members.append(self.entity_id)

                # Get the entity_ids of the listeners if available in Home Assistant
                group_members.extend(
                    [
                        listener
                        if (
                            listener := self._get_entity_id_from_jid(
                                beolink_listener.jid
                            )
                        )
                        is not None
                        else f"listener_not_in_hass-{beolink_listener.jid}"
                        for beolink_listener in beolink_listeners
                    ]
                )

        self._attr_group_members = group_members

        self.async_write_ha_state()

    def _get_entity_id_from_jid(self, jid: str) -> str | None:
        """Get entity_id from Beolink JID (if available)."""

        unique_id = get_serial_number_from_jid(jid)

        entity_registry = er.async_get(self.hass)
        return entity_registry.async_get_entity_id(
            Platform.MEDIA_PLAYER, DOMAIN, unique_id
        )

    def _get_beolink_jid(self, entity_id: str) -> str:
        """Get beolink JID from entity_id."""

        entity_registry = er.async_get(self.hass)

        # Check for valid bang_olufsen media_player entity
        entity_entry = entity_registry.async_get(entity_id)

        if (
            entity_entry is None
            or entity_entry.domain != Platform.MEDIA_PLAYER
            or entity_entry.platform != DOMAIN
            or entity_entry.config_entry_id is None
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_grouping_entity",
                translation_placeholders={"entity_id": entity_id},
            )

        config_entry = self.hass.config_entries.async_get_entry(
            entity_entry.config_entry_id
        )
        if TYPE_CHECKING:
            assert config_entry

        # Return JID
        return cast(str, config_entry.data[CONF_BEOLINK_JID])

    async def _async_update_sound_modes(
        self, active_sound_mode: ListeningModeProps | ListeningModeRef | None = None
    ) -> None:
        """Update the available sound modes."""
        sound_modes = await self._client.get_listening_mode_set()

        if active_sound_mode is None:
            active_sound_mode = await self._client.get_active_listening_mode()

        # Add the key to make the labels unique (As labels are not required to be unique on B&O devices)
        for sound_mode in sound_modes:
            label = f"{sound_mode.name} ({sound_mode.id})"

            self._sound_modes[label] = sound_mode.id

            if sound_mode.id == active_sound_mode.id:
                self._attr_sound_mode = label

        # Set available options
        self._attr_sound_mode_list = list(self._sound_modes)

        self.async_write_ha_state()

    @property
    def state(self) -> MediaPlayerState:
        """Return the current state of the media player."""
        return BANG_OLUFSEN_STATES[self._state]

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if self._volume.level and self._volume.level.level is not None:
            return float(self._volume.level.level / 100)
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if self._volume.muted and self._volume.muted.muted:
            return self._volume.muted.muted
        return None

    @property
    def media_content_type(self) -> str:
        """Return the current media type."""
        # Hard to determine content type
        if self._source_change.id == BangOlufsenSource.URI_STREAMER.id:
            return MediaType.URL
        return MediaType.MUSIC

    @property
    def media_duration(self) -> int | None:
        """Return the total duration of the current track in seconds."""
        return self._playback_metadata.total_duration_seconds

    @property
    def media_position(self) -> int | None:
        """Return the current playback progress."""
        return self._playback_progress.progress

    @property
    def media_image_url(self) -> str | None:
        """Return URL of the currently playing music."""
        return self._media_image.url

    @property
    def media_image_remotely_accessible(self) -> bool:
        """Return whether or not the image of the current media is available outside the local network."""
        return not self._media_image.has_local_image

    @property
    def media_title(self) -> str | None:
        """Return the currently playing title."""
        return self._playback_metadata.title

    @property
    def media_album_name(self) -> str | None:
        """Return the currently playing album name."""
        return self._playback_metadata.album_name

    @property
    def media_album_artist(self) -> str | None:
        """Return the currently playing artist name."""
        return self._playback_metadata.artist_name

    @property
    def media_track(self) -> int | None:
        """Return the currently playing track."""
        return self._playback_metadata.track

    @property
    def media_channel(self) -> str | None:
        """Return the currently playing channel."""
        return self._playback_metadata.organization

    @property
    def source(self) -> str | None:
        """Return the current audio source."""

        # Try to fix some of the source_change chromecast weirdness.
        if hasattr(self._playback_metadata, "title"):
            # source_change is chromecast but line in is selected.
            if self._playback_metadata.title == BangOlufsenSource.LINE_IN.name:
                return BangOlufsenSource.LINE_IN.name

            # source_change is chromecast but bluetooth is selected.
            if self._playback_metadata.title == BangOlufsenSource.BLUETOOTH.name:
                return BangOlufsenSource.BLUETOOTH.name

            # source_change is line in, bluetooth or optical but stale metadata is sent through the WebSocket,
            # And the source has not changed.
            if self._source_change.id in (
                BangOlufsenSource.BLUETOOTH.id,
                BangOlufsenSource.LINE_IN.id,
                BangOlufsenSource.SPDIF.id,
            ):
                return BangOlufsenSource.CHROMECAST.name

        # source_change is chromecast and there is metadata but no artwork. Bluetooth does support metadata but not artwork
        # So i assume that it is bluetooth and not chromecast
        if (
            hasattr(self._playback_metadata, "art")
            and self._playback_metadata.art is not None
            and len(self._playback_metadata.art) == 0
            and self._source_change.id == BangOlufsenSource.CHROMECAST.id
        ):
            return BangOlufsenSource.BLUETOOTH.name

        return self._source_change.name

    async def async_turn_off(self) -> None:
        """Set the device to "networkStandby"."""
        await self._client.post_standby()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._client.set_current_volume_level(
            volume_level=VolumeLevel(level=int(volume * 100))
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute media player."""
        await self._client.set_volume_mute(volume_mute=VolumeMute(muted=mute))

    async def async_media_play_pause(self) -> None:
        """Toggle play/pause media player."""
        if self.state == MediaPlayerState.PLAYING:
            await self.async_media_pause()
        elif self.state in (MediaPlayerState.PAUSED, MediaPlayerState.IDLE):
            await self.async_media_play()

    async def async_media_pause(self) -> None:
        """Pause media player."""
        await self._client.post_playback_command(command="pause")

    async def async_media_play(self) -> None:
        """Play media player."""
        await self._client.post_playback_command(command="play")

    async def async_media_stop(self) -> None:
        """Pause media player."""
        await self._client.post_playback_command(command="stop")

    async def async_media_next_track(self) -> None:
        """Send the next track command."""
        await self._client.post_playback_command(command="skip")

    async def async_media_seek(self, position: float) -> None:
        """Seek to position in ms."""
        if self._source_change.id == BangOlufsenSource.DEEZER.id:
            await self._client.seek_to_position(position_ms=int(position * 1000))
            # Try to prevent the playback progress from bouncing in the UI.
            self._attr_media_position_updated_at = utcnow()
            self._playback_progress = PlaybackProgress(progress=int(position))

            self.async_write_ha_state()
        else:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="non_deezer_seeking"
            )

    async def async_media_previous_track(self) -> None:
        """Send the previous track command."""
        await self._client.post_playback_command(command="prev")

    async def async_clear_playlist(self) -> None:
        """Clear the current playback queue."""
        await self._client.post_clear_queue()

    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        if source not in self._sources.values():
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={
                    "invalid_source": source,
                    "valid_sources": ",".join(list(self._sources.values())),
                },
            )

        key = [x for x in self._sources if self._sources[x] == source][0]

        # Check for source type
        if source in self._audio_sources.values():
            # Audio
            await self._client.set_active_source(source_id=key)
        else:
            # Video
            await self._client.post_remote_trigger(id=key)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select a sound mode."""
        # Ensure only known sound modes known by the integration can be activated.
        if sound_mode not in self._sound_modes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_sound_mode",
                translation_placeholders={
                    "invalid_sound_mode": sound_mode,
                    "valid_sound_modes": ", ".join(list(self._sound_modes)),
                },
            )

        await self._client.activate_listening_mode(id=self._sound_modes[sound_mode])

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Play from: netradio station id, URI, favourite or Deezer."""
        # Convert audio/mpeg, audio/aac etc. to MediaType.MUSIC
        if media_type.startswith("audio/"):
            media_type = MediaType.MUSIC

        if media_type not in VALID_MEDIA_TYPES:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_media_type",
                translation_placeholders={
                    "invalid_media_type": media_type,
                    "valid_media_types": ",".join(VALID_MEDIA_TYPES),
                },
            )

        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )

            media_id = async_process_play_media_url(self.hass, sourced_media.url)

            # Exit if the source uses unsupported file.
            if media_id.endswith(".m3u"):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="m3u_invalid_format"
                )

        if announce:
            extra = kwargs.get(ATTR_MEDIA_EXTRA, {})

            absolute_volume = extra.get("overlay_absolute_volume", None)
            offset_volume = extra.get("overlay_offset_volume", None)
            tts_language = extra.get("overlay_tts_language", "en-us")

            # Construct request
            overlay_play_request = OverlayPlayRequest()

            # Define volume level
            if absolute_volume:
                overlay_play_request.volume_absolute = absolute_volume

            elif offset_volume:
                # Ensure that the volume is not above 100
                if not self._volume.level or not self._volume.level.level:
                    _LOGGER.warning("Error setting volume")
                else:
                    overlay_play_request.volume_absolute = min(
                        self._volume.level.level + offset_volume, 100
                    )

            if media_type == BangOlufsenMediaType.OVERLAY_TTS:
                # Bang & Olufsen cloud TTS
                overlay_play_request.text_to_speech = (
                    OverlayPlayRequestTextToSpeechTextToSpeech(
                        lang=tts_language, text=media_id
                    )
                )
            else:
                overlay_play_request.uri = Uri(location=media_id)

            await self._client.post_overlay_play(overlay_play_request)

        elif media_type in (MediaType.URL, MediaType.MUSIC):
            await self._client.post_uri_source(uri=Uri(location=media_id))

        # The "provider" media_type may not be suitable for overlay all the time.
        # Use it for now.
        elif media_type == BangOlufsenMediaType.TTS:
            await self._client.post_overlay_play(
                overlay_play_request=OverlayPlayRequest(
                    uri=Uri(location=media_id),
                )
            )

        elif media_type == BangOlufsenMediaType.RADIO:
            await self._client.run_provided_scene(
                scene_properties=SceneProperties(
                    action_list=[
                        Action(
                            type="radio",
                            radio_station_id=media_id,
                        )
                    ]
                )
            )

        elif media_type == BangOlufsenMediaType.FAVOURITE:
            await self._client.activate_preset(id=int(media_id))

        elif media_type in (BangOlufsenMediaType.DEEZER, BangOlufsenMediaType.TIDAL):
            try:
                # Play Deezer flow.
                if media_id == "flow" and media_type == BangOlufsenMediaType.DEEZER:
                    deezer_id = None

                    if "id" in kwargs[ATTR_MEDIA_EXTRA]:
                        deezer_id = kwargs[ATTR_MEDIA_EXTRA]["id"]

                    await self._client.start_deezer_flow(
                        user_flow=UserFlow(user_id=deezer_id)
                    )

                # Play a playlist or album.
                elif any(match in media_id for match in ("playlist", "album")):
                    start_from = 0
                    if "start_from" in kwargs[ATTR_MEDIA_EXTRA]:
                        start_from = kwargs[ATTR_MEDIA_EXTRA]["start_from"]

                    await self._client.add_to_queue(
                        play_queue_item=PlayQueueItem(
                            provider=PlayQueueItemType(value=media_type),
                            start_now_from_position=start_from,
                            type="playlist",
                            uri=media_id,
                        )
                    )

                # Play a track.
                else:
                    await self._client.add_to_queue(
                        play_queue_item=PlayQueueItem(
                            provider=PlayQueueItemType(value=media_type),
                            start_now_from_position=0,
                            type="track",
                            uri=media_id,
                        )
                    )

            except ApiException as error:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="play_media_error",
                    translation_placeholders={
                        "media_type": media_type,
                        "error_message": json.loads(error.body)["message"],
                    },
                ) from error

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the WebSocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def async_join_players(self, group_members: list[str]) -> None:
        """Create a Beolink session with defined group members."""

        # Use the touch to join if no entities have been defined
        # Touch to join will make the device connect to any other currently-playing
        # Beolink compatible B&O device.
        # Repeated presses / calls will cycle between compatible playing devices.
        if len(group_members) == 0:
            await self._async_beolink_join()
            return

        # Get JID for each group member
        jids = [self._get_beolink_jid(group_member) for group_member in group_members]
        await self._async_beolink_expand(jids)

    async def async_unjoin_player(self) -> None:
        """Unjoin Beolink session. End session if leader."""
        await self._async_beolink_leave()

    async def _async_beolink_join(self) -> None:
        """Join a Beolink multi-room experience."""
        await self._client.join_latest_beolink_experience()

    async def _async_beolink_expand(self, beolink_jids: list[str]) -> None:
        """Expand a Beolink multi-room experience with a device or devices."""
        # Ensure that the current source is expandable
        if not self._beolink_sources[cast(str, self._source_change.id)]:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={
                    "invalid_source": cast(str, self._source_change.id),
                    "valid_sources": ", ".join(list(self._beolink_sources)),
                },
            )

        # Try to expand to all defined devices
        for beolink_jid in beolink_jids:
            await self._client.post_beolink_expand(jid=beolink_jid)

    async def _async_beolink_leave(self) -> None:
        """Leave the current Beolink experience."""
        await self._client.post_beolink_leave()
