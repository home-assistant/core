"""Support for Apple TV media player."""

from collections.abc import Callable, Coroutine
from datetime import datetime
from functools import wraps
import logging
from typing import Any, Concatenate, override

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
from yarl import URL

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_platforms,
)
from homeassistant.util import dt as dt_util

from . import AppleTvConfigEntry, AppleTVManager
from .browse_media import build_app_list
from .const import DOMAIN, SIGNAL_GROUP_CHANGED
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
    | MediaPlayerEntityFeature.GROUPING
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
    FeatureName.AddOutputDevices: MediaPlayerEntityFeature.GROUPING,
    FeatureName.RemoveOutputDevices: MediaPlayerEntityFeature.GROUPING,
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


def _catch_command_errors[_T: AppleTvMediaPlayer, **_P](
    func: Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Raise a HomeAssistantError when a command can't be sent to the Apple TV."""

    @wraps(func)
    async def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except (
            TimeoutError,
            exceptions.BlockedStateError,
            exceptions.ConnectionLostError,
            exceptions.InvalidStateError,
            exceptions.OperationTimeoutError,
            exceptions.ProtocolError,
        ) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
            ) from ex

    return wrapper


type _GroupingPlayers = dict[str, tuple[AppleTvMediaPlayer, AppleTV]]


@callback
def _grouping_players(hass: HomeAssistant) -> _GroupingPlayers:
    """Return each player that can be grouped and its connection, by output device ID."""
    players: _GroupingPlayers = {}
    for platform in async_get_platforms(hass, DOMAIN):
        if platform.domain != MEDIA_PLAYER_DOMAIN:
            continue
        for entity in platform.entities.values():
            if (
                isinstance(entity, AppleTvMediaPlayer)
                and (atv := entity.grouping_atv)
                and (output_device_id := atv.device_info.output_device_id)
            ):
                players[output_device_id] = (entity, atv)
    return players


def _grouping_unavailable(entity_id: str) -> ServiceValidationError:
    """Return the error for a player that can't be grouped now."""
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="grouping_unavailable",
        translation_placeholders={"entity_id": entity_id},
    )


def _find_leader(
    players: _GroupingPlayers, output_device_id: str
) -> tuple[AppleTvMediaPlayer, AppleTV] | None:
    """Return the player that has the given device in its group."""
    for leader_id, (player, atv) in players.items():
        if leader_id != output_device_id and any(
            device.identifier == output_device_id for device in atv.audio.output_devices
        ):
            return player, atv
    return None


class AppleTvMediaPlayer(
    AppleTVEntity, MediaPlayerEntity, PowerListener, AudioListener, PushListener
):
    """Representation of an Apple TV media player."""

    _attr_supported_features = SUPPORT_APPLE_TV
    _attr_name = None

    def __init__(self, name: str, identifier: str, manager: AppleTVManager) -> None:
        """Initialize the Apple TV media player."""
        super().__init__(name, identifier, manager)
        self._playing: Playing | None = None
        self._playing_last_updated: datetime | None = None
        self._app_list: dict[str, str] = {}

    @override
    async def async_added_to_hass(self) -> None:
        """Handle when an entity is about to be added to Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_GROUP_CHANGED, self._async_update_group_members
            )
        )
        async_dispatcher_send(self.hass, SIGNAL_GROUP_CHANGED)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Let the other players drop this player from their group members."""
        await super().async_will_remove_from_hass()
        async_dispatcher_send(self.hass, SIGNAL_GROUP_CHANGED)

    @callback
    @override
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Let the other players rebuild their group members."""
        super().async_entity_id_changed(old_entity_id)
        async_dispatcher_send(self.hass, SIGNAL_GROUP_CHANGED)

    @callback
    @override
    def async_device_connected(self, atv: AppleTV) -> None:
        """Handle when connection is made to device."""
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
            if feature_info and feature_info.state is not FeatureState.Unsupported:
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
    @override
    def async_device_disconnected(self) -> None:
        """Handle when connection was lost to device."""
        self._attr_supported_features = SUPPORT_APPLE_TV

    @property
    @override
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self.manager.is_connecting:
            return None
        if self.atv is None:
            return MediaPlayerState.OFF
        if (
            self._is_feature_available(FeatureName.PowerState)
            and self.atv.power.power_state is PowerState.Off
        ):
            return MediaPlayerState.OFF
        if self._playing:
            state = self._playing.device_state
            if state in (DeviceState.Idle, DeviceState.Loading):
                return MediaPlayerState.IDLE
            if state is DeviceState.Playing:
                return MediaPlayerState.PLAYING
            if state in (DeviceState.Paused, DeviceState.Seeking, DeviceState.Stopped):
                return MediaPlayerState.PAUSED
            return MediaPlayerState.IDLE  # type: ignore[unreachable]  # Bad or unknown state?
        return None

    @callback
    @override
    def playstatus_update(self, updater: PushUpdater, playstatus: Playing) -> None:
        """Print what is currently playing when it changes.

        This is a callback function from pyatv.interface.PushListener.
        """
        self._playing = playstatus
        self._playing_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    @callback
    @override
    def playstatus_error(self, updater: PushUpdater, exception: Exception) -> None:
        """Inform about an error and restart push updates.

        This is a callback function from pyatv.interface.PushListener.
        """
        _LOGGER.warning("A %s error occurred: %s", exception.__class__, exception)
        self._playing = None
        self.async_write_ha_state()

    @callback
    @override
    def powerstate_update(self, old_state: PowerState, new_state: PowerState) -> None:
        """Update power state when it changes.

        This is a callback function from pyatv.interface.PowerListener.
        """
        self.async_write_ha_state()

    @callback
    @override
    def volume_update(self, old_level: float, new_level: float) -> None:
        """Update volume when it changes.

        This is a callback function from pyatv.interface.AudioListener.
        """
        self.async_write_ha_state()

    @callback
    @override
    def volume_device_update(
        self, output_device: OutputDevice, old_level: float, new_level: float
    ) -> None:
        """Output device volume was updated.

        This is a callback function from pyatv.interface.AudioListener.
        """

    @callback
    @override
    def outputdevices_update(
        self, old_devices: list[OutputDevice], new_devices: list[OutputDevice]
    ) -> None:
        """Output devices were updated.

        This is a callback function from pyatv.interface.AudioListener.
        """
        async_dispatcher_send(self.hass, SIGNAL_GROUP_CHANGED)

    @property
    @override
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
    @override
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
    @override
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return list(self._app_list.keys())

    @property
    @override
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
    @override
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        if self._playing:
            return self._playing.content_identifier
        return None

    @property
    def grouping_atv(self) -> AppleTV | None:
        """Return the connection, if this player can be grouped."""
        # The manager drops a closed connection before the entity is told about it
        if (atv := self.manager.atv) and atv.features.in_state(
            FeatureState.Available, FeatureName.OutputDevices
        ):
            return atv
        return None

    @callback
    def _async_update_group_members(self) -> None:
        """Rebuild the group members from the output devices of the group leader."""
        if self.atv is not self.manager.atv:
            # Closed by the manager, this entity is told about it later
            return
        self._attr_group_members = None
        if (atv := self.grouping_atv) and (
            output_device_id := atv.device_info.output_device_id
        ):
            players = _grouping_players(self.hass)
            leader: tuple[AppleTvMediaPlayer, AppleTV] = (self, atv)
            # A member lists no output devices or only itself, its leader has the group
            if all(
                device.identifier == output_device_id
                for device in atv.audio.output_devices
            ):
                leader = _find_leader(players, output_device_id) or leader
            leader_player, leader_atv = leader
            self._attr_group_members = [
                leader_player.entity_id,
                *(
                    players[device.identifier][0].entity_id
                    for device in leader_atv.audio.output_devices
                    if device.identifier in players
                    and players[device.identifier][0] is not leader_player
                ),
            ]
        self.async_write_ha_state()

    @property
    @override
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if self.atv and self._is_feature_available(FeatureName.Volume):
            return self.atv.audio.volume / 100.0  # from percent
        return None

    @property
    @override
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if self._playing:
            return self._playing.total_time
        return None

    @property
    @override
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if self._playing:
            return self._playing.position
        return None

    @property
    @override
    def media_position_updated_at(self) -> datetime | None:
        """Last valid time of media position."""
        if self.state in {MediaPlayerState.PLAYING, MediaPlayerState.PAUSED}:
            return self._playing_last_updated
        return None

    @override
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
            if play_item.path and self._is_feature_available(FeatureName.StreamFile):
                media_id = str(play_item.path)
            else:
                media_id = async_process_play_media_url(self.hass, play_item.url)
            media_type = MediaType.MUSIC

        use_stream_file = self._is_feature_available(FeatureName.StreamFile) and (
            media_type == MediaType.MUSIC or await is_streamable(media_id)
        )

        try:
            if use_stream_file:
                _LOGGER.debug("Streaming %s via RAOP", media_id)
                await self.atv.stream.stream_file(media_id)
            elif self._is_feature_available(FeatureName.PlayUrl) and (
                (parsed_url := URL(media_id)).is_absolute() and parsed_url.host
            ):
                _LOGGER.debug("Playing %s via AirPlay", media_id)
                await self.atv.stream.play_url(media_id)
            else:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="streaming_not_supported",
                )
        except exceptions.NotSupportedError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="streaming_not_supported",
            ) from ex
        except (
            exceptions.BlockedStateError,
            exceptions.ConnectionLostError,
            exceptions.InvalidStateError,
            exceptions.OperationTimeoutError,
            exceptions.PlaybackError,
            exceptions.ProtocolError,
        ) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="stream_failed",
            ) from ex

    @property
    @override
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

    @override
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
    @override
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if self._playing:
            return self._playing.title
        return None

    @property
    @override
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        if self._playing and self._is_feature_available(FeatureName.Artist):
            return self._playing.artist
        return None

    @property
    @override
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        if self._playing and self._is_feature_available(FeatureName.Album):
            return self._playing.album
        return None

    @property
    @override
    def media_series_title(self) -> str | None:
        """Title of series of current playing media, TV show only."""
        if self._playing and self._is_feature_available(FeatureName.SeriesName):
            return self._playing.series_name
        return None

    @property
    @override
    def media_season(self) -> str | None:
        """Season of current playing media, TV show only."""
        if self._playing and self._is_feature_available(FeatureName.SeasonNumber):
            return str(self._playing.season_number)
        return None

    @property
    @override
    def media_episode(self) -> str | None:
        """Episode of current playing media, TV show only."""
        if self._playing and self._is_feature_available(FeatureName.EpisodeNumber):
            return str(self._playing.episode_number)
        return None

    @property
    @override
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
    @override
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        if self._playing and self._is_feature_available(FeatureName.Shuffle):
            return self._playing.shuffle is not ShuffleState.Off
        return None

    def _is_feature_available(self, feature: FeatureName) -> bool:
        """Return if a feature is available."""
        if self.atv:
            return self.atv.features.in_state(FeatureState.Available, feature)
        return False

    @override
    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        if media_content_id == "apps" or (
            # If we can't stream files or URLs, we can't browse media.
            # In that case the `BROWSE_MEDIA` feature was added
            # because of AppList/LaunchApp
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

    @override
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        if self.atv and self._is_feature_available(FeatureName.TurnOn):
            await self.atv.power.turn_on()

    @override
    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        if (
            self.atv
            and (self._is_feature_available(FeatureName.TurnOff))
            and (
                not self._is_feature_available(FeatureName.PowerState)
                or self.atv.power.power_state is PowerState.On
            )
        ):
            await self.atv.power.turn_off()

    @override
    @_catch_command_errors
    async def async_media_play_pause(self) -> None:
        """Pause media on media player."""
        if self.atv and self._playing:
            await self.atv.remote_control.play_pause()

    @override
    @_catch_command_errors
    async def async_media_play(self) -> None:
        """Play media."""
        if self.atv:
            await self.atv.remote_control.play()

    @override
    @_catch_command_errors
    async def async_media_stop(self) -> None:
        """Stop the media player."""
        if self.atv:
            await self.atv.remote_control.stop()

    @override
    @_catch_command_errors
    async def async_media_pause(self) -> None:
        """Pause the media player."""
        if self.atv:
            await self.atv.remote_control.pause()

    @override
    @_catch_command_errors
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if self.atv:
            await self.atv.remote_control.next()

    @override
    @_catch_command_errors
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if self.atv:
            await self.atv.remote_control.previous()

    @override
    @_catch_command_errors
    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        if self.atv:
            await self.atv.remote_control.set_position(round(position))

    @override
    @_catch_command_errors
    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        if self.atv:
            await self.atv.audio.volume_up()

    @override
    @_catch_command_errors
    async def async_volume_down(self) -> None:
        """Turn volume down for media player."""
        if self.atv:
            await self.atv.audio.volume_down()

    @override
    @_catch_command_errors
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        if self.atv:
            # pyatv expects volume in percent
            await self.atv.audio.set_volume(volume * 100.0)

    @override
    @_catch_command_errors
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        if self.atv:
            mode = {
                RepeatMode.ONE: RepeatState.Track,
                RepeatMode.ALL: RepeatState.All,
            }.get(repeat, RepeatState.Off)
            await self.atv.remote_control.set_repeat(mode)

    @override
    @_catch_command_errors
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        if self.atv:
            await self.atv.remote_control.set_shuffle(
                ShuffleState.Songs if shuffle else ShuffleState.Off
            )

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if self.atv:
            if app_id := self._app_list.get(source):
                await self.atv.apps.launch_app(app_id)

    def _member_output_device_id(
        self, players_by_entity_id: dict[str, str], entity_id: str
    ) -> str:
        """Return the output device ID of a player that should join the group."""
        entity_entry = er.async_get(self.hass).async_get(entity_id)
        if (
            entity_entry is None
            or entity_entry.platform != DOMAIN
            or entity_entry.domain != MEDIA_PLAYER_DOMAIN
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_grouping_entity",
                translation_placeholders={"entity_id": entity_id},
            )
        if (output_device_id := players_by_entity_id.get(entity_id)) is None:
            raise _grouping_unavailable(entity_id)
        return output_device_id

    @override
    @_catch_command_errors
    async def async_join_players(self, group_members: list[str]) -> None:
        """Add other players to the group of this player."""
        if (
            atv := self.grouping_atv
        ) is None or atv.device_info.output_device_id is None:
            raise _grouping_unavailable(self.entity_id)
        players_by_entity_id = {
            player.entity_id: output_device_id
            for output_device_id, (player, _) in _grouping_players(self.hass).items()
        }
        member_ids = [
            self._member_output_device_id(players_by_entity_id, entity_id)
            for entity_id in group_members
            if entity_id != self.entity_id
        ]
        grouped = {device.identifier for device in atv.audio.output_devices}
        # pyatv waits for a device update, which an unchanged group never sends
        if new_ids := [
            device_id for device_id in member_ids if device_id not in grouped
        ]:
            await atv.audio.add_output_devices(*new_ids)  # type: ignore[arg-type]

    @override
    @_catch_command_errors
    async def async_unjoin_player(self) -> None:
        """Remove this player from its group, or end the group it leads."""
        if (atv := self.grouping_atv) is None or (
            output_device_id := atv.device_info.output_device_id
        ) is None:
            raise _grouping_unavailable(self.entity_id)
        if others := [
            device.identifier
            for device in atv.audio.output_devices
            if device.identifier != output_device_id
        ]:
            await atv.audio.remove_output_devices(*others)  # type: ignore[arg-type]
        elif leader := _find_leader(_grouping_players(self.hass), output_device_id):
            await leader[1].audio.remove_output_devices(output_device_id)  # type: ignore[arg-type]
