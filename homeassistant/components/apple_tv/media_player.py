"""Support for Apple TV media player."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from pyatv import exceptions
from pyatv.const import (
    DeviceState,
    FeatureName,
    FeatureState,
    MediaType as AppleMediaType,
    PowerState,
    RepeatState,
    ShuffleState,
)
from pyatv.helpers import is_streamable
from pyatv.interface import (
    AppleTV,
    AudioListener,
    OutputDevice,
    Playing,
    PowerListener,
    PushListener,
    PushUpdater,
)

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AppleTvConfigEntry, AppleTVManager
from .browse_media import build_app_list
from .entity import AppleTVEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# We always consider these to be supported
SUPPORT_BASE = MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF

# This is the "optimistic" view of supported features and will be returned until the
# actual set of supported feature have been determined (will always be all or a subset
# of these).
SUPPORT_APPLE_TV = (
    SUPPORT_BASE
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SHUFFLE_SET
)


# Map features in pyatv to Home Assistant
SUPPORT_FEATURE_MAPPING = {
    FeatureName.PlayUrl: MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PLAY_MEDIA,
    FeatureName.StreamFile: MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PLAY_MEDIA,
    FeatureName.Pause: MediaPlayerEntityFeature.PAUSE,
    FeatureName.Play: MediaPlayerEntityFeature.PLAY,
    FeatureName.SetPosition: MediaPlayerEntityFeature.SEEK,
    FeatureName.Stop: MediaPlayerEntityFeature.STOP,
    FeatureName.Next: MediaPlayerEntityFeature.NEXT_TRACK,
    FeatureName.Previous: MediaPlayerEntityFeature.PREVIOUS_TRACK,
    FeatureName.VolumeUp: MediaPlayerEntityFeature.VOLUME_STEP,
    FeatureName.VolumeDown: MediaPlayerEntityFeature.VOLUME_STEP,
    FeatureName.SetRepeat: MediaPlayerEntityFeature.REPEAT_SET,
    FeatureName.SetShuffle: MediaPlayerEntityFeature.SHUFFLE_SET,
    FeatureName.SetVolume: MediaPlayerEntityFeature.VOLUME_SET,
    FeatureName.AppList: MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.SELECT_SOURCE,
    FeatureName.LaunchApp: MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.SELECT_SOURCE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AppleTvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Load Apple TV media player based on a config entry."""
    name: str = config_entry.data[CONF_NAME]
    assert config_entry.unique_id is not None
    manager = config_entry.runtime_data
    async_add_entities([AppleTvMediaPlayer(name, config_entry.unique_id, manager)])


class AppleTvMediaPlayer(
    AppleTVEntity, MediaPlayerEntity, PowerListener, AudioListener, PushListener
):
    """Representation of an Apple TV media player."""

    _attr_supported_features = SUPPORT_APPLE_TV

    def __init__(self, name: str, identifier: str, manager: AppleTVManager) -> None:
        """Initialize the Apple TV media player."""
        super().__init__(name, identifier, manager)
        self._playing: Playing | None = None
        self._playing_last_updated: datetime | None = None
        self._app_list: dict[str, str] = {}

    @callback
    def async_device_connected(self, atv: AppleTV) -> None:
        """Handle when connection is made to device."""
        # NB: Do not use _is_feature_available here as it only works when playing
        if atv.features.in_state(FeatureState.Available, FeatureName.PushUpdates):
            atv.push_updater.listener = self
            atv.push_updater.start()

        self._attr_supported_features = SUPPORT_BASE

        # Determine the actual set of supported features. All features not reported as
        # "Unsupported" are considered here as the state of such a feature can never
        # change after a connection has been established, i.e. an unsupported feature
        # can never change to be supported.
        all_features = atv.features.all_features()
        for feature_name, support_flag in SUPPORT_FEATURE_MAPPING.items():
            feature_info = all_features.get(feature_name)
            if feature_info and feature_info.state != FeatureState.Unsupported:
                self._attr_supported_features |= support_flag

        # No need to schedule state update here as that will happen when the first
        # metadata update arrives (sometime very soon after this callback returns)

        # Listen to power updates
        atv.power.listener = self

        # Listen to volume updates
        atv.audio.listener = self

        if atv.features.in_state(FeatureState.Available, FeatureName.AppList):
            self.manager.config_entry.async_create_task(
                self.hass, self._update_app_list(), eager_start=True
            )

    async def _update_app_list(self) -> None:
        _LOGGER.debug("Updating app list")
        if not self.atv:
            return
        try:
            apps = await self.atv.apps.app_list()
        except exceptions.NotSupportedError:
            _LOGGER.error("Listing apps is not supported")
        except exceptions.ProtocolError:
            _LOGGER.exception("Failed to update app list")
        else:
            self._app_list = {
                app_name: app.identifier
                for app in sorted(apps, key=lambda app: (app.name or "").lower())
                if (app_name := app.name) is not None
            }
            self.async_write_ha_state()

    @callback
    def async_device_disconnected(self) -> None:
        """Handle when connection was lost to device."""
        self._attr_supported_features = SUPPORT_APPLE_TV

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self.manager.is_connecting:
            return None
        if self.atv is None:
            return MediaPlayerState.OFF
        if (
            self._is_feature_available(FeatureName.PowerState)
            and self.atv.power.power_state == PowerState.Off
        ):
            return MediaPlayerState.STANDBY
        if self._playing:
            state = self._playing.device_state
            if state in (DeviceState.Idle, DeviceState.Loading):
                return MediaPlayerState.IDLE
            if state == DeviceState.Playing:
                return MediaPlayerState.PLAYING
            if state in (DeviceState.Paused, DeviceState.Seeking, DeviceState.Stopped):
                return MediaPlayerState.PAUSED
            return MediaPlayerState.STANDBY  # Bad or unknown state?
        return None

    @callback
    def playstatus_update(self, updater: PushUpdater, playstatus: Playing) -> None:
        """Print what is currently playing when it changes.

        This is a callback function from pyatv.interface.PushListener.
        """
        self._playing = playstatus
        self._playing_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    @callback
    def playstatus_error(self, updater: PushUpdater, exception: Exception) -> None:
        """Inform about an error and restart push updates.

        This is a callback function from pyatv.interface.PushListener.
        """
        _LOGGER.warning("A %s error occurred: %s", exception.__class__, exception)
        self._playing = None
        self.async_write_ha_state()

    @callback
    def powerstate_update(self, old_state: PowerState, new_state: PowerState) -> None:
        """Update power state when it changes.

        This is a callback function from pyatv.interface.PowerListener.
        """
        self.async_write_ha_state()

    @callback
    def volume_update(self, old_level: float, new_level: float) -> None:
        """Update volume when it changes.

        This is a callback function from pyatv.interface.AudioListener.
        """
        self.async_write_ha_state()

    @callback
    def outputdevices_update(
        self, old_devices: list[OutputDevice], new_devices: list[OutputDevice]
    ) -> None:
        """Output devices were updated.

        This is a callback function from pyatv.interface.AudioListener.
        """

    @property
    def app_id(self) -> str | None:
        """ID of the current running app."""
        if (
            self.atv
            and self._is_feature_available(FeatureName.App)
            and (app := self.atv.metadata.app) is not None
        ):
            return app.identifier
        return None

    @property
    def app_name(self) -> str | None:
        """Name of the current running app."""
        if (
            self.atv
            and self._is_feature_available(FeatureName.App)
            and (app := self.atv.metadata.app) is not None
        ):
            return app.name
        return None

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return list(self._app_list.keys())

    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        if self._playing:
            return {
                AppleMediaType.Video: MediaType.VIDEO,
                AppleMediaType.Music: MediaType.MUSIC,
                AppleMediaType.TV: MediaType.TVSHOW,
            }.get(self._playing.media_type)
        return None

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        if self._playing:
            return self._playing.content_identifier
        return None

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if self.atv and self._is_feature_available(FeatureName.Volume):
            return self.atv.audio.volume / 100.0  # from percent
        return None

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if self._playing:
            return self._playing.total_time
        return None

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if self._playing:
            return self._playing.position
        return None

    @property
    def media_position_updated_at(self) -> datetime | None:
        """Last valid time of media position."""
        if self.state in {MediaPlayerState.PLAYING, MediaPlayerState.PAUSED}:
            return self._playing_last_updated
        return None

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play_media command to the media player."""
        # If input (file) has a file format supported by pyatv, then stream it with
        # RAOP. Otherwise try to play it with regular AirPlay.
        if not self.atv:
            return
        if media_type in {MediaType.APP, MediaType.URL}:
            await self.atv.apps.launch_app(media_id)
            return

        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)
            media_type = MediaType.MUSIC

        if self._is_feature_available(FeatureName.StreamFile) and (
            media_type == MediaType.MUSIC or await is_streamable(media_id)
        ):
            _LOGGER.debug("Streaming %s via RAOP", media_id)
            await self.atv.stream.stream_file(media_id)
        elif self._is_feature_available(FeatureName.PlayUrl):
            _LOGGER.debug("Playing %s via AirPlay", media_id)
            await self.atv.stream.play_url(media_id)
        else:
            _LOGGER.error("Media streaming is not possible with current configuration")

    @property
    def media_image_hash(self) -> str | None:
        """Hash value for media image."""
        state = self.state
        if (
            self.atv
            and self._playing
            and self._is_feature_available(FeatureName.Artwork)
            and state not in {None, MediaPlayerState.OFF, MediaPlayerState.IDLE}
        ):
            return self.atv.metadata.artwork_id
        return None

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch media image of current playing image."""
        state = self.state
        if (
            self.atv
            and self._playing
            and state not in {MediaPlayerState.OFF, MediaPlayerState.IDLE}
        ):
            artwork = await self.atv.metadata.artwork()
            if artwork:
                return artwork.bytes, artwork.mimetype

        return None, None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if self._playing:
            return self._playing.title
        return None

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        if self._playing and self._is_feature_available(FeatureName.Artist):
            return self._playing.artist
        return None

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        if self._playing and self._is_feature_available(FeatureName.Album):
            return self._playing.album
        return None

    @property
    def media_series_title(self) -> str | None:
        """Title of series of current playing media, TV show only."""
        if self._playing and self._is_feature_available(FeatureName.SeriesName):
            return self._playing.series_name
        return None

    @property
    def media_season(self) -> str | None:
        """Season of current playing media, TV show only."""
        if self._playing and self._is_feature_available(FeatureName.SeasonNumber):
            return str(self._playing.season_number)
        return None

    @property
    def media_episode(self) -> str | None:
        """Episode of current playing media, TV show only."""
        if self._playing and self._is_feature_available(FeatureName.EpisodeNumber):
            return str(self._playing.episode_number)
        return None

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        if (
            self._playing
            and self._is_feature_available(FeatureName.Repeat)
            and (repeat := self._playing.repeat)
        ):
            return {
                RepeatState.Track: RepeatMode.ONE,
                RepeatState.All: RepeatMode.ALL,
            }.get(repeat, RepeatMode.OFF)
        return None

    @property
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        if self._playing and self._is_feature_available(FeatureName.Shuffle):
            return self._playing.shuffle != ShuffleState.Off
        return None

    def _is_feature_available(self, feature: FeatureName) -> bool:
        """Return if a feature is available."""
        if self.atv and self._playing:
            return self.atv.features.in_state(FeatureState.Available, feature)
        return False

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        if media_content_id == "apps" or (
            # If we can't stream files or URLs, we can't browse media.
            # In that case the `BROWSE_MEDIA` feature was added because of AppList/LaunchApp
            not self._is_feature_available(FeatureName.PlayUrl)
            and not self._is_feature_available(FeatureName.StreamFile)
        ):
            return build_app_list(self._app_list)

        if self._app_list:
            kwargs = {}
        else:
            # If it has no apps, assume it has no display
            kwargs = {
                "content_filter": lambda item: item.media_content_type.startswith(
                    "audio/"
                ),
            }

        cur_item = await media_source.async_browse_media(
            self.hass, media_content_id, **kwargs
        )

        # If media content id is not None, we're browsing into a media source
        if media_content_id is not None:
            return cur_item

        # Add app item if we have one
        if self._app_list and cur_item.children and isinstance(cur_item.children, list):
            cur_item.children.insert(0, build_app_list(self._app_list))

        return cur_item

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        if self.atv and self._is_feature_available(FeatureName.TurnOn):
            await self.atv.power.turn_on()

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        if (
            self.atv
            and (self._is_feature_available(FeatureName.TurnOff))
            and (
                not self._is_feature_available(FeatureName.PowerState)
                or self.atv.power.power_state == PowerState.On
            )
        ):
            await self.atv.power.turn_off()

    async def async_media_play_pause(self) -> None:
        """Pause media on media player."""
        if self.atv and self._playing:
            await self.atv.remote_control.play_pause()

    async def async_media_play(self) -> None:
        """Play media."""
        if self.atv:
            await self.atv.remote_control.play()

    async def async_media_stop(self) -> None:
        """Stop the media player."""
        if self.atv:
            await self.atv.remote_control.stop()

    async def async_media_pause(self) -> None:
        """Pause the media player."""
        if self.atv:
            await self.atv.remote_control.pause()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if self.atv:
            await self.atv.remote_control.next()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if self.atv:
            await self.atv.remote_control.previous()

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        if self.atv:
            await self.atv.remote_control.set_position(round(position))

    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        if self.atv:
            await self.atv.audio.volume_up()

    async def async_volume_down(self) -> None:
        """Turn volume down for media player."""
        if self.atv:
            await self.atv.audio.volume_down()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        if self.atv:
            # pyatv expects volume in percent
            await self.atv.audio.set_volume(volume * 100.0)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        if self.atv:
            mode = {
                RepeatMode.ONE: RepeatState.Track,
                RepeatMode.ALL: RepeatState.All,
            }.get(repeat, RepeatState.Off)
            await self.atv.remote_control.set_repeat(mode)

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        if self.atv:
            await self.atv.remote_control.set_shuffle(
                ShuffleState.Songs if shuffle else ShuffleState.Off
            )

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if self.atv:
            if app_id := self._app_list.get(source):
                await self.atv.apps.launch_app(app_id)
