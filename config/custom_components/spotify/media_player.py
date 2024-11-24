# noqa: ignore=all

"""Support for interacting with Spotify Connect."""

# Important notes about HA State writes:
#
# `self.async_write_ha_state()` should always be used inside of the event loop (any method that is async itself or a callback).
# If you are in a `async def` method or one wrapped in `@callback`, use `async_write_ha_state` since you are inside of the event loop.

# `self.schedule_update_ha_state(force_refresh=False)` should be unsed when not inside of the event loop (e.g. for sync functions that are ran
# inside of the executor thread).  If you are in a `def` method (no async) then use `schedule_update_ha_state` since you are inside of the event loop.

from __future__ import annotations

import datetime as dt
import time
import urllib.parse
from datetime import timedelta, datetime
from typing import Any, Callable, Concatenate, ParamSpec, TypeVar, Tuple
from yarl import URL

from soco import (
    SoCo,
)
from soco.core import (
    PLAY_MODE_BY_MEANING as SONOS_PLAY_MODE_BY_MEANING,
    PLAY_MODES as SONOS_PLAY_MODES,
)
from soco.plugins.sharelink import ShareLinkPlugin

from spotifywebapipython import (
    SpotifyClient,
    SpotifyDiscovery,
    SpotifyApiError,
    SpotifyWebApiError,
)
from spotifywebapipython.zeroconfapi import *
from spotifywebapipython.models import (
    Album,
    AlbumPageSaved,
    AlbumPageSimplified,
    AlbumSimplified,
    Artist,
    ArtistInfo,
    ArtistPage,
    Audiobook,
    AudiobookPageSimplified,
    AudioFeatures,
    Category,
    CategoryPage,
    Chapter,
    Context,
    Device as PlayerDevice,
    Episode,
    EpisodePageSaved,
    EpisodePageSimplified,
    ImageObject,
    PlayerPlayState,
    PlayerQueueInfo,
    PlayHistoryPage,
    Playlist,
    PlaylistPage,
    PlaylistPageSimplified,
    SearchResponse,
    Show,
    ShowPageSaved,
    SpotifyConnectDevice,
    SpotifyConnectDevices,
    Track,
    TrackRecommendations,
    TrackSaved,
    TrackPage,
    TrackPageSaved,
    TrackPageSimplified,
    UserProfile,
)

from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    BrowseMedia,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntry
from homeassistant.util.dt import utcnow

from .appmessages import STAppMessages
from .browse_media import (
    async_browse_media_library_index,
    BrowsableMedia,
    browse_media_node,
    PLAYABLE_MEDIA_TYPES,
    SPOTIFY_LIBRARY_MAP,
)
from .instancedata_spotify import InstanceDataSpotify
from .const import (
    DOMAIN,
    DOMAIN_SCRIPT,
    LOGGER,
    TRACE_MSG_DELAY_DEVICE_SONOS,
)
from .utils import (
    passwordMaskString,
    positionHMS_fromMilliSeconds,
    positionHMS_fromSeconds,
    validateDelay,
)

# get smartinspect logger reference; create a new session for this module name.
from smartinspectpython.siauto import (
    SIAuto,
    SILevel,
    SISession,
    SIMethodParmListContext,
    SIColors,
)

_logsi: SISession = SIAuto.Si.GetSession(__name__)
if _logsi == None:
    _logsi = SIAuto.Si.AddSession(__name__, True)
_logsi.SystemLogger = LOGGER


# Sonos constants.
SONOS_NOT_IMPLEMENTED: str = "NOT_IMPLEMENTED"
SONOS_COMMAND_DELAY: float = 0.50

REPEAT_TO_SONOS = {
    RepeatMode.OFF: False,
    RepeatMode.ALL: True,
    RepeatMode.ONE: "ONE",
}

SONOS_TO_REPEAT = {meaning: mode for mode, meaning in REPEAT_TO_SONOS.items()}


# our extra state attribute names.
ATTR_SPOTIFY_CONTEXT_URI = "sp_context_uri"
ATTR_SPOTIFY_DEVICE_ID = "sp_device_id"
ATTR_SPOTIFY_DEVICE_NAME = "sp_device_name"
ATTR_SPOTIFY_DEVICE_IS_BRAND_SONOS = "sp_device_is_brand_sonos"
ATTR_SPOTIFY_ITEM_TYPE = "sp_item_type"
ATTR_SPOTIFY_PLAYLIST_NAME = "sp_playlist_name"
ATTR_SPOTIFY_PLAYLIST_URI = "sp_playlist_uri"
ATTR_SPOTIFY_TRACK_IS_EXPLICIT = "sp_track_is_explicit"
ATTR_SPOTIFY_USER_COUNTRY = "sp_user_country"
ATTR_SPOTIFY_USER_DISPLAY_NAME = "sp_user_display_name"
ATTR_SPOTIFY_USER_EMAIL = "sp_user_email"
ATTR_SPOTIFY_USER_ID = "sp_user_id"
ATTR_SPOTIFY_USER_PRODUCT = "sp_user_product"
ATTR_SPOTIFY_USER_URI = "sp_user_uri"

ATTRVALUE_NO_DEVICE = "no_device"
ATTRVALUE_UNKNOWN = "unknown"


# annotate the `spotify_exception_handler` callable.
_SpotifyMediaPlayerT = TypeVar("_SpotifyMediaPlayerT", bound="SpotifyMediaPlayer")
_R = TypeVar("_R")
_P = ParamSpec("_P")


SCAN_INTERVAL = timedelta(seconds=1)
"""
Time interval (in seconds) for HA to scan for status updates.
Note that the Spotify Web API does not get called every time HA update method is called
though; check update method for logic that controls this.
"""

SPOTIFY_SCAN_INTERVAL: int = 30
"""
Time interval (in seconds) to scan spotify connect player for updates.
"""

SPOTIFY_SCAN_INTERVAL_TRACK_ENDSTART: int = 3
"""
Time interval (in seconds) to scan spotify connect player for updates
due to a track ending / starting.
"""

SPOTIFY_SCAN_INTERVAL_COMMAND: int = 6
"""
Time interval (in seconds) to scan spotify connect player for updates
due to a player command.  This gives the Spotify Connect Player time to
update its PlayState status.
"""


REPEAT_MODE_MAPPING_TO_HA = {
    "context": RepeatMode.ALL,
    "off": RepeatMode.OFF,
    "track": RepeatMode.ONE,
}
""" maps spotify repeat modes to home assistant repeat modes. """


REPEAT_MODE_MAPPING_TO_SPOTIFY = {
    value: key for key, value in REPEAT_MODE_MAPPING_TO_HA.items()
}
""" maps home assistant repeat modes to spotify repeat modes. """


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """
    Set up the media player based on a config entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        entry (ConfigEntry):
            HomeAssistant configuration entry dictionary.  This contains configuration
            settings for the specific component device entry.
        async_add_entities (AddEntitiesCallback):
            Callback function to add all entities to Home Assistant for this platform.

    This function is called as part of the __init__.async_setup_entry event flow,
    which was initiated via the `hass.config_entries.async_forward_entry_setup` call.
    """
    try:
        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': MediaPlayer async_setup_entry is starting - entry (ConfigEntry) object"
            % entry.title,
            entry,
        )

        # get integration instance data from HA datastore.
        data: InstanceDataSpotify = hass.data[DOMAIN][entry.entry_id]

        # create the platform instance, passing our initialization parameters.
        _logsi.LogVerbose(
            "'%s': MediaPlayer async_setup_entry is creating the SpotifyMediaPlayer instance"
            % entry.title
        )
        media_player = SpotifyMediaPlayer(data)

        # add all entities to Home Assistant.
        _logsi.LogVerbose(
            "'%s': MediaPlayer async_setup_entry is adding SpotifyMediaPlayer instance entities to Home Assistant"
            % entry.title
        )
        async_add_entities([media_player], True)

        # store the reference to the media player object.
        _logsi.LogVerbose(
            "'%s': MediaPlayer async_setup_entry is storing the SpotifyMediaPlayer reference to hass.data[DOMAIN]"
            % entry.title
        )
        hass.data[DOMAIN][entry.entry_id].media_player = media_player

        # trace.
        _logsi.LogVerbose("'%s': MediaPlayer async_setup_entry complete" % entry.title)

    except Exception as ex:
        # trace.
        _logsi.LogException(
            "'%s': MediaPlayer async_setup_entry exception" % entry.title,
            ex,
            logToSystemLogger=False,
        )
        raise

    finally:
        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


def spotify_exception_handler(
    func: Callable[Concatenate[_SpotifyMediaPlayerT, _P], _R],
) -> Callable[Concatenate[_SpotifyMediaPlayerT, _P], _R | None]:
    """
    Decorate SpotifyClient calls to handle Spotify exception.

    A decorator that wraps the passed in function, catches Spotify errors,
    aiohttp exceptions and handles the availability of the media player.
    """

    def wrapper(
        self: _SpotifyMediaPlayerT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R | None:
        try:
            # indicate we are in a command event.
            self._isInCommandEvent = True
            _logsi.WatchDateTime(
                SILevel.Debug, "HASpotifyCommandEventLastDT", datetime.now()
            )

            # call the function.
            result = func(self, *args, **kwargs)

            # do not update HA state in this handler!  doing so causes UI buttons
            # pressed to "toggle" between states.  the "self.schedule_update_ha_state(force_refresh=False)"
            # call should be done in the individual methods.

            # return function result to caller.
            return result

        except HomeAssistantError:
            raise  # pass handled exceptions on thru
        except ValueError:
            raise  # pass handled exceptions on thru
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)
        except Exception as ex:
            _logsi.LogException(None, ex)
            raise HomeAssistantError(str(ex)) from ex

        finally:
            # indicate we are NOT in a command event.
            self._isInCommandEvent = False

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a media player command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

    return wrapper


class SpotifyMediaPlayer(MediaPlayerEntity):
    """
    Representation of a Spotify media player device.
    """

    def __init__(self, data: InstanceDataSpotify) -> None:
        """
        Initializes a new instance of the Spotify media player entity class.

        Args:
            data (InstanceDataSpotify):
                The media player entity instance data parameters that were created
                in the `__init__.async_setup_entry` method.
        """
        methodParms: SIMethodParmListContext = None

        try:
            # trace.
            methodParms = _logsi.EnterMethodParmList(SILevel.Debug)
            methodParms.AppendKeyValue("data.media_player", str(data.media_player))
            methodParms.AppendKeyValue("data.session", str(data.session))
            methodParms.AppendKeyValue("data.spotifyClient", str(data.spotifyClient))
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "SpotifyMediaPlayer initialization arguments",
                methodParms,
            )

            # initialize instance storage.
            self._id = data.spotifyClient.UserProfile.Id
            self._playlist: Playlist = None
            self.data = data
            self._currentScanInterval: int = 0
            self._commandScanInterval: int = 0
            self._lastKnownTimeRemainingSeconds: int = 0
            self._isInCommandEvent: bool = False
            self._source_at_poweroff: str = None
            self._volume_level_saved: float = None
            self._playerState: PlayerPlayState = PlayerPlayState()
            self._spotifyConnectDevice: SpotifyConnectDevice = None
            self._sonosDevice: SoCo = None

            # initialize base class attributes (MediaPlayerEntity).
            self._attr_icon = "mdi:spotify"
            self._attr_media_image_remotely_accessible = False
            self._attr_state = MediaPlayerState.OFF

            # A unique_id for this entity within this domain.
            # Note: This is NOT used to generate the user visible Entity ID used in automations.
            self._attr_unique_id = data.spotifyClient.UserProfile.Id

            # we will set "self._attr_has_entity_name = False", which causes the "self._attr_name"
            # to be used as-is.  use "self._attr_has_entity_name = True", to append the "self._attr_name"
            # value to the end of "DeviceInfo.name" value.
            self._attr_has_entity_name = False
            self._attr_name = f"Spotify {data.spotifyClient.UserProfile.DisplayName}"

            # set device information.
            # this contains information about the device that is partially visible in the UI.
            # for more information see: https://developers.home-assistant.io/docs/device_registry_index/#device-properties
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, data.spotifyClient.UserProfile.Id)},
                manufacturer="Spotify AB",
                model=f"Spotify {self.data.spotifyClient.UserProfile.Product.capitalize()} Account",
                name=self._attr_name,
                entry_type=DeviceEntryType.SERVICE,
                configuration_url="https://open.spotify.com",
            )
            _logsi.LogDictionary(
                SILevel.Verbose,
                "'%s': MediaPlayer device information dictionary" % self.name,
                self._attr_device_info,
                prettyPrint=True,
            )

            # set features supported by this media player.
            # most features will NOT be supported if the Spotify user does not have a PREMIUM
            # membership level, as the Spotify Web API requires a premium membership for most
            # of the player control functions.
            if self.data.spotifyClient.UserProfile.Product == "premium":
                _logsi.LogVerbose(
                    "'%s': MediaPlayer is setting supported features for Spotify Premium user"
                    % self.name
                )
                self._attr_supported_features = (
                    MediaPlayerEntityFeature.BROWSE_MEDIA
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
                    | MediaPlayerEntityFeature.TURN_OFF
                    | MediaPlayerEntityFeature.TURN_ON
                    | MediaPlayerEntityFeature.VOLUME_MUTE
                    | MediaPlayerEntityFeature.VOLUME_SET
                    | MediaPlayerEntityFeature.VOLUME_STEP
                )
            else:
                _logsi.LogVerbose(
                    "'%s': MediaPlayer is setting supported features for Spotify Non-Premium user"
                    % self.name
                )
                self._attr_supported_features = (
                    MediaPlayerEntityFeature.BROWSE_MEDIA
                    | MediaPlayerEntityFeature.PAUSE
                    | MediaPlayerEntityFeature.PLAY
                    | MediaPlayerEntityFeature.PLAY_MEDIA
                    | MediaPlayerEntityFeature.SELECT_SOURCE
                    | MediaPlayerEntityFeature.TURN_OFF
                    | MediaPlayerEntityFeature.TURN_ON
                    | MediaPlayerEntityFeature.VOLUME_MUTE
                    | MediaPlayerEntityFeature.VOLUME_SET
                    | MediaPlayerEntityFeature.VOLUME_STEP
                )

            # we will (by default) set polling to true, as the SpotifyClient does not support websockets
            # for player update notifications.
            _logsi.LogVerbose(
                "'%s': MediaPlayer device polling is being enabled, as the device does not support websockets"
                % self.name
            )
            self._attr_should_poll = True

            # trace.
            _logsi.LogObject(
                SILevel.Verbose,
                "'%s': MediaPlayer SpotifyClient object" % self.name,
                self.data.spotifyClient,
            )
            _logsi.LogObject(
                SILevel.Verbose,
                "'%s': MediaPlayer initialization complete" % self.name,
                self,
            )

        except Exception as ex:
            # trace.
            _logsi.LogException(
                "'%s': MediaPlayer initialization exception" % self.name,
                ex,
                logToSystemLogger=False,
            )
            raise

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        # build list of our extra state attributes to return to HA UI.
        attributes = {}
        attributes[ATTR_SPOTIFY_DEVICE_ID] = ATTRVALUE_NO_DEVICE
        attributes[ATTR_SPOTIFY_DEVICE_NAME] = ATTRVALUE_NO_DEVICE
        attributes[ATTR_SPOTIFY_DEVICE_IS_BRAND_SONOS] = False
        attributes[ATTR_SPOTIFY_ITEM_TYPE] = ATTRVALUE_UNKNOWN
        attributes[ATTR_SPOTIFY_TRACK_IS_EXPLICIT] = False
        attributes[ATTR_SPOTIFY_USER_COUNTRY] = ATTRVALUE_UNKNOWN
        attributes[ATTR_SPOTIFY_USER_DISPLAY_NAME] = ATTRVALUE_UNKNOWN
        attributes[ATTR_SPOTIFY_USER_EMAIL] = ATTRVALUE_UNKNOWN
        attributes[ATTR_SPOTIFY_USER_ID] = ATTRVALUE_UNKNOWN
        attributes[ATTR_SPOTIFY_USER_PRODUCT] = ATTRVALUE_UNKNOWN
        attributes[ATTR_SPOTIFY_USER_URI] = ATTRVALUE_UNKNOWN

        self.data.spotifyClient.UserProfile.DisplayName

        # add currently active playstate information.
        if self._playerState is not None:
            if self._playerState.Device is not None:
                attributes[ATTR_SPOTIFY_DEVICE_ID] = self._playerState.Device.Id
                attributes[ATTR_SPOTIFY_DEVICE_NAME] = self._playerState.Device.Name
            if self._playerState.Context is not None:
                attributes[ATTR_SPOTIFY_CONTEXT_URI] = self._playerState.Context.Uri
                attributes["media_context_content_id"] = self._playerState.Context.Uri
            if self._playerState.ItemType is not None:
                attributes[ATTR_SPOTIFY_ITEM_TYPE] = self._playerState.ItemType
            if self._spotifyConnectDevice is not None:
                attributes[ATTR_SPOTIFY_DEVICE_IS_BRAND_SONOS] = (
                    self._spotifyConnectDevice.DeviceInfo.IsBrandSonos
                )
            if self._playerState.Item is not None:
                track: Track = self._playerState.Item
                if track.Explicit:
                    attributes[ATTR_SPOTIFY_TRACK_IS_EXPLICIT] = track.Explicit

        # add currently active playlist information.
        if self._playlist is not None:
            attributes[ATTR_SPOTIFY_PLAYLIST_NAME] = self._playlist.Name
            attributes[ATTR_SPOTIFY_PLAYLIST_URI] = self._playlist.Uri
            attributes["media_playlist_content_id"] = self._playlist.Uri

        # add userprofile information.
        if self.data.spotifyClient is not None:
            profile: UserProfile = self.data.spotifyClient.UserProfile
            if profile is not None:
                attributes[ATTR_SPOTIFY_USER_COUNTRY] = profile.Country
                attributes[ATTR_SPOTIFY_USER_DISPLAY_NAME] = profile.DisplayName
                attributes[ATTR_SPOTIFY_USER_EMAIL] = profile.EMail
                attributes[ATTR_SPOTIFY_USER_ID] = profile.Id
                attributes[ATTR_SPOTIFY_USER_PRODUCT] = profile.Product
                attributes[ATTR_SPOTIFY_USER_URI] = profile.Uri

        return attributes

    @property
    def state(self) -> MediaPlayerState:
        """Return the playback state."""
        return self._attr_state

    @property
    def media_content_id(self) -> str | None:
        """Return the media URL."""
        return self._attr_media_content_id

    @property
    def media_content_type(self) -> str | None:
        """Return the media type."""
        return self._attr_media_content_type

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self._attr_media_duration

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self._attr_media_position

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """
        When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        return self._attr_media_position_updated_at

    @property
    def media_image_url(self) -> str | None:
        """Return the media image URL."""
        return self._attr_media_image_url

    @property
    def media_title(self) -> str | None:
        """Return the media title."""
        return self._attr_media_title

    @property
    def media_artist(self) -> str | None:
        """Return the media artist."""
        return self._attr_media_artist

    @property
    def media_album_name(self) -> str | None:
        """Return the media album."""
        return self._attr_media_album_name

    @property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        return self._attr_media_track

    @property
    def media_playlist(self):
        """Title of current playing playlist."""
        if self._playlist is not None:
            return self._playlist.Name
        return None

    @property
    def media_playlist_content_id(self):
        """Content ID of current playing playlist."""
        if self._playlist is not None:
            return self._playlist.Uri
        return None

    @property
    def media_playlist_content_type(self):
        """Content Type of current playing playlist."""
        if self._playlist is not None:
            return self._playlist.Type
        return None

    @property
    def media_playlist_description(self):
        """Description of current playing playlist."""
        if self._playlist is not None:
            return self._playlist.Description
        return None

    @property
    def media_playlist_image_url(self):
        """Image URL of current playing playlist."""
        if self._playlist is not None:
            return self._playlist.ImageUrl
        return None

    @property
    def source(self) -> str | None:
        """Return the current playback device."""
        return self._attr_source

    @property
    def source_list(self) -> list[str] | None:
        """Return a list of source devices."""

        # get spotify client cached device list.
        if "GetSpotifyConnectDevices" in self.data.spotifyClient.ConfigurationCache:
            result: SpotifyConnectDevices = self.data.spotifyClient.ConfigurationCache[
                "GetSpotifyConnectDevices"
            ]

            # get the list of device names to hide (omit) in the list.
            sourceListHide: list = self.data.OptionSourceListHide

            # build list of device names for the source list.
            deviceNames: list[str] = []
            device: PlayerDevice
            for device in result.GetDeviceList():
                if device.Name.lower() not in sourceListHide:
                    deviceNames.append(device.Name)
            return deviceNames

        return None

    @property
    def shuffle(self) -> bool | None:
        """Shuffling state."""
        return self._attr_shuffle

    @property
    def repeat(self) -> RepeatMode | str | None:
        """Return current repeat mode."""
        return self._attr_repeat

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0.0 to 1.0)."""
        return self._attr_volume_level

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._attr_is_volume_muted

    @spotify_exception_handler
    def media_play(self) -> None:
        """Start or resume playback."""
        _logsi.LogVerbose(
            STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "media_play"
        )

        # update ha state.
        self._attr_state = MediaPlayerState.PLAYING
        self.schedule_update_ha_state(force_refresh=False)

        # resume playback (use currently active player).
        if self._sonosDevice is not None:
            _logsi.LogVerbose(
                "'%s': Issuing command to Sonos device '%s' ('%s'): PLAY"
                % (
                    self.name,
                    self._sonosDevice.ip_address,
                    self._sonosDevice.player_name,
                )
            )
            self._sonosDevice.play()

            # give SoCo api time to process the change.
            _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % SONOS_COMMAND_DELAY)
            time.sleep(SONOS_COMMAND_DELAY)

        else:
            # call Spotify Web API to process the request.
            self.data.spotifyClient.PlayerMediaResume()

    @spotify_exception_handler
    def media_pause(self) -> None:
        """Pause playback."""
        _logsi.LogVerbose(
            STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "media_pause"
        )

        # update ha state.
        self._attr_state = MediaPlayerState.PAUSED
        self.schedule_update_ha_state(force_refresh=False)

        # pause playback (use currently active player).
        if self._sonosDevice is not None:
            _logsi.LogVerbose(
                "'%s': Issuing command to Sonos device '%s' ('%s'): PAUSE"
                % (
                    self.name,
                    self._sonosDevice.ip_address,
                    self._sonosDevice.player_name,
                )
            )
            self._sonosDevice.pause()

            # give SoCo api time to process the change.
            _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % SONOS_COMMAND_DELAY)
            time.sleep(SONOS_COMMAND_DELAY)

        else:
            # call Spotify Web API to process the request.
            self.data.spotifyClient.PlayerMediaPause()

    @spotify_exception_handler
    def media_previous_track(self) -> None:
        """Skip to previous track."""
        _logsi.LogVerbose(
            STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "media_previous_track"
        )

        # skip to previous track (use currently active player).
        if self._sonosDevice is not None:
            _logsi.LogVerbose(
                "'%s': Issuing command to Sonos device '%s' ('%s'): PREVIOUS"
                % (
                    self.name,
                    self._sonosDevice.ip_address,
                    self._sonosDevice.player_name,
                )
            )
            self._sonosDevice.previous()

            # give SoCo api time to process the change.
            _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % SONOS_COMMAND_DELAY)
            time.sleep(SONOS_COMMAND_DELAY)

        else:
            # call Spotify Web API to process the request.
            self.data.spotifyClient.PlayerMediaSkipPrevious()

    @spotify_exception_handler
    def media_next_track(self) -> None:
        """Skip to next track."""
        _logsi.LogVerbose(
            STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "media_next_track"
        )

        # skip to next track (use currently active player).
        if self._sonosDevice is not None:
            _logsi.LogVerbose(
                "'%s': Issuing command to Sonos device '%s' ('%s'): NEXT"
                % (
                    self.name,
                    self._sonosDevice.ip_address,
                    self._sonosDevice.player_name,
                )
            )
            self._sonosDevice.next()

            # give SoCo api time to process the change.
            _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % SONOS_COMMAND_DELAY)
            time.sleep(SONOS_COMMAND_DELAY)

        else:
            # call Spotify Web API to process the request.
            self.data.spotifyClient.PlayerMediaSkipNext()

    @spotify_exception_handler
    def media_seek(self, position: float) -> None:
        """Send seek command."""
        _logsi.LogVerbose(
            STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS,
            self.name,
            "media_seek",
            "position='%s'" % (position),
        )

        # update ha state.
        self._attr_media_position = position
        self._attr_media_position_updated_at = utcnow()
        self.schedule_update_ha_state(force_refresh=False)

        # seek to track position (use currently active player).
        if self._sonosDevice is not None:
            sonosPosition: str = positionHMS_fromSeconds(
                position
            )  # convert from seconds to Sonos H:MM:SS format
            _logsi.LogVerbose(
                "'%s': Issuing command to Sonos device '%s' ('%s'): SEEK (position=%s)"
                % (
                    self.name,
                    self._sonosDevice.ip_address,
                    self._sonosDevice.player_name,
                    sonosPosition,
                )
            )
            self._sonosDevice.seek(str(sonosPosition))

            # give SoCo api time to process the change.
            _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % SONOS_COMMAND_DELAY)
            time.sleep(SONOS_COMMAND_DELAY)

        else:
            # call Spotify Web API to process the request.
            self.data.spotifyClient.PlayerMediaSeek(int(position * 1000))

    @spotify_exception_handler
    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        _logsi.LogVerbose(
            STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS,
            self.name,
            "mute_volume",
            "mute='%s'" % (mute),
        )

        self._attr_is_volume_muted = mute

        if mute:
            self._volume_level_saved = self._attr_volume_level
            self.schedule_update_ha_state(force_refresh=False)
            self.set_volume_level(0.0)
        else:
            # did we save the volume on a previous mute request?  if not, then default volume.
            if self._volume_level_saved is None or self._volume_level_saved == 0.0:
                _logsi.LogVerbose(
                    "Previously saved volume was not set; defaulting to 0.10"
                )
                self._volume_level_saved = 0.10
            self._attr_volume_level = self._volume_level_saved
            self.schedule_update_ha_state(force_refresh=False)
            self.set_volume_level(self._volume_level_saved)

    @spotify_exception_handler
    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """
        Play media; called by media browser when a browsed item is selected for playing.
        """
        methodParms: SIMethodParmListContext = None

        try:
            # trace.
            methodParms = _logsi.EnterMethodParmList(SILevel.Debug)
            methodParms.AppendKeyValue("media_type", media_type)
            methodParms.AppendKeyValue("media_id", media_id)
            methodParms.AppendKeyValue("**kwargs", kwargs)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                STAppMessages.MSG_MEDIAPLAYER_SERVICE % (self.name, "play_media"),
                methodParms,
            )

            # get enqueue keyword arguments (if any).
            enqueue: MediaPlayerEnqueue = kwargs.get(ATTR_MEDIA_ENQUEUE, None)

            # spotify can't handle URI's with query strings or anchors
            # yet, they do generate those types of URI in their official clients.
            media_id: str = str(URL(media_id).with_query(None).with_fragment(None))

            # is this an enqueue request?
            if enqueue is not None:
                _logsi.LogVerbose(
                    "Enqueue command received for this play media request: '%s'"
                    % (enqueue)
                )

                if enqueue == MediaPlayerEnqueue.ADD:
                    # add to queue request.
                    _logsi.LogVerbose(
                        "Adding uri to Spotify Player Queue: '%s'" % (media_id)
                    )
                    self.data.spotifyClient.AddPlayerQueueItem(media_id)
                    return

                elif enqueue == MediaPlayerEnqueue.NEXT:
                    # play next request.
                    _logsi.LogVerbose("Playing next item in the player queue")
                    self.data.spotifyClient.PlayerMediaSkipNext()
                    return

                elif enqueue == MediaPlayerEnqueue.PLAY:
                    # play request.
                    pass  # we will handle this below.

                elif enqueue == MediaPlayerEnqueue.REPLACE:
                    # play now and clear queue request.
                    pass  # we will handle this below.

                else:
                    _logsi.LogWarning(
                        "Spotify Connect Player does not support '%s' enqueue requests; request ignored"
                        % enqueue
                    )
                    return

            # set current source device reference.
            deviceId: str = self._attr_source

            # start play based upon the media type.
            if media_type in {MediaType.TRACK, MediaType.EPISODE, MediaType.MUSIC}:
                # self._sonosDevice = None
                self._attr_state = MediaPlayerState.PLAYING
                self.schedule_update_ha_state(force_refresh=False)
                _logsi.LogVerbose(
                    "Playing via PlayerMediaPlayTracks: uris='%s', deviceId='%s'"
                    % (media_id, deviceId)
                )
                self.service_spotify_player_media_play_tracks(
                    media_id, deviceId=deviceId
                )

            elif media_type in PLAYABLE_MEDIA_TYPES:
                # self._sonosDevice = None
                self._attr_state = MediaPlayerState.PLAYING
                self.schedule_update_ha_state(force_refresh=False)
                _logsi.LogVerbose(
                    "Playing via PlayerMediaPlayContext: contextUri='%s', deviceId='%s'"
                    % (media_id, deviceId)
                )
                self.service_spotify_player_media_play_context(
                    media_id, deviceId=deviceId
                )

            else:
                _logsi.LogWarning("Media type '%s' is not supported" % media_type)
                return

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    @spotify_exception_handler
    def select_source(self, source: str) -> None:
        """Select playback device."""
        try:
            # trace.
            methodParms = _logsi.EnterMethodParmList(SILevel.Debug)
            methodParms.AppendKeyValue("source", source)
            methodParms.AppendKeyValue("self.state", self._attr_state)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS
                % (self.name, "select_source", "source='%s'" % (source)),
                methodParms,
            )

            # was a source selected?  if not, then we are done.
            if (source is None) or (len(source) == 0):
                raise HomeAssistantError(
                    "'%s': Source argument was not specified while trying to select a source.)"
                    % (self.name)
                )

            # are we currently powered off?
            if self._attr_state == MediaPlayerState.OFF:
                # power on the player.
                # note that the `turn_on()` method will issue a transfer playback to the specified source.
                self.turn_on()
                self._isInCommandEvent = (
                    True  # turn "in a command event" indicator back on.
                )

            else:
                # transfer playback to the specified source.
                self.service_spotify_player_transfer_playback(
                    source,
                    (self._attr_state != MediaPlayerState.PAUSED),
                    refreshDeviceList=True,
                    forceActivateDevice=True,
                )

            # set the selected source.
            self._attr_source = source
            _logsi.LogVerbose(
                "'%s': Selected source was changed to: '%s'"
                % (self.name, self._attr_source)
            )

            # set default device name to use for player transport functions that are executed
            # but there is no active Spotify player device.
            self.data.spotifyClient.DefaultDeviceId = self._attr_source

        except HomeAssistantError:
            raise  # pass handled exceptions on thru

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    @spotify_exception_handler
    def set_shuffle(self, shuffle: bool) -> None:
        """Enable/Disable shuffle mode."""
        _logsi.LogVerbose(
            STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS,
            self.name,
            "set_shuffle",
            "shuffle='%s'" % (shuffle),
        )

        # update ha state.
        self._attr_shuffle = shuffle
        self.schedule_update_ha_state(force_refresh=False)

        # set shuffle mode (use currently active player).
        if self._sonosDevice is not None:
            _logsi.LogVerbose(
                "'%s': Issuing command to Sonos device '%s' ('%s'): SHUFFLE"
                % (
                    self.name,
                    self._sonosDevice.ip_address,
                    self._sonosDevice.player_name,
                )
            )
            # set the Sonos PlayMode directly (instead of setting the Sonos `shuffle` property)!
            # the Spotify Web API PlayerState `RepeatState` value can sometimes be different than what the
            # Sonos device reports for its `repeat` property value!
            sonos_repeat: str
            if self._playerState.RepeatState == "track":
                sonos_repeat = "ONE"
            elif self._playerState.RepeatState == "off":
                sonos_repeat = False
            elif self._playerState.RepeatState == "context":
                sonos_repeat = True
            else:  # assume off if nothing else.
                sonos_repeat = False
            self._sonosDevice.play_mode = SONOS_PLAY_MODE_BY_MEANING[
                (shuffle, sonos_repeat)
            ]

            # give SoCo api time to process the change.
            _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % SONOS_COMMAND_DELAY)
            time.sleep(SONOS_COMMAND_DELAY)

        else:
            # call Spotify Web API to process the request.
            self.data.spotifyClient.PlayerSetShuffleMode(shuffle)

    @spotify_exception_handler
    def set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        _logsi.LogVerbose(
            STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS,
            self.name,
            "set_repeat",
            "repeat='%s'" % (repeat),
        )

        # update ha state.
        if repeat not in REPEAT_MODE_MAPPING_TO_SPOTIFY:
            raise ValueError(f"Unsupported repeat mode: {repeat}")
        self._attr_repeat = repeat
        self.schedule_update_ha_state(force_refresh=False)

        # set repeat mode (use currently active player).
        if self._sonosDevice is not None:
            _logsi.LogVerbose(
                "'%s': Issuing command to Sonos device '%s' ('%s'): REPEAT"
                % (
                    self.name,
                    self._sonosDevice.ip_address,
                    self._sonosDevice.player_name,
                )
            )
            # set the Sonos PlayMode directly (instead of setting the Sonos repeat property)!
            # The Spotify Web API PlayerState `ShuffleState` value can sometimes be different than what the
            # Sonos device reports for its `shuffle` property value!
            sonos_repeat = REPEAT_TO_SONOS[repeat]
            self._sonosDevice.play_mode = SONOS_PLAY_MODE_BY_MEANING[
                (self._playerState.ShuffleState, sonos_repeat)
            ]

            # give SoCo api time to process the change.
            _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % SONOS_COMMAND_DELAY)
            time.sleep(SONOS_COMMAND_DELAY)

        else:
            # call Spotify Web API to process the request.
            self.data.spotifyClient.PlayerSetRepeatMode(
                REPEAT_MODE_MAPPING_TO_SPOTIFY[repeat]
            )

    @spotify_exception_handler
    def set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        _logsi.LogVerbose(
            STAppMessages.MSG_MEDIAPLAYER_SERVICE_WITH_PARMS,
            self.name,
            "set_volume_level",
            "volume='%s'" % (volume),
        )

        # validations.
        if volume is None:
            volume = 0.0

        # update ha state.
        self._attr_volume_level = volume
        self.schedule_update_ha_state(force_refresh=False)

        # set volume (use currently active player).
        if self._sonosDevice is not None:
            _logsi.LogVerbose(
                "'%s': Issuing command to Sonos device '%s' ('%s'): VOLUME"
                % (
                    self.name,
                    self._sonosDevice.ip_address,
                    self._sonosDevice.player_name,
                )
            )
            nVolume: int = int(volume * 100)
            self._sonosDevice.volume = nVolume

            # give SoCo api time to process the change.
            _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % SONOS_COMMAND_DELAY)
            time.sleep(SONOS_COMMAND_DELAY)

        else:
            # call Spotify Web API to process the request.
            self.data.spotifyClient.PlayerSetVolume(int(volume * 100))

    @spotify_exception_handler
    def turn_off(self) -> None:
        """Turn off media player."""
        try:
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(
                STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "turn_off"
            )
            _logsi.LogVerbose("'%s': entity_id=%s" % (self.name, self.entity_id))

            # save currently active source.
            _logsi.LogVerbose(
                "'%s': Active source at PowerOff: '%s'" % (self.name, self._attr_source)
            )
            self._source_at_poweroff: str = self._attr_source

            # set media player state and update ha state.
            self._attr_state = MediaPlayerState.OFF
            _logsi.LogVerbose(
                "'%s': MediaPlayerState set to '%s'" % (self.name, self._attr_state)
            )
            self.schedule_update_ha_state(force_refresh=False)

            # get current player state.
            self._playerState, self._spotifyConnectDevice, self._sonosDevice = (
                self._GetPlayerPlaybackState()
            )

            # pause playback
            if (self._spotifyConnectDevice) and (
                self.data.spotifyClient.UserProfile.IsProductPremium
            ):
                if self._sonosDevice is not None:
                    _logsi.LogVerbose(
                        "'%s': Issuing command to Sonos device '%s' ('%s'): PAUSE"
                        % (
                            self.name,
                            self._sonosDevice.ip_address,
                            self._sonosDevice.player_name,
                        )
                    )
                    self._sonosDevice.pause()

                    # give SoCo api time to process the change.
                    _logsi.LogVerbose(
                        TRACE_MSG_DELAY_DEVICE_SONOS % SONOS_COMMAND_DELAY
                    )
                    time.sleep(SONOS_COMMAND_DELAY)

                else:
                    if self._playerState.IsPlaying:
                        self.data.spotifyClient.PlayerMediaPause(
                            self._spotifyConnectDevice.DeviceInfo.DeviceId
                        )

            # call script to power off device.
            self._CallScriptPower(self.data.OptionScriptTurnOff, "turn_off")

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)
        except Exception as ex:
            _logsi.LogException(None, ex)
            raise HomeAssistantError(str(ex)) from ex

        finally:
            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    @spotify_exception_handler
    def turn_on(self) -> None:
        """Turn on media player."""
        try:
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(
                STAppMessages.MSG_MEDIAPLAYER_SERVICE, self.name, "turn_on"
            )

            # if already powered on then we are done.
            if self._attr_state is not MediaPlayerState.OFF:
                _logsi.LogVerbose(
                    "'%s': MediaPlayer is already powered on (state=%s); nothing to do"
                    % (self.name, self._attr_state)
                )
                return

            # set media player state to IDLE.
            self._attr_state = MediaPlayerState.IDLE
            _logsi.LogVerbose(
                "'%s': MediaPlayerState set to '%s'" % (self.name, self._attr_state)
            )
            # self.schedule_update_ha_state(force_refresh=False)

            # call script to power on device.
            self._CallScriptPower(self.data.OptionScriptTurnOn, "turn_on")

            # just in case the OptionScriptTurnOn reset the state, set media player state to IDLE.
            self._attr_state = MediaPlayerState.IDLE

            # get current Spotify Connect player state.
            self._playerState, self._spotifyConnectDevice, self._sonosDevice = (
                self._GetPlayerPlaybackState()
            )

            # update the source list (spotify connect devices cache).
            self.data.spotifyClient.GetSpotifyConnectDevices(refresh=True)

            # try to automatically select a source for play.
            # if spotify web api player is not found and a default spotify connect device is configured, then select it;
            # otherwise, select the last active device source;
            # otherwise, select the currently active Spotify Connect device source;
            # otherwise, we cannot automatically select a source!
            source: str = None
            if (self._spotifyConnectDevice is None) and (
                self.data.OptionDeviceDefault is not None
            ):
                source = PlayerDevice.GetNameFromSelectItem(
                    self.data.OptionDeviceDefault
                )
                _logsi.LogVerbose(
                    "'%s': Spotify configuration default device source will be selected: '%s'"
                    % (self.name, source)
                )
            elif self._source_at_poweroff is not None:
                source = self._source_at_poweroff
                _logsi.LogVerbose(
                    "'%s': Last active device source will be selected: '%s'"
                    % (self.name, source)
                )
            elif self._spotifyConnectDevice is not None:
                source = self._spotifyConnectDevice.DeviceInfo.RemoteName
                _logsi.LogVerbose(
                    "'%s': Currently active Spotify Connect device source will be selected: '%s'"
                    % (self.name, source)
                )
            else:
                _logsi.LogVerbose(
                    "'%s': Could not auto-select a source for play" % (self.name)
                )

            # activate the selected source.
            if source is not None:
                self.select_source(source)
                self._isInCommandEvent = (
                    True  # turn "in a command event" indicator back on.
                )

            # is playing content paused?  if so, then resume play.
            if (self._playerState.Device.IsActive) and (
                self._playerState.Actions.Pausing
            ):
                _logsi.LogVerbose(
                    "'%s': MediaPlayer turned on - resuming play on source device: '%s'"
                    % (self.name, self._playerState.Device.Name)
                )
                self.media_play()
                self._isInCommandEvent = (
                    True  # turn "in a command event" indicator back on.
                )

            # trace.
            _logsi.LogVerbose("'%s': MediaPlayer turn_on complete" % (self.name))

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)
        except Exception as ex:
            _logsi.LogException(None, ex)
            raise HomeAssistantError(str(ex)) from ex

        finally:
            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    def update(self) -> None:
        """Update state and attributes."""

        # trace.
        _logsi.WatchDateTime(SILevel.Debug, "HASpotifyUpdateLastDT", datetime.now())

        # is the media player enabled?  if not, then there is nothing to do.
        if not self.enabled:
            # _logsi.LogVerbose("'%s': Update - Integration is disabled; nothing to do" % self.name)
            return

        # is the media player powered off?  if so, then there is nothing to do.
        if self._attr_state == MediaPlayerState.OFF:
            # _logsi.LogVerbose("'%s': Update - Integration is powered off; nothing to do" % self.name)
            return

        # is the media player in a command event?  if so, then exit as updates are
        # happening that we don't want overridden just yet.
        if self._isInCommandEvent:
            _logsi.LogVerbose(
                "'%s': Update - Integration is in a command event; bypassing update"
                % self.name
            )
            return

        try:
            # trace.
            _logsi.EnterMethod(SILevel.Debug)

            _logsi.LogVerbose(
                "'%s': Scan interval %d check - commandScanInterval=%d, currentScanInterval=%d, lastKnownTimeRemainingSeconds=%d, state=%s"
                % (
                    self.name,
                    SPOTIFY_SCAN_INTERVAL,
                    self._commandScanInterval,
                    self._currentScanInterval,
                    self._lastKnownTimeRemainingSeconds,
                    str(self._attr_state),
                )
            )

            # have we reached a scan interval?
            if not ((self._currentScanInterval % SPOTIFY_SCAN_INTERVAL) == 0):
                # no - decrement the current scan interval counts.
                self._currentScanInterval = self._currentScanInterval - 1
                if self._commandScanInterval > 0:
                    self._commandScanInterval = self._commandScanInterval - 1

                # if last known time remaining value is less than current scan interval then
                # use the lesser last known time remaining value as the current scan interval.
                # this can happen when a user seeks to a new position, and the track time
                # remaining is less than the current scan interval.  we will also check the
                # last known time remaining value for greater than zero, as it is zero at startup.
                if (
                    (self._lastKnownTimeRemainingSeconds > 0)
                    and (
                        self._lastKnownTimeRemainingSeconds < self._currentScanInterval
                    )
                    and (self._attr_state == MediaPlayerState.PLAYING)
                ):
                    self._currentScanInterval = self._lastKnownTimeRemainingSeconds
                    _logsi.LogVerbose(
                        "'%s': Resetting current scan interval to last known time remaining value - currentScanInterval=%d, lastKnownTimeRemainingSeconds=%d, state=%s"
                        % (
                            self.name,
                            self._currentScanInterval,
                            self._lastKnownTimeRemainingSeconds,
                            str(self._attr_state),
                        )
                    )

                # we will query Spotify for player state if ANY of the following:
                # - we reached a scan interval (e.g. 30 seconds).
                # - within specified seconds of an issued command (e.g. 5 seconds).
                # - within specified seconds of a playing track ending.
                if (
                    (self._currentScanInterval == 0)
                    or (
                        self._commandScanInterval > 0
                        and self._commandScanInterval <= SPOTIFY_SCAN_INTERVAL_COMMAND
                    )
                    or (
                        (
                            self._lastKnownTimeRemainingSeconds
                            <= SPOTIFY_SCAN_INTERVAL_TRACK_ENDSTART
                        )
                        and (self._attr_state == MediaPlayerState.PLAYING)
                    )
                ):
                    # yes - allow the update
                    pass
                else:
                    # no - keep waiting to update.
                    return

            # # TEST TODO - force token expire!!!
            # leave the following comments in here, in case you need to test token expire logic.
            # this will force the token to expire in 30 seconds, instead of the 1 hour Spotify default.
            #
            # _logsi.LogWarning("TEST TODO - Forcing token expiration in 30 seconds for testing purposes", colorValue=SIColors.Red)
            # self.data.spotifyClient.AuthToken._ExpiresIn = 30
            # unix_epoch = datetime(1970, 1, 1)
            # dtUtcNow:datetime = datetime.utcnow()
            # self.data.spotifyClient.AuthToken._ExpireDateTimeUtc = dtUtcNow + timedelta(seconds=self.data.spotifyClient.AuthToken._ExpiresIn)
            # self.data.spotifyClient.AuthToken._ExpiresAt = int((dtUtcNow - unix_epoch).total_seconds())  # seconds from epoch, current date
            # self.data.spotifyClient.AuthToken._ExpiresAt = self.data.spotifyClient.AuthToken._ExpiresAt + self.data.spotifyClient.AuthToken._ExpiresIn             # add ExpiresIn seconds

            # get now playing status.
            _logsi.LogVerbose(
                "'%s': update method - getting Spotify Connect Player state" % self.name
            )
            self._playerState, self._spotifyConnectDevice, self._sonosDevice = (
                self._GetPlayerPlaybackState()
            )
            self._UpdateHAFromPlayerPlayState(self._playerState)
            _logsi.WatchDateTime(
                SILevel.Debug, "HASpotifyPlaystateLastUpdate", datetime.now()
            )

            # update the scan interval for next time.
            self._currentScanInterval = SPOTIFY_SCAN_INTERVAL - 1

            # calculate the time (in seconds) remaining on the playing track.
            if self._playerState is not None:
                if self._playerState.Item is not None:
                    track: Track = self._playerState.Item
                    self._lastKnownTimeRemainingSeconds = (
                        track.DurationMS - self._playerState.ProgressMS
                    )
                    if self._lastKnownTimeRemainingSeconds > 1000:
                        self._lastKnownTimeRemainingSeconds = int(
                            self._lastKnownTimeRemainingSeconds / 1000
                        )  # convert MS to Seconds
                    else:
                        self._lastKnownTimeRemainingSeconds = 0
                    _logsi.LogVerbose(
                        "'%s': playerState track ProgressMS=%s, DurationMS=%d, lastKnownTimeRemainingSeconds=%d"
                        % (
                            self.name,
                            self._playerState.ProgressMS,
                            track.DurationMS,
                            self._lastKnownTimeRemainingSeconds,
                        )
                    )

            # did the now playing context change?
            context: Context = self._playerState.Context
            if (context is not None) and (
                self._playlist is None or self._playlist.Uri != context.Uri
            ):
                # yes - if it's a playlist, then we need to update the stored playlist reference.
                self._playlist = None
                if context.Type == MediaType.PLAYLIST:
                    try:
                        _logsi.LogVerbose(
                            "Retrieving playlist for context uri '%s'" % context.Uri
                        )
                        spotifyId: str = SpotifyClient.GetIdFromUri(context.Uri)
                        self._playlist = self.data.spotifyClient.GetPlaylist(spotifyId)

                    except Exception as ex:
                        _logsi.LogException(
                            "Unable to load spotify playlist '%s'. Continuing without playlist data"
                            % context.Uri,
                            ex,
                        )
                        self._playlist = None

                else:
                    self._playlist = None

            elif context is None:
                self._playlist = None

        except SpotifyWebApiError as ex:
            _logsi.LogException(None, ex)
            raise HomeAssistantError(ex.Message) from ex

        except Exception as ex:
            _logsi.LogException(None, ex)
            raise HomeAssistantError(str(ex)) from ex

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    def to_seconds(self, timestr: str):
        """
        Convert an "HH:MM:SS" string value to total number of seconds.
        """
        if (timestr is None) or (timestr == SONOS_NOT_IMPLEMENTED):
            return 0

        seconds = 0
        for part in timestr.split(":"):
            seconds = seconds * 60 + int(part, 10)
        return seconds

    @callback
    def _handle_devices_update(self) -> None:
        """
        Handle updated data from the coordinator.
        """
        if not self.enabled:
            return

        # inform HA of our current state.
        self.schedule_update_ha_state(force_refresh=False)

    def _GetPlayerPlaybackState(
        self,
    ) -> tuple[PlayerPlayState, SpotifyConnectDevice, SoCo]:
        """
        Get Spotify Player Playback state and active device.

        Returns:
            A tuple that consists of:
            - A `PlayerPlayState` object that contains the current player state.
            - A `SpotifyConnectDevice` object that contains the currently active Spotify Connect device,
              or None if no device is active.
            - A `SoCo` object that contains the current active Sonos device, or None if not a Sonos device.
        """
        playerState: PlayerPlayState = None
        spotifyConnectDevice: SpotifyConnectDevice = None
        sonosDevice: SoCo = None

        try:
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose("'%s': Getting Spotify Connect Player state" % self.name)
            _logsi.LogVerbose(
                "'%s': Currently selected Source: '%s'"
                % (self.name, str(self._attr_source))
            )

            # query the Spotify Web API to get playback status.
            playerState = self.data.spotifyClient.GetPlayerPlaybackState(
                additionalTypes=MediaType.EPISODE.value
            )

            # did Spotify Web API report an active device?
            # if not, then use the currently selected source device.
            if playerState.Device.Name is None:
                playerState.Device._Name = self._attr_source

            # find the currently active device in the available Spotify Connect device cache.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            spotifyConnectDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(
                playerState.Device.Name
            )
            if spotifyConnectDevice is None:
                spotifyConnectDevice = scDevices.GetDeviceById(playerState.Device.Id)

            # if current playback device is a Sonos device, then we will set the sonosDevice reference
            # and use the SoCo API to get the Sonos playback status.
            if (spotifyConnectDevice is not None) and (
                spotifyConnectDevice.DeviceInfo.IsBrandSonos
            ):
                _logsi.LogVerbose(
                    "'%s': Sonos device detected; setting Sonos Control API reference for Sonos device '%s' ('%s')"
                    % (
                        self.name,
                        spotifyConnectDevice.DiscoveryResult.HostIpAddress,
                        spotifyConnectDevice.DeviceInfo.RemoteName,
                    )
                )
                sonosDevice = SoCo(spotifyConnectDevice.DiscoveryResult.HostIpAddress)

                # # has the Sonos device ip changed?
                # if (self._sonosDevice is None):
                #     _logsi.LogVerbose("'%s': SonosDevice IP is being changed from '%s' to '%s' ('%s')" % (self.name, 'None', spotifyConnectDevice.DiscoveryResult.HostIpAddress, spotifyConnectDevice.DeviceInfo.RemoteName))
                # elif (self._sonosDevice.ip_address != spotifyConnectDevice.DiscoveryResult.HostIpAddress):
                #     _logsi.LogVerbose("'%s': SonosDevice IP is being changed from '%s' to '%s' ('%s')" % (self.name, self._sonosDevice.ip_address, spotifyConnectDevice.DiscoveryResult.HostIpAddress, spotifyConnectDevice.DeviceInfo.RemoteName))
                #     self._sonosDevice = SoCo(spotifyConnectDevice.DiscoveryResult.HostIpAddress)
                # else:
                #     _logsi.LogVerbose("'%s': SonosDevice IP was not changed from '%s' ('%s')" % (self.name, self._sonosDevice.ip_address, self._sonosDevice.player_name))

                # use the SoCo API to get Sonos playback status.
                # build a spotify playback status instance so we can use a common update method.
                _logsi.LogVerbose(
                    "'%s': Getting Sonos device status via Sonos Control API for device: '%s' ('%s')"
                    % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                )
                sonosTrackInfo: dict = sonosDevice.get_current_track_info()
                _logsi.LogDictionary(
                    SILevel.Verbose,
                    "'%s': Sonos device current_track_info results for device: '%s' ('%s')"
                    % (self.name, sonosDevice.ip_address, sonosDevice.player_name),
                    sonosTrackInfo,
                    prettyPrint=True,
                )
                sonosTransportInfo: dict = sonosDevice.get_current_transport_info()
                _logsi.LogDictionary(
                    SILevel.Verbose,
                    "'%s': Sonos device get_current_transport_info results for device: '%s' ('%s')"
                    % (self.name, sonosDevice.ip_address, sonosDevice.player_name),
                    sonosTransportInfo,
                    prettyPrint=True,
                )

                # update Spotify Web API player state with Sonos player state.
                if spotifyConnectDevice is not None:
                    playerState._Device._Id = spotifyConnectDevice.DeviceInfo.DeviceId
                playerState._Device._Name = sonosDevice.player_name
                playerState._Device._VolumePercent = sonosDevice.volume
                playerState._Device._IsActive = True
                playerState._Device._IsRestricted = True
                playerState._Device._SupportsVolume = True
                playerState._Device._Type = "SPEAKER"

                # try to get the spotify uri from the "metadata" music library DIDL value, as
                # the "uri" value (e.g. "x-sonos-vli:RINCON_38420B909DC801400:2,spotify:e934941535d7b182815bf688490ce8a8")
                # is not a true spotify uri value (e.g. "spotify:track:6kYyS9g4WJeRzTYqsmcMmM")
                spotifyUri: str = sonosTrackInfo.get("uri", "")
                didl: str = sonosTrackInfo.get("metadata", None)
                if didl:
                    METADATA_ID: str = "x-sonos-spotify:"
                    idx: int = didl.find(METADATA_ID)
                    if idx > -1:
                        spotifyUri: str = didl[idx + len(METADATA_ID) :]
                        spotifyUri = urllib.parse.unquote(spotifyUri)
                        idx = spotifyUri.find("?")
                        if idx > -1:
                            spotifyUri = spotifyUri[:idx]
                spotifyType = self.data.spotifyClient.GetTypeFromUri(spotifyUri) or ""
                spotifyId = self.data.spotifyClient.GetIdFromUri(spotifyUri) or ""

                # set base item properties.
                playerState.ItemType = spotifyType
                sTimeValue: str = sonosTrackInfo.get("position", None)
                playerState._ProgressMS = (
                    self.to_seconds(sTimeValue) * 1000
                )  # convert h:mm:ss to milliseconds

                # set some item properties based on the playing type (episode or non-episode).
                if spotifyType == "episode":
                    # get the episode data from spotify, as Sonos Soco data is incomplete.
                    playerState._CurrentlyPlayingType = "episode"
                    episode: Episode = self.data.spotifyClient.GetEpisode(spotifyId)
                    if episode.Id is not None:
                        playerState._Item = episode
                        if playerState._Context is None:
                            playerState._Context = Context()
                            playerState._Context._Type = episode.Show.Type
                            playerState._Context._Uri = episode.Show.Uri
                            playerState._Context._Href = episode.Show.Href
                            playerState._Context._ExternalUrls = (
                                episode.Show.ExternalUrls
                            )
                    else:
                        # if data could not be obtained from spotify, then use what's
                        # available from Sonos Soco api metadata.
                        playerState._Item = Episode()
                        playerState._Item._Name = sonosTrackInfo.get("title", "")
                        playerState._Item._Uri = spotifyUri
                        playerState._Item._Description = (
                            "Sonos device does not provide a description"
                        )
                        sTimeValue: str = sonosTrackInfo.get("duration", None)
                        playerState._Item._DurationMS = (
                            self.to_seconds(sTimeValue) * 1000
                        )  # convert h:mm:ss to milliseconds
                        playerState._Item._Explicit = False
                        playerState._Item._Href = (
                            "https://api.spotify.com/v1/episodes/" + spotifyId
                        )
                        playerState._Item._HtmlDescription = (
                            playerState._Item._Description
                        )
                        playerState._Item._Id = spotifyId
                        playerState._Item.Images.append(ImageObject())
                        playerState._Item.Images[0]._Url = sonosTrackInfo.get(
                            "album_art", ""
                        )
                        playerState._Item._TrackNumber = sonosTrackInfo.get(
                            "playlist_position", ""
                        )
                        playerState._Item._ReleaseDate = "0000"
                        playerState._Item._ReleaseDatePrecision = "year"
                        playerState._Item._Type = "episode"
                        playerState._Item._Show = Show()
                        playerState._Item._Show._Name = sonosTrackInfo.get(
                            "album", ""
                        )  # TODO get this from metadata (<r:podcast>The Elfstones of Shannara</r:podcast>)
                        playerState._Item._Show.Images.append(ImageObject())
                        playerState._Item._Show.Images[0]._Url = sonosTrackInfo.get(
                            "album_art", ""
                        )
                        playerState._Item._Show._Publisher = sonosTrackInfo.get(
                            "artist", ""
                        )

                        # if show name not set then get it from metadata.
                        if playerState._Item._Show._Name == "":
                            if didl:
                                METADATA_ID: str = "<r:podcast>"
                                METADATA_END: str = "</r:podcast>"
                                idx: int = didl.find(METADATA_ID)
                                if idx > -1:
                                    metaValue: str = didl[idx + len(METADATA_ID) :]
                                    idx = metaValue.find(METADATA_END)
                                    if idx > -1:
                                        metaValue = metaValue[:idx]
                                        playerState._Item._Show._Name = metaValue

                    # if episode is playing then resolve the underlying type (audiobook / podcast show).
                    if self.data.spotifyClient.IsChapterEpisode(spotifyId):
                        playerState.ItemType = "audiobook"
                    else:
                        playerState.ItemType = "podcast"

                elif spotifyType == "track":
                    # get the track data from spotify, as Sonos Soco data is incomplete.
                    track: Track = self.data.spotifyClient.GetTrack(spotifyId)
                    if track.Id is not None:
                        playerState._Item = track
                        if playerState._Context is None:
                            playerState._Context = Context()
                            playerState._Context._Type = track.Album.Type
                            playerState._Context._Uri = track.Album.Uri
                            playerState._Context._Href = track.Album.Href
                            playerState._Context._ExternalUrls = (
                                track.Album.ExternalUrls
                            )
                    else:
                        # if data could not be obtained from spotify, then use what's
                        # available from Sonos Soco api metadata.
                        playerState._CurrentlyPlayingType = "track"
                        playerState.ItemType = playerState._CurrentlyPlayingType
                        playerState._Item = Track()
                        playerState._Item._Name = sonosTrackInfo.get("title", "")
                        playerState._Item._Uri = spotifyUri
                        playerState._Item._Description = (
                            "Sonos device does not provide a description"
                        )
                        sTimeValue: str = sonosTrackInfo.get("duration", None)
                        playerState._Item._DurationMS = (
                            self.to_seconds(sTimeValue) * 1000
                        )  # convert h:mm:ss to milliseconds
                        playerState._Item._Explicit = False
                        playerState._Item._Href = (
                            "https://api.spotify.com/v1/episodes/" + spotifyId
                        )
                        playerState._Item._HtmlDescription = (
                            playerState._Item._Description
                        )
                        playerState._Item._Id = spotifyId
                        playerState._Item._TrackNumber = sonosTrackInfo.get(
                            "playlist_position", ""
                        )
                        playerState._Item._ReleaseDate = "0000"
                        playerState._Item._ReleaseDatePrecision = "year"
                        playerState._Item._Type = "track"
                        playerState._Item._Album = Album()
                        playerState._Item._Album._Name = sonosTrackInfo.get("album", "")
                        playerState._Item._Album.Images.append(ImageObject())
                        playerState._Item._Album.Images[0]._Url = sonosTrackInfo.get(
                            "album_art", ""
                        )
                        playerState._Item.Artists.append(Artist())
                        playerState._Item.Artists[0]._Name = sonosTrackInfo.get(
                            "artist", ""
                        )

                # set transport actions.
                currentTransportState: str = sonosTransportInfo.get(
                    "current_transport_state", ""
                )
                if currentTransportState == "PLAYING":
                    playerState._IsPlaying = True
                elif currentTransportState in ["PAUSED_PLAYBACK", "STOPPED"]:
                    playerState.Actions._Pausing = True

                # only update the following PlayState attributes from SoCo if they are NOT set.
                # these values are used to set the Sonos PlayMode value, which is the actual value that determines
                # what the Repeat and Shuffle settings are (ya, it's weird!).  What is odd is that the Spotify
                # Web API PlayerState values for Shuffle and Repeat can be different than what the Sonos Controller
                # API (SoCo) report for the device!  This is why we use the Spotify Web API PlayerState values.
                if playerState._ShuffleState is None:
                    playerState._ShuffleState = sonosDevice.shuffle
                if playerState._RepeatState is None:
                    sonosRepeat = sonosDevice.repeat
                    if sonosRepeat == "ONE":
                        playerState._RepeatState = "track"
                    elif sonosRepeat == False:
                        playerState._RepeatState = "off"
                    elif sonosRepeat == True:
                        playerState._RepeatState = "context"

                # trace.
                _logsi.LogObject(
                    SILevel.Verbose,
                    "'%s': Current Spotify player PlayState (built from Sonos device current state)"
                    % self.name,
                    playerState,
                    excludeNonPublic=True,
                )

            # trace.
            _logsi.LogObject(
                SILevel.Verbose,
                "'%s': Current Spotify Connect device instance" % self.name,
                spotifyConnectDevice,
                excludeNonPublic=False,
            )
            _logsi.LogObject(
                SILevel.Verbose,
                "'%s': Current Sonos device instance" % self.name,
                sonosDevice,
                excludeNonPublic=False,
            )

            # return to caller.
            return playerState, spotifyConnectDevice, sonosDevice

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    def _UpdateHAFromPlayerPlayState(self, playerPlayState: PlayerPlayState) -> None:
        """
        Updates all media_player attributes that have to do with now playing information.
        """
        try:
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogObject(
                SILevel.Verbose,
                "'%s': Updating HA state from Spotify PlayerPlayState object"
                % self.name,
                playerPlayState,
                excludeNonPublic=True,
            )

            # initialize media attributes.
            self._attr_media_album_name = None
            self._attr_media_artist = None
            self._attr_media_content_id = None
            self._attr_media_content_type = None
            self._attr_media_duration = None
            self._attr_media_image_url = None
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
            self._attr_media_title = None
            self._attr_media_track = None
            self._attr_repeat = None
            self._attr_shuffle = None
            self._attr_volume_level = None
            self._attr_is_volume_muted = None

            # initialize supported features.
            self._attr_supported_features = (
                self._attr_supported_features | MediaPlayerEntityFeature.NEXT_TRACK
            )
            self._attr_supported_features = (
                self._attr_supported_features | MediaPlayerEntityFeature.PREVIOUS_TRACK
            )
            self._attr_supported_features = (
                self._attr_supported_features | MediaPlayerEntityFeature.REPEAT_SET
            )
            self._attr_supported_features = (
                self._attr_supported_features | MediaPlayerEntityFeature.SEEK
            )
            self._attr_supported_features = (
                self._attr_supported_features | MediaPlayerEntityFeature.SHUFFLE_SET
            )

            # does player state exist?  if not, then we are done.
            if playerPlayState is None:
                _logsi.LogVerbose(
                    "'%s': Spotify PlayerPlayState object was not set; nothing to do"
                    % self.name
                )
                return

            # if player is not OFF, then update media player state.
            if self._attr_state is not MediaPlayerState.OFF:
                if self._isInCommandEvent:
                    pass
                elif playerPlayState.IsPlaying == True:
                    self._attr_state = MediaPlayerState.PLAYING
                elif playerPlayState.IsPlaying == False:
                    self._attr_state = MediaPlayerState.PAUSED
                else:
                    self._attr_state = MediaPlayerState.IDLE
                _logsi.LogVerbose(
                    "'%s': MediaPlayerState set to '%s'" % (self.name, self._attr_state)
                )

            self._attr_is_volume_muted = playerPlayState.IsMuted
            self._attr_shuffle = playerPlayState.ShuffleState

            # update item-related attributes (e.g. track? episode? etc)?
            if playerPlayState.Item is not None:
                item = playerPlayState.Item
                episode: Episode = playerPlayState.Item

                self._attr_media_content_id = item.Uri
                self._attr_media_content_type = item.Type
                self._attr_media_duration = item.DurationMS / 1000
                self._attr_media_title = item.Name

                # update media album name attribute.
                if item.Type == MediaType.EPISODE.value:
                    self._attr_media_album_name = episode.Show.Name
                else:
                    self._attr_media_album_name = item.Album.Name

                # update media artist attribute.
                if item.Type == MediaType.EPISODE.value:
                    self._attr_media_artist = episode.Show.Publisher
                else:
                    self._attr_media_artist = ", ".join(
                        artist.Name for artist in item.Artists
                    )

                # update media content type attribute.
                if item.Type == MediaType.EPISODE.value:
                    self._attr_media_content_type = MediaType.PODCAST
                else:
                    self._attr_media_content_type = MediaType.MUSIC

                # update media image url attribute.
                # for episodes, use the episode image if present; otherwise use the show image if present.
                # for everything else, use the album image if present.
                if item.Type == MediaType.EPISODE.value:
                    if episode.ImageUrl is not None:
                        self._attr_media_image_url = episode.ImageUrl
                    if episode.Show.ImageUrl is not None:
                        self._attr_media_image_url = episode.Show.ImageUrl
                elif item.Album.ImageUrl is not None:
                    self._attr_media_image_url = item.Album.ImageUrl

                # update media track attribute (will not exist for episodes).
                if item.Type == MediaType.TRACK.value:
                    self._attr_media_track = item.TrackNumber

            # update device-related attributes.
            if playerPlayState.Device is not None:
                device = playerPlayState.Device
                self._attr_volume_level = float(device.VolumePercent / 100)

                if self._attr_source is None:
                    # if a source is not set, then use current source (if source is active).
                    if self._attr_state in [
                        MediaPlayerState.PLAYING,
                        MediaPlayerState.PAUSED,
                        MediaPlayerState.IDLE,
                        MediaPlayerState.BUFFERING,
                    ]:
                        _logsi.LogVerbose(
                            "'%s': Source value is not set; using Spotify Web API player name ('%s')"
                            % (self.name, playerPlayState.Device.Name)
                        )
                        self._attr_source = playerPlayState.Device.Name
                        self.data.spotifyClient.DefaultDeviceId = self._attr_source

                elif (self._attr_source != playerPlayState.Device.Name) and (
                    playerPlayState.Device.Name is not None
                ):
                    # if a source is set, but does not match the currently playing source, then
                    # force it to be the currently playing source.
                    # this seems to happen a lot for Sonos devices!
                    _logsi.LogVerbose(
                        "'%s': Source value ('%s') does not match Spotify Web API player name ('%s'); using Spotify Web API player name"
                        % (self.name, self._attr_source, playerPlayState.Device.Name)
                    )
                    self._attr_source = playerPlayState.Device.Name
                    self.data.spotifyClient.DefaultDeviceId = self._attr_source

                    # check to see if currently active device is in the Spotify Connect device list cache.
                    # if it's not in the cache, then we need to refresh the Spotify Connect device list cache
                    scDevices: SpotifyConnectDevices = (
                        self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
                    )
                    if not scDevices.ContainsDeviceName(playerPlayState.Device.Name):
                        _logsi.LogVerbose(
                            "'%s': Spotify PlayerPlayState device name '%s' was not found in the Spotify Connect device list cache; refreshing cache"
                            % (self.name, self._attr_source)
                        )
                        # it's risky refreshing the Spotify Connect device list here, as this method fires every second.
                        self.data.spotifyClient.GetSpotifyConnectDevices(refresh=True)

            # update seek-related attributes.
            if playerPlayState.ProgressMS is not None:
                self._attr_media_position = playerPlayState.ProgressMS / 1000
                self._attr_media_position_updated_at = utcnow()

            # update repeat related attributes.
            if playerPlayState.RepeatState is not None:
                if playerPlayState.RepeatState == "context":
                    self._attr_repeat = RepeatMode.ALL.value
                elif playerPlayState.RepeatState == "track":
                    self._attr_repeat = RepeatMode.ONE.value
                else:
                    self._attr_repeat = RepeatMode.OFF.value

            # update supported features based upon available actions.
            # note if the selected action is true, then it is not allowed (disallowed).
            if playerPlayState.Actions is not None:
                # 2024/07/24
                # commented some of the following, as some media players (e.g. mini-media player) do not
                # display / hide the corresponding transport button correctly!

                # if playerPlayState.Actions.SkippingNext:
                #     self._attr_supported_features = self._attr_supported_features & (~MediaPlayerEntityFeature.NEXT_TRACK)
                #     _logsi.LogVerbose("'%s': MediaPlayerState NEXT_TRACK is not allowed" % self.name)

                # if playerPlayState.Actions.SkippingPrev:
                #     self._attr_supported_features = self._attr_supported_features & (~MediaPlayerEntityFeature.PREVIOUS_TRACK)
                #     _logsi.LogVerbose("'%s': MediaPlayerState PREVIOUS_TRACK is not allowed" % self.name)

                if playerPlayState.Actions.TogglingRepeatTrack:
                    self._attr_supported_features = self._attr_supported_features & (
                        ~MediaPlayerEntityFeature.REPEAT_SET
                    )
                    _logsi.LogVerbose(
                        "'%s': MediaPlayerState REPEAT_SET is not allowed" % self.name
                    )

                # if playerPlayState.Actions.Seeking:
                #     self._attr_supported_features = self._attr_supported_features & (~MediaPlayerEntityFeature.SEEK)
                #     _logsi.LogVerbose("'%s': MediaPlayerState SEEK is not allowed" % self.name)

                if playerPlayState.Actions.TogglingShuffle:
                    self._attr_supported_features = self._attr_supported_features & (
                        ~MediaPlayerEntityFeature.SHUFFLE_SET
                    )
                    _logsi.LogVerbose(
                        "'%s': MediaPlayerState SHUFFLE_SET is not allowed" % self.name
                    )
                pass

        except Exception as ex:
            _logsi.LogException(None, ex)
            raise HomeAssistantError(str(ex)) from ex

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    def _CallScriptPower(self, scriptEntityId: str, title: str) -> None:
        """
        Calls the supplied script for a power on / off event.

        Args:
            scriptEntityId (str):
                Name of the script to execute.
            title (str):
                Title to use in trace logs and error messages.

        Verifies that the script is installed, and the media player entity id
        is valid and available (not disabled).
        """
        entity_registry: EntityRegistry = None

        try:
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose(
                "'%s': MediaPlayer is verifying Spotify '%s' integration script configuration"
                % (self.name, title)
            )

            # if Spotify integration is NOT installed, then log the services that ARE installed in case we need it.
            # TODO uncomment as needed, as this logs a LOT of information!
            # serviceAll = self.hass.services.async_services()
            # _logsi.LogDictionary(SILevel.Verbose, "'%s': MediaPlayer ALL services list" % self.name, serviceAll, prettyPrint=True)

            # if no script name was selected in config options then there is nothing else to do.
            if scriptEntityId is None:
                _logsi.LogVerbose(
                    "'%s': MediaPlayer '%s' script is not configured - nothing to do"
                    % (self.name, title)
                )
                return

            # is the specified script entity id in the hass entity registry?
            # it will NOT be in the entity registry if it's deleted.
            # it WILL be in the entity registry if it is disabled, with disabled property = True.
            entity_registry = er.async_get(self.hass)
            registry_entry: RegistryEntry = entity_registry.async_get(scriptEntityId)
            _logsi.LogObject(
                SILevel.Verbose,
                "'%s': MediaPlayer RegistryEntry for entity_id: '%s'"
                % (self.name, scriptEntityId),
                registry_entry,
            )

            # raise exceptions if Spotify Entity is not configured or is disabled.
            if registry_entry is None:
                raise HomeAssistantError(
                    "'%s': MediaPlayer '%s' script entity '%s' does not exist (recently deleted or renamed maybe?)"
                    % (self.name, title, scriptEntityId)
                )
            if registry_entry.disabled:
                raise HomeAssistantError(
                    "'%s': MediaPlayer '%s' script entity '%s' is currently disabled; re-enable the script to continue"
                    % (self.name, title, scriptEntityId)
                )

            # call the script syncronously, so we wait until it returns.
            _logsi.LogVerbose(
                "'%s': MediaPlayer is calling the '%s' script '%s' (entityid='%s', uniqueid='%s')"
                % (
                    self.name,
                    title,
                    registry_entry.name or registry_entry.original_name,
                    registry_entry.entity_id,
                    registry_entry.unique_id,
                )
            )
            self.hass.services.call(
                DOMAIN_SCRIPT,
                registry_entry.unique_id,  # use the uniqueid
                {},  # no parameters
                blocking=True,  # wait for service to complete before returning
                return_response=False,  # does not return service response data.
            )

        finally:
            # free resources.
            entity_registry = None

            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    # -----------------------------------------------------------------------------------
    # Custom Services
    # -----------------------------------------------------------------------------------

    def _GetUserProfilePartialDictionary(self, userProfile: UserProfile) -> dict:
        """
        Returns a dictionary of a partial UserProfile object that can be returned with
        selected service results.  This allows the caller to know exactly what Spotify
        user made the given request.
        """
        # return the user profile that retrieved the result, as well as the result.
        return {
            "country": userProfile.Country,
            "display_name": userProfile.DisplayName,
            "email": userProfile.EMail,
            "id": userProfile.Id,
            "product": userProfile.Product,
            "type": userProfile.Type,
            "uri": userProfile.Uri,
        }

    def _GetDefaultDeviceOption(
        self,
        deviceId: str = None,
    ) -> str:
        """
        Returns the Spotify defult device option if an "*" was specified for the `deviceId` argument.

        Args:
            deviceId (str):
                The Spotify Player device id to verify.
        Returns:
            One of the following values:
            - if the `deviceId` argument is not an "*", then the argument value is returned as-is.
            - otherwise, if a Spotify default device option was configured then it's deviceId value is returned.
            - otherwise, None is returned to indicate that the active player will be used.
        """
        if deviceId == "*":
            if self.data.OptionDeviceDefault is not None:
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )
                deviceName = PlayerDevice.GetNameFromSelectItem(
                    self.data.OptionDeviceDefault
                )
                _logsi.LogVerbose(
                    "'%s': Spotify default device will be used: '%s' (%s)"
                    % (self.name, deviceName, deviceId)
                )
            else:
                _logsi.LogVerbose(
                    "'%s': Spotify default device was not configured; will use currently active Spotify Player device"
                    % (self.name)
                )
                deviceId = None

        return deviceId

    def service_spotify_add_player_queue_items(
        self,
        uris: str,
        deviceId: str = None,
        verifyDeviceId: bool = True,
        delay: float = 0.15,
    ) -> None:
        """
        Add one or more items to the end of the user's current playback queue.

        Args:
            uris (str):
                A list of Spotify track or episode URIs to add to the queue; can be track or episode URIs.
                All URIs must be of the same type - you cannot mix and match tracks and episodes!
                Example: [`spotify:track:6zd8T1PBe9JFHmuVnurdRp` ,`spotify:track:1kWUud3vY5ij5r62zxpTRy`].
                It can also be specified as a comma-delimited string.
                Example: `spotify:track:6zd8T1PBe9JFHmuVnurdRp,spotify:track:1kWUud3vY5ij5r62zxpTRy`.
                An unlimited number of items can be added in one request, but the more items the longer it
                will take.
            deviceId (str):
                The id or name of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
                Example: `Web Player (Chrome)`
            verifyDeviceId (bool):
                True to verify a device id is active; otherwise, false to assume that a
                device id is already active.
                Default is True.
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the add request.  This delay will give the
                Spotify web api time to process the queue change before another command is issued.
                Default is 0.15; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_add_player_queue_items"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("uris", uris)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("verifyDeviceId", verifyDeviceId)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Add Player Queue Items Service",
                apiMethodParms,
            )

            # follow artist(s).
            _logsi.LogVerbose("Adding items(s) to Spotify Player Queue")
            self.data.spotifyClient.AddPlayerQueueItems(
                uris, deviceId, verifyDeviceId, delay
            )

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_check_album_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Check if one or more albums (or the currently playing album) exists in the current
        user's 'Your Library' favorites.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the albums.
                Maximum: 50 IDs.
                Example: `6vc9OTcyd3hyzabCmsdnwE,382ObEPsp2rxGrnsizN5TX`
                If null, the currently playing track album uri id value is used.

        Returns:
            A dictionary of the ids, along with a boolean status for each that indicates
            if the album is saved (True) in the users 'Your Library' or not (False).
        """
        apiMethodName: str = "service_spotify_check_album_favorites"
        apiMethodParms: SIMethodParmListContext = None
        result: dict = {}

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Check Album Favorites Service", apiMethodParms
            )

            # check Spotify album favorites.
            _logsi.LogVerbose("Check Spotify Album Favorites")
            result = self.data.spotifyClient.CheckAlbumFavorites(ids)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_check_artists_following(
        self,
        ids: str = None,
    ) -> None:
        """
        Check if one or more artists (or the currently playing artist) is followed in the current
        user's 'Your Library' favorites.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the artists.
                Maximum: 50 IDs.
                Example: `2CIMQHirSU0MQqyYHq0eOx,1IQ2e1buppatiN1bxUVkrk`
                If null, the currently playing track artist uri id value is used.

        Returns:
            A dictionary of the IDs, along with a boolean status for each that indicates
            if the user follows the ID (True) or not (False).
        """
        apiMethodName: str = "service_spotify_check_artists_following"
        apiMethodParms: SIMethodParmListContext = None
        result: dict = {}

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Follow Artists Service", apiMethodParms
            )

            # check Spotify artists following.
            _logsi.LogVerbose("Check Spotify Artists Following")
            result = self.data.spotifyClient.CheckArtistsFollowing(ids)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_check_audiobook_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Check if one or more audiobooks (or the currently playing audiobook) exists in the current
        user's 'Your Library' favorites.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the audiobooks.
                Maximum: 50 IDs.
                Example: `3PFyizE2tGCSRLusl2Qizf,7iHfbu1YPACw6oZPAFJtqe`
                If null, the currently playing audiobook uri id value is used.

        Returns:
            A dictionary of the ids, along with a boolean status for each that indicates
            if the audiobook is saved (True) in the users 'Your Library' or not (False).
        """
        apiMethodName: str = "service_spotify_check_audiobook_favorites"
        apiMethodParms: SIMethodParmListContext = None
        result: dict = {}

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Check Audiobook Favorites Service",
                apiMethodParms,
            )

            # check Spotify audiobook favorites.
            _logsi.LogVerbose("Check Spotify Audiobook Favorites")
            result = self.data.spotifyClient.CheckAudiobookFavorites(ids)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_check_episode_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Check if one or more episodes (or the currently playing episode) exists in the current
        user's 'Your Library' favorites.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the episodes.
                Maximum: 50 IDs.
                Example: `3F97boSWlXi8OzuhWClZHQ,1hPX5WJY6ja6yopgVPBqm4`
                If null, the currently playing episode uri id value is used.

        Returns:
            A dictionary of the ids, along with a boolean status for each that indicates
            if the episode is saved (True) in the users 'Your Library' or not (False).
        """
        apiMethodName: str = "service_spotify_check_episode_favorites"
        apiMethodParms: SIMethodParmListContext = None
        result: dict = {}

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Check Episode Favorites Service",
                apiMethodParms,
            )

            # check Spotify episode favorites.
            _logsi.LogVerbose("Check Spotify Episode Favorites")
            result = self.data.spotifyClient.CheckEpisodeFavorites(ids)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_check_playlist_followers(
        self,
        playlistId: str = None,
        userIds: str = None,
    ) -> None:
        """
        Check to see if the current user is following a specified playlist.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                Example: `3cEYpjA9oz9GiPac4AsH4n`
            userIds (str):
                A comma-separated list of Spotify User ID's to check.
                Maximum: 5 ID's.
                Example: `1kWUud3vY5ij5r62zxpTRy,2takcwOaAZWiXQijPHIx7B`
                Deprecated - A single item list containing current user's Spotify Username; Maximum of 1 id.

        Returns:
            Array of boolean, containing a single boolean status that indicates
            if the user follows the playlist (True) or not (False).
        """
        apiMethodName: str = "service_spotify_check_playlist_followers"
        apiMethodParms: SIMethodParmListContext = None
        result: dict = {}

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            apiMethodParms.AppendKeyValue("userIds", userIds)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Check Playlist Followers Service",
                apiMethodParms,
            )

            # validations.
            if userIds is None:
                userIds = self.data.spotifyClient.UserProfile.Id

            # check Spotify playlist followers.
            _logsi.LogVerbose("Check Spotify Playlist Followers")
            result = self.data.spotifyClient.CheckPlaylistFollowers(playlistId, userIds)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_check_show_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Check if one or more shows (or the currently playing show) exists in the current
        user's 'Your Library' favorites.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the shows.
                Maximum: 50 IDs.
                Example: `6kAsbP8pxwaU2kPibKTuHE,4rOoJ6Egrf8K2IrywzwOMk`
                If null, the currently playing show uri id value is used.

        Returns:
            A dictionary of the ids, along with a boolean status for each that indicates
            if the show is saved (True) in the users 'Your Library' or not (False).
        """
        apiMethodName: str = "service_spotify_check_show_favorites"
        apiMethodParms: SIMethodParmListContext = None
        result: dict = {}

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Check Show Favorites Service", apiMethodParms
            )

            # check Spotify show favorites.
            _logsi.LogVerbose("Check Spotify Show Favorites")
            result = self.data.spotifyClient.CheckShowFavorites(ids)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_check_track_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Check if one or more tracks (or the currently playing track) exists in the current
        user's 'Your Library' favorites.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the tracks.
                Maximum: 50 IDs.
                Example: `1kWUud3vY5ij5r62zxpTRy,4eoYKv2kDwJS7gRGh5q6SK`
                If null, the currently playing context uri id value is used.

        Returns:
            A dictionary of the ids, along with a boolean status for each that indicates
            if the track is saved (True) in the users 'Your Library' or not (False).
        """
        apiMethodName: str = "service_spotify_check_track_favorites"
        apiMethodParms: SIMethodParmListContext = None
        result: dict = {}

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Check Track Favorites Service", apiMethodParms
            )

            # check Spotify track favorites.
            _logsi.LogVerbose("Check Spotify Track Favorites")
            result = self.data.spotifyClient.CheckTrackFavorites(ids)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_check_users_following(
        self,
        ids: str,
    ) -> None:
        """
        Check to see if the current user is following one or more users.

        Args:
            ids (str):
                A comma-separated list of Spotify user ID's to check.
                Maximum: 50 ID's.
                Example: `smedjan`

        Returns:
            A dictionary of the IDs, along with a boolean status for each that indicates
            if the user follows the ID (True) or not (False).
        """
        apiMethodName: str = "service_spotify_check_users_following"
        apiMethodParms: SIMethodParmListContext = None
        result: dict = {}

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Check Users Following Service", apiMethodParms
            )

            # check Spotify users following.
            _logsi.LogVerbose("Check Spotify Users Following")
            result = self.data.spotifyClient.CheckUsersFollowing(ids)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_follow_artists(
        self,
        ids: str = None,
    ) -> None:
        """
        Add the current user as a follower of one or more artists.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the artists.
                Maximum: 50 IDs.
                Example: `2CIMQHirSU0MQqyYHq0eOx,1IQ2e1buppatiN1bxUVkrk`
                If null, the currently playing track artist uri id value is used.
        """
        apiMethodName: str = "service_spotify_follow_artists"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Follow Artists Service", apiMethodParms
            )

            # follow artist(s).
            _logsi.LogVerbose("Adding items(s) to Spotify Artist Favorites")
            self.data.spotifyClient.FollowArtists(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_follow_playlist(
        self,
        playlistId: str = None,
        public: bool = True,
    ) -> None:
        """
        Add the current user as a follower of a playlist.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                Example: `3cEYpjA9oz9GiPac4AsH4n`
                If null, the currently playing playlist uri id value is used.
            public (bool):
                If true the playlist will be included in user's public playlists, if false it
                will remain private.
                Default = True.
        """
        apiMethodName: str = "service_spotify_follow_playlist"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            apiMethodParms.AppendKeyValue("public", public)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Follow Playlist Service", apiMethodParms
            )

            # follow playlist.
            _logsi.LogVerbose("Adding items to Spotify Playlist Favorites")
            self.data.spotifyClient.FollowPlaylist(playlistId, public)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_follow_users(
        self,
        ids: str = None,
    ) -> None:
        """
        Add the current user as a follower of one or more users.

        Args:
            ids (str):
                A comma-separated list of the Spotify user IDs.
                A maximum of 50 IDs can be sent in one request.
                Example: `smedjan`
        """
        apiMethodName: str = "service_spotify_follow_users"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Follow Artists Service", apiMethodParms
            )

            # follow user(s).
            _logsi.LogVerbose("Adding items(s) to Spotify User Favorites")
            self.data.spotifyClient.FollowUsers(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_album(
        self,
        albumId: str = None,
        market: str = None,
    ) -> dict:
        """
        Get Spotify catalog information for a single album.

        Args:
            albumId (str):
                The Spotify ID of the album.
                Example: `6vc9OTcyd3hyzabCmsdnwE`
                If omitted, the currently playing album uri id value is used.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `Album` object that contains the album details.
        """
        apiMethodName: str = "service_spotify_get_album"
        apiMethodParms: SIMethodParmListContext = None
        result: Album = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("albumId", albumId)
            apiMethodParms.AppendKeyValue("market", market)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Album Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetAlbum(albumId, market)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_album_favorites(
        self,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get a list of the albums saved in the current Spotify user's 'Your Library'.

        Args:
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Example: `ES`
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `AlbumPageSaved` object that contains album information.
        """
        apiMethodName: str = "service_spotify_get_album_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Album Favorites Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: AlbumPageSaved = self.data.spotifyClient.GetAlbumFavorites(
                limit, offset, market, limitTotal, sortResult
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_album_new_releases(
        self,
        limit: int = 20,
        offset: int = 0,
        country: str = None,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get a list of new album releases featured in Spotify.

        Args:
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).
            country (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Example: `ES`
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `AlbumPageSimplified` object that contains album information.
        """
        apiMethodName: str = "service_spotify_get_album_new_releases"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("country", country)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Album New Releases Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: AlbumPageSimplified = self.data.spotifyClient.GetAlbumNewReleases(
                limit, offset, country, limitTotal, sortResult
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_album_tracks(
        self,
        albumId: str = None,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        limitTotal: int = None,
    ) -> dict:
        """
        Get Spotify catalog information about an album's tracks.

        Args:
            albumId (str):
                The Spotify ID of the album.
                Example: `6vc9OTcyd3hyzabCmsdnwE`
                If null, the currently playing album uri id value is used; a Spotify Free or Premium account
                is required to correctly read the currently playing context.
            limit (int):
                The maximum number of items to return in a page of items when manual paging is used.
                Default: 20, Range: 1 to 50.
                See the `limitTotal` argument for automatic paging option.
            offset (int):
                The index of the first item to return; use with limit to get the next set of items.
                Default: 0 (the first item).
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `TrackPageSimplified` object that contains album track information.
        """
        apiMethodName: str = "service_spotify_get_album_tracks"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("albumId", albumId)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Album Tracks Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: TrackPageSimplified = self.data.spotifyClient.GetAlbumTracks(
                albumId, limit, offset, market, limitTotal
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_artist(
        self,
        artistId: str = None,
    ) -> dict:
        """
        Get Spotify catalog information for a single artist.

        Args:
            artistId (str):
                The Spotify ID of the artist.
                If null, the currently playing artist uri id value is used.
                Example: `6APm8EjxOHSYM5B4i3vT3q`

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `Artist` object that contains the artist details.
        """
        apiMethodName: str = "service_spotify_get_artist"
        apiMethodParms: SIMethodParmListContext = None
        result: Artist = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("artistId", artistId)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Artist Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetArtist(artistId)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_artist_albums(
        self,
        artistId: str,
        include_groups: str = "album",
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get Spotify catalog information about an artist's albums.

        Args:
            artistId (str):
                The Spotify ID of the artist.
                If null, the currently playing artist uri id value is used.
                Example: `6APm8EjxOHSYM5B4i3vT3q`
            include_groups (str):
                A comma-separated list of keywords that will be used to filter the response.
                If not supplied, all album types will be returned.
                Valid values are: `album`, `single`, `appears_on`, `compilation`
                Example: `single,appears_on`
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return; use with limit to get the next set of items.
                Default: 0 (the first item).
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that is
                available in that market will be returned.
                If a valid user access token is specified in the request header, the country associated with
                the user account will take priority over this parameter.
                Example: `ES`
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `AlbumPageSimplified` object that contains artist album information.
        """
        apiMethodName: str = "service_spotify_get_artist_albums"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("artistId", artistId)
            apiMethodParms.AppendKeyValue("include_groups", include_groups)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Artist Albums Service", apiMethodParms
            )

            # validations.
            if include_groups is None:
                include_groups = "album"

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: AlbumPageSimplified = self.data.spotifyClient.GetArtistAlbums(
                artistId, include_groups, limit, offset, market, limitTotal, sortResult
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_artist_info(
        self,
        artistId: str,
    ) -> dict:
        """
        Get artist about information from the Spotify Artist Biography page for the
        specified Spotify artist ID.

        Args:
            artistId (str):
                The Spotify ID of the artist.
                Example: `6APm8EjxOHSYM5B4i3vT3q`
                If null, the currently playing artist uri id value is used; a Spotify Free or Premium account
                is required to correctly read the currently playing context.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `ArtistInfo` object that contains artist album information.
        """
        apiMethodName: str = "service_spotify_get_artist_info"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("artistId", artistId)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Artist Info Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: ArtistInfo = self.data.spotifyClient.GetArtistInfo(artistId)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_artist_related_artists(
        self,
        artistId: str,
        sortResult: bool = True,
    ) -> dict:
        """
        Get Spotify catalog information about artists similar to a given artist.
        Similarity is based on analysis of the Spotify community's listening history.

        Args:
            artistId (str):
                The Spotify ID of the artist.
                If null, the currently playing artist uri id value is used.
                Example: `6APm8EjxOHSYM5B4i3vT3q`
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A list of `Artist` objects that contain artist information.
        """
        apiMethodName: str = "service_spotify_get_artist_related_artists"
        apiMethodParms: SIMethodParmListContext = None
        result: list = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("artistId", artistId)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Artist Related Artists Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: list = self.data.spotifyClient.GetArtistRelatedArtists(
                artistId, sortResult
            )

            # build dictionary result from array.
            resultArray: list = []
            item: Artist
            for item in result:
                resultArray.append(item.ToDictionary())

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": resultArray,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_artist_top_tracks(
        self,
        artistId: str,
        market: str = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get Spotify catalog information about an artist's top tracks by country.

        Args:
            artistId (str):
                The Spotify ID of the artist.
                Example: `6APm8EjxOHSYM5B4i3vT3q`
                If null, the currently playing artist uri id value is used; a Spotify Free or Premium account
                is required to correctly read the currently playing context.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A list of `Track` objects of matching results.
        """
        apiMethodName: str = "service_spotify_get_artist_top_tracks"
        apiMethodParms: SIMethodParmListContext = None
        result: list = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("artistId", artistId)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Artist Top Tracks Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: list = self.data.spotifyClient.GetArtistTopTracks(
                artistId, market, sortResult
            )

            # build dictionary result from array.
            resultArray: list = []
            item: Track
            for item in result:
                resultArray.append(item.ToDictionary())

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": resultArray,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_artists_followed(
        self,
        after: str = None,
        limit: int = 20,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get the current user's followed artists.

        Args:
            after (str):
                The last artist ID retrieved from the previous request, or null for
                the first request.
                Example: `0I2XqVXqHScXjHhk6AYYRe`
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `ArtistPage` object that contains artist information.
        """
        apiMethodName: str = "service_spotify_get_artists_followed"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("after", after)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Artists Followed Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: ArtistPage = self.data.spotifyClient.GetArtistsFollowed(
                after, limit, limitTotal, sortResult
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_audiobook(
        self,
        audiobookId: str = None,
        market: str = None,
    ) -> dict:
        """
        Get Spotify catalog information for a single audiobook.

        Audiobooks are only available within the US, UK, Canada, Ireland, New Zealand and Australia markets.

        Args:
            audiobookId (str):
                The Spotify ID for the audiobook.
                Example: `74aydHJKgYz3AIq3jjBSv1`
                If null, the currently playing audiobook uri id value is used; a Spotify Free or Premium account
                is required to correctly read the currently playing context.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `Audiobook` object that contains audiobook details.
        """
        apiMethodName: str = "service_spotify_get_audiobook"
        apiMethodParms: SIMethodParmListContext = None
        result: Audiobook = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("audiobookId", audiobookId)
            apiMethodParms.AppendKeyValue("market", market)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Audiobook Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: Audiobook = self.data.spotifyClient.GetAudiobook(
                audiobookId, market
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_audiobook_chapters(
        self,
        audiobookId: str = None,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        limitTotal: int = None,
    ) -> dict:
        """
        Get Spotify catalog information about an audiobook's chapters.

        Args:
            audiobookId (str):
                The Spotify ID for the audiobook.
                Example: `74aydHJKgYz3AIq3jjBSv1`
                If null, the currently playing audiobook uri id value is used; a Spotify Free or Premium account
                is required to correctly read the currently playing context.
            limit (int):
                The maximum number of items to return in a page of items when manual paging is used.
                Default: 20, Range: 1 to 50.
                See the `limitTotal` argument for automatic paging option.
            offset (int):
                The index of the first item to return; use with limit to get the next set of items.
                Default: 0 (the first item).
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `ChapterPageSimplified` object that contains simplified chapter information for the audiobook Id.
        """
        apiMethodName: str = "service_spotify_get_audiobook_chapters"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("audiobookId", audiobookId)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Audiobook Chapters Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: AudiobookPageSimplified = (
                self.data.spotifyClient.GetAudiobookChapters(
                    audiobookId, limit, offset, market, limitTotal
                )
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_audiobook_favorites(
        self,
        limit: int = 20,
        offset: int = 0,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get a list of the audiobooks saved in the current Spotify user's 'Your Library'.

        Args:
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `AudiobookPageSimplified` object that contains saved audiobook information.
        """
        apiMethodName: str = "service_spotify_get_audiobook_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Audiobook Favorites Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: AudiobookPageSimplified = (
                self.data.spotifyClient.GetAudiobookFavorites(
                    limit, offset, limitTotal, sortResult
                )
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_browse_categorys_list(
        self,
        country: str = None,
        locale: str = None,
        refresh: str = False,
    ) -> dict:
        """
        Get a sorted list of ALL categories used to tag items in Spotify.

        Args:
            country (str):
                A country: an ISO 3166-1 alpha-2 country code.
                Provide this parameter if you want the list of returned items to be relevant to a
                particular country. If omitted, the returned items will be relevant to all countries.
                Example: `SE`
            locale (str):
                The desired language, consisting of a lowercase ISO 639-1 language code and an uppercase
                ISO 3166-1 alpha-2 country code, joined by an underscore.
                For example: `es_MX`, meaning "Spanish (Mexico)".
                Provide this parameter if you want the results returned in a particular language (where available).
                Note: if locale is not supplied, or if the specified language is not available, all strings will
                be returned in the Spotify default language (American English). The locale parameter, combined with
                the country parameter, may give odd results if not carefully matched. For example country=`SE` and
                locale=`de_DE` will return a list of categories relevant to Sweden but as German language strings.
                Example: `sv_SE`
            refresh (bool):
                True to return real-time information from the spotify web api and
                update the cache; otherwise, False to just return the cached value.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `CategoryPage` object that contains the list category details.
        """
        apiMethodName: str = "service_spotify_get_browse_categorys_list"
        apiMethodParms: SIMethodParmListContext = None
        result: CategoryPage = CategoryPage()

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("country", country)
            apiMethodParms.AppendKeyValue("locale", locale)
            apiMethodParms.AppendKeyValue("refresh", refresh)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Browse Categorys List Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            resultArray: list[Category] = (
                self.data.spotifyClient.GetBrowseCategorysList(country, locale, refresh)
            )

            # build a CategoryPage object so we can convert to a dictionary.
            category: Category
            for category in resultArray:
                result.Items.append(category)

            # set CategoryPage object summary.
            result.Total = len(resultArray)
            result.Limit = result.Total
            result.DateLastRefreshed = datetime.utcnow().timestamp()

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_category_playlists(
        self,
        categoryId: str = None,
        limit: int = 20,
        offset: int = 0,
        country: str = None,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get a list of Spotify playlists tagged with a particular category.

        Args:
            categoryId (str):
                The Spotify category ID for the category.
                Example: `dinner`
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The page index offset of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).
            country (str):
                A country: an ISO 3166-1 alpha-2 country code.
                Provide this parameter if you want the list of returned items to be relevant to a
                particular country. If omitted, the returned items will be relevant to all countries.
                Example: `SE`
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `PlaylistPageSimplified` object that contains playlist information.
            - message: string that describes what was returned (e.g. 'Popular Playlists').
        """
        apiMethodName: str = "service_spotify_get_category_playlists"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("categoryId", categoryId)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("country", country)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Category Playlists Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            # have to treat this one a little bit differently due to return of a Tuple[] value.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            response: Tuple[PlaylistPageSimplified, str]
            response = self.data.spotifyClient.GetCategoryPlaylists(
                categoryId, limit, offset, country, limitTotal, sortResult
            )
            _logsi.LogObject(SILevel.Verbose, "response Tuple object", response)

            result: PlaylistPageSimplified = response[0]
            message: str = response[1]

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
                "message": message,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_chapter(
        self,
        chapterId: str = None,
        market: str = None,
    ) -> dict:
        """
        Get Spotify catalog information for a single audiobook chapter identified by its unique Spotify ID.

        Args:
            chapterId (str):
                The Spotify ID of the chapter.
                Example: `3V0yw9UDrYAfkhAvTrvt9Y`
                If null, the currently playing chapter uri id value is used; a Spotify Free or Premium account
                is required to correctly read the currently playing context.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `Chapter` object that contain the chapter details.
        """
        apiMethodName: str = "service_spotify_get_chapter"
        apiMethodParms: SIMethodParmListContext = None
        result: Chapter = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("chapterId", chapterId)
            apiMethodParms.AppendKeyValue("market", market)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Chapter Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetChapter(chapterId, market)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_episode(
        self,
        episodeId: str = None,
        market: str = None,
    ) -> dict:
        """
        Get Spotify catalog information for a single episode identified by its unique Spotify ID.

        Args:
            episodeId (str):
                The Spotify ID of the episode.
                Example: `512ojhOuo1ktJprKbVcKyQ`
                If null, the currently playing episode uri id value is used; a Spotify Free or Premium account
                is required to correctly read the currently playing context.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `Episode` object that contain the episode details.
        """
        apiMethodName: str = "service_spotify_get_episode"
        apiMethodParms: SIMethodParmListContext = None
        result: Episode = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("episodeId", episodeId)
            apiMethodParms.AppendKeyValue("market", market)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Episode Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetEpisode(episodeId, market)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_episode_favorites(
        self,
        limit: int = 20,
        offset: int = 0,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get a list of the episodes saved in the current Spotify user's 'Your Library'.

        Args:
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `EpisodePageSaved` object that contains saved audiobook information.
        """
        apiMethodName: str = "service_spotify_get_episode_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Episode Favorites Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: EpisodePageSaved = self.data.spotifyClient.GetEpisodeFavorites(
                limit, offset, limitTotal, sortResult
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_featured_playlists(
        self,
        limit: int = 20,
        offset: int = 0,
        country: str = None,
        locale: str = None,
        timestamp: str = None,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get a list of Spotify featured playlists (shown, for example, on a Spotify player's 'Browse' tab).

        Args:
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The page index offset of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).
            country (str):
                A country: an ISO 3166-1 alpha-2 country code.
                Provide this parameter if you want the list of returned items to be relevant to a
                particular country. If omitted, the returned items will be relevant to all countries.
                Example: `SE`
            locale (str):
                The desired language, consisting of a lowercase ISO 639-1 language code and an uppercase
                ISO 3166-1 alpha-2 country code, joined by an underscore.
                For example: `es_MX`, meaning "Spanish (Mexico)".
                Provide this parameter if you want the results returned in a particular language (where available).
                Note: if locale is not supplied, or if the specified language is not available, all strings will
                be returned in the Spotify default language (American English). The locale parameter, combined with
                the country parameter, may give odd results if not carefully matched. For example country=`SE` and
                locale=`de_DE` will return a list of categories relevant to Sweden but as German language strings.
                Example: `sv_SE`
            timestamp (str):
                A timestamp in ISO 8601 format: yyyy-MM-ddTHH:mm:ss.
                Use this parameter to specify the user's local time to get results tailored for that specific date
                and time in the day. If not provided, the response defaults to the current UTC time.
                Example: `2023-10-23T09:00:00` for a user whose local time is 9AM.
                If there were no featured playlists (or there is no data) at the specified time, the response will
                revert to the current UTC time.
                Example: `2023-10-23T09:00:00`
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `PlaylistPageSimplified` object that contains playlist information.
            - message: string that describes what was returned (e.g. 'Popular Playlists').
        """
        apiMethodName: str = "service_spotify_get_featured_playlists"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("country", country)
            apiMethodParms.AppendKeyValue("locale", locale)
            apiMethodParms.AppendKeyValue("timestamp", timestamp)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Featured Playlists Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            # have to treat this one a little bit differently due to return of a Tuple[] value.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            response: Tuple[PlaylistPageSimplified, str]
            response = self.data.spotifyClient.GetFeaturedPlaylists(
                limit, offset, country, locale, timestamp, limitTotal, sortResult
            )
            _logsi.LogObject(SILevel.Verbose, "response Tuple object", response)

            result: PlaylistPageSimplified = response[0]
            message: str = response[1]

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
                "message": message,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_player_devices(
        self,
        refresh: bool = True,
        sortResult: bool = True,
    ) -> dict:
        """
        Get information about a user's available Spotify Connect player devices.

        Some device models are not supported and will not be listed in the API response.

        This method requires the `user-read-playback-state` scope.

        Args:
            refresh (bool):
                True (default) to return real-time information from the spotify web api and
                update the cache; otherwise, False to just return the cached value.
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A list of `Device` objects that contain the device details, sorted by name.
        """
        apiMethodName: str = "service_spotify_get_player_devices"
        apiMethodParms: SIMethodParmListContext = None
        result: list = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("refresh", refresh)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Player Devices Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetPlayerDevices(refresh, sortResult)

            # build dictionary result from array.
            resultArray: list = []
            item: PlayerDevice
            for item in result:
                resultArray.append(item.ToDictionary())

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": resultArray,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_player_now_playing(
        self, market: str = None, additionalTypes: str = None
    ) -> dict:
        """
        Get the object currently being played on the user's Spotify account.

        This method requires the `user-read-currently-playing` scope.

        Args:
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            additionalTypes (str):
                A comma-separated list of item types that your client supports besides the default track type.
                Valid types are: `track` and `episode`.
                Specify `episode` to get podcast track information.
                Note: This parameter was introduced to allow existing clients to maintain their current behaviour
                and might be deprecated in the future. In addition to providing this parameter, make sure that your client
                properly handles cases of new types in the future by checking against the type field of each object.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `PlayerPlayState` object that contains the player now playing details.
        """
        apiMethodName: str = "service_spotify_get_player_now_playing"
        apiMethodParms: SIMethodParmListContext = None
        result: PlayerPlayState = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("additionalTypes", additionalTypes)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Player Now Playing Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetPlayerNowPlaying(
                market, additionalTypes
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_player_playback_state(
        self, market: str = None, additionalTypes: str = None
    ) -> dict:
        """
        Get information about the user's current playback state, including track or episode, progress,
        and active device.

        This method requires the `user-read-playback-state` scope.

        Args:
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            additionalTypes (str):
                A comma-separated list of item types that your client supports besides the default track type.
                Valid types are: `track` and `episode`.
                Specify `episode` to get podcast track information.
                Note: This parameter was introduced to allow existing clients to maintain their current behaviour
                and might be deprecated in the future. In addition to providing this parameter, make sure that your client
                properly handles cases of new types in the future by checking against the type field of each object.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `PlayerPlayState` object that contains the playback state details.
        """
        apiMethodName: str = "service_spotify_get_player_playback_state"
        apiMethodParms: SIMethodParmListContext = None
        result: PlayerPlayState = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("additionalTypes", additionalTypes)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Player Playback State Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetPlayerPlaybackState(
                market, additionalTypes
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_player_queue_info(self) -> dict:
        """
        Get the list of objects that make up the user's playback queue.

        This method requires the `user-read-currently-playing` and `user-read-playback-state` scope.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `PlayerQueueInfo` object that contains the player queue information.
        """
        apiMethodName: str = "service_spotify_get_player_queue_info"
        apiMethodParms: SIMethodParmListContext = None
        result: PlayerQueueInfo = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Player Queue Info Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetPlayerQueueInfo()

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_player_recent_tracks(
        self, limit: int = 20, after: int = 0, before: int = 0, limitTotal: int = None
    ) -> dict:
        """
        Get tracks from the current user's recently played tracks.
        Note: Currently doesn't support podcast episodes.

        This method requires the `user-read-recently-played` scope.

        Args:
            limit (int):
                The maximum number of items to return in a page of items.
                Default: `20`, Range: `1` to `50`.
            after (int):
                Returns all items after (but not including) this cursor position, which is
                a Unix timestamp in milliseconds.
                If `after` is specified, `before` must not be specified.
                Use with limit to get the next set of items.
                Default: `0` (the first item).
            before (int):
                Returns all items before (but not including) this cursor position, which is
                a Unix timestamp in milliseconds.
                If `before` is specified, `after` must not be specified.
                Use with limit to get the next set of items.
                Default: `0` (the first item).
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)

        The `after` and `before` arguments are based upon local time (not UTC time).  Recently
        played item history uses a local timestamp, and NOT a UTC timestamp.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `PlayHistoryPage` object that contains the playlist details.
        """
        apiMethodName: str = "service_spotify_get_player_recent_tracks"
        apiMethodParms: SIMethodParmListContext = None
        result: PlayHistoryPage = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("after", after)
            apiMethodParms.AppendKeyValue("before", before)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Player Recent Tracks Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetPlayerRecentTracks(
                limit, after, before, limitTotal
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_playlist(
        self,
        playlistId: str = None,
        market: str = None,
        fields: str = None,
        additionalTypes: str = None,
    ) -> dict:
        """
        Get a playlist owned by a Spotify user.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                If null, the currently playing playlist uri id value is used.
                Example: `5v5ETK9WFXAnGQ3MRubKuE`
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Example: `ES`
            fields (str):
                Filters for the query: a comma-separated list of the fields to return.
                If omitted, all fields are returned.
            additionalTypes (str):
                A comma-separated list of item types that your client supports besides the default track type.
                Valid types are: track and episode.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `Playlist` object that contains the playlist details.
        """
        apiMethodName: str = "service_spotify_get_playlist"
        apiMethodParms: SIMethodParmListContext = None
        result: Playlist = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("fields", fields)
            apiMethodParms.AppendKeyValue("additionalTypes", additionalTypes)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Playlist Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetPlaylist(
                playlistId, market, fields, additionalTypes
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_playlist_cover_image(
        self,
        playlistId: str = None,
    ) -> dict:
        """
        Get the current image associated with a specific playlist.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                If null, the currently playing playlist uri id value is used.
                Example: `5v5ETK9WFXAnGQ3MRubKuE`

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `ImageObject` object that contains the playlist cover image details.
        """
        apiMethodName: str = "service_spotify_get_playlist_cover_image"
        apiMethodParms: SIMethodParmListContext = None
        result: Playlist = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Playlist Cover Image Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetPlaylistCoverImage(playlistId)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_playlist_favorites(
        self,
        limit: int = 20,
        offset: int = 0,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get a list of the playlists owned or followed by the current Spotify user.

        Args:
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `PlaylistPageSimplified` object that contains playlist information.
        """
        apiMethodName: str = "service_spotify_get_playlist_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Playlist Favorites Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: PlaylistPageSimplified = (
                self.data.spotifyClient.GetPlaylistFavorites(
                    limit, offset, limitTotal, sortResult
                )
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_playlist_items(
        self,
        playlistId: str = None,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        fields: str = None,
        additionalTypes: str = None,
        limitTotal: int = None,
    ) -> dict:
        """
        Get full details of the items of a playlist owned by a Spotify user.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                Example: `5v5ETK9WFXAnGQ3MRubKuE`
                If null, the currently playing playlist uri id value is used.
            limit (int):
                The maximum number of items to return in a page of items when manual paging is used.
                Default: 50, Range: 1 to 50.
                See the `limitTotal` argument for automatic paging option.
            offset (int):
                The page index offset of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            fields (str):
                Filters for the query: a comma-separated list of the fields to return.
                If omitted, all fields are returned.
                For example, to get just the playlist's description and URI:
                `fields=description,uri`.
                A dot separator can be used to specify non-reoccurring fields, while parentheses can be used
                to specify reoccurring fields within objects. For example, to get just the added date and user
                ID of the adder:
                `fields=tracks.items(added_at,added_by.id)`.
                Use multiple parentheses to drill down into nested objects, for example:
                `fields=tracks.items(track(name,href,album(name,href)))`.
                Fields can be excluded by prefixing them with an exclamation mark, for example:
                `fields=tracks.items(track(name,href,album(!name,href)))`
                Example: fields=items(added_by.id,track(name,href,album(name,href)))
            additionalTypes (str):
                A comma-separated list of item types that your client supports besides the default track type.
                Valid types are: track and episode.
                Note: This parameter was introduced to allow existing clients to maintain their current behaviour
                and might be deprecated in the future.  In addition to providing this parameter, make sure that your
                client properly handles cases of new types in the future by checking against the type field of each object.
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `PlaylistPage` object that contains playlist information.
        """
        apiMethodName: str = "service_spotify_get_playlist_items"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("fields", fields)
            apiMethodParms.AppendKeyValue("additionalTypes", additionalTypes)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Playlist Items Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: PlaylistPage = self.data.spotifyClient.GetPlaylistItems(
                playlistId, limit, offset, market, fields, additionalTypes, limitTotal
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_playlists_for_user(
        self,
        userId: str,
        limit: int = 20,
        offset: int = 0,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get a list of the playlists owned or followed by the current Spotify user.

        Args:
            userId (str):
                The user's Spotify user ID.
                Example: `smedjan`
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `PlaylistPageSimplified` object that contains user playlist information.
        """
        apiMethodName: str = "service_spotify_get_playlists_for_user"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("userId", userId)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Playlists For User Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: PlaylistPageSimplified = (
                self.data.spotifyClient.GetPlaylistsForUser(
                    userId, limit, offset, limitTotal, sortResult
                )
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_show(
        self,
        showId: str = None,
        market: str = None,
    ) -> dict:
        """
        Get Spotify catalog information for a single show identified by its unique Spotify ID.

        Args:
            showId (str):
                The Spotify ID for the show.
                If null, the currently playing show uri id value is used.
                Example: `5CfCWKI5pZ28U0uOzXkDHe`
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Example: `ES`

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `Show` object that contain the show details.
        """
        apiMethodName: str = "service_spotify_get_show"
        apiMethodParms: SIMethodParmListContext = None
        result: Show = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("showId", showId)
            apiMethodParms.AppendKeyValue("market", market)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Show Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetShow(showId, market)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_show_episodes(
        self,
        showId: str = None,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        limitTotal: int = None,
    ) -> dict:
        """
        Get Spotify catalog information about a show's episodes.

        Args:
            showId (str):
                The Spotify ID for the show.
                If null, the currently playing show uri id value is used.
                Example: `6kAsbP8pxwaU2kPibKTuHE`
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return; use with limit to get the next set of items.
                Default: 0 (the first item).
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `EpisodePageSimplified` object that contains the show episodes.
        """
        apiMethodName: str = "service_spotify_get_show_episodes"
        apiMethodParms: SIMethodParmListContext = None
        result: EpisodePageSimplified = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("showId", showId)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("additionaoffsetlTypes", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Show Episodes Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetShowEpisodes(
                showId, limit, offset, market, limitTotal
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_show_favorites(
        self,
        limit: int = 20,
        offset: int = 0,
        limitTotal: int = None,
        sortResult: bool = True,
        excludeAudiobooks: bool = True,
    ) -> dict:
        """
        Get a list of the shows saved in the current Spotify user's 'Your Library'.

        Args:
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True
            excludeAudiobooks (bool):
                True to exclude audiobook shows from the returned list, leaving only podcast shows;
                otherwise, False to include all results returned by the Spotify Web API.
                Default: True

        For some reason, Spotify Web API returns audiobooks AND podcasts with the `/me/shows` service.
        Spotify Web API returns only audiobooks with the `/me/audiobooks` service.
        The reasoning for that is unclear, but the `excludeAudiobooks` argument allows you to
        only return podcast shows in the results if desired.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `ShowPageSaved` object that contains playlist information.
        """
        apiMethodName: str = "service_spotify_get_show_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            apiMethodParms.AppendKeyValue("excludeAudiobooks", excludeAudiobooks)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Show Favorites Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: ShowPageSaved = self.data.spotifyClient.GetShowFavorites(
                limit, offset, limitTotal, sortResult, excludeAudiobooks
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_spotify_connect_device(
        self,
        deviceValue: str,
        verifyUserContext: bool = True,
        verifyTimeout: float = 5,
        refreshDeviceList: bool = True,
        activateDevice: bool = True,
        delay: float = 0.25,
    ) -> dict:
        """
        Get information about a specific Spotify Connect player device, and (optionally)
        activate the device if it requires it.

        This method requires the `user-read-playback-state` scope.

        Resolves a Spotify Connect device from a specified device id, name, alias id,
        or alias name.  This will ensure that the device can be found on the network, as well
        as connect to the device if necessary with the current user context.

        Args:
            deviceValue (str):
                The device id / name value to check.
            verifyUserContext (bool):
                If True, the active user context of the resolved device is checked to ensure it
                matches the user context specified on the class constructor.
                If False, the user context will not be checked.
                Default is True.
            verifyTimeout (float):
                Maximum time to wait (in seconds) for the device to become active in the Spotify
                Connect device list.  This value is only used if a Connect command has to be
                issued to activate the device.
                Default is 5; value range is 0 - 10.
            refreshDeviceList (bool):
                True to refresh the Spotify Connect device list; otherwise, False to use the
                Spotify Connect device list cache.
            activateDevice (bool):
                True to activate the device if necessary; otherwise, False.
            delay (float):
                Time delay (in seconds) to wait AFTER issuing any command to the device.
                This delay will give the spotify zeroconf api time to process the change before
                another command is issued.
                Default is 0.25; value range is 0 - 10.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `SpotifyConnectDevice` object that contains the device details.
        """
        apiMethodName: str = "service_spotify_get_spotify_connect_device"
        apiMethodParms: SIMethodParmListContext = None
        result: SpotifyConnectDevice = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("deviceValue", deviceValue)
            apiMethodParms.AppendKeyValue("verifyUserContext", verifyUserContext)
            apiMethodParms.AppendKeyValue("verifyTimeout", verifyTimeout)
            apiMethodParms.AppendKeyValue("refreshDeviceList", refreshDeviceList)
            apiMethodParms.AppendKeyValue("activateDevice", activateDevice)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Get Spotify Connect Device service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetSpotifyConnectDevice(
                deviceValue,
                verifyUserContext,
                verifyTimeout,
                refreshDeviceList,
                activateDevice,
                delay,
            )

            # if result not found then raise exception.
            if result is None:
                raise HomeAssistantError(
                    'Device "%s" could not be found in the Spotify Connect device list.'
                    % deviceValue
                )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_spotify_connect_devices(
        self,
        refresh: bool = True,
        sortResult: bool = True,
    ) -> dict:
        """
        Get information about all available Spotify Connect player devices.

        This method requires the `user-read-playback-state` scope.

        Args:
            refresh (bool):
                True (default) to return real-time information from the spotify zeroconf api and
                update the cache; otherwise, False to just return the cached value.
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `SpotifyConnectDevices` object that contain the device details.
        """
        apiMethodName: str = "service_spotify_get_spotify_connect_devices"
        apiMethodParms: SIMethodParmListContext = None
        result: SpotifyConnectDevices = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("refresh", refresh)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Spotify Connect Devices Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetSpotifyConnectDevices(
                refresh, sortResult
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_track(
        self,
        trackId: str = None,
    ) -> dict:
        """
        Get Spotify catalog information for a single track identified by its unique Spotify ID.

        Args:
            trackId (str):
                The Spotify ID of the track.
                Example: `1kWUud3vY5ij5r62zxpTRy`
                If null, the currently playing track uri id value is used; a Spotify Free or Premium account
                is required to correctly read the currently playing context.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `Track` object that contain the track details.
        """
        apiMethodName: str = "service_spotify_get_track"
        apiMethodParms: SIMethodParmListContext = None
        result: Track = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("trackId", trackId)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Track Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.GetTrack(trackId)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_track_favorites(
        self,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get a list of the tracks saved in the current Spotify user's 'Your Library'.

        Args:
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Example: `ES`
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `TrackPageSaved` object that contains track favorites.
        """
        apiMethodName: str = "service_spotify_get_track_favorites"
        apiMethodParms: SIMethodParmListContext = None
        result: TrackPageSaved = TrackPageSaved()

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Track Favorites Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: TrackPageSaved = self.data.spotifyClient.GetTrackFavorites(
                limit, offset, market, limitTotal, sortResult
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_track_recommendations(
        self,
        limit: int = 20,
        market: str = None,
        seedArtists: str = None,
        seedGenres: str = None,
        seedTracks: str = None,
        minAcousticness: float = None,
        maxAcousticness: float = None,
        targetAcousticness: float = None,
        minDanceability: float = None,
        maxDanceability: float = None,
        targetDanceability: float = None,
        minDurationMS: int = None,
        maxDurationMS: int = None,
        targetDurationMS: int = None,
        minEnergy: float = None,
        maxEnergy: float = None,
        targetEnergy: float = None,
        minInstrumentalness: float = None,
        maxInstrumentalness: float = None,
        targetInstrumentalness: float = None,
        minKey: int = None,
        maxKey: int = None,
        targetKey: int = None,
        minLiveness: float = None,
        maxLiveness: float = None,
        targetLiveness: float = None,
        minLoudness: float = None,
        maxLoudness: float = None,
        targetLoudness: float = None,
        minMode: float = None,
        maxMode: float = None,
        targetMode: float = None,
        minPopularity: int = None,
        maxPopularity: int = None,
        targetPopularity: int = None,
        minSpeechiness: float = None,
        maxSpeechiness: float = None,
        targetSpeechiness: float = None,
        minTempo: int = None,
        maxTempo: int = None,
        targetTempo: int = None,
        minTimeSignature: int = None,
        maxTimeSignature: int = None,
        targetTimeSignature: int = None,
        minValence: float = None,
        maxValence: float = None,
        targetValence: float = None,
    ) -> dict:
        """
        Get track recommendations for specified criteria.

        Args:
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            seedArtists (str):
                A comma separated list of Spotify IDs for seed artists.
                Up to 5 seed values may be provided in any combination of seedArtists, seedTracks and seedGenres.
                Note: only required if seedGenres and seedTracks are not set.
                Example: `4NHQUGzhtTLFvgF5SZesLK`
            seedGenres (str):
                A comma separated list of any genres in the set of available genre seeds.
                Up to 5 seed values may be provided in any combination of seedArtists, seedTracks and seedGenres.
                Note: only required if seedArtists and seedTracks are not set.
                Example: `classical,country`
            seedTracks (str):
                A comma separated list of Spotify IDs for a seed track.
                Up to 5 seed values may be provided in any combination of seedArtists, seedTracks and seedGenres.
                Note: only required if seedArtists and seedGenres are not set.
                Example: `0c6xIDDpzE81m2q797ordA`
            minAcousticness (float):
                Restrict results to only those tracks whose acousticness level is greater than the specified value.
                Range: `0` - `1`
            maxAcousticness (float):
                Restrict results to only those tracks whose acousticness level is less than the specified value.
                Range: `0` - `1`
            targetAcousticness (float):
                Restrict results to only those tracks whose acousticness level is equal to the specified value.
                Range: `0` - `1`
            minDanceability (float):
                Restrict results to only those tracks whose danceability level is greater than the specified value.
                Range: `0` - `1`
            maxDanceability (float):
                Restrict results to only those tracks whose danceability level is less than the specified value.
                Range: `0` - `1`
            targetDanceability (float):
                Restrict results to only those tracks whose acousticness is equal to the specified value.
                Range: `0` - `1`
            minDurationMS (int):
                Restrict results to only those tracks whose duration is greater than the specified value in milliseconds.
            maxDurationMS (int):
                Restrict results to only those tracks whose duration is less than the specified value in milliseconds.
            targetDurationMS (int):
                Restrict results to only those tracks whose duration is equal to the specified value in milliseconds.
            minEnergy (float):
                Restrict results to only those tracks whose energy level is greater than the specified value.
                Range: `0` - `1`
            maxEnergy (float):
                Restrict results to only those tracks whose energy level is less than the specified value.
                Range: `0` - `1`
            targetEnergy (float):
                Restrict results to only those tracks whose energy level is equal to the specified value.
                Range: `0` - `1`
            minInstrumentalness (float):
                Restrict results to only those tracks whose instrumentalness level is greater than the specified value.
                Range: `0` - `1`
            maxInstrumentalness (float):
                Restrict results to only those tracks whose instrumentalness level is less than the specified value.
                Range: `0` - `1`
            targetInstrumentalness (float):
                Restrict results to only those tracks whose instrumentalness level is equal to the specified value.
                Range: `0` - `1`
            minKey (int):
                Restrict results to only those tracks whose key level is greater than the specified value.
                Range: `0` - `11`
            maxKey (int):
                Restrict results to only those tracks whose key level is less than the specified value.
                Range: `0` - `11`
            targetKey (int):
                Restrict results to only those tracks whose key level is equal to the specified value.
                Range: `0` - `11`
            minLiveness (float):
                Restrict results to only those tracks whose liveness level is greater than the specified value.
                Range: `0` - `1`
            maxLiveness (float):
                Restrict results to only those tracks whose liveness level is less than the specified value.
                Range: `0` - `1`
            targetLiveness (float):
                Restrict results to only those tracks whose liveness level is equal to the specified value.
                Range: `0` - `1`
            minLoudness (float):
                Restrict results to only those tracks whose loudness level is greater than the specified value.
            maxLoudness (float):
                Restrict results to only those tracks whose loudness level is less than the specified value.
            targetLoudness (float):
                Restrict results to only those tracks whose loudness level is equal to the specified value.
            minMode (float):
                Restrict results to only those tracks whose mode level is greater than the specified value.
                Range: `0` - `1`
            maxMode (float):
                Restrict results to only those tracks whose mode level is less than the specified value.
                Range: `0` - `1`
            targetMode (float):
                Restrict results to only those tracks whose mode level is equal to the specified value.
                Range: `0` - `1`
            minPopularity (int):
                Restrict results to only those tracks whose popularity level is greater than the specified value.
                Range: `0` - `100`
            maxPopularity (int):
                Restrict results to only those tracks whose popularity level is less than the specified value.
                Range: `0` - `100`
            targetPopularity (int):
                Restrict results to only those tracks whose popularity level is equal to the specified value.
                Range: `0` - `100`
            minSpeechiness (float):
                Restrict results to only those tracks whose speechiness level is greater than the specified value.
                Range: `0` - `1`
            maxSpeechiness (float):
                Restrict results to only those tracks whose speechiness level is less than the specified value.
                Range: `0` - `1`
            targetSpeechiness (float):
                Restrict results to only those tracks whose speechiness level is equal to the specified value.
                Range: `0` - `1`
            minTempo (int):
                Restrict results to only those tracks with a tempo greater than the specified number of beats per minute.
            maxTempo (int):
                Restrict results to only those tracks with a tempo less than the specified number of beats per minute.
            targetTempo (int):
                Restrict results to only those tracks with a tempo equal to the specified number of beats per minute.
            minTimeSignature (int):
                Restrict results to only those tracks whose time signature is greater than the specified value.
                Maximum value: 11
            maxTimeSignature (int):
                Restrict results to only those tracks whose time signature is less than the specified value.
            targetTimeSignature (int):
                Restrict results to only those tracks whose time signature is equal to the specified value.
            minValence (float):
                Restrict results to only those tracks whose valence level is greater than the specified value.
                Range: `0` - `1`
            maxValence (float):
                Restrict results to only those tracks whose valence level is less than the specified value.
                Range: `0` - `1`
            targetValence (float):
                Restrict results to only those tracks whose valence level is equal to the specified value.
                Range: `0` - `1`

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `TrackRecommendations` object that contains track information.
        """
        apiMethodName: str = "service_spotify_get_track_recommendations"
        apiMethodParms: SIMethodParmListContext = None
        result: TrackRecommendations = TrackRecommendations()

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("seedArtists", seedArtists)
            apiMethodParms.AppendKeyValue("seedGenres", seedGenres)
            apiMethodParms.AppendKeyValue("seedTracks", seedTracks)
            apiMethodParms.AppendKeyValue("minAcousticness", minAcousticness)
            apiMethodParms.AppendKeyValue("maxAcousticness", maxAcousticness)
            apiMethodParms.AppendKeyValue("targetAcousticness", targetAcousticness)
            apiMethodParms.AppendKeyValue("minDanceability", minDanceability)
            apiMethodParms.AppendKeyValue("maxDanceability", maxDanceability)
            apiMethodParms.AppendKeyValue("targetDanceability", targetDanceability)
            apiMethodParms.AppendKeyValue("minDurationMS", minDurationMS)
            apiMethodParms.AppendKeyValue("maxDurationMS", maxDurationMS)
            apiMethodParms.AppendKeyValue("targetDurationMS", targetDurationMS)
            apiMethodParms.AppendKeyValue("minEnergy", minEnergy)
            apiMethodParms.AppendKeyValue("maxEnergy", maxEnergy)
            apiMethodParms.AppendKeyValue("targetEnergy", targetEnergy)
            apiMethodParms.AppendKeyValue("minInstrumentalness", minInstrumentalness)
            apiMethodParms.AppendKeyValue("maxInstrumentalness", maxInstrumentalness)
            apiMethodParms.AppendKeyValue(
                "targetInstrumentalness", targetInstrumentalness
            )
            apiMethodParms.AppendKeyValue("minKey", minKey)
            apiMethodParms.AppendKeyValue("maxKey", maxKey)
            apiMethodParms.AppendKeyValue("targetKey", targetKey)
            apiMethodParms.AppendKeyValue("minLiveness", minLiveness)
            apiMethodParms.AppendKeyValue("maxLiveness", maxLiveness)
            apiMethodParms.AppendKeyValue("targetLiveness", targetLiveness)
            apiMethodParms.AppendKeyValue("minLoudness", minLoudness)
            apiMethodParms.AppendKeyValue("maxLoudness", maxLoudness)
            apiMethodParms.AppendKeyValue("targetLoudness", targetLoudness)
            apiMethodParms.AppendKeyValue("minMode", minMode)
            apiMethodParms.AppendKeyValue("maxMode", maxMode)
            apiMethodParms.AppendKeyValue("targetMode", targetMode)
            apiMethodParms.AppendKeyValue("minPopularity", minPopularity)
            apiMethodParms.AppendKeyValue("maxPopularity", maxPopularity)
            apiMethodParms.AppendKeyValue("targetPopularity", targetPopularity)
            apiMethodParms.AppendKeyValue("minSpeechiness", minSpeechiness)
            apiMethodParms.AppendKeyValue("maxSpeechiness", maxSpeechiness)
            apiMethodParms.AppendKeyValue("targetSpeechiness", targetSpeechiness)
            apiMethodParms.AppendKeyValue("minTempo", minTempo)
            apiMethodParms.AppendKeyValue("maxTempo", maxTempo)
            apiMethodParms.AppendKeyValue("targetTempo", targetTempo)
            apiMethodParms.AppendKeyValue("minTimeSignature", minTimeSignature)
            apiMethodParms.AppendKeyValue("maxTimeSignature", maxTimeSignature)
            apiMethodParms.AppendKeyValue("targetTimeSignature", targetTimeSignature)
            apiMethodParms.AppendKeyValue("minValence", minValence)
            apiMethodParms.AppendKeyValue("maxValence", maxValence)
            apiMethodParms.AppendKeyValue("targetValence", targetValence)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Track Recommendations Service",
                apiMethodParms,
            )

            # reset default values to None so they are processed correctly by the api.
            if minAcousticness == 0:
                minAcousticness = None
            if maxAcousticness == 0:
                maxAcousticness = None
            if targetAcousticness == 0:
                targetAcousticness = None

            if minDanceability == 0:
                minDanceability = None
            if maxDanceability == 0:
                maxDanceability = None
            if targetDanceability == 0:
                targetDanceability = None

            if minDurationMS == 0:
                minDurationMS = None
            if maxDurationMS == 0:
                maxDurationMS = None
            if targetDurationMS == 0:
                targetDurationMS = None

            if minEnergy == 0:
                minEnergy = None
            if maxEnergy == 0:
                maxEnergy = None
            if targetEnergy == 0:
                targetEnergy = None

            if minInstrumentalness == 0:
                minInstrumentalness = None
            if maxInstrumentalness == 0:
                maxInstrumentalness = None
            if targetInstrumentalness == 0:
                targetInstrumentalness = None

            if minKey == 0:
                minKey = None
            if maxKey == 0:
                maxKey = None
            if targetKey == 0:
                targetKey = None

            if minLiveness == 0:
                minLiveness = None
            if maxLiveness == 0:
                maxLiveness = None
            if targetLiveness == 0:
                targetLiveness = None

            if minLoudness == 0:
                minLoudness = None
            if maxLoudness == 0:
                maxLoudness = None
            if targetLoudness == 0:
                targetLoudness = None

            if minMode == 0:
                minMode = None
            if maxMode == 0:
                maxMode = None
            if targetMode == 0:
                targetMode = None

            if minPopularity == 0:
                minPopularity = None
            if maxPopularity == 0:
                maxPopularity = None
            if targetPopularity == 0:
                targetPopularity = None

            if minSpeechiness == 0:
                minSpeechiness = None
            if maxSpeechiness == 0:
                maxSpeechiness = None
            if targetSpeechiness == 0:
                targetSpeechiness = None

            if minTempo == 0:
                minTempo = None
            if maxTempo == 0:
                maxTempo = None
            if targetTempo == 0:
                targetTempo = None

            if minTimeSignature == 0:
                minTimeSignature = None
            if maxTimeSignature == 0:
                maxTimeSignature = None
            if targetTimeSignature == 0:
                targetTimeSignature = None

            if minValence == 0:
                minValence = None
            if maxValence == 0:
                maxValence = None
            if targetValence == 0:
                targetValence = None

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: TrackPageSaved = self.data.spotifyClient.GetTrackRecommendations(
                limit,
                market,
                seedArtists,
                seedGenres,
                seedTracks,
                minAcousticness,
                maxAcousticness,
                targetAcousticness,
                minDanceability,
                maxDanceability,
                targetDanceability,
                minDurationMS,
                maxDurationMS,
                targetDurationMS,
                minEnergy,
                maxEnergy,
                targetEnergy,
                minInstrumentalness,
                maxInstrumentalness,
                targetInstrumentalness,
                minKey,
                maxKey,
                targetKey,
                minLiveness,
                maxLiveness,
                targetLiveness,
                minLoudness,
                maxLoudness,
                targetLoudness,
                minMode,
                maxMode,
                targetMode,
                minPopularity,
                maxPopularity,
                targetPopularity,
                minSpeechiness,
                maxSpeechiness,
                targetSpeechiness,
                minTempo,
                maxTempo,
                targetTempo,
                minTimeSignature,
                maxTimeSignature,
                targetTimeSignature,
                minValence,
                maxValence,
                targetValence,
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_tracks_audio_features(
        self,
        ids: str,
    ) -> dict:
        """
        Get audio features for multiple tracks based on their Spotify IDs.

        Args:
            ids (list[str]):
                A comma-separated list of the Spotify track IDs.
                Maximum: 100 IDs.
                Example: `7ouMYWpwJ422jRcDASZB7P,4VqPOruhp5EdPBeR92t6lQ,2takcwOaAZWiXQijPHIx7B`

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A list of `AudioFeatures` objects that contain the audio feature details.
        """
        apiMethodName: str = "service_spotify_get_tracks_audio_features"
        apiMethodParms: SIMethodParmListContext = None
        result: list = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Get Tracks Audio Features Service",
                apiMethodParms,
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: TrackPageSaved = self.data.spotifyClient.GetTracksAudioFeatures(ids)

            # build dictionary result from array.
            resultArray: list = []
            item: AudioFeatures
            for item in result:
                resultArray.append(item.ToDictionary())

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": resultArray,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_users_top_artists(
        self,
        timeRange: str = "medium_term",
        limit: int = 20,
        offset: int = 0,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get the current user's top artists based on calculated affinity.

        Args:
            timeRange (str):
                Over what time frame the affinities are computed.
                Valid values:
                - long_term (calculated from several years of data and including all new data as it becomes available).
                - medium_term (approximately last 6 months).
                - short_term (approximately last 4 weeks).
                Default: `medium_term`
                Example: `long_term`
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item), Range: 0 to 1000
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `ArtistPage` object of matching results.
        """
        apiMethodName: str = "service_spotify_get_users_top_artists"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("timeRange", timeRange)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Users Top Artists Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: ArtistPage = self.data.spotifyClient.GetUsersTopArtists(
                timeRange, limit, offset, limitTotal, sortResult
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_get_users_top_tracks(
        self,
        timeRange: str = "medium_term",
        limit: int = 20,
        offset: int = 0,
        limitTotal: int = None,
        sortResult: bool = True,
    ) -> dict:
        """
        Get the current user's top tracks based on calculated affinity.

        Args:
            timeRange (str):
                Over what time frame the affinities are computed.
                Valid values:
                - long_term (calculated from several years of data and including all new data as it becomes available).
                - medium_term (approximately last 6 months).
                - short_term (approximately last 4 weeks).
                Default: `medium_term`
                Example: `long_term`
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The index of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item), Range: 0 to 1000
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum count specified.
                Default: None (disabled)
            sortResult (bool):
                True to sort the items by name; otherwise, False to leave the items in the same order they
                were returned in by the Spotify Web API.
                Default: True

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `TrackPage` object of matching results.
        """
        apiMethodName: str = "service_spotify_get_users_top_tracks"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("timeRange", timeRange)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            apiMethodParms.AppendKeyValue("sortResult", sortResult)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Get Users Top Tracks Service", apiMethodParms
            )

            # request information from Spotify Web API.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result: TrackPage = self.data.spotifyClient.GetUsersTopTracks(
                timeRange, limit, offset, limitTotal, sortResult
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_player_activate_devices(
        self,
        verifyUserContext: bool = False,
        delay: float = 0.50,
    ) -> dict:
        """
        Activates all Spotify Connect player devices, and (optionally) switches the active user
        context to the current user context for each device.

        Args:
            verifyUserContext (bool):
                If True, the active user context of the resolved device is checked to ensure it
                matches the user context specified on the class constructor.
                If False, the user context will not be checked.
                Default is False.
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the final Connect command (if necessary).
                This delay will give the spotify web api time to process the device list change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_player_activate_devices"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("verifyUserContext", verifyUserContext)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Player Activate Devices Service",
                apiMethodParms,
            )

            # process Spotify Web API request.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.PlayerActivateDevices(
                verifyUserContext, delay
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyZeroconfApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    @spotify_exception_handler
    def service_spotify_player_media_pause(
        self,
        deviceId: str = None,
        delay: float = 0.50,
    ) -> None:
        """
        Pause media play for the specified Spotify Connect device.

        Args:
            deviceId (str):
                The id or name of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
                Example: `Web Player (Chrome)`
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_player_media_pause"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Player Media Pause Service", apiMethodParms
            )

            # validations.
            delay = validateDelay(delay, 0.50, 10)
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )

            # get selected device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            playerState: PlayerPlayState
            spotifyConnectDevice: SpotifyConnectDevice
            sonosDevice: SoCo

            # get current player state.
            # ignore what we get for device from _GetPlayerPlaybackState, as it's the active device
            # and may be NOT what the user asked for (via deviceId argument).
            playerState, spotifyConnectDevice, sonosDevice = (
                self._GetPlayerPlaybackState()
            )

            # process based on device type.
            if sonosDevice is not None:
                # for Sonos, use the SoCo API command.
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): PAUSE"
                    % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                )
                sonosDevice.pause()

                # give SoCo api time to process the change.
                if delay > 0:
                    _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                    time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API command.
                self.data.spotifyClient.PlayerMediaPause(deviceId, delay)

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a media player command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    @spotify_exception_handler
    def service_spotify_player_media_play_context(
        self,
        contextUri: str,
        offsetUri: str = None,
        offsetPosition: int = -1,
        positionMS: int = -1,
        deviceId: str = None,
        delay: float = 0.50,
    ) -> None:
        """
        Start playing one or more tracks of the specified context on a Spotify Connect device.

        Args:
            contextUri (str):
                Spotify URI of the context to play.
                Valid contexts are albums, artists & playlists.
                Example: `spotify:album:6vc9OTcyd3hyzabCmsdnwE`.
            offsetUri (str):
                Indicates from what Uri in the context playback should start.
                Only available when contextUri corresponds to an artist, album or playlist.
                The offsetPosition argument will be used if this value is null.
                For Sonos devices, this argument is ignored.
                Default is null.
                Example: `spotify:track:1301WleyT98MSxVHPZCA6M` start playing at the specified track Uri.
            offsetPosition (int):
                Indicates from what position in the context playback should start.
                The value is zero-based, and must be a positive number, or -1 to disable positioning.
                Only available when contextUri corresponds to an album or playlist.
                Default is `0`.
                Example: `3`  start playing at track number 4.
            positionMS (int):
                The position in milliseconds to seek to; must be a positive number, or -1 to disable positioning.
                Passing in a position that is greater than the length of the track will cause the
                player to start playing the next track.
                Default is `0`.
                Example: `25000`
            deviceId (str):
                The id of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_player_media_play_context"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("contextUri", contextUri)
            apiMethodParms.AppendKeyValue("offsetUri", offsetUri)
            apiMethodParms.AppendKeyValue("offsetPosition", offsetPosition)
            apiMethodParms.AppendKeyValue("positionMS", positionMS)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Player Media Play Context Service",
                apiMethodParms,
            )

            # validations.
            if offsetPosition == -1:
                offsetPosition = None
            if positionMS == -1:
                positionMS = None

            delay = validateDelay(delay, 0.50, 10)
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )

            # get selected device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            # start playing one or more tracks of the specified context on a Spotify Connect device.
            if (scDevice is not None) and (scDevice.DeviceInfo.IsBrandSonos):
                if offsetPosition is None:
                    offsetPosition = 0
                if positionMS is None:
                    positionMS = 0

                # Sonos cannot handle playing an artist context!
                # if this is an artist context, then we will get a list of the artist's albums
                # and add them to the queue.
                if contextUri.find(":artist:") > -1:
                    artistId: str = contextUri.replace("spotify:artist:", "")
                    # includeGroups:str = 'album,single,appears_on,compilation'
                    includeGroups: str = "album"
                    _logsi.LogVerbose(
                        "'%s': Getting ALL albums for artist id: %s"
                        % (self.name, artistId)
                    )
                    pageObj: AlbumPageSimplified = (
                        self.data.spotifyClient.GetArtistAlbums(
                            artistId, includeGroups, limitTotal=75
                        )
                    )
                    contextUri: list = []
                    albumSimplified: AlbumSimplified
                    for albumSimplified in pageObj.Items:
                        contextUri.append(albumSimplified.Uri)

                # build a list of all item uri's.
                # remove any leading / trailing spaces in case user put a space between the items.
                arrUris: list[str] = None
                if isinstance(contextUri, list):
                    arrUris = contextUri
                else:
                    arrUris = contextUri.split(",")
                    for idx in range(0, len(arrUris)):
                        arrUris[idx] = arrUris[idx].strip()

                # for Sonos, use the SoCo API command.
                sonosDevice = SoCo(scDevice.DiscoveryResult.HostIpAddress)
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): CLEAR_QUEUE"
                    % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                )
                sonosDevice.clear_queue()
                sharelink = ShareLinkPlugin(sonosDevice)
                for uri in arrUris:
                    _logsi.LogVerbose(
                        "'%s': Issuing command to Sonos device '%s' ('%s'): ADD_SHARE_LINK_TO_QUEUE (uri=%s)"
                        % (
                            self.name,
                            sonosDevice.ip_address,
                            sonosDevice.player_name,
                            uri,
                        )
                    )
                    sharelink.add_share_link_to_queue(uri)
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): PLAY_FROM_QUEUE (index=%s)"
                    % (
                        self.name,
                        sonosDevice.ip_address,
                        sonosDevice.player_name,
                        offsetPosition,
                    )
                )
                sonosDevice.play_from_queue(index=offsetPosition)

                # give SoCo api time to process the change.
                if delay > 0:
                    _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                    time.sleep(delay)

                # is seek position specified, then seek to the position.
                if positionMS > 0:
                    sonosPosition: str = positionHMS_fromMilliSeconds(
                        positionMS
                    )  # convert from milliseconds to Sonos H:MM:SS format
                    _logsi.LogVerbose(
                        "'%s': Issuing command to Sonos device '%s' ('%s'): SEEK (position=%s)"
                        % (
                            self.name,
                            sonosDevice.ip_address,
                            sonosDevice.player_name,
                            sonosPosition,
                        )
                    )
                    sonosDevice.seek(position=sonosPosition)

                    # give SoCo api time to process the change.
                    if delay > 0:
                        _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                        time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API command.
                self.data.spotifyClient.PlayerMediaPlayContext(
                    contextUri, offsetUri, offsetPosition, positionMS, deviceId, delay
                )

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a media player command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)

        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    @spotify_exception_handler
    def service_spotify_player_media_play_track_favorites(
        self,
        deviceId: str = None,
        shuffle: bool = False,
        delay: float = 0.50,
        resolveDeviceId: bool = True,
        limitTotal: int = None,
    ) -> None:
        """
        Start playing one or more tracks on the specified Spotify Connect device.

        Args:
            deviceId (str):
                The id of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
            shuffle (bool):
                True to set player shuffle mode to on; otherwise, False for no shuffle.
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
            resolveDeviceId (bool):
                True to resolve the supplied `deviceId` value; otherwise, False not resolve the `deviceId`
                value as it has already been resolved.
                Default is True.
            limitTotal (int):
                The maximum number of items to retrieve from favorites.
                Default: 200.
        """
        apiMethodName: str = "service_spotify_player_media_play_track_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("shuffle", shuffle)
            apiMethodParms.AppendKeyValue("delay", delay)
            apiMethodParms.AppendKeyValue("resolveDeviceId", resolveDeviceId)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Player Media Play Favorite Tracks Service",
                apiMethodParms,
            )

            # validations.
            delay = validateDelay(delay, 0.50, 10)
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )
            if (resolveDeviceId is None) or (not isinstance(resolveDeviceId, bool)):
                resolveDeviceId = True
            if (
                (limitTotal is None)
                or (not isinstance(limitTotal, int))
                or (limitTotal < 1)
            ):
                limitTotal = 200

            # get selected device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            # start playing track favorites on the specified Spotify Connect device.
            if (scDevice is not None) and (scDevice.DeviceInfo.IsBrandSonos):
                # get current users favorite tracks.
                tracks: TrackPageSaved = self.data.spotifyClient.GetTrackFavorites(
                    limitTotal=limitTotal
                )
                if tracks.ItemsCount == 0:
                    _logsi.LogVerbose(
                        "Current user has no favorite tracks; nothing to do"
                    )
                    return

                offsetPosition: int = 0

                # build a list of all item uri's.
                arrUris: list[str] = []
                trackSaved: TrackSaved
                for trackSaved in tracks.Items:
                    arrUris.append(trackSaved.Track.Uri)

                # for Sonos, use the SoCo API command.
                sonosDevice = SoCo(scDevice.DiscoveryResult.HostIpAddress)
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): CLEAR_QUEUE"
                    % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                )
                sonosDevice.clear_queue()
                sharelink = ShareLinkPlugin(sonosDevice)
                for uri in arrUris:
                    _logsi.LogVerbose(
                        "'%s': Issuing command to Sonos device '%s' ('%s'): ADD_SHARE_LINK_TO_QUEUE (uri=%s)"
                        % (
                            self.name,
                            sonosDevice.ip_address,
                            sonosDevice.player_name,
                            uri,
                        )
                    )
                    sharelink.add_share_link_to_queue(uri)

                # set desired shuffle mode.
                self.service_spotify_player_set_shuffle_mode(
                    state=shuffle, deviceId=deviceId, delay=delay
                )

                # skip first track if shuffle is enabled.
                if (len(arrUris) > 1) and (shuffle is True):
                    offsetPosition = 1

                # play the queue.
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): PLAY_FROM_QUEUE (index=%s)"
                    % (
                        self.name,
                        sonosDevice.ip_address,
                        sonosDevice.player_name,
                        offsetPosition,
                    )
                )
                sonosDevice.play_from_queue(index=offsetPosition)

                # give SoCo api time to process the change.
                if delay > 0:
                    _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                    time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API command.
                self.data.spotifyClient.PlayerMediaPlayTrackFavorites(
                    deviceId, shuffle, delay, resolveDeviceId, limitTotal
                )

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    @spotify_exception_handler
    def service_spotify_player_media_play_tracks(
        self,
        uris: str,
        positionMS: int = -1,
        deviceId: str = None,
        delay: float = 0.50,
    ) -> None:
        """
        Start playing one or more tracks on the specified Spotify Connect device.

        Args:
            uris (str):
                A list of Spotify track URIs to play; can be track or episode URIs.
                Example: [`spotify:track:4iV5W9uYEdYUVa79Axb7Rh` ,`spotify:episode:512ojhOuo1ktJprKbVcKyQ`].
                It can also be specified as a comma-delimited string.
                Example: `spotify:track:4iV5W9uYEdYUVa79Axb7Rh,spotify:episode:512ojhOuo1ktJprKbVcKyQ`.
                A maximum of 50 items can be added in one request.
            positionMS (int):
                The position in milliseconds to seek to; must be a positive number, or -1 to disable positioning.
                Passing in a position that is greater than the length of the track will cause the
                player to start playing the next track.
                Default is `0`.
                Example: `25000`
            deviceId (str):
                The id of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_player_media_play_tracks"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("uris", uris)
            apiMethodParms.AppendKeyValue("positionMS", positionMS)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Player Media Play Tracks Service",
                apiMethodParms,
            )

            # validations.
            if positionMS == -1:
                positionMS = None

            delay = validateDelay(delay, 0.50, 10)
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )

            # get selected device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            # start playing one or more tracks on the specified Spotify Connect device.
            if (scDevice is not None) and (scDevice.DeviceInfo.IsBrandSonos):
                offsetPosition: int = 0
                if positionMS is None:
                    positionMS = 0

                # build a list of all item uri's.
                # remove any leading / trailing spaces in case user put a space between the items.
                arrUris: list[str] = None
                if isinstance(uris, list):
                    arrUris = uris
                else:
                    arrUris = uris.split(",")
                    for idx in range(0, len(arrUris)):
                        arrUris[idx] = arrUris[idx].strip()

                # for Sonos, use the SoCo API command.
                sonosDevice = SoCo(scDevice.DiscoveryResult.HostIpAddress)
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): CLEAR_QUEUE"
                    % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                )
                sonosDevice.clear_queue()
                sharelink = ShareLinkPlugin(sonosDevice)
                for uri in arrUris:
                    _logsi.LogVerbose(
                        "'%s': Issuing command to Sonos device '%s' ('%s'): ADD_SHARE_LINK_TO_QUEUE (uri=%s)"
                        % (
                            self.name,
                            sonosDevice.ip_address,
                            sonosDevice.player_name,
                            uri,
                        )
                    )
                    sharelink.add_share_link_to_queue(uri)
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): PLAY_FROM_QUEUE (index=%s)"
                    % (
                        self.name,
                        sonosDevice.ip_address,
                        sonosDevice.player_name,
                        offsetPosition,
                    )
                )
                sonosDevice.play_from_queue(index=offsetPosition)

                # give SoCo api time to process the change.
                if delay > 0:
                    _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                    time.sleep(delay)

                # is seek position specified, then seek to the position.
                if positionMS > 0:
                    sonosPosition: str = positionHMS_fromMilliSeconds(
                        positionMS
                    )  # convert from milliseconds to Sonos H:MM:SS format
                    _logsi.LogVerbose(
                        "'%s': Issuing command to Sonos device '%s' ('%s'): SEEK (position=%s)"
                        % (
                            self.name,
                            sonosDevice.ip_address,
                            sonosDevice.player_name,
                            sonosPosition,
                        )
                    )
                    sonosDevice.seek(position=sonosPosition)

                    # give SoCo api time to process the change.
                    if delay > 0:
                        _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                        time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API command.
                self.data.spotifyClient.PlayerMediaPlayTracks(
                    uris, positionMS, deviceId, delay
                )

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a media player command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    @spotify_exception_handler
    def service_spotify_player_media_resume(
        self,
        deviceId: str = None,
        delay: float = 0.50,
    ) -> None:
        """
        Resume media play for the specified Spotify Connect device.

        Args:
            deviceId (str):
                The id or name of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
                Example: `Web Player (Chrome)`
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_player_media_resume"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Player Media Resume Service", apiMethodParms
            )

            # validations.
            delay = validateDelay(delay, 0.50, 10)
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )

            # get selected device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            playerState: PlayerPlayState
            spotifyConnectDevice: SpotifyConnectDevice
            sonosDevice: SoCo

            # get current player state.
            # ignore what we get for device from _GetPlayerPlaybackState, as it's the active device
            # and may be NOT what the user asked for (via deviceId argument).
            playerState, spotifyConnectDevice, sonosDevice = (
                self._GetPlayerPlaybackState()
            )

            # process based on device type.
            if sonosDevice is not None:
                # for Sonos, use the SoCo API command.
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): RESUME"
                    % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                )
                sonosDevice.play()

                # give SoCo api time to process the change.
                if delay > 0:
                    _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                    time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API command.
                self.data.spotifyClient.PlayerMediaResume(deviceId, delay)

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a media player command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    @spotify_exception_handler
    def service_spotify_player_media_seek(
        self,
        positionMS: int = -1,
        deviceId: str = None,
        delay: float = 0.50,
        relativePositionMS: int = 0,
    ) -> None:
        """
        Seeks to the given absolute or relative position in the user's currently playing track
        for the specified Spotify Connect device.

        Args:
            positionMS (int):
                The absolute position in milliseconds to seek to; must be a positive number.
                Passing in a position that is greater than the length of the track will cause the
                player to start playing the next song.
                Example = `25000` to start playing at the 25 second mark.
            deviceId (str):
                The id or name of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
                Example: `Web Player (Chrome)`
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
            relativePositionMS (int):
                The relative position in milliseconds to seek to; can be a positive or negative number.
                Example = `-10000` to seek behind by 10 seconds.
                Example = `10000` to seek ahead by 10 seconds.
        """
        apiMethodName: str = "service_spotify_player_media_seek"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("positionMS", positionMS)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("delay", delay)
            apiMethodParms.AppendKeyValue("relativePositionMS", positionMS)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Player Media Seek Service", apiMethodParms
            )

            # validations.
            if positionMS == -1:
                positionMS = None
            if relativePositionMS == 0:
                relativePositionMS = None

            # validations.
            delay = validateDelay(delay, 0.50, 10)
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )

            # get selected device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            playerState: PlayerPlayState
            spotifyConnectDevice: SpotifyConnectDevice
            sonosDevice: SoCo

            # get current player state.
            # ignore what we get for device from _GetPlayerPlaybackState, as it's the active device
            # and may be NOT what the user asked for (via deviceId argument).
            playerState, spotifyConnectDevice, sonosDevice = (
                self._GetPlayerPlaybackState()
            )

            # set seek position based on device type.
            if sonosDevice is not None:
                # was relative seeking specified?
                if (relativePositionMS != 0) and (
                    (positionMS is None) or (positionMS <= 0)
                ):
                    newPositionMS: int = playerState.ProgressMS
                    if (newPositionMS is not None) and (newPositionMS > 0):
                        # calculate new position; if less than zero, then force it to zero.
                        newPositionMS += relativePositionMS
                        if newPositionMS < 0:
                            newPositionMS = 0
                        positionMS = newPositionMS

                # for Sonos, use the SoCo API command.
                sonosPosition: str = positionHMS_fromMilliSeconds(
                    positionMS
                )  # convert from milliseconds to Sonos H:MM:SS format
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): SEEK (position=%s)"
                    % (
                        self.name,
                        sonosDevice.ip_address,
                        sonosDevice.player_name,
                        sonosPosition,
                    )
                )
                sonosDevice.seek(position=sonosPosition)

                # give SoCo api time to process the change.
                if delay > 0:
                    _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                    time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API command.
                self.data.spotifyClient.PlayerMediaSeek(
                    positionMS, deviceId, delay, relativePositionMS
                )

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a media player command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    @spotify_exception_handler
    def service_spotify_player_media_skip_next(
        self,
        deviceId: str = None,
        delay: float = 0.50,
    ) -> None:
        """
        Skips to next track in the user's queue for the specified Spotify Connect device.

        Args:
            deviceId (str):
                The id or name of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
                Example: `Web Player (Chrome)`
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_player_media_skip_next"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Player Media Skip Next Service",
                apiMethodParms,
            )

            # validations.
            delay = validateDelay(delay, 0.50, 10)
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )

            # get selected device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            playerState: PlayerPlayState
            spotifyConnectDevice: SpotifyConnectDevice
            sonosDevice: SoCo

            # get current player state.
            # ignore what we get for device from _GetPlayerPlaybackState, as it's the active device
            # and may be NOT what the user asked for (via deviceId argument).
            playerState, spotifyConnectDevice, sonosDevice = (
                self._GetPlayerPlaybackState()
            )

            # process based on device type.
            if sonosDevice is not None:
                # for Sonos, use the SoCo API command.
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): SKIP_NEXT"
                    % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                )
                sonosDevice.next()

                # give SoCo api time to process the change.
                if delay > 0:
                    _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                    time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API command.
                self.data.spotifyClient.PlayerMediaSkipNext(deviceId, delay)

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a media player command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    @spotify_exception_handler
    def service_spotify_player_media_skip_previous(
        self,
        deviceId: str = None,
        delay: float = 0.50,
    ) -> None:
        """
        Skips to previous track in the user's queue for the specified Spotify Connect device.

        Args:
            deviceId (str):
                The id or name of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
                Example: `Web Player (Chrome)`
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_player_media_skip_previous"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Player Media Skip Previous Service",
                apiMethodParms,
            )

            # validations.
            delay = validateDelay(delay, 0.50, 10)
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )

            # get selected device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            playerState: PlayerPlayState
            spotifyConnectDevice: SpotifyConnectDevice
            sonosDevice: SoCo

            # get current player state.
            # ignore what we get for device from _GetPlayerPlaybackState, as it's the active device
            # and may be NOT what the user asked for (via deviceId argument).
            playerState, spotifyConnectDevice, sonosDevice = (
                self._GetPlayerPlaybackState()
            )

            # process based on device type.
            if sonosDevice is not None:
                # for Sonos, use the SoCo API command.
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): SKIP_PREVIOUS"
                    % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                )
                sonosDevice.previous()

                # give SoCo api time to process the change.
                if delay > 0:
                    _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                    time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API command.
                self.data.spotifyClient.PlayerMediaSkipPrevious(deviceId, delay)

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a media player command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_player_resolve_device_id(
        self,
        deviceValue: str,
        verifyUserContext: bool = True,
        verifyTimeout: float = 5.0,
    ) -> dict:
        """
        Resolves a Spotify Connect device identifier from a specified device id, name, alias id,
        or alias name.  This will ensure that the device id can be found on the network, as well
        as connect to the device if necessary with the current user context.

        Args:
            deviceValue (str):
                The device id / name value to check.
            verifyUserContext (bool):
                If True, the active user context of the resolved device is checked to ensure it
                matches the user context specified on the class constructor.
                If False, the user context will not be checked.
                Default is True.
            verifyTimeout (float):
                Maximum time to wait (in seconds) for the device to become active in the Spotify
                Connect device list.  This value is only used if a Connect command has to be
                issued to activate the device.
                Default is 5; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_player_resolve_device_id"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("deviceValue", deviceValue)
            apiMethodParms.AppendKeyValue("verifyUserContext", verifyUserContext)
            apiMethodParms.AppendKeyValue("verifyTimeout", verifyTimeout)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Player Resolve Device Id Service",
                apiMethodParms,
            )

            # process Spotify Web API request.
            _logsi.LogVerbose(STAppMessages.MSG_SERVICE_QUERY_WEB_API)
            result = self.data.spotifyClient.PlayerResolveDeviceId(
                deviceValue, verifyUserContext, verifyTimeout
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyZeroconfApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_player_set_repeat_mode(
        self,
        state: str = "off",
        deviceId: str = None,
        delay: float = 0.50,
    ) -> None:
        """
        Set repeat mode for the specified Spotify Connect device.

        Args:
            state (str):
                The repeat mode to set:
                - `track`   - will repeat the current track.
                - `context` - will repeat the current context.
                - `off`     - will turn repeat off.
                Default: `off`
            deviceId (str):
                The id or name of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
                Example: `Web Player (Chrome)`
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_player_set_repeat_mode"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("state", state)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Player Set Repeat Mode Service",
                apiMethodParms,
            )

            # validations.
            delay = validateDelay(delay, 0.50, 10)
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )

            # get selected device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            # set repeat mode based on device type.
            if (scDevice is not None) and (scDevice.DeviceInfo.IsBrandSonos):
                # get current Spotify Connect player state.
                playerState = self.data.spotifyClient.GetPlayerPlaybackState(
                    additionalTypes=MediaType.EPISODE.value
                )

                # set the Sonos PlayMode directly (instead of setting the Sonos repeat property)!
                # The Spotify Web API PlayerState `ShuffleState` value can sometimes be different than what the
                # Sonos device reports for its `shuffle` property value!
                if state == "track":
                    sonos_repeat = "ONE"
                elif state == "off":
                    sonos_repeat = False
                elif state == "context":
                    sonos_repeat = True
                else:
                    sonos_repeat = False
                playMode: str = SONOS_PLAY_MODE_BY_MEANING[
                    (playerState.ShuffleState, sonos_repeat)
                ]

                # for Sonos, use the SoCo API command.
                sonosDevice = SoCo(scDevice.DiscoveryResult.HostIpAddress)
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): REPEAT (playmode=%s)"
                    % (
                        self.name,
                        sonosDevice.ip_address,
                        sonosDevice.player_name,
                        playMode,
                    )
                )
                sonosDevice.play_mode = playMode

                # give SoCo api time to process the change.
                if delay > 0:
                    _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                    time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API command.
                self.data.spotifyClient.PlayerSetRepeatMode(state, deviceId, delay)

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a media player command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_player_set_shuffle_mode(
        self,
        state: bool = False,
        deviceId: str = None,
        delay: float = 0.50,
    ) -> None:
        """
        Set shuffle mode for the specified Spotify Connect device.

        Args:
            state (bool):
                The shuffle mode to set:
                - `True`  - Shuffle user's playback.
                - `False` - Do not shuffle user's playback.
                Default: `False`
            deviceId (str):
                The id or name of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
                Example: `Web Player (Chrome)`
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_player_set_shuffle_mode"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("state", state)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Player Set Shuffle Mode Service",
                apiMethodParms,
            )

            # validations.
            delay = validateDelay(delay, 0.50, 10)
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )
            if state is None:
                state = False

            # get selected device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            # set shuffle mode based on device type.
            if (scDevice is not None) and (scDevice.DeviceInfo.IsBrandSonos):
                # get current Spotify Connect player state.
                playerState = self.data.spotifyClient.GetPlayerPlaybackState(
                    additionalTypes=MediaType.EPISODE.value
                )

                # set the Sonos PlayMode directly (instead of setting the Sonos `shuffle` property)!
                # the Spotify Web API PlayerState `RepeatState` value can sometimes be different than what the
                # Sonos device reports for its `repeat` property value!
                sonos_repeat: str
                if playerState.RepeatState == "track":
                    sonos_repeat = "ONE"
                elif playerState.RepeatState == "off":
                    sonos_repeat = False
                elif playerState.RepeatState == "context":
                    sonos_repeat = True
                else:  # assume off if nothing else.
                    sonos_repeat = False
                playMode: str = SONOS_PLAY_MODE_BY_MEANING[(state, sonos_repeat)]

                # for Sonos, use the SoCo API command.
                sonosDevice = SoCo(scDevice.DiscoveryResult.HostIpAddress)
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): SHUFFLE (playmode=%s)"
                    % (
                        self.name,
                        sonosDevice.ip_address,
                        sonosDevice.player_name,
                        playMode,
                    )
                )
                sonosDevice.play_mode = playMode

                # give SoCo api time to process the change.
                if delay > 0:
                    _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                    time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API command.
                self.data.spotifyClient.PlayerSetShuffleMode(state, deviceId, delay)

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a media player command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_player_set_volume_level(
        self,
        volumeLevel: int,
        deviceId: str = None,
        delay: float = 0.50,
    ) -> None:
        """
        Set volume level for the specified Spotify Connect device.

        Args:
            volumeLevel (int):
                The volume to set.
                Must be a value from 0 to 100 inclusive.
                Example: `50`
            deviceId (str):
                The id or name of the device this command is targeting.
                If not supplied, the user's currently active device is the target.
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
                Example: `Web Player (Chrome)`
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
        """
        apiMethodName: str = "service_spotify_player_set_volume_level"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("volumeLevel", volumeLevel)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Player Set Volume Level Service",
                apiMethodParms,
            )

            # validations.
            delay = validateDelay(delay, 0.50, 10)
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )

            # get selected device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(refresh=False)
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            # set volume level based on device type.
            if (scDevice is not None) and (scDevice.DeviceInfo.IsBrandSonos):
                # for Sonos, use the SoCo API command.
                sonosDevice = SoCo(scDevice.DiscoveryResult.HostIpAddress)
                _logsi.LogVerbose(
                    "'%s': Issuing command to Sonos device '%s' ('%s'): VOLUME"
                    % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                )
                sonosDevice.volume = volumeLevel

                # give SoCo api time to process the change.
                if delay > 0:
                    _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                    time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API command.
                self.data.spotifyClient.PlayerSetVolume(volumeLevel, deviceId, delay)

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a media player command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_player_transfer_playback(
        self,
        deviceId: str = None,
        play: bool = True,
        delay: float = 0.50,
        refreshDeviceList: bool = True,
        forceActivateDevice: bool = True,
    ) -> None:
        """
        Transfer playback to a new Spotify Connect device and optionally begin playback.

        Args:
            deviceId (str):
                The id of the device on which playback should be started/transferred.
                Example: `Bose-ST10-1`
                Example: `0d1841b0976bae2a3a310dd74c0f3df354899bc8`
            play (bool):
                The transfer method:
                - `True`  - ensure playback happens on new device.
                - `False` - keep the current playback state.
                Default is `True`
            delay (float):
                Time delay (in seconds) to wait AFTER issuing the command to the player.
                This delay will give the spotify web api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.
            refreshDeviceList (bool):
                True to refresh the Spotify Connect device list; otherwise, False to use the
                Spotify Connect device list cache.
                Default is True.
            forceActivateDevice (bool):
                True to issue a Spotify Connect Disconnect call prior to transfer, which will
                force the device to reconnect to Spotify Connect; otherwise, False to not
                disconnect.
                Default is True.
        """
        apiMethodName: str = "service_spotify_player_transfer_playback"
        apiMethodParms: SIMethodParmListContext = None
        sonosDevice: SoCo = None
        saveSource: str = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("deviceId", deviceId)
            apiMethodParms.AppendKeyValue("play", play)
            apiMethodParms.AppendKeyValue("delay", delay)
            apiMethodParms.AppendKeyValue("refreshDeviceList", refreshDeviceList)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Player Transfer Playback Service",
                apiMethodParms,
            )

            # validations.
            delay = validateDelay(delay, 0.50, 10)
            if play is None:
                play = True
            if deviceId == "":
                deviceId = None
            if deviceId is None or deviceId == "*":
                deviceId = PlayerDevice.GetIdFromSelectItem(
                    self.data.OptionDeviceDefault
                )

            # save current source in the event of an exception.
            saveSource = self._attr_source

            # get current Spotify Connect player state.
            self._playerState, self._spotifyConnectDevice, self._sonosDevice = (
                self._GetPlayerPlaybackState()
            )

            # get current device name and id values (if any).
            currentDeviceName: str = self._playerState.Device.Name or ""
            currentDeviceId: str = self._playerState.Device.Id or ""
            _logsi.LogVerbose(
                "'%s': Transferring playback from source device name: '%s' (id=%s)"
                % (self.name, currentDeviceName, currentDeviceId)
            )

            # is there an active spotify connect device?
            # if so, then we will pause playback on the device before we transfer control
            # to the target device.
            if self._playerState.Device.Id is not None:
                # capture (and ignore) any errors, in case the device is not responsive.
                try:
                    # pause playback based on device type.
                    if self._sonosDevice is not None:
                        _logsi.LogVerbose(
                            "'%s': Sonos device is active; issuing command to PAUSE Sonos player name '%s'"
                            % (self.name, self._playerState.Device.Name)
                        )
                        self._sonosDevice.pause()

                        # give SoCo api time to process the change.
                        if delay > 0:
                            _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                            time.sleep(delay)

                    else:
                        # for everything else, just use the Spotify Web API.
                        if self._playerState.IsPlaying:
                            self.data.spotifyClient.PlayerMediaPause(
                                self._playerState.Device.Id, delay
                            )

                except Exception as ex:
                    _logsi.LogException(
                        "'%s': Exception occurred while pausing device '%s' (ignored)"
                        % (self.name, self._playerState.Device.Name),
                        ex,
                        logToSystemLogger=False,
                    )

            # get target device reference from cached list of Spotify Connect devices.
            scDevices: SpotifyConnectDevices = (
                self.data.spotifyClient.GetSpotifyConnectDevices(
                    refresh=refreshDeviceList
                )
            )
            scDevice: SpotifyConnectDevice = scDevices.GetDeviceByName(deviceId)
            if scDevice is None:
                scDevice = scDevices.GetDeviceById(deviceId)

            # trace.
            if scDevice is not None:
                _logsi.LogVerbose(
                    "'%s': Transferring playback to target device name: '%s'"
                    % (self.name, scDevice.Title)
                )

            # transfer playback based on device type.
            if (scDevice is not None) and (scDevice.DeviceInfo.IsBrandSonos):
                # create Sonos device controller.
                _logsi.LogVerbose(
                    "'%s': Target device is a Sonos device; creating SoCo Controller instance for Sonos device '%s' ('%s')"
                    % (
                        self.name,
                        scDevice.DiscoveryResult.HostIpAddress,
                        scDevice.DeviceInfo.RemoteName,
                    )
                )
                sonosDevice = SoCo(scDevice.DiscoveryResult.HostIpAddress)

                # trace.
                sonosMusicSource: str = sonosDevice.music_source
                _logsi.LogVerbose(
                    "'%s': Sonos device '%s' ('%s') music source: '%s'"
                    % (
                        self.name,
                        sonosDevice.ip_address,
                        sonosDevice.player_name,
                        sonosMusicSource,
                    )
                )

                # was the Sonos device music source set to Spotify Connect?
                # if not, then try to activate spotify connect on the Sonos device.
                if sonosMusicSource != "SPOTIFY_CONNECT":
                    _logsi.LogVerbose(
                        "'%s': Activating Spotify Connect music source on Sonos device '%s' ('%s')"
                        % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                    )
                    scDevice = self.data.spotifyClient.GetSpotifyConnectDevice(
                        scDevice.Name, refreshDeviceList=False, activateDevice=True
                    )

                    # at this point the Sonos device should be set to the SPOTIFY_CONNECT music source.
                    # note that we have to issue a transport play command to actually transfer control to the
                    # Sonos device though; just connecting to the device will not transfer control!
                    # we will issue the play command below, based on the current Sonos transport state.

                    # refresh sonos music source property value, as it will change after device activation.
                    sonosMusicSource = sonosDevice.music_source
                    _logsi.LogVerbose(
                        "'%s': Sonos device '%s' ('%s') music source (after activation): '%s'"
                        % (
                            self.name,
                            sonosDevice.ip_address,
                            sonosDevice.player_name,
                            sonosMusicSource,
                        )
                    )

                # get current Sonos transport status.
                sonosTransportInfo: dict = sonosDevice.get_current_transport_info()
                currentTransportState: str = sonosTransportInfo.get(
                    "current_transport_state", None
                )
                currentTransportStatus: str = sonosTransportInfo.get(
                    "current_transport_status", None
                )
                _logsi.LogVerbose(
                    "'%s': Sonos device '%s' ('%s') current_transport_state (before activation transfer): '%s' (Status=%s)"
                    % (
                        self.name,
                        sonosDevice.ip_address,
                        sonosDevice.player_name,
                        currentTransportState,
                        currentTransportStatus,
                    )
                )

                # was the Sonos device music source set to Spotify Connect?
                if sonosMusicSource == "SPOTIFY_CONNECT":
                    _logsi.LogVerbose(
                        "'%s': Sonos device music source is currently set to SPOTIFY_CONNECT"
                        % (self.name)
                    )

                    # issue a transport play command to actually transfer control to the Sonos device.
                    _logsi.LogVerbose(
                        "'%s': Issuing transport command to transfer Sonos device '%s' ('%s'): PLAY"
                        % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                    )
                    sonosDevice.play()

                    # give SoCo api time to process the change.
                    if delay > 0:
                        _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                        time.sleep(delay)

                    # get current Sonos transport status.
                    sonosTransportInfo: dict = sonosDevice.get_current_transport_info()
                    currentTransportState: str = sonosTransportInfo.get(
                        "current_transport_state", None
                    )
                    currentTransportStatus: str = sonosTransportInfo.get(
                        "current_transport_status", None
                    )
                    _logsi.LogVerbose(
                        "'%s': Sonos device '%s' ('%s') current_transport_state (after activation transfer): '%s' (Status=%s)"
                        % (
                            self.name,
                            sonosDevice.ip_address,
                            sonosDevice.player_name,
                            currentTransportState,
                            currentTransportStatus,
                        )
                    )

                    # stop / start play as requested.
                    if currentTransportState == "PLAYING":
                        if play == False:
                            _logsi.LogVerbose(
                                "'%s': Issuing command to Sonos device '%s' ('%s'): PAUSE"
                                % (
                                    self.name,
                                    sonosDevice.ip_address,
                                    sonosDevice.player_name,
                                )
                            )
                            sonosDevice.pause()
                    elif currentTransportState in [
                        "PAUSED_PLAYBACK",
                        "STOPPED",
                        "TRANSITIONING",
                    ]:
                        if play == True:
                            _logsi.LogVerbose(
                                "'%s': Issuing command to Sonos device '%s' ('%s'): PLAY"
                                % (
                                    self.name,
                                    sonosDevice.ip_address,
                                    sonosDevice.player_name,
                                )
                            )
                            sonosDevice.play()

                    # give SoCo api time to process the change.
                    if delay > 0:
                        _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                        time.sleep(delay)

                # was source device playing anything?
                elif self._playerState.Item is None:
                    _logsi.LogVerbose(
                        "'%s': Spotify Web API PlayerState Item reference not set (nothing is playing)"
                        % (self.name)
                    )

                    # source device is not playing anything, so just issue a play command to the Sonos device
                    # to let it choose what to play.
                    _logsi.LogVerbose(
                        "'%s': Issuing command to Sonos device '%s' ('%s'): PLAY"
                        % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                    )
                    sonosDevice.play()

                    # give SoCo api time to process the change.
                    if delay > 0:
                        _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                        time.sleep(delay)

                else:
                    _logsi.LogVerbose(
                        "'%s': Sonos device music source is NOT set to Spotify Connect; "
                        % (self.name)
                    )

                    # at this point the source device is playing something, but the target Sonos device is not
                    # set to the SPOTIFY_CONNECT music source.  we will create a local queue on the target Sonos
                    # device with what was playing on the source device.  we will then start play on the local queue.
                    # note that this will not behave the same on the target device, as it is playing from a local
                    # queue instead of the Spotify Connect queue.
                    _logsi.LogVerbose(
                        "'%s': Creating local queue from source playerstate for Sonos device '%s' ('%s')"
                        % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                    )

                    # retrieve spotify web api player queue - this includes the currently playing item, as well
                    # as the first 20 items from the queue.
                    queue: PlayerQueueInfo = (
                        self.data.spotifyClient.GetPlayerQueueInfo()
                    )

                    # build a list of all queue item uri's, adding the currently playing item first.
                    arrUris: list[str] = []
                    arrUris.append(self._playerState.Item.Uri)
                    if queue.QueueCount > 0:
                        queueTrack: Track
                        for queueTrack in queue.Queue:
                            arrUris.append(queueTrack.Uri)

                    # build the Sonos local queue, adding all Spotify Web API player queue items.
                    sonosDevice = SoCo(scDevice.DiscoveryResult.HostIpAddress)
                    _logsi.LogVerbose(
                        "'%s': Issuing command to Sonos device '%s' ('%s'): CLEAR_QUEUE"
                        % (self.name, sonosDevice.ip_address, sonosDevice.player_name)
                    )
                    sonosDevice.clear_queue()
                    sharelink = ShareLinkPlugin(sonosDevice)
                    for uri in arrUris:
                        _logsi.LogVerbose(
                            "'%s': Issuing command to Sonos device '%s' ('%s'): ADD_SHARE_LINK_TO_QUEUE (uri=%s)"
                            % (
                                self.name,
                                sonosDevice.ip_address,
                                sonosDevice.player_name,
                                uri,
                            )
                        )
                        sharelink.add_share_link_to_queue(uri)
                    _logsi.LogVerbose(
                        "'%s': Issuing command to Sonos device '%s' ('%s'): PLAY_FROM_QUEUE (index=%s)"
                        % (
                            self.name,
                            sonosDevice.ip_address,
                            sonosDevice.player_name,
                            0,
                        )
                    )
                    sonosDevice.play_from_queue(index=0)

                    # give SoCo api time to process the change.
                    if delay > 0:
                        _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                        time.sleep(delay)

                    # find position of currently playing track.
                    sonosPosition: str = positionHMS_fromMilliSeconds(
                        self._playerState.ProgressMS
                    )  # convert from milliseconds to Sonos H:MM:SS format
                    _logsi.LogVerbose(
                        "'%s': Issuing command to Sonos device '%s' ('%s'): SEEK (position=%s)"
                        % (
                            self.name,
                            sonosDevice.ip_address,
                            sonosDevice.player_name,
                            sonosPosition,
                        )
                    )
                    sonosDevice.seek(position=sonosPosition)

                    # give SoCo api time to process the change.
                    if delay > 0:
                        _logsi.LogVerbose(TRACE_MSG_DELAY_DEVICE_SONOS % delay)
                        time.sleep(delay)

            else:
                # for everything else, just use the Spotify Web API.
                # note that we refreshed the device list earlier in this method, so don't have the api refresh it again.
                self.data.spotifyClient.PlayerTransferPlayback(
                    deviceId, play, delay, refreshDeviceList=False
                )

            # get current Spotify Connect player state.
            self._playerState, self._spotifyConnectDevice, self._sonosDevice = (
                self._GetPlayerPlaybackState()
            )

            # reset internal SonosDevice to the SonosDevice that we just created (if transferring to Sonos).
            self._sonosDevice = sonosDevice

            # set the selected source.
            if scDevice is not None:
                self._attr_source = scDevice.Name
                _logsi.LogVerbose(
                    "'%s': Selected source was changed to: '%s'"
                    % (self.name, self._attr_source)
                )

            # media player command was processed, so force a scan window at the next interval.
            _logsi.LogVerbose(
                "'%s': Processed a transfer playback command - forcing a playerState scan window for the next %d updates"
                % (self.name, SPOTIFY_SCAN_INTERVAL_COMMAND - 1)
            )
            self._commandScanInterval = SPOTIFY_SCAN_INTERVAL_COMMAND

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            # assume source could not be transferred if an exception occurred.
            _logsi.LogVerbose(
                "'%s': SpotifyApiError while transferring playback source; resetting source to: '%s'"
                % (self.name, self._attr_source)
            )
            self._attr_source = saveSource
            raise HomeAssistantError(ex.Message)

        except SpotifyWebApiError as ex:
            # assume source could not be transferred if an exception occurred.
            _logsi.LogVerbose(
                "'%s': SpotifyWebApiError while transferring playback source; resetting source to: '%s'"
                % (self.name, self._attr_source)
            )
            self._attr_source = saveSource
            raise HomeAssistantError(ex.Message)

        except Exception as ex:
            # assume source could not be transferred if an exception occurred.
            _logsi.LogVerbose(
                "'%s': Exception while transferring playback source; resetting source to: '%s'"
                % (self.name, self._attr_source)
            )
            self._attr_source = saveSource

            # trace.
            _logsi.LogException(None, ex)
            raise HomeAssistantError(str(ex)) from ex

        finally:
            # set default device name to use for player transport functions that are executed
            # but there is no active Spotify player device.
            self.data.spotifyClient.DefaultDeviceId = self._attr_source

            # update ha state.
            self.schedule_update_ha_state(force_refresh=False)

            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_playlist_cover_image_add(
        self,
        playlistId: str,
        imagePath: str,
    ) -> None:
        """
        Replace the image used to represent a specific playlist.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                Example: `5v5ETK9WFXAnGQ3MRubKuE`
            imagePath (str):
                The fully-qualified path of the image to be uploaded.
                The image must be in JPEG format, and cannot exceed 256KB in Base64 encoded size.
        """
        apiMethodName: str = "service_spotify_playlist_cover_image_add"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            apiMethodParms.AppendKeyValue("imagePath", imagePath)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Playlist Add Cover Image Service",
                apiMethodParms,
            )

            # add playlist cover image.
            _logsi.LogVerbose("Adding cover image to Spotify playlist")
            self.data.spotifyClient.AddPlaylistCoverImage(playlistId, imagePath)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_playlist_change(
        self,
        playlistId: str,
        name: str = None,
        description: str = None,
        public: bool = True,
        collaborative: bool = False,
        imagePath: str = None,
    ) -> None:
        """
        Change a playlist's details (name, description, and public / private state).

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                Example: `5AC9ZXA7nJ7oGWO911FuDG`
            name (str):
                The updated name for the playlist, for example "My New Playlist Title"
                This name does not need to be unique; a user may have several playlists with
                the same name.
            description (str):
                The updated playlist description, as displayed in Spotify Clients and in the Web API.
            public (bool):
                If true, the playlist will be public; if false, it will be private.
            collaborative (bool):
                If true, the playlist will become collaborative and other users will be able to modify
                the playlist in their Spotify client.
                Note: You can only set collaborative to true on non-public playlists.
            imagePath (str):
                A fully-qualified path of an image to display for the playlist.
                The image must be in JPEG format, and cannot exceed 256KB in Base64 encoded size.
                Specify null if you do not wish to update the existing playlist image.
        """
        apiMethodName: str = "service_spotify_playlist_change"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            apiMethodParms.AppendKeyValue("name", name)
            apiMethodParms.AppendKeyValue("description", description)
            apiMethodParms.AppendKeyValue("public", public)
            apiMethodParms.AppendKeyValue("collaborative", collaborative)
            apiMethodParms.AppendKeyValue("imagePath", imagePath)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Playlist Change Service", apiMethodParms
            )

            # create Spotify playlist.
            _logsi.LogVerbose("Changing Spotify Playlist Details")
            self.data.spotifyClient.ChangePlaylistDetails(
                playlistId, name, description, public, collaborative, imagePath
            )

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_playlist_create(
        self,
        userId: str,
        name: str = None,
        description: str = None,
        public: bool = True,
        collaborative: bool = False,
        imagePath: str = None,
    ) -> dict:
        """
        Create an empty playlist for a Spotify user.

        This method requires the `playlist-modify-public` and `playlist-modify-private` scope.

        Args:
            userId (str):
                The user's Spotify user ID.
                Example: `32k99y2kg5lnn3mxhtmd2bpdkjfu`
            name (str):
                The name for the new playlist, for example "My Playlist".
                This name does not need to be unique; a user may have several playlists with
                the same name.
            description (str):
                The playlist description, as displayed in Spotify Clients and in the Web API.
            public (bool):
                If true, the playlist will be public; if false, it will be private.
                To be able to create private playlists, the user must have granted the
                `playlist-modify-private` scope.
                Defaults to true.
            collaborative (bool):
                If true, the playlist will be collaborative.
                Note: to create a collaborative playlist you must also set public to false.
                To create collaborative playlists you must have granted `playlist-modify-private`
                and `playlist-modify-public` scope.
                Defaults to false.
            imagePath (str):
                A fully-qualified path of an image to display for the playlist.
                The image must be in JPEG format, and cannot exceed 256KB in Base64 encoded size.
                Omit this argument if you do not wish to add a playlist image.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `Playlist` object that contains the playlist details.
        """
        apiMethodName: str = "service_spotify_playlist_create"
        apiMethodParms: SIMethodParmListContext = None
        result: Playlist = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("userId", userId)
            apiMethodParms.AppendKeyValue("name", name)
            apiMethodParms.AppendKeyValue("description", description)
            apiMethodParms.AppendKeyValue("public", public)
            apiMethodParms.AppendKeyValue("collaborative", collaborative)
            apiMethodParms.AppendKeyValue("imagePath", imagePath)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Playlist Create Service", apiMethodParms
            )

            # create Spotify playlist.
            _logsi.LogVerbose("Creating Spotify Playlist")
            result = self.data.spotifyClient.CreatePlaylist(
                userId, name, description, public, collaborative, imagePath
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_playlist_items_add(
        self,
        playlistId: str,
        uris: str,
        position: int = None,
    ) -> dict:
        """
        Add one or more items to a user's playlist.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                Example: `5AC9ZXA7nJ7oGWO911FuDG`
            uris (str):
                A comma-separated list of Spotify URIs to add; can be track or episode URIs.
                Example: `spotify:track:4iV5W9uYEdYUVa79Axb7Rh,spotify:episode:512ojhOuo1ktJprKbVcKyQ`.
                A maximum of 100 items can be specified in one request.
                If nothing is specified, then the track (or episode) uri currently playing is used.
            position (int):
                The position to insert the items, a zero-based index.
                For example, to insert the items in the first position: position=0;
                to insert the items in the third position: position=2.
                If omitted, the items will be appended to the playlist.
                Items are added in the order they are listed in the `uris` argument.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A snapshot ID for the updated playlist.
        """
        apiMethodName: str = "service_spotify_playlist_items_add"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            apiMethodParms.AppendKeyValue("uris", uris)
            apiMethodParms.AppendKeyValue("position", position)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Playlist Add Items Service", apiMethodParms
            )

            # validation - if position is -1 then set it to None (treat as append).
            if isinstance(position, int) and position == -1:
                position = None

            # add items to Spotify playlist.
            _logsi.LogVerbose("Adding item(s) to Spotify playlist")
            result: str = self.data.spotifyClient.AddPlaylistItems(
                playlistId, uris, position
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_playlist_items_clear(
        self,
        playlistId: str,
    ) -> dict:
        """
        Removes (clears) all items from a user's playlist.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                Example: `5AC9ZXA7nJ7oGWO911FuDG`

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A snapshot ID for the updated playlist.
        """
        apiMethodName: str = "service_spotify_playlist_items_clear"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Playlist Clear Items Service", apiMethodParms
            )

            # clear items from Spotify playlist.
            _logsi.LogVerbose("Clearing item(s) from Spotify playlist")
            result: str = self.data.spotifyClient.ClearPlaylistItems(playlistId)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_playlist_items_remove(
        self,
        playlistId: str = None,
        uris: str = None,
        snapshotId: str = None,
    ) -> dict:
        """
        Remove one or more items from a user's playlist.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                Example: `5AC9ZXA7nJ7oGWO911FuDG`
            uris (str):
                A comma-separated list of Spotify URIs to remove; can be track or episode URIs.
                Example: `spotify:track:4iV5W9uYEdYUVa79Axb7Rh,spotify:episode:512ojhOuo1ktJprKbVcKyQ`.
                A maximum of 100 items can be specified in one request.
                If nothing is specified, then the track (or episode) uri currently playing is used.
            snapshotId (str):
                The playlist's snapshot ID against which you want to make the changes.
                The API will validate that the specified items exist and in the specified positions and
                make the changes, even if more recent changes have been made to the playlist.
                If null, the current playlist is updated.
                Default is null.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A snapshot ID for the updated playlist.
        """
        apiMethodName: str = "service_spotify_playlist_items_remove"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            apiMethodParms.AppendKeyValue("uris", uris)
            apiMethodParms.AppendKeyValue("snapshotId", snapshotId)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Playlist Remove Items Service", apiMethodParms
            )

            # remove items from Spotify playlist.
            _logsi.LogVerbose("Removing item(s) from Spotify playlist")
            result: str = self.data.spotifyClient.RemovePlaylistItems(
                playlistId, uris, snapshotId
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_playlist_items_reorder(
        self,
        playlistId: str,
        rangeStart: int,
        insertBefore: int,
        rangeLength: int = 1,
        snapshotId: str = None,
    ) -> dict:
        """
        Reorder items in a user's playlist.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                Example: `5AC9ZXA7nJ7oGWO911FuDG`
            rangeStart (int):
                The position of the first item to be reordered.
                This is a one-offset integer (NOT zero-offset).
            insertBefore (int):
                The position where the items should be inserted.
                To reorder the items to the end of the playlist, simply set `insertBefore`
                to the position after the last item.
                This is a one-offset integer (NOT zero-offset).
            rangeLength (int):
                The amount of items to be reordered; defaults to 1 if not set.
                The range of items to be reordered begins from the `rangeStart` position, and includes
                the `rangeLength` subsequent items.
            snapshotId (str):
                The playlist's snapshot ID against which you want to make the changes.
                If null, the current playlist is updated.
                Example: `MTk3LGEzMjUwZGYwODljNmI5ZjAxZTRjZThiOGI4NzZhM2U5M2IxOWUyMDQ`
                Default is null.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A snapshot ID for the updated playlist.
        """
        apiMethodName: str = "service_spotify_playlist_items_reorder"
        apiMethodParms: SIMethodParmListContext = None
        result: dict = {}

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            apiMethodParms.AppendKeyValue("rangeStart", rangeStart)
            apiMethodParms.AppendKeyValue("insertBefore", insertBefore)
            apiMethodParms.AppendKeyValue("rangeLength", rangeLength)
            apiMethodParms.AppendKeyValue("snapshotId", snapshotId)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Reorder Playlist Items Service",
                apiMethodParms,
            )

            # reorder playlist items.
            _logsi.LogVerbose("Reorder Spotify Playlist Items")
            result = self.data.spotifyClient.ReorderPlaylistItems(
                playlistId, rangeStart, insertBefore, rangeLength, snapshotId
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_playlist_items_replace(
        self,
        playlistId: str = None,
        uris: str = None,
    ) -> dict:
        """
        Replace one or more items in a user's playlist. Replacing items in a playlist will
        overwrite its existing items.

        This method can also be used to clear a playlist.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                Example: `5AC9ZXA7nJ7oGWO911FuDG`
            uris (str):
                A comma-separated list of Spotify URIs to replace; can be track or episode URIs.
                Example: `spotify:track:4iV5W9uYEdYUVa79Axb7Rh,spotify:episode:26c0zVyOv1lzfYpBXdh1zC`.
                A maximum of 100 items can be specified in one request.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A snapshot ID for the updated playlist.
        """
        apiMethodName: str = "service_spotify_playlist_items_replace"
        apiMethodParms: SIMethodParmListContext = None
        result: dict = {}

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            apiMethodParms.AppendKeyValue("uris", uris)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Replace Playlist Items Service",
                apiMethodParms,
            )

            # replace playlist items.
            _logsi.LogVerbose("Replace Spotify Playlist Items")
            result = self.data.spotifyClient.ReplacePlaylistItems(playlistId, uris)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result,
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_remove_album_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Remove one or more albums from the current user's 'Your Library'.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the albums.
                Maximum: 50 IDs.
                Example: `6vc9OTcyd3hyzabCmsdnwE,382ObEPsp2rxGrnsizN5TX`
                If null, the currently playing track album uri id value is used.
        """
        apiMethodName: str = "service_spotify_remove_album_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Remove Album Favorites Service",
                apiMethodParms,
            )

            # remove items from Spotify album favorites.
            _logsi.LogVerbose("Removing items(s) from Spotify Album Favorites")
            self.data.spotifyClient.RemoveAlbumFavorites(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_remove_audiobook_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Remove one or more audiobooks from the current user's 'Your Library'.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the audiobooks.
                Maximum: 50 IDs.
                Example: `3PFyizE2tGCSRLusl2Qizf,7iHfbu1YPACw6oZPAFJtqe`
                If null, the currently playing audiobook uri id value is used.
        """
        apiMethodName: str = "service_spotify_remove_audiobook_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Remove Audiobook Favorites Service",
                apiMethodParms,
            )

            # remove items from Spotify audiobook favorites.
            _logsi.LogVerbose("Removing items(s) from Spotify Audiobook Favorites")
            self.data.spotifyClient.RemoveAudiobookFavorites(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_remove_episode_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Remove one or more episodes from the current user's 'Your Library'.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the episodes.
                Maximum: 50 IDs.
                Example: `3F97boSWlXi8OzuhWClZHQ,1hPX5WJY6ja6yopgVPBqm4`
                If null, the currently playing episode uri id value is used.
        """
        apiMethodName: str = "service_spotify_remove_episode_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Remove Episode Favorites Service",
                apiMethodParms,
            )

            # remove items from Spotify episode favorites.
            _logsi.LogVerbose("Removing items(s) from Spotify Episode Favorites")
            self.data.spotifyClient.RemoveEpisodeFavorites(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_remove_show_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Remove one or more shows from the current user's 'Your Library'.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the shows.
                Maximum: 50 IDs.
                Example: `6kAsbP8pxwaU2kPibKTuHE,4rOoJ6Egrf8K2IrywzwOMk`
                If null, the currently playing show uri id value is used.
        """
        apiMethodName: str = "service_spotify_remove_show_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Remove Show Favorites Service", apiMethodParms
            )

            # remove items from Spotify show favorites.
            _logsi.LogVerbose("Removing items(s) from Spotify Show Favorites")
            self.data.spotifyClient.RemoveShowFavorites(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_remove_track_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Remove one or more tracks from the current user's 'Your Library'.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the tracks.
                Maximum: 50 IDs.
                Example: `1kWUud3vY5ij5r62zxpTRy,4eoYKv2kDwJS7gRGh5q6SK`
                If null, the currently playing context uri id value is used.
        """
        apiMethodName: str = "service_spotify_remove_track_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Remove Track Favorites Service",
                apiMethodParms,
            )

            # remove items from Spotify track favorites.
            _logsi.LogVerbose("Removing items(s) from Spotify Track Favorites")
            self.data.spotifyClient.RemoveTrackFavorites(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_save_album_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Save one or more albums to the current user's 'Your Library'.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the albums.
                Maximum: 50 IDs.
                Example: `6vc9OTcyd3hyzabCmsdnwE,382ObEPsp2rxGrnsizN5TX`
                If null, the currently playing track album uri id value is used.
        """
        apiMethodName: str = "service_spotify_save_album_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Save Album Favorites Service", apiMethodParms
            )

            # save items to Spotify album favorites.
            _logsi.LogVerbose("Saving items(s) to Spotify Album Favorites")
            self.data.spotifyClient.SaveAlbumFavorites(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_save_audiobook_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Save one or more audiobook to the current user's 'Your Library'.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the audiobooks.
                Maximum: 50 IDs.
                Example: `3PFyizE2tGCSRLusl2Qizf,7iHfbu1YPACw6oZPAFJtqe`
                If null, the currently playing audiobook uri id value is used.
        """
        apiMethodName: str = "service_spotify_save_audiobook_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Save Audiobook Favorites Service",
                apiMethodParms,
            )

            # save items to Spotify audiobook favorites.
            _logsi.LogVerbose("Saving items(s) to Spotify Audiobook Favorites")
            self.data.spotifyClient.SaveAudiobookFavorites(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_save_episode_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Save one or more episodes to the current user's 'Your Library'.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the episode.
                Maximum: 50 IDs.
                Example: `3F97boSWlXi8OzuhWClZHQ,1hPX5WJY6ja6yopgVPBqm4`
                If null, the currently playing episode uri id value is used.
        """
        apiMethodName: str = "service_spotify_save_episode_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Save Episode Favorites Service",
                apiMethodParms,
            )

            # save items to Spotify episode favorites.
            _logsi.LogVerbose("Saving items(s) to Spotify Episode Favorites")
            self.data.spotifyClient.SaveEpisodeFavorites(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_save_show_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Save one or more show to the current user's 'Your Library'.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the shows.
                Maximum: 50 IDs.
                Example: `6kAsbP8pxwaU2kPibKTuHE,4rOoJ6Egrf8K2IrywzwOMk`
                If null, the currently playing show uri id value is used.
        """
        apiMethodName: str = "service_spotify_save_show_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Save Show Favorites Service", apiMethodParms
            )

            # save items to Spotify show favorites.
            _logsi.LogVerbose("Saving items(s) to Spotify Show Favorites")
            self.data.spotifyClient.SaveShowFavorites(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_save_track_favorites(
        self,
        ids: str = None,
    ) -> None:
        """
        Save one or more tracks to the current user's 'Your Library'.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the tracks.
                Maximum: 50 IDs.
                Example: `1kWUud3vY5ij5r62zxpTRy,4eoYKv2kDwJS7gRGh5q6SK`
                If null, the currently playing context uri id value is used.
        """
        apiMethodName: str = "service_spotify_save_track_favorites"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Save Track Favorites Service", apiMethodParms
            )

            # save items to Spotify track favorites.
            _logsi.LogVerbose("Saving items(s) to Spotify Track Favorites")
            self.data.spotifyClient.SaveTrackFavorites(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_search_albums(
        self,
        criteria: str,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        includeExternal: str = None,
        limitTotal: int = None,
    ) -> dict:
        """
        Get Spotify catalog information about albums that match a keyword string.

        Args:
            criteria (str):
                Your search query.
                You can narrow down your search using field filters.
                The available filters are album, artist, track, year, upc, tag:hipster, tag:new,
                isrc, and genre. Each field filter only applies to certain result types.
                The artist and year filters can be used while searching albums, artists and tracks.
                You can filter on a single year or a range (e.g. 1955-1960).
                The album filter can be used while searching albums and tracks.
                The genre filter can be used while searching artists and tracks.
                The isrc and track filters can be used while searching tracks.
                The upc, tag:new and tag:hipster filters can only be used while searching albums.
                The tag:new filter will return albums released in the past two weeks and tag:hipster
                can be used to return only albums with the lowest 10% popularity.
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The page index offset of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).  Range: 0 to 1000.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            includeExternal (str):
                If "audio" is specified it signals that the client can play externally hosted audio content, and
                marks the content as playable in the response. By default externally hosted audio content is marked
                as unplayable in the response.
                Allowed values: "audio"
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `AlbumPageSimplified` object of matching results.
        """
        apiMethodName: str = "service_spotify_search_albums"
        apiMethodParms: SIMethodParmListContext = None
        result: SearchResponse = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("criteria", criteria)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("includeExternal", includeExternal)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Search Albums Service", apiMethodParms
            )

            # get Spotify catalog information about Albums that match a keyword string.
            _logsi.LogVerbose("Searching Spotify Albums for criteria")
            searchResponse: SearchResponse = self.data.spotifyClient.SearchAlbums(
                criteria, limit, offset, market, includeExternal, limitTotal
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": searchResponse.Albums.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_search_artists(
        self,
        criteria: str,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        includeExternal: str = None,
        limitTotal: int = None,
    ) -> dict:
        """
        Get Spotify catalog information about artists that match a keyword string.

        Args:
            criteria (str):
                Your search query.
                You can narrow down your search using field filters.
                The available filters are album, artist, track, year, upc, tag:hipster, tag:new,
                isrc, and genre. Each field filter only applies to certain result types.
                The artist and year filters can be used while searching albums, artists and tracks.
                You can filter on a single year or a range (e.g. 1955-1960).
                The album filter can be used while searching albums and tracks.
                The genre filter can be used while searching artists and tracks.
                The isrc and track filters can be used while searching tracks.
                The upc, tag:new and tag:hipster filters can only be used while searching albums.
                The tag:new filter will return albums released in the past two weeks and tag:hipster
                can be used to return only albums with the lowest 10% popularity.
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The page index offset of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).  Range: 0 to 1000.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            includeExternal (str):
                If "audio" is specified it signals that the client can play externally hosted audio content, and
                marks the content as playable in the response. By default externally hosted audio content is marked
                as unplayable in the response.
                Allowed values: "audio"
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `ArtistPage` object of matching results.
        """
        apiMethodName: str = "service_spotify_search_artists"
        apiMethodParms: SIMethodParmListContext = None
        result: SearchResponse = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("criteria", criteria)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("includeExternal", includeExternal)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Search Artists Service", apiMethodParms
            )

            # get Spotify catalog information about Artists that match a keyword string.
            _logsi.LogVerbose("Searching Spotify Artists for criteria")
            searchResponse: SearchResponse = self.data.spotifyClient.SearchArtists(
                criteria, limit, offset, market, includeExternal, limitTotal
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": searchResponse.Artists.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_search_audiobooks(
        self,
        criteria: str,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        includeExternal: str = None,
        limitTotal: int = None,
    ) -> dict:
        """
        Get Spotify catalog information about audiobooks that match a keyword string.

        Args:
            criteria (str):
                Your search query.
                You can narrow down your search using field filters.
                The available filters are album, artist, track, year, upc, tag:hipster, tag:new,
                isrc, and genre. Each field filter only applies to certain result types.
                The artist and year filters can be used while searching albums, artists and tracks.
                You can filter on a single year or a range (e.g. 1955-1960).
                The album filter can be used while searching albums and tracks.
                The genre filter can be used while searching artists and tracks.
                The isrc and track filters can be used while searching tracks.
                The upc, tag:new and tag:hipster filters can only be used while searching albums.
                The tag:new filter will return albums released in the past two weeks and tag:hipster
                can be used to return only albums with the lowest 10% popularity.
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The page index offset of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).  Range: 0 to 1000.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            includeExternal (str):
                If "audio" is specified it signals that the client can play externally hosted audio content, and
                marks the content as playable in the response. By default externally hosted audio content is marked
                as unplayable in the response.
                Allowed values: "audio"
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `AudiobookPageSimplified` object of matching results.
        """
        apiMethodName: str = "service_spotify_search_audiobooks"
        apiMethodParms: SIMethodParmListContext = None
        result: SearchResponse = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("criteria", criteria)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("includeExternal", includeExternal)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Search Audiobooks Service", apiMethodParms
            )

            # get Spotify catalog information about Audiobooks that match a keyword string.
            _logsi.LogVerbose("Searching Spotify Audiobooks for criteria")
            searchResponse: SearchResponse = self.data.spotifyClient.SearchAudiobooks(
                criteria, limit, offset, market, includeExternal, limitTotal
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": searchResponse.Audiobooks.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_search_episodes(
        self,
        criteria: str,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        includeExternal: str = None,
        limitTotal: int = None,
    ) -> dict:
        """
        Get Spotify catalog information about episodes that match a keyword string.

        Args:
            criteria (str):
                Your search query.
                You can narrow down your search using field filters.
                The available filters are album, artist, track, year, upc, tag:hipster, tag:new,
                isrc, and genre. Each field filter only applies to certain result types.
                The artist and year filters can be used while searching albums, artists and tracks.
                You can filter on a single year or a range (e.g. 1955-1960).
                The album filter can be used while searching albums and tracks.
                The genre filter can be used while searching artists and tracks.
                The isrc and track filters can be used while searching tracks.
                The upc, tag:new and tag:hipster filters can only be used while searching albums.
                The tag:new filter will return albums released in the past two weeks and tag:hipster
                can be used to return only albums with the lowest 10% popularity.
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The page index offset of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).  Range: 0 to 1000.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            includeExternal (str):
                If "audio" is specified it signals that the client can play externally hosted audio content, and
                marks the content as playable in the response. By default externally hosted audio content is marked
                as unplayable in the response.
                Allowed values: "audio"
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `EpisodePageSimplified` object of matching results.
        """
        apiMethodName: str = "service_spotify_search_episodes"
        apiMethodParms: SIMethodParmListContext = None
        result: SearchResponse = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("criteria", criteria)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("includeExternal", includeExternal)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Search Episodes Service", apiMethodParms
            )

            # get Spotify catalog information about Episodes that match a keyword string.
            _logsi.LogVerbose("Searching Spotify Episodes for criteria")
            searchResponse: SearchResponse = self.data.spotifyClient.SearchEpisodes(
                criteria, limit, offset, market, includeExternal, limitTotal
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": searchResponse.Episodes.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_search_playlists(
        self,
        criteria: str,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        includeExternal: str = None,
        limitTotal: int = None,
    ) -> dict:
        """
        Get Spotify catalog information about playlists that match a keyword string.

        Args:
            criteria (str):
                Your search query.
                You can narrow down your search using field filters.
                The available filters are album, artist, track, year, upc, tag:hipster, tag:new,
                isrc, and genre. Each field filter only applies to certain result types.
                The artist and year filters can be used while searching albums, artists and tracks.
                You can filter on a single year or a range (e.g. 1955-1960).
                The album filter can be used while searching albums and tracks.
                The genre filter can be used while searching artists and tracks.
                The isrc and track filters can be used while searching tracks.
                The upc, tag:new and tag:hipster filters can only be used while searching albums.
                The tag:new filter will return albums released in the past two weeks and tag:hipster
                can be used to return only albums with the lowest 10% popularity.
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The page index offset of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).  Range: 0 to 1000.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            includeExternal (str):
                If "audio" is specified it signals that the client can play externally hosted audio content, and
                marks the content as playable in the response. By default externally hosted audio content is marked
                as unplayable in the response.
                Allowed values: "audio"
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `PlaylistPageSimplified` object of matching results.
        """
        apiMethodName: str = "service_spotify_search_playlists"
        apiMethodParms: SIMethodParmListContext = None
        result: SearchResponse = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("criteria", criteria)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("includeExternal", includeExternal)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Search Playlists Service", apiMethodParms
            )

            # get Spotify catalog information about Playlists that match a keyword string.
            _logsi.LogVerbose("Searching Spotify Playlists for criteria")
            searchResponse: SearchResponse = self.data.spotifyClient.SearchPlaylists(
                criteria, limit, offset, market, includeExternal, limitTotal
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": searchResponse.Playlists.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_search_shows(
        self,
        criteria: str,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        includeExternal: str = None,
        limitTotal: int = None,
    ) -> dict:
        """
        Get Spotify catalog information about shows (aka. podcasts) that match a keyword string.

        Args:
            criteria (str):
                Your search query.
                You can narrow down your search using field filters.
                The available filters are album, artist, track, year, upc, tag:hipster, tag:new,
                isrc, and genre. Each field filter only applies to certain result types.
                The artist and year filters can be used while searching albums, artists and tracks.
                You can filter on a single year or a range (e.g. 1955-1960).
                The album filter can be used while searching albums and tracks.
                The genre filter can be used while searching artists and tracks.
                The isrc and track filters can be used while searching tracks.
                The upc, tag:new and tag:hipster filters can only be used while searching albums.
                The tag:new filter will return albums released in the past two weeks and tag:hipster
                can be used to return only albums with the lowest 10% popularity.
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The page index offset of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).  Range: 0 to 1000.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            includeExternal (str):
                If "audio" is specified it signals that the client can play externally hosted audio content, and
                marks the content as playable in the response. By default externally hosted audio content is marked
                as unplayable in the response.
                Allowed values: "audio"
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An `ShowPageSimplified` object of matching results.
        """
        apiMethodName: str = "service_spotify_search_shows"
        apiMethodParms: SIMethodParmListContext = None
        result: SearchResponse = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("criteria", criteria)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("includeExternal", includeExternal)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Search Shows Service", apiMethodParms
            )

            # get Spotify catalog information about Episodes that match a keyword string.
            _logsi.LogVerbose("Searching Spotify Shows for criteria")
            searchResponse: SearchResponse = self.data.spotifyClient.SearchShows(
                criteria, limit, offset, market, includeExternal, limitTotal
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": searchResponse.Shows.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_search_tracks(
        self,
        criteria: str,
        limit: int = 20,
        offset: int = 0,
        market: str = None,
        includeExternal: str = None,
        limitTotal: int = None,
    ) -> dict:
        """
        Get Spotify catalog information about tracks that match a keyword string.

        Args:
            criteria (str):
                Your search query.
                You can narrow down your search using field filters.
                The available filters are album, artist, track, year, upc, tag:hipster, tag:new,
                isrc, and genre. Each field filter only applies to certain result types.
                The artist and year filters can be used while searching albums, artists and tracks.
                You can filter on a single year or a range (e.g. 1955-1960).
                The album filter can be used while searching albums and tracks.
                The genre filter can be used while searching artists and tracks.
                The isrc and track filters can be used while searching tracks.
                The upc, tag:new and tag:hipster filters can only be used while searching albums.
                The tag:new filter will return albums released in the past two weeks and tag:hipster
                can be used to return only albums with the lowest 10% popularity.
            limit (int):
                The maximum number of items to return in a page of items.
                Default: 20, Range: 1 to 50.
            offset (int):
                The page index offset of the first item to return.
                Use with limit to get the next set of items.
                Default: 0 (the first item).  Range: 0 to 1000.
            market (str):
                An ISO 3166-1 alpha-2 country code. If a country code is specified, only content that
                is available in that market will be returned.  If a valid user access token is specified
                in the request header, the country associated with the user account will take priority over
                this parameter.
                Note: If neither market or user country are provided, the content is considered unavailable for the client.
                Users can view the country that is associated with their account in the account settings.
                Example: `ES`
            includeExternal (str):
                If "audio" is specified it signals that the client can play externally hosted audio content, and
                marks the content as playable in the response. By default externally hosted audio content is marked
                as unplayable in the response.
                Allowed values: "audio"
            limitTotal (int):
                The maximum number of items to return for the request.
                If specified, this argument overrides the limit and offset argument values
                and paging is automatically used to retrieve all available items up to the
                maximum number specified.
                Default: None (disabled)

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `TrackPage` object of matching results.
        """
        apiMethodName: str = "service_spotify_search_tracks"
        apiMethodParms: SIMethodParmListContext = None
        result: SearchResponse = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("criteria", criteria)
            apiMethodParms.AppendKeyValue("limit", limit)
            apiMethodParms.AppendKeyValue("offset", offset)
            apiMethodParms.AppendKeyValue("market", market)
            apiMethodParms.AppendKeyValue("includeExternal", includeExternal)
            apiMethodParms.AppendKeyValue("limitTotal", limitTotal)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Search Tracks Service", apiMethodParms
            )

            # get Spotify catalog information about Playlists that match a keyword string.
            _logsi.LogVerbose("Searching Spotify Tracks for criteria")
            searchResponse: SearchResponse = self.data.spotifyClient.SearchTracks(
                criteria, limit, offset, market, includeExternal, limitTotal
            )

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": searchResponse.Tracks.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_unfollow_artists(
        self,
        ids: str = None,
    ) -> None:
        """
        Remove the current user as a follower of one or more artists.

        Args:
            ids (str):
                A comma-separated list of the Spotify IDs for the artists.
                Maximum: 50 IDs.
                Example: `2CIMQHirSU0MQqyYHq0eOx,1IQ2e1buppatiN1bxUVkrk`
                If null, the currently playing track artist uri id value is used.
        """
        apiMethodName: str = "service_spotify_unfollow_artists"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Unfollow Artists Service", apiMethodParms
            )

            # unfollow artist(s).
            _logsi.LogVerbose("Removing items(s) from Spotify Artist Favorites")
            self.data.spotifyClient.UnfollowArtists(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_unfollow_playlist(
        self,
        playlistId: str = None,
    ) -> None:
        """
        Remove the current user as a follower of a playlist.

        Args:
            playlistId (str):
                The Spotify ID of the playlist.
                Example: `3cEYpjA9oz9GiPac4AsH4n`
                If null, the currently playing playlist uri id value is used.
        """
        apiMethodName: str = "service_spotify_unfollow_playlist"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("playlistId", playlistId)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Unfollow Playlist Service", apiMethodParms
            )

            # unfollow playlist.
            _logsi.LogVerbose("Removing items from Spotify Playlist Favorites")
            self.data.spotifyClient.UnfollowPlaylist(playlistId)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_unfollow_users(
        self,
        ids: str = None,
    ) -> None:
        """
        Remove the current user as a follower of one or more users.

        Args:
            ids (str):
                A comma-separated list of Spotify user IDs.
                A maximum of 50 IDs can be sent in one request.
                Example: `smedjan`
        """
        apiMethodName: str = "service_spotify_unfollow_users"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("ids", ids)
            _logsi.LogMethodParmList(
                SILevel.Verbose, "Spotify Unfollow Users Service", apiMethodParms
            )

            # unfollow user(s).
            _logsi.LogVerbose("Removing items(s) from Spotify Users Favorites")
            self.data.spotifyClient.UnfollowUsers(ids)

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_zeroconf_device_connect(
        self,
        username: str,
        password: str,
        loginid: str,
        hostIpv4Address: str,
        hostIpPort: str,
        cpath: str,
        version: str = "1.0",
        useSSL: bool = False,
        preDisconnect: bool = False,
        verifyDeviceListEntry: bool = False,
        delay: float = 0.50,
    ) -> dict:
        """
        Calls the `addUser` Spotify Zeroconf API endpoint to issue a call to SpConnectionLoginBlob.  If successful,
        the associated device id is added to the Spotify Connect active device list for the specified user account.

        Args:
            username (str):
                Spotify Connect user name to login with (e.g. "yourspotifyusername").
                This MUST match the account name (or one of them) that was used to configure Spotify Connect
                on the manufacturer device.
            password (str):
                Spotify Connect user password to login with.
            loginId (str):
                Spotify Connect login id to login with (e.g. "31l77fd87g8h9j00k89f07jf87ge").
                This is also known as the canonical user id value.
                This MUST be the value that relates to the `username` argument.
            hostIpv4Address (str):
                IPV4 address (as a string) at which the Spotify Connect Zeroconf API can be reached
                on the Spotify Connect device (e.g. "192.168.1.81").
            hostIpPort (int):
                Port number (as an integer) at which the Spotify Connect Zeroconf API can be reached
                on the Spotify Connect device (e.g. "8200").
            cpath (str):
                Spotify Connect Zeroconf API CPath property value (e.g. "/zc").
            version (str):
                Spotify Connect Zeroconf API version number that the device supports (e.g. "2.10.0").
                Default is '1.0'.
            useSSL (bool):
                True if the host device utilizes HTTPS Secure Sockets Layer (SSL) support;
                otherwise, False to utilize HTTP.
                Default is False (HTTP).
            preDisconnect (bool):
                True if a Disconnect should be made prior to the Connect call.  This will ensure that the
                active user is logged out, which must be done if switching user accounts;
                otherwise, False to not issue a Disconnect call.
                Default is False.
            verifyDeviceListEntry (bool):
                True to ensure that the device id is present in the Spotify Connect device list before
                issuing a call to Connect; otherwise, False to always call Connect to add the device.
                Default is False.
            delay (float):
                Time delay (in seconds) to wait AFTER issuing a command to the device.
                This delay will give the spotify zeroconf api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.

        The login (on the device) is performed asynchronously, so the return result only indicates whether the library
        is able to perform the login attempt.  You should issue a call to the Spotify Web API `Get Available Devices`
        endpoint to check the current device list to ensure that the device id was successfully added or not.

        Use the `verifyDeviceListEntry` argument to check if the device is currently listed in the Spotify Connect
        device list.  If True, a `GetInformation` call is issued to get the device id, and a `GetPlayerDevice` call
        is made to check if the device id is in the Spotify Connect device list.  If the device id is found in the
        Spotify Connect device list then the Connect command is not issued; if the device id is NOT found in the Spotify
        Connect device list then the Connect command is issued

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `ZeroconfResponse` object that contains the response.
        """
        apiMethodName: str = "service_spotify_zeroconf_device_connect"
        apiMethodParms: SIMethodParmListContext = None
        result: ZeroconfResponse = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("hostIpv4Address", hostIpv4Address)
            apiMethodParms.AppendKeyValue("hostIpPort", hostIpPort)
            apiMethodParms.AppendKeyValue("cpath", cpath)
            apiMethodParms.AppendKeyValue("version", version)
            apiMethodParms.AppendKeyValue("useSSL", useSSL)
            apiMethodParms.AppendKeyValue("username", username)
            apiMethodParms.AppendKeyValue(
                "password (with mask)", passwordMaskString(password)
            )
            apiMethodParms.AppendKeyValue("loginid", loginid)
            apiMethodParms.AppendKeyValue("preDisconnect", preDisconnect)
            apiMethodParms.AppendKeyValue(
                "verifyDeviceListEntry", verifyDeviceListEntry
            )
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Connect ZeroConf Device Connect Service",
                apiMethodParms,
            )

            # validations.
            if preDisconnect is None:
                preDisconnect = False
            if verifyDeviceListEntry is None:
                verifyDeviceListEntry = False

            # create Spotify Zeroconf API connection object for the device.
            zconn: ZeroconfConnect = ZeroconfConnect(
                hostIpAddress=hostIpv4Address,
                hostIpPort=hostIpPort,
                cpath=cpath,
                version=version,
                useSSL=useSSL,
                tokenStorageDir=self.data.spotifyClient.TokenStorageDir,
                tokenStorageFile=self.data.spotifyClient.TokenStorageFile,
                tokenAuthInBrowser=False,
            )

            # are we verifying if the device id is already in the Spotify Connect device list?
            if verifyDeviceListEntry:
                # trace.
                _logsi.LogVerbose(
                    "'%s': Checking current Spotify Connect device list for Device ID (%s) ..."
                    % (self.name, zconn.Uri)
                )

                # get the device id of the device.
                info: ZeroconfGetInfo = zconn.GetInformation()

                # is the device in the current Spotify Connect device list?  if so, then we are done.
                playerDevice: PlayerDevice = self.data.spotifyClient.GetPlayerDevice(
                    info.DeviceId, True
                )
                if playerDevice is not None:
                    _logsi.LogVerbose(
                        "'%s': Device ID '%s' (%s) is already in the Spotify Connect device list; nothing to do"
                        % (self.name, playerDevice.Id, playerDevice.Name)
                    )

                    # return the (partial) user profile that retrieved the result, as well as the result itself.
                    return {
                        "user_profile": self._GetUserProfilePartialDictionary(
                            self.data.spotifyClient.UserProfile
                        ),
                        "result": info.ToDictionary(),
                    }

                # trace.
                _logsi.LogVerbose(
                    "'%s': Device ID '%s' (%s) was not found in the Spotify Connect device list; device will be activated"
                    % (self.name, info.DeviceId, info.RemoteName)
                )

            # disconnect the device from Spotify Connect.
            if preDisconnect == True:
                result = zconn.Disconnect(delay)

            # default user credentials if not specified.  these are the same credentials that
            # are stored in the configuration options settings, which were loaded when the
            # spotifyClient instance was created.
            if username is None:
                username = self.data.spotifyClient._SpotifyConnectUsername
            if password is None:
                password = self.data.spotifyClient._SpotifyConnectPassword
            if loginid is None:
                loginid = self.data.spotifyClient._SpotifyConnectLoginId

            # connect the device to Spotify Connect, which should make it known to any available
            # Spotify Connect player clients.
            result = zconn.Connect(username, password, loginid, delay)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyZeroconfApiError as ex:
            raise HomeAssistantError(ex.Message)
        except Exception as ex:
            _logsi.LogException(
                "'%s': MediaPlayer %s exception: %s"
                % (self.name, apiMethodName, str(ex)),
                ex,
                logToSystemLogger=False,
            )
            raise HomeAssistantError(str(ex)) from ex

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_zeroconf_device_disconnect(
        self,
        hostIpv4Address: str,
        hostIpPort: str,
        cpath: str,
        version: str = "1.0",
        useSSL: bool = False,
        delay: float = 0.50,
    ) -> dict:
        """
        Calls the `resetUsers` Spotify Zeroconf API endpoint to issue a call to SpConnectionLogout.
        The currently logged in user (if any) will be logged out of Spotify Connect, and the
        device id removed from the active Spotify Connect device list.

        Args:
            hostIpv4Address (str):
                IPV4 address (as a string) at which the Spotify Connect Zeroconf API can be reached
                on the Spotify Connect device (e.g. "192.168.1.81").
            hostIpPort (int):
                Port number (as an integer) at which the Spotify Connect Zeroconf API can be reached
                on the Spotify Connect device (e.g. "8200").
            cpath (str):
                Spotify Connect Zeroconf API CPath property value (e.g. "/zc").
            version (str):
                Spotify Connect Zeroconf API version number that the device supports (e.g. "2.10.0").
                Default is '1.0'.
            useSSL (bool):
                True if the host device utilizes HTTPS Secure Sockets Layer (SSL) support;
                otherwise, False to utilize HTTP.
                Default is False (HTTP).
            delay (float):
                Time delay (in seconds) to wait AFTER issuing a command to the device.
                This delay will give the spotify zeroconf api time to process the change before
                another command is issued.
                Default is 0.50; value range is 0 - 10.

        The URI value consists of an IP Address, port, CPath, and version value that are used to send
        requests to / receive responses from a headless Spotify Connect device.  These values can be
        obtained from a Zeroconf discovery process.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `ZeroconfResponse` object that contains the response.
        """
        apiMethodName: str = "service_spotify_zeroconf_device_disconnect"
        apiMethodParms: SIMethodParmListContext = None
        result: ZeroconfResponse = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("hostIpv4Address", hostIpv4Address)
            apiMethodParms.AppendKeyValue("hostIpPort", hostIpPort)
            apiMethodParms.AppendKeyValue("cpath", cpath)
            apiMethodParms.AppendKeyValue("version", version)
            apiMethodParms.AppendKeyValue("useSSL", useSSL)
            apiMethodParms.AppendKeyValue("delay", delay)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Connect ZeroConf Device Disconnect Service",
                apiMethodParms,
            )

            # create Spotify Zeroconf API connection object for the device.
            zconn: ZeroconfConnect = ZeroconfConnect(
                hostIpAddress=hostIpv4Address,
                hostIpPort=hostIpPort,
                cpath=cpath,
                version=version,
                useSSL=useSSL,
                tokenStorageDir=self.data.spotifyClient.TokenStorageDir,
                tokenStorageFile=self.data.spotifyClient.TokenStorageFile,
                tokenAuthInBrowser=False,
            )

            # disconnect the device from Spotify Connect.
            result = zconn.Disconnect(delay)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyZeroconfApiError as ex:
            raise HomeAssistantError(ex.Message)
        except Exception as ex:
            _logsi.LogException(
                "'%s': MediaPlayer %s exception: %s"
                % (self.name, apiMethodName, str(ex)),
                ex,
                logToSystemLogger=False,
            )
            raise HomeAssistantError(str(ex)) from ex

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_zeroconf_device_getinfo(
        self,
        hostIpv4Address: str,
        hostIpPort: str,
        cpath: str,
        version: str = "1.0",
        useSSL: bool = False,
    ) -> dict:
        """
        Calls the `getInfo` Spotify Zeroconf API endpoint to return information about the device.

        Args:
            hostIpv4Address (str):
                IPV4 address (as a string) at which the Spotify Connect Zeroconf API can be reached
                on the Spotify Connect device (e.g. "192.168.1.81").
            hostIpPort (int):
                Port number (as an integer) at which the Spotify Connect Zeroconf API can be reached
                on the Spotify Connect device (e.g. "8200").
            cpath (str):
                Spotify Connect Zeroconf API CPath property value (e.g. "/zc").
            version (str):
                Spotify Connect Zeroconf API version number that the device supports (e.g. "2.10.0").
                Default is '1.0'.
            useSSL (bool):
                True if the host device utilizes HTTPS Secure Sockets Layer (SSL) support;
                otherwise, False to utilize HTTP.
                Default is False (HTTP).

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: A `ZeroconfGetInfo` object that contains the response.
        """
        apiMethodName: str = "service_spotify_zeroconf_getinfo"
        apiMethodParms: SIMethodParmListContext = None
        result: ZeroconfGetInfo = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("hostIpv4Address", hostIpv4Address)
            apiMethodParms.AppendKeyValue("hostIpPort", hostIpPort)
            apiMethodParms.AppendKeyValue("cpath", cpath)
            apiMethodParms.AppendKeyValue("version", version)
            apiMethodParms.AppendKeyValue("useSSL", useSSL)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify Connect ZeroConf Device Get Information Service",
                apiMethodParms,
            )

            # create Spotify Zeroconf API connection object for the device.
            zconn: ZeroconfConnect = ZeroconfConnect(
                hostIpAddress=hostIpv4Address,
                hostIpPort=hostIpPort,
                cpath=cpath,
                version=version,
                useSSL=useSSL,
                tokenStorageDir=self.data.spotifyClient.TokenStorageDir,
                tokenStorageFile=self.data.spotifyClient.TokenStorageFile,
                tokenAuthInBrowser=False,
            )

            # get Spotify Connect device information.
            result = zconn.GetInformation()

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": result.ToDictionary(),
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyZeroconfApiError as ex:
            raise HomeAssistantError(ex.Message)
        except Exception as ex:
            _logsi.LogException(
                "'%s': MediaPlayer %s exception: %s"
                % (self.name, apiMethodName, str(ex)),
                ex,
                logToSystemLogger=False,
            )
            raise HomeAssistantError(str(ex)) from ex

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    def service_spotify_zeroconf_discover_devices(
        self,
        timeout: int = 5,
    ) -> dict:
        """
        Discover Spotify Connect devices on the local network via the
        ZeroConf (aka MDNS) service, and return details about each device.

        Args:
            timeout (int):
                Maximum amount of time to wait (in seconds) for the
                discovery to complete.
                Default is 5 seconds.

        Returns:
            A dictionary that contains the following keys:
            - user_profile: A (partial) user profile that retrieved the result.
            - result: An array of `ZeroconfDiscoveryResult` objects of matching results.
        """
        apiMethodName: str = "service_spotify_zeroconf_discover_devices"
        apiMethodParms: SIMethodParmListContext = None

        try:
            # trace.
            apiMethodParms = _logsi.EnterMethodParmList(SILevel.Debug, apiMethodName)
            apiMethodParms.AppendKeyValue("timeout", timeout)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "Spotify ZeroConf Discover Devices Service",
                apiMethodParms,
            )

            # create a new instance of the discovery class.
            # do not verify device connections;
            # do not print device details to the console as they are discovered.
            discovery: SpotifyDiscovery = SpotifyDiscovery(
                self.data.spotifyClient.ZeroconfClient, printToConsole=False
            )

            # discover Spotify Connect devices on the network, waiting up to the specified
            # time in seconds for all devices to be discovered.
            discovery.DiscoverDevices(timeout)

            # return the (partial) user profile that retrieved the result, as well as the result itself.
            return {
                "user_profile": self._GetUserProfilePartialDictionary(
                    self.data.spotifyClient.UserProfile
                ),
                "result": [item.ToDictionary() for item in discovery.DiscoveryResults],
            }

        # the following exceptions have already been logged, so we just need to
        # pass them back to HA for display in the log (or service UI).
        except SpotifyApiError as ex:
            raise HomeAssistantError(ex.Message)
        except SpotifyWebApiError as ex:
            raise HomeAssistantError(ex.Message)
        except Exception as ex:
            _logsi.LogException(
                "'%s': MediaPlayer %s exception: %s"
                % (self.name, apiMethodName, str(ex)),
                ex,
                logToSystemLogger=False,
            )
            raise HomeAssistantError(str(ex)) from ex

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug, apiMethodName)

    async def async_added_to_hass(self) -> None:
        """
        Run when this Entity has been added to HA.

        Importantly for a push integration, the module that will be getting updates
        needs to notify HA of changes.  In our case, we created a DataUpdateCoordinator
        instance that will inform us when the Spotify Connect device list has changed.  We
        will register some callback methods here so that we can forward the change
        notifications on to Home Assistant (e.g. a call to `self.async_write_ha_state`).

        The call back registration is done once this entity is registered with Home
        Assistant (rather than in the `__init__` method).
        """
        try:
            # trace.
            _logsi.EnterMethod(SILevel.Debug)

            # call base class method.
            await super().async_added_to_hass()

            # add listener that will inform HA of our state if a user removes the device instance.
            _logsi.LogVerbose(
                "'%s': adding '_handle_devices_update' listener" % self.name
            )
            self.async_on_remove(
                self.data.devices.async_add_listener(self._handle_devices_update)
            )

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    async def async_will_remove_from_hass(self) -> None:
        """
        Entity being removed from hass (the opposite of async_added_to_hass).

        Remove any registered call backs here.
        """
        try:
            # trace.
            _logsi.EnterMethod(SILevel.Debug)
            _logsi.LogVerbose("'%s': removing instance from hass" % self.name)

            # nothing to do here.

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """
        Implement the websocket media browsing helper.
        """
        methodParms: SIMethodParmListContext = None

        try:
            # trace.
            methodParms = _logsi.EnterMethodParmList(SILevel.Debug)
            methodParms.AppendKeyValue("media_content_type", media_content_type)
            methodParms.AppendKeyValue("media_content_id", media_content_id)
            _logsi.LogMethodParmList(
                SILevel.Verbose,
                "'%s': MediaPlayer is browsing for media content type '%s'"
                % (self.name, media_content_type),
                methodParms,
            )

            # browse spotifysplus device media.
            if media_content_type is None and media_content_id is None:
                # handle initial media browser selection (e.g. show the starting index).
                _logsi.LogVerbose(
                    "'%s': MediaPlayer is browsing main media library index content id '%s'"
                    % (self.name, media_content_id)
                )
                return await async_browse_media_library_index(
                    self.hass,
                    self.data.spotifyClient,
                    self.name,
                    self.source,
                    SPOTIFY_LIBRARY_MAP,
                    BrowsableMedia.SPOTIFY_LIBRARY_INDEX,
                    media_content_type,
                    media_content_id,
                )

            elif media_content_type == "favorites":
                # ignore Sonos-Card "favorites" node queries.
                _logsi.LogVerbose(
                    "'%s': ignoring Sonos-Card favorites query (no SoundTouch equivalent)"
                    % self.name
                )

                # Sonos-Card requires a valid BrowseMedia object, so return an empty one.
                browseMedia: BrowseMedia = BrowseMedia(
                    can_expand=False,
                    can_play=False,
                    children=[],
                    children_media_class=None,
                    media_class=None,
                    media_content_id=media_content_id,
                    media_content_type=media_content_type,
                    title="Favorites not supported",
                )
                return browseMedia

            else:
                # handle spotifysplus media library selection.
                # note that this is NOT async, as SpotifyClient is not async!
                _logsi.LogVerbose(
                    "'%s': MediaPlayer is browsing media node content id '%s'"
                    % (self.name, media_content_id)
                )
                return await self.hass.async_add_executor_job(
                    browse_media_node,
                    self.hass,
                    self.data.spotifyClient,
                    self.name,
                    self.source,
                    SPOTIFY_LIBRARY_MAP,
                    media_content_type,
                    media_content_id,
                )

        except Exception as ex:
            # trace.
            _logsi.LogException(
                "'%s': MediaPlayer async_browse_media exception: %s"
                % (self.name, str(ex)),
                ex,
                logToSystemLogger=False,
            )
            raise HomeAssistantError(str(ex)) from ex

        finally:
            # trace.
            _logsi.LeaveMethod(SILevel.Debug)
