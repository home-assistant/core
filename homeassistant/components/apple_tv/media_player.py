"""Support for Apple TV media player."""
import logging

from pyatv import exceptions
from pyatv.const import (
    DeviceState,
    FeatureName,
    FeatureState,
    MediaType,
    PowerState,
    RepeatState,
    ShuffleState,
)
from pyatv.helpers import is_streamable

from homeassistant.components.media_player import BrowseMedia, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_APP,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_TVSHOW,
    MEDIA_TYPE_VIDEO,
    REPEAT_MODE_ALL,
    REPEAT_MODE_OFF,
    REPEAT_MODE_ONE,
    SUPPORT_BROWSE_MEDIA,
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
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from . import AppleTVEntity
from .browse_media import build_app_list
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# We always consider these to be supported
SUPPORT_BASE = SUPPORT_TURN_ON | SUPPORT_TURN_OFF

# This is the "optimistic" view of supported features and will be returned until the
# actual set of supported feature have been determined (will always be all or a subset
# of these).
SUPPORT_APPLE_TV = (
    SUPPORT_BASE
    | SUPPORT_BROWSE_MEDIA
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_SEEK
    | SUPPORT_STOP
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_REPEAT_SET
    | SUPPORT_SHUFFLE_SET
)


# Map features in pyatv to Home Assistant
SUPPORT_FEATURE_MAPPING = {
    FeatureName.PlayUrl: SUPPORT_PLAY_MEDIA,
    FeatureName.StreamFile: SUPPORT_PLAY_MEDIA,
    FeatureName.Pause: SUPPORT_PAUSE,
    FeatureName.Play: SUPPORT_PLAY,
    FeatureName.SetPosition: SUPPORT_SEEK,
    FeatureName.Stop: SUPPORT_STOP,
    FeatureName.Next: SUPPORT_NEXT_TRACK,
    FeatureName.Previous: SUPPORT_PREVIOUS_TRACK,
    FeatureName.VolumeUp: SUPPORT_VOLUME_STEP,
    FeatureName.VolumeDown: SUPPORT_VOLUME_STEP,
    FeatureName.SetRepeat: SUPPORT_REPEAT_SET,
    FeatureName.SetShuffle: SUPPORT_SHUFFLE_SET,
    FeatureName.SetVolume: SUPPORT_VOLUME_SET,
    FeatureName.AppList: SUPPORT_BROWSE_MEDIA | SUPPORT_SELECT_SOURCE,
    FeatureName.LaunchApp: SUPPORT_BROWSE_MEDIA | SUPPORT_SELECT_SOURCE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Apple TV media player based on a config entry."""
    name = config_entry.data[CONF_NAME]
    manager = hass.data[DOMAIN][config_entry.unique_id]
    async_add_entities([AppleTvMediaPlayer(name, config_entry.unique_id, manager)])


class AppleTvMediaPlayer(AppleTVEntity, MediaPlayerEntity):
    """Representation of an Apple TV media player."""

    _attr_supported_features = SUPPORT_APPLE_TV

    def __init__(self, name, identifier, manager, **kwargs):
        """Initialize the Apple TV media player."""
        super().__init__(name, identifier, manager, **kwargs)
        self._playing = None
        self._app_list = {}

    @callback
    def async_device_connected(self, atv):
        """Handle when connection is made to device."""
        # NB: Do not use _is_feature_available here as it only works when playing
        if self.atv.features.in_state(FeatureState.Available, FeatureName.PushUpdates):
            self.atv.push_updater.listener = self
            self.atv.push_updater.start()

        self._attr_supported_features = SUPPORT_BASE

        # Determine the actual set of supported features. All features not reported as
        # "Unsupported" are considered here as the state of such a feature can never
        # change after a connection has been established, i.e. an unsupported feature
        # can never change to be supported.
        all_features = self.atv.features.all_features()
        for feature_name, support_flag in SUPPORT_FEATURE_MAPPING.items():
            feature_info = all_features.get(feature_name)
            if feature_info and feature_info.state != FeatureState.Unsupported:
                self._attr_supported_features |= support_flag

        # No need to schedule state update here as that will happen when the first
        # metadata update arrives (sometime very soon after this callback returns)

        # Listen to power updates
        self.atv.power.listener = self

        if self.atv.features.in_state(FeatureState.Available, FeatureName.AppList):
            self.hass.create_task(self._update_app_list())

    async def _update_app_list(self):
        _LOGGER.debug("Updating app list")
        try:
            apps = await self.atv.apps.app_list()
        except exceptions.NotSupportedError:
            _LOGGER.error("Listing apps is not supported")
        except exceptions.ProtocolError:
            _LOGGER.exception("Failed to update app list")
        else:
            self._app_list = {
                app.name: app.identifier
                for app in sorted(apps, key=lambda app: app.name.lower())
            }
            self.async_write_ha_state()

    @callback
    def async_device_disconnected(self):
        """Handle when connection was lost to device."""
        self.atv.push_updater.stop()
        self.atv.push_updater.listener = None
        self.atv.power.listener = None
        self._attr_supported_features = SUPPORT_APPLE_TV

    @property
    def state(self):
        """Return the state of the device."""
        if self.manager.is_connecting:
            return None
        if self.atv is None:
            return STATE_OFF
        if (
            self._is_feature_available(FeatureName.PowerState)
            and self.atv.power.power_state == PowerState.Off
        ):
            return STATE_STANDBY
        if self._playing:
            state = self._playing.device_state
            if state in (DeviceState.Idle, DeviceState.Loading):
                return STATE_IDLE
            if state == DeviceState.Playing:
                return STATE_PLAYING
            if state in (DeviceState.Paused, DeviceState.Seeking, DeviceState.Stopped):
                return STATE_PAUSED
            return STATE_STANDBY  # Bad or unknown state?
        return None

    @callback
    def playstatus_update(self, _, playing):
        """Print what is currently playing when it changes."""
        self._playing = playing
        self.async_write_ha_state()

    @callback
    def playstatus_error(self, _, exception):
        """Inform about an error and restart push updates."""
        _LOGGER.warning("A %s error occurred: %s", exception.__class__, exception)
        self._playing = None
        self.async_write_ha_state()

    @callback
    def powerstate_update(self, old_state: PowerState, new_state: PowerState):
        """Update power state when it changes."""
        self.async_write_ha_state()

    @property
    def app_id(self):
        """ID of the current running app."""
        if self._is_feature_available(FeatureName.App):
            return self.atv.metadata.app.identifier
        return None

    @property
    def app_name(self):
        """Name of the current running app."""
        if self._is_feature_available(FeatureName.App):
            return self.atv.metadata.app.name
        return None

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._app_list.keys())

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self._playing:
            return {
                MediaType.Video: MEDIA_TYPE_VIDEO,
                MediaType.Music: MEDIA_TYPE_MUSIC,
                MediaType.TV: MEDIA_TYPE_TVSHOW,
            }.get(self._playing.media_type)
        return None

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        if self._playing:
            return self._playing.content_identifier
        return None

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._is_feature_available(FeatureName.Volume):
            return self.atv.audio.volume / 100.0  # from percent
        return None

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self._playing:
            return self._playing.total_time
        return None

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._playing:
            return self._playing.position
        return None

    @property
    def media_position_updated_at(self):
        """Last valid time of media position."""
        if self.state in (STATE_PLAYING, STATE_PAUSED):
            return dt_util.utcnow()
        return None

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player."""
        # If input (file) has a file format supported by pyatv, then stream it with
        # RAOP. Otherwise try to play it with regular AirPlay.
        if media_type == MEDIA_TYPE_APP:
            await self.atv.apps.launch_app(media_id)
        elif self._is_feature_available(FeatureName.StreamFile) and (
            await is_streamable(media_id) or media_type == MEDIA_TYPE_MUSIC
        ):
            _LOGGER.debug("Streaming %s via RAOP", media_id)
            await self.atv.stream.stream_file(media_id)
        elif self._is_feature_available(FeatureName.PlayUrl):
            _LOGGER.debug("Playing %s via AirPlay", media_id)
            await self.atv.stream.play_url(media_id)
        else:
            _LOGGER.error("Media streaming is not possible with current configuration")

    @property
    def media_image_hash(self):
        """Hash value for media image."""
        state = self.state
        if (
            self._playing
            and self._is_feature_available(FeatureName.Artwork)
            and state not in [None, STATE_OFF, STATE_IDLE]
        ):
            return self.atv.metadata.artwork_id
        return None

    async def async_get_media_image(self):
        """Fetch media image of current playing image."""
        state = self.state
        if self._playing and state not in [STATE_OFF, STATE_IDLE]:
            artwork = await self.atv.metadata.artwork()
            if artwork:
                return artwork.bytes, artwork.mimetype

        return None, None

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._playing:
            return self._playing.title
        return None

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        if self._is_feature_available(FeatureName.Artist):
            return self._playing.artist
        return None

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        if self._is_feature_available(FeatureName.Album):
            return self._playing.album
        return None

    @property
    def media_series_title(self):
        """Title of series of current playing media, TV show only."""
        if self._is_feature_available(FeatureName.SeriesName):
            return self._playing.series_name
        return None

    @property
    def media_season(self):
        """Season of current playing media, TV show only."""
        if self._is_feature_available(FeatureName.SeasonNumber):
            return str(self._playing.season_number)
        return None

    @property
    def media_episode(self):
        """Episode of current playing media, TV show only."""
        if self._is_feature_available(FeatureName.EpisodeNumber):
            return str(self._playing.episode_number)
        return None

    @property
    def repeat(self):
        """Return current repeat mode."""
        if self._is_feature_available(FeatureName.Repeat):
            return {
                RepeatState.Track: REPEAT_MODE_ONE,
                RepeatState.All: REPEAT_MODE_ALL,
            }.get(self._playing.repeat, REPEAT_MODE_OFF)
        return None

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        if self._is_feature_available(FeatureName.Shuffle):
            return self._playing.shuffle != ShuffleState.Off
        return None

    def _is_feature_available(self, feature):
        """Return if a feature is available."""
        if self.atv and self._playing:
            return self.atv.features.in_state(FeatureState.Available, feature)
        return False

    async def async_browse_media(
        self,
        media_content_type=None,
        media_content_id=None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return build_app_list(self._app_list)

    async def async_turn_on(self):
        """Turn the media player on."""
        if self._is_feature_available(FeatureName.TurnOn):
            await self.atv.power.turn_on()

    async def async_turn_off(self):
        """Turn the media player off."""
        if (self._is_feature_available(FeatureName.TurnOff)) and (
            not self._is_feature_available(FeatureName.PowerState)
            or self.atv.power.power_state == PowerState.On
        ):
            await self.atv.power.turn_off()

    async def async_media_play_pause(self):
        """Pause media on media player."""
        if self._playing:
            await self.atv.remote_control.play_pause()

    async def async_media_play(self):
        """Play media."""
        if self.atv:
            await self.atv.remote_control.play()

    async def async_media_stop(self):
        """Stop the media player."""
        if self.atv:
            await self.atv.remote_control.stop()

    async def async_media_pause(self):
        """Pause the media player."""
        if self.atv:
            await self.atv.remote_control.pause()

    async def async_media_next_track(self):
        """Send next track command."""
        if self.atv:
            await self.atv.remote_control.next()

    async def async_media_previous_track(self):
        """Send previous track command."""
        if self.atv:
            await self.atv.remote_control.previous()

    async def async_media_seek(self, position):
        """Send seek command."""
        if self.atv:
            await self.atv.remote_control.set_position(position)

    async def async_volume_up(self):
        """Turn volume up for media player."""
        if self.atv:
            await self.atv.audio.volume_up()

    async def async_volume_down(self):
        """Turn volume down for media player."""
        if self.atv:
            await self.atv.audio.volume_down()

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        if self.atv:
            # pyatv expects volume in percent
            await self.atv.audio.set_volume(volume * 100.0)

    async def async_set_repeat(self, repeat):
        """Set repeat mode."""
        if self.atv:
            mode = {
                REPEAT_MODE_ONE: RepeatState.Track,
                REPEAT_MODE_ALL: RepeatState.All,
            }.get(repeat, RepeatState.Off)
            await self.atv.remote_control.set_repeat(mode)

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        if self.atv:
            await self.atv.remote_control.set_shuffle(
                ShuffleState.Songs if shuffle else ShuffleState.Off
            )

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if app_id := self._app_list.get(source):
            await self.atv.apps.launch_app(app_id)
