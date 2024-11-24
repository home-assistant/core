# noqa: ignore=all

"""
The spotify integration.
"""

from __future__ import annotations

from asyncio import run_coroutine_threadsafe
from datetime import timedelta
from typing import Any
from urllib3._version import __version__ as urllib3_version

import functools
import logging
import voluptuous as vol

from spotifywebapipython import SpotifyClient
from spotifywebapipython.models import Device, SpotifyConnectDevices

from homeassistant.components import zeroconf
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .appmessages import STAppMessages
from .const import (
    CONF_OPTION_DEVICE_LOGINID,
    CONF_OPTION_DEVICE_PASSWORD,
    CONF_OPTION_DEVICE_USERNAME,
    DOMAIN,
    SPOTIFY_SCOPES,
)
from .instancedata_spotify import InstanceDataSpotify

__all__ = [
    "DOMAIN",
]

_LOGGER = logging.getLogger(__name__)

TOKEN_STATUS: str = "status"
TOKEN_STATUS_REFRESH_EVENT: str = "TokenRefreshEvent"

try:
    from smartinspectpython.siauto import (
        SIAuto,
        SILevel,
        SISession,
        SIConfigurationTimer,
    )

    # load SmartInspect settings from a configuration settings file.
    siConfigPath: str = "./smartinspect.cfg"
    SIAuto.Si.LoadConfiguration(siConfigPath)

    # start monitoring the configuration file for changes, and reload it when it changes.
    # this will check the file for changes every 60 seconds.
    siConfig: SIConfigurationTimer = SIConfigurationTimer(SIAuto.Si, siConfigPath)

    # get smartinspect logger reference; create a new session for this module name.
    _logsi: SISession = SIAuto.Si.GetSession(__name__)
    if _logsi == None:
        _logsi = SIAuto.Si.AddSession(__name__, True)
    _logsi.SystemLogger = _LOGGER
    _logsi.LogSeparator(SILevel.Error)
    _logsi.LogVerbose("__init__.py HAS Spotify: initialization")
    _logsi.LogAppDomain(SILevel.Verbose)
    _logsi.LogSystem(SILevel.Verbose)

except Exception as ex:
    _LOGGER.warning("HAS Spotify could not init SmartInspect debugging! %s", str(ex))

PLATFORMS = [Platform.MEDIA_PLAYER]
"""
List of platforms to support.
There should be a matching .py file for each (e.g. "media_player")
"""

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)
""" Configuration schema. """


# -----------------------------------------------------------------------------------
# Custom Service Schemas.
# -----------------------------------------------------------------------------------
SERVICE_SPOTIFY_ADD_PLAYER_QUEUE_ITEMS: str = "add_player_queue_items"
SERVICE_SPOTIFY_CHECK_ALBUM_FAVORITES: str = "check_album_favorites"
SERVICE_SPOTIFY_CHECK_ARTISTS_FOLLOWING: str = "check_artists_following"
SERVICE_SPOTIFY_CHECK_AUDIOBOOK_FAVORITES: str = "check_audiobook_favorites"
SERVICE_SPOTIFY_CHECK_EPISODE_FAVORITES: str = "check_episode_favorites"
SERVICE_SPOTIFY_CHECK_PLAYLIST_FOLLOWERS: str = "check_playlist_followers"
SERVICE_SPOTIFY_CHECK_SHOW_FAVORITES: str = "check_show_favorites"
SERVICE_SPOTIFY_CHECK_TRACK_FAVORITES: str = "check_track_favorites"
SERVICE_SPOTIFY_CHECK_USERS_FOLLOWING: str = "check_users_following"
SERVICE_SPOTIFY_FOLLOW_ARTISTS: str = "follow_artists"
SERVICE_SPOTIFY_FOLLOW_PLAYLIST: str = "follow_playlist"
SERVICE_SPOTIFY_FOLLOW_USERS: str = "follow_users"
SERVICE_SPOTIFY_GET_ALBUM: str = "get_album"
SERVICE_SPOTIFY_GET_ALBUM_FAVORITES: str = "get_album_favorites"
SERVICE_SPOTIFY_GET_ALBUM_NEW_RELEASES: str = "get_album_new_releases"
SERVICE_SPOTIFY_GET_ALBUM_TRACKS: str = "get_album_tracks"
SERVICE_SPOTIFY_GET_ARTIST: str = "get_artist"
SERVICE_SPOTIFY_GET_ARTIST_ALBUMS: str = "get_artist_albums"
SERVICE_SPOTIFY_GET_ARTIST_INFO: str = "get_artist_info"
SERVICE_SPOTIFY_GET_ARTIST_RELATED_ARTISTS: str = "get_artist_related_artists"
SERVICE_SPOTIFY_GET_ARTIST_TOP_TRACKS: str = "get_artist_top_tracks"
SERVICE_SPOTIFY_GET_ARTISTS_FOLLOWED: str = "get_artists_followed"
SERVICE_SPOTIFY_GET_AUDIOBOOK: str = "get_audiobook"
SERVICE_SPOTIFY_GET_AUDIOBOOK_CHAPTERS: str = "get_audiobook_chapters"
SERVICE_SPOTIFY_GET_AUDIOBOOK_FAVORITES: str = "get_audiobook_favorites"
SERVICE_SPOTIFY_GET_BROWSE_CATEGORYS_LIST: str = "get_browse_categorys_list"
SERVICE_SPOTIFY_GET_CATEGORY_PLAYLISTS: str = "get_category_playlists"
SERVICE_SPOTIFY_GET_CHAPTER: str = "get_chapter"
SERVICE_SPOTIFY_GET_EPISODE: str = "get_episode"
SERVICE_SPOTIFY_GET_EPISODE_FAVORITES: str = "get_episode_favorites"
SERVICE_SPOTIFY_GET_FEATURED_PLAYLISTS: str = "get_featured_playlists"
SERVICE_SPOTIFY_GET_PLAYER_DEVICES: str = "get_player_devices"
SERVICE_SPOTIFY_GET_PLAYER_NOW_PLAYING: str = "get_player_now_playing"
SERVICE_SPOTIFY_GET_PLAYER_PLAYBACK_STATE: str = "get_player_playback_state"
SERVICE_SPOTIFY_GET_PLAYER_QUEUE_INFO: str = "get_player_queue_info"
SERVICE_SPOTIFY_GET_PLAYER_RECENT_TRACKS: str = "get_player_recent_tracks"
SERVICE_SPOTIFY_GET_PLAYLIST: str = "get_playlist"
SERVICE_SPOTIFY_GET_PLAYLIST_COVER_IMAGE: str = "get_playlist_cover_image"
SERVICE_SPOTIFY_GET_PLAYLIST_FAVORITES: str = "get_playlist_favorites"
SERVICE_SPOTIFY_GET_PLAYLIST_ITEMS: str = "get_playlist_items"
SERVICE_SPOTIFY_GET_PLAYLISTS_FOR_USER: str = "get_playlists_for_user"
SERVICE_SPOTIFY_GET_SHOW: str = "get_show"
SERVICE_SPOTIFY_GET_SHOW_EPISODES: str = "get_show_episodes"
SERVICE_SPOTIFY_GET_SHOW_FAVORITES: str = "get_show_favorites"
SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICE: str = "get_spotify_connect_device"
SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICES: str = "get_spotify_connect_devices"
SERVICE_SPOTIFY_GET_TRACK: str = "get_track"
SERVICE_SPOTIFY_GET_TRACK_FAVORITES: str = "get_track_favorites"
SERVICE_SPOTIFY_GET_TRACK_RECOMMENDATIONS: str = "get_track_recommendations"
SERVICE_SPOTIFY_GET_TRACKS_AUDIO_FEATURES: str = "get_tracks_audio_features"
SERVICE_SPOTIFY_GET_USERS_TOP_ARTISTS: str = "get_users_top_artists"
SERVICE_SPOTIFY_GET_USERS_TOP_TRACKS: str = "get_users_top_tracks"
SERVICE_SPOTIFY_PLAYER_ACTIVATE_DEVICES: str = "player_activate_devices"
SERVICE_SPOTIFY_PLAYER_MEDIA_PAUSE: str = "player_media_pause"
SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_CONTEXT: str = "player_media_play_context"
SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACK_FAVORITES: str = (
    "player_media_play_track_favorites"
)
SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACKS: str = "player_media_play_tracks"
SERVICE_SPOTIFY_PLAYER_MEDIA_RESUME: str = "player_media_resume"
SERVICE_SPOTIFY_PLAYER_MEDIA_SEEK: str = "player_media_seek"
SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_NEXT: str = "player_media_skip_next"
SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_PREVIOUS: str = "player_media_skip_previous"
SERVICE_SPOTIFY_PLAYER_RESOLVE_DEVICE_ID: str = "player_resolve_device_id"
SERVICE_SPOTIFY_PLAYER_SET_REPEAT_MODE: str = "player_set_repeat_mode"
SERVICE_SPOTIFY_PLAYER_SET_SHUFFLE_MODE: str = "player_set_shuffle_mode"
SERVICE_SPOTIFY_PLAYER_SET_VOLUME_LEVEL: str = "player_set_volume_level"
SERVICE_SPOTIFY_PLAYER_TRANSFER_PLAYBACK: str = "player_transfer_playback"
SERVICE_SPOTIFY_PLAYLIST_CHANGE: str = "playlist_change"
SERVICE_SPOTIFY_PLAYLIST_COVER_IMAGE_ADD: str = "playlist_cover_image_add"
SERVICE_SPOTIFY_PLAYLIST_CREATE: str = "playlist_create"
SERVICE_SPOTIFY_PLAYLIST_ITEMS_ADD: str = "playlist_items_add"
SERVICE_SPOTIFY_PLAYLIST_ITEMS_CLEAR: str = "playlist_items_clear"
SERVICE_SPOTIFY_PLAYLIST_ITEMS_REMOVE: str = "playlist_items_remove"
SERVICE_SPOTIFY_PLAYLIST_ITEMS_REORDER: str = "playlist_items_reorder"
SERVICE_SPOTIFY_PLAYLIST_ITEMS_REPLACE: str = "playlist_items_replace"
SERVICE_SPOTIFY_REMOVE_ALBUM_FAVORITES: str = "remove_album_favorites"
SERVICE_SPOTIFY_REMOVE_AUDIOBOOK_FAVORITES: str = "remove_audiobook_favorites"
SERVICE_SPOTIFY_REMOVE_EPISODE_FAVORITES: str = "remove_episode_favorites"
SERVICE_SPOTIFY_REMOVE_SHOW_FAVORITES: str = "remove_show_favorites"
SERVICE_SPOTIFY_REMOVE_TRACK_FAVORITES: str = "remove_track_favorites"
SERVICE_SPOTIFY_SAVE_ALBUM_FAVORITES: str = "save_album_favorites"
SERVICE_SPOTIFY_SAVE_AUDIOBOOK_FAVORITES: str = "save_audiobook_favorites"
SERVICE_SPOTIFY_SAVE_EPISODE_FAVORITES: str = "save_episode_favorites"
SERVICE_SPOTIFY_SAVE_SHOW_FAVORITES: str = "save_show_favorites"
SERVICE_SPOTIFY_SAVE_TRACK_FAVORITES: str = "save_track_favorites"
SERVICE_SPOTIFY_SEARCH_ALBUMS: str = "search_albums"
SERVICE_SPOTIFY_SEARCH_ARTISTS: str = "search_artists"
SERVICE_SPOTIFY_SEARCH_AUDIOBOOKS: str = "search_audiobooks"
SERVICE_SPOTIFY_SEARCH_EPISODES: str = "search_episodes"
SERVICE_SPOTIFY_SEARCH_PLAYLISTS: str = "search_playlists"
SERVICE_SPOTIFY_SEARCH_SHOWS: str = "search_shows"
SERVICE_SPOTIFY_SEARCH_TRACKS: str = "search_tracks"
SERVICE_SPOTIFY_UNFOLLOW_ARTISTS: str = "unfollow_artists"
SERVICE_SPOTIFY_UNFOLLOW_PLAYLIST: str = "unfollow_playlist"
SERVICE_SPOTIFY_UNFOLLOW_USERS: str = "unfollow_users"
SERVICE_SPOTIFY_ZEROCONF_DEVICE_CONNECT: str = "zeroconf_device_connect"
SERVICE_SPOTIFY_ZEROCONF_DEVICE_DISCONNECT: str = "zeroconf_device_disconnect"
SERVICE_SPOTIFY_ZEROCONF_DEVICE_GETINFO: str = "zeroconf_device_getinfo"
SERVICE_SPOTIFY_ZEROCONF_DISCOVER_DEVICES: str = "zeroconf_discover_devices"


SERVICE_SPOTIFY_ADD_PLAYER_QUEUE_ITEMS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("uris"): cv.string,
        vol.Optional("device_id"): cv.string,
        vol.Optional("verify_device_id"): cv.boolean,
        vol.Optional("delay", default=0.15): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_CHECK_ALBUM_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_CHECK_ARTISTS_FOLLOWING_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_CHECK_AUDIOBOOK_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_CHECK_EPISODE_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_CHECK_PLAYLIST_FOLLOWERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("playlist_id"): cv.string,
        vol.Optional("user_ids"): cv.string,
    }
)

SERVICE_SPOTIFY_CHECK_SHOW_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_CHECK_TRACK_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_CHECK_USERS_FOLLOWING_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_FOLLOW_ARTISTS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_FOLLOW_PLAYLIST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("playlist_id"): cv.string,
        vol.Optional("public"): cv.boolean,
    }
)

SERVICE_SPOTIFY_FOLLOW_USERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_ALBUM_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("album_id"): cv.string,
        vol.Optional("market"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_ALBUM_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_ALBUM_NEW_RELEASES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("country"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_ALBUM_TRACKS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("album_id"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_GET_ARTIST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("artist_id"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_ARTIST_ALBUMS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("artist_id"): cv.string,
        vol.Optional("include_groups"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_ARTIST_INFO_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("artist_id"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_ARTIST_RELATED_ARTISTS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("artist_id"): cv.string,
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_ARTIST_TOP_TRACKS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("artist_id"): cv.string,
        vol.Optional("market"): cv.string,
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_ARTISTS_FOLLOWED_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("after"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_AUDIOBOOK_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("audiobook_id"): cv.string,
        vol.Optional("market"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_AUDIOBOOK_CHAPTERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("audiobook_id"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_GET_AUDIOBOOK_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_BROWSE_CATEGORYS_LIST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("country"): cv.string,
        vol.Optional("locale"): cv.string,
        vol.Optional("refresh"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_CATEGORY_PLAYLISTS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("category_id"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("country"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_CHAPTER_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("chapter_id"): cv.string,
        vol.Optional("market"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_EPISODE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("episode_id"): cv.string,
        vol.Optional("market"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_EPISODE_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_FEATURED_PLAYLISTS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("country"): cv.string,
        vol.Optional("locale"): cv.string,
        vol.Optional("timestamp"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_PLAYER_DEVICES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("refresh"): cv.boolean,
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_PLAYER_NOW_PLAYING_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("market"): cv.string,
        vol.Optional("additional_types"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_PLAYER_PLAYBACK_STATE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("market"): cv.string,
        vol.Optional("additional_types"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_PLAYER_QUEUE_INFO_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)

SERVICE_SPOTIFY_GET_PLAYER_RECENT_TRACKS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("after", default=0): vol.All(vol.Range(min=0, max=99999999999999)),
        vol.Optional("before", default=0): vol.All(
            vol.Range(min=0, max=99999999999999)
        ),
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_GET_PLAYLIST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("playlist_id"): cv.string,
        vol.Optional("market"): cv.string,
        vol.Optional("fields"): cv.string,
        vol.Optional("additional_types"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_PLAYLIST_COVER_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("playlist_id"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_PLAYLIST_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_PLAYLIST_ITEMS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("playlist_id"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("fields"): cv.string,
        vol.Optional("additional_types"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_GET_PLAYLISTS_FOR_USER_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("user_id"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_SHOW_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("show_id"): cv.string,
        vol.Optional("market"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_SHOW_EPISODES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("show_id"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_GET_SHOW_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
        vol.Optional("exclude_audiobooks"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("device_value"): cv.string,
        vol.Optional("verify_user_context"): cv.boolean,
        vol.Optional("verify_timeout", default=5.0): vol.All(
            vol.Range(min=0, max=10.0)
        ),
        vol.Optional("refresh_device_list"): cv.boolean,
        vol.Optional("activate_device"): cv.boolean,
        vol.Optional("delay", default=0.25): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("refresh"): cv.boolean,
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_TRACK_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("track_id"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_TRACK_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_TRACK_RECOMMENDATIONS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("limit", default=20): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("market"): cv.string,
        vol.Optional("seed_artists"): cv.string,
        vol.Optional("seed_genres"): cv.string,
        vol.Optional("seed_tracks"): cv.string,
        vol.Optional("min_acousticness", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("max_acousticness", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("target_acousticness", default=0): vol.All(
            vol.Range(min=0, max=1.0)
        ),
        vol.Optional("min_danceability", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("max_danceability", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("target_danceability", default=0): vol.All(
            vol.Range(min=0, max=1.0)
        ),
        vol.Optional("min_duration_ms", default=0): vol.All(
            vol.Range(min=0, max=999999999)
        ),
        vol.Optional("max_duration_ms", default=0): vol.All(
            vol.Range(min=0, max=999999999)
        ),
        vol.Optional("target_duration_ms", default=0): vol.All(
            vol.Range(min=0, max=999999999)
        ),
        vol.Optional("min_energy", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("max_energy", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("target_energy", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("min_instrumentalness", default=0): vol.All(
            vol.Range(min=0, max=1.0)
        ),
        vol.Optional("max_instrumentalness", default=0): vol.All(
            vol.Range(min=0, max=1.0)
        ),
        vol.Optional("target_instrumentalness", default=0): vol.All(
            vol.Range(min=0, max=1.0)
        ),
        vol.Optional("min_key", default=0): vol.All(vol.Range(min=0, max=11)),
        vol.Optional("max_key", default=0): vol.All(vol.Range(min=0, max=11)),
        vol.Optional("target_key", default=0): vol.All(vol.Range(min=0, max=11)),
        vol.Optional("min_liveness", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("max_liveness", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("target_liveness", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("min_loudness", default=0): vol.All(
            vol.Range(min=-1000.0, max=1000.0)
        ),
        vol.Optional("max_loudness", default=0): vol.All(
            vol.Range(min=-1000.0, max=1000.0)
        ),
        vol.Optional("target_loudness", default=0): vol.All(
            vol.Range(min=-1000.0, max=1000.0)
        ),
        vol.Optional("min_mode", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("max_mode", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("target_mode", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("min_popularity", default=0): vol.All(vol.Range(min=0, max=100)),
        vol.Optional("max_popularity", default=0): vol.All(vol.Range(min=0, max=100)),
        vol.Optional("target_popularity", default=0): vol.All(
            vol.Range(min=0, max=100)
        ),
        vol.Optional("min_speechiness", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("max_speechiness", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("target_speechiness", default=0): vol.All(
            vol.Range(min=0, max=1.0)
        ),
        vol.Optional("min_tempo", default=0): vol.All(vol.Range(min=0, max=99999)),
        vol.Optional("max_tempo", default=0): vol.All(vol.Range(min=0, max=99999)),
        vol.Optional("target_tempo", default=0): vol.All(vol.Range(min=0, max=99999)),
        vol.Optional("min_time_signature", default=0): vol.All(
            vol.Range(min=0, max=99999)
        ),
        vol.Optional("max_time_signature", default=0): vol.All(
            vol.Range(min=0, max=99999)
        ),
        vol.Optional("target_time_signature", default=0): vol.All(
            vol.Range(min=0, max=99999)
        ),
        vol.Optional("min_valence", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("max_valence", default=0): vol.All(vol.Range(min=0, max=1.0)),
        vol.Optional("target_valence", default=0): vol.All(vol.Range(min=-0, max=1.0)),
    }
)

SERVICE_SPOTIFY_GET_TRACKS_AUDIO_FEATURES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_GET_USERS_TOP_ARTISTS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("time_range"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_GET_USERS_TOP_TRACKS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("time_range"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
        vol.Optional("sort_result"): cv.boolean,
    }
)

SERVICE_SPOTIFY_PLAYER_ACTIVATE_DEVICES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("verify_user_context"): cv.boolean,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_PLAYER_MEDIA_PAUSE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("device_id"): cv.string,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_CONTEXT_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("context_uri"): cv.string,
        vol.Optional("offset_uri"): cv.string,
        vol.Optional("offset_position", default=-1): vol.All(
            vol.Range(min=-1, max=500)
        ),
        vol.Optional("position_ms", default=-1): vol.All(
            vol.Range(min=-1, max=999999999)
        ),
        vol.Optional("device_id"): cv.string,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACK_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("device_id"): cv.string,
        vol.Optional("shuffle"): cv.boolean,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
        vol.Optional("resolve_device_id"): cv.boolean,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=999999)),
    }
)

SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACKS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("uris"): cv.string,
        vol.Optional("position_ms", default=-1): vol.All(
            vol.Range(min=-1, max=999999999)
        ),
        vol.Optional("device_id"): cv.string,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_PLAYER_MEDIA_RESUME_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("device_id"): cv.string,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_PLAYER_MEDIA_SEEK_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("position_ms", default=-1): vol.All(
            vol.Range(min=-1, max=999999999)
        ),
        vol.Optional("device_id"): cv.string,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
        vol.Optional("relative_position_ms", default=0): vol.All(
            vol.Range(min=-999999999, max=999999999)
        ),
    }
)

SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_NEXT_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("device_id"): cv.string,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_PREVIOUS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("device_id"): cv.string,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_PLAYER_RESOLVE_DEVICE_ID_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("device_value"): cv.string,
        vol.Optional("verify_user_context"): cv.boolean,
        vol.Optional("verify_timeout", default=5.0): vol.All(
            vol.Range(min=0, max=10.0)
        ),
    }
)

SERVICE_SPOTIFY_PLAYER_SET_REPEAT_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("state"): cv.string,
        vol.Optional("device_id"): cv.string,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_PLAYER_SET_SHUFFLE_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("state"): cv.boolean,
        vol.Optional("device_id"): cv.string,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_PLAYER_SET_VOLUME_LEVEL_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("volume_level", default=0): vol.All(vol.Range(min=0, max=100)),
        vol.Optional("device_id"): cv.string,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_PLAYER_TRANSFER_PLAYBACK_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("device_id"): cv.string,
        vol.Optional("play"): cv.boolean,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
        vol.Optional("refresh_device_list"): cv.boolean,
        vol.Optional("force_activate_device"): cv.boolean,
    }
)

SERVICE_SPOTIFY_PLAYLIST_CHANGE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("playlist_id"): cv.string,
        vol.Required("name"): cv.string,
        vol.Required("description"): cv.string,
        vol.Required("public"): cv.boolean,
        vol.Required("collaborative"): cv.boolean,
        vol.Optional("image_path"): cv.string,
    }
)

SERVICE_SPOTIFY_PLAYLIST_COVER_IMAGE_ADD_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("playlist_id"): cv.string,
        vol.Required("image_path"): cv.string,
    }
)

SERVICE_SPOTIFY_PLAYLIST_CREATE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("user_id"): cv.string,
        vol.Required("name"): cv.string,
        vol.Required("description"): cv.string,
        vol.Required("public"): cv.boolean,
        vol.Required("collaborative"): cv.boolean,
        vol.Optional("image_path"): cv.string,
    }
)

SERVICE_SPOTIFY_PLAYLIST_ITEMS_ADD_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("playlist_id"): cv.string,
        vol.Optional("uris"): cv.string,
        vol.Optional("position"): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_PLAYLIST_ITEMS_CLEAR_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("playlist_id"): cv.string,
    }
)

SERVICE_SPOTIFY_PLAYLIST_ITEMS_REMOVE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("playlist_id"): cv.string,
        vol.Optional("uris"): cv.string,
        vol.Optional("snapshot_id"): cv.string,
    }
)

SERVICE_SPOTIFY_PLAYLIST_ITEMS_REORDER_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("playlist_id"): cv.string,
        vol.Required("range_start"): vol.All(vol.Range(min=0, max=99999)),
        vol.Required("insert_before"): vol.All(vol.Range(min=0, max=99999)),
        vol.Optional("range_length"): vol.All(vol.Range(min=0, max=99999)),
        vol.Optional("snapshot_id"): cv.string,
    }
)

SERVICE_SPOTIFY_PLAYLIST_ITEMS_REPLACE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("playlist_id"): cv.string,
        vol.Optional("uris"): cv.string,
    }
)

SERVICE_SPOTIFY_REMOVE_ALBUM_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_REMOVE_AUDIOBOOK_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_REMOVE_EPISODE_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_REMOVE_SHOW_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_REMOVE_TRACK_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_SAVE_ALBUM_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_SAVE_AUDIOBOOK_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_SAVE_EPISODE_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_SAVE_SHOW_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_SAVE_TRACK_FAVORITES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_SEARCH_ALBUMS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("criteria"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("include_external"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_SEARCH_ARTISTS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("criteria"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("include_external"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_SEARCH_AUDIOBOOKS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("criteria"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("include_external"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_SEARCH_EPISODES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("criteria"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("include_external"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_SEARCH_PLAYLISTS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("criteria"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("include_external"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_SEARCH_SHOWS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("criteria"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("include_external"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_SEARCH_TRACKS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("criteria"): cv.string,
        vol.Optional("limit", default=50): vol.All(vol.Range(min=0, max=50)),
        vol.Optional("offset", default=0): vol.All(vol.Range(min=0, max=500)),
        vol.Optional("market"): cv.string,
        vol.Optional("include_external"): cv.string,
        vol.Optional("limit_total", default=0): vol.All(vol.Range(min=0, max=9999)),
    }
)

SERVICE_SPOTIFY_UNFOLLOW_ARTISTS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_UNFOLLOW_PLAYLIST_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("playlist_id"): cv.string,
    }
)

SERVICE_SPOTIFY_UNFOLLOW_USERS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("ids"): cv.string,
    }
)

SERVICE_SPOTIFY_ZEROCONF_DEVICE_CONNECT_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("host_ipv4_address"): cv.string,
        vol.Required("host_ip_port", default=8200): vol.All(
            vol.Range(min=1, max=65535)
        ),
        vol.Required("cpath"): cv.string,
        vol.Optional("version"): cv.string,
        vol.Optional("use_ssl"): cv.boolean,
        vol.Optional("username"): cv.string,
        vol.Optional("password"): cv.string,
        vol.Optional("loginid"): cv.string,
        vol.Optional("pre_disconnect"): cv.boolean,
        vol.Optional("verify_device_list_entry"): cv.boolean,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_ZEROCONF_DEVICE_DISCONNECT_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("host_ipv4_address"): cv.string,
        vol.Required("host_ip_port", default=8200): vol.All(
            vol.Range(min=1, max=65535)
        ),
        vol.Required("cpath"): cv.string,
        vol.Optional("version"): cv.string,
        vol.Optional("use_ssl"): cv.boolean,
        vol.Optional("delay", default=0.50): vol.All(vol.Range(min=0, max=10.0)),
    }
)

SERVICE_SPOTIFY_ZEROCONF_DEVICE_GETINFO_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("host_ipv4_address"): cv.string,
        vol.Required("host_ip_port", default=8200): vol.All(
            vol.Range(min=1, max=65535)
        ),
        vol.Required("cpath"): cv.string,
        vol.Optional("version"): cv.string,
        vol.Optional("use_ssl"): cv.boolean,
    }
)

SERVICE_SPOTIFY_ZEROCONF_DISCOVER_DEVICES_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("timeout", default=5): vol.All(vol.Range(min=1, max=10)),
    }
)


def _trace_LogTextFile(filePath: str, title: str) -> None:
    """
    Log the contents of the specified text file to the SmartInspect trace log.

    Args:
        filePath (str):
            Fully-qualified file path to log.
        title (str):
            Title to assign to the log entry.

    """
    _logsi.LogTextFile(SILevel.Verbose, title, filePath)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """
    Set up the component.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        config (ConfigType):
            HomeAssistant validation configuration object.

    The __init__.py module "async_setup" method is executed once for the component
    configuration, no matter how many devices are configured for the component.
    It takes care of loading the services that the component provides, as well as the
    ConfigType dictionary.  The ConfigType dictionary contains Home Assistant configuration
    entries that reference this component type: 'default_config', 'frontend' (themes, etc),
    'automation', 'script', and 'scenes' sub-dictionaries.
    """
    try:
        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        if _logsi.IsOn(SILevel.Verbose):
            _logsi.LogVerbose("Component async_setup starting")

            # log the manifest file contents.
            # as of HA 2024.6, we have to use an executor job to do this as the trace uses a blocking file open / read call.
            myConfigDir: str = "%s/custom_components/%s" % (
                hass.config.config_dir,
                DOMAIN,
            )
            myManifestPath: str = "%s/manifest.json" % (myConfigDir)
            await hass.async_add_executor_job(
                _trace_LogTextFile,
                myManifestPath,
                "Integration Manifest File (%s)" % myManifestPath,
            )

            # log verion information for supporting packages.
            _logsi.LogValue(SILevel.Verbose, "urllib3 version", urllib3_version)

            for item in config:
                itemKey: str = str(item)
                itemObj = config[itemKey]
                if isinstance(itemObj, dict):
                    _logsi.LogDictionary(
                        SILevel.Verbose,
                        "ConfigType '%s' data (dictionary)" % itemKey,
                        itemObj,
                        prettyPrint=True,
                    )
                elif isinstance(itemObj, list):
                    _logsi.LogArray(
                        SILevel.Verbose,
                        "ConfigType '%s' data (list)" % itemKey,
                        itemObj,
                    )
                else:
                    _logsi.LogObject(
                        SILevel.Verbose,
                        "ConfigType '%s' data (object)" % (itemKey),
                        itemObj,
                    )

        if DOMAIN in config:
            # remind user to remove Spotify settings from configuration.yaml if present.
            async_create_issue(
                hass,
                DOMAIN,
                "removed_yaml",
                breaks_in_ha_version="2022.8.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="removed_yaml",
            )

        async def service_handle_spotify_command(service: ServiceCall) -> None:
            """
            Handle service requests that do not return service response data from Spotify endpoints.

            Args:
                service (ServiceCall):
                    ServiceCall instance that contains service data (requested service name, field parameters, etc).
            """
            try:
                _logsi.EnterMethod(SILevel.Debug)
                _logsi.LogVerbose(
                    STAppMessages.MSG_SERVICE_CALL_START,
                    service.service,
                    "service_handle_spotify_command",
                )
                _logsi.LogObject(
                    SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_PARM, service
                )
                _logsi.LogDictionary(
                    SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_DATA, service.data
                )

                # get player instance from service parameter; if not found, then we are done.
                entity = _GetEntityFromServiceData(hass, service, "entity_id")
                if entity is None:
                    return

                # process service request.
                if service.service == SERVICE_SPOTIFY_ADD_PLAYER_QUEUE_ITEMS:
                    # add player queue items.
                    uris = service.data.get("uris")
                    device_id = service.data.get("device_id")
                    verify_device_id = service.data.get("verify_device_id")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_add_player_queue_items,
                        uris,
                        device_id,
                        verify_device_id,
                        delay,
                    )

                elif service.service == SERVICE_SPOTIFY_FOLLOW_ARTISTS:
                    # follow artist(s).
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_follow_artists, ids
                    )

                elif service.service == SERVICE_SPOTIFY_FOLLOW_PLAYLIST:
                    # follow playlist.
                    playlist_id = service.data.get("playlist_id")
                    public = service.data.get("public")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_follow_playlist, playlist_id, public
                    )

                elif service.service == SERVICE_SPOTIFY_FOLLOW_USERS:
                    # follow user(s).
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_follow_users, ids
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_MEDIA_PAUSE:
                    # pause media play.
                    device_id = service.data.get("device_id")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_media_pause, device_id, delay
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_CONTEXT:
                    # start playing one or more tracks of the specified context.
                    context_uri = service.data.get("context_uri")
                    offset_uri = service.data.get("offset_uri")
                    offset_position = service.data.get("offset_position")
                    position_ms = service.data.get("position_ms")
                    device_id = service.data.get("device_id")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_media_play_context,
                        context_uri,
                        offset_uri,
                        offset_position,
                        position_ms,
                        device_id,
                        delay,
                    )

                elif (
                    service.service == SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACK_FAVORITES
                ):
                    # start playing all track favorites.
                    device_id = service.data.get("device_id")
                    shuffle = service.data.get("shuffle")
                    delay = service.data.get("delay")
                    resolve_device_id = service.data.get("resolve_device_id")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_media_play_track_favorites,
                        device_id,
                        shuffle,
                        delay,
                        resolve_device_id,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACKS:
                    # start playing one or more tracks.
                    uris = service.data.get("uris")
                    position_ms = service.data.get("position_ms")
                    device_id = service.data.get("device_id")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_media_play_tracks,
                        uris,
                        position_ms,
                        device_id,
                        delay,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_MEDIA_RESUME:
                    # resume media play.
                    device_id = service.data.get("device_id")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_media_resume, device_id, delay
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_MEDIA_SEEK:
                    # seeks to the given position in the currently playing track.
                    position_ms = service.data.get("position_ms")
                    device_id = service.data.get("device_id")
                    delay = service.data.get("delay")
                    relative_position_ms = service.data.get("relative_position_ms")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_media_seek,
                        position_ms,
                        device_id,
                        delay,
                        relative_position_ms,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_NEXT:
                    # skip to next track.
                    device_id = service.data.get("device_id")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_media_skip_next, device_id, delay
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_PREVIOUS:
                    # skip to next track.
                    device_id = service.data.get("device_id")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_media_skip_previous,
                        device_id,
                        delay,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_SET_REPEAT_MODE:
                    # set player repeat mode.
                    state = service.data.get("state")
                    device_id = service.data.get("device_id")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_set_repeat_mode,
                        state,
                        device_id,
                        delay,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_SET_SHUFFLE_MODE:
                    # set player shuffle mode.
                    state = service.data.get("state")
                    device_id = service.data.get("device_id")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_set_shuffle_mode,
                        state,
                        device_id,
                        delay,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_SET_VOLUME_LEVEL:
                    # set player shuffle mode.
                    volume_level = service.data.get("volume_level")
                    device_id = service.data.get("device_id")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_set_volume_level,
                        volume_level,
                        device_id,
                        delay,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_TRANSFER_PLAYBACK:
                    # transfer playback to a new Spotify Connect device.
                    device_id = service.data.get("device_id")
                    play = service.data.get("play")
                    delay = service.data.get("delay")
                    refresh_device_list = service.data.get("refresh_device_list")
                    force_activate_device = service.data.get("force_activate_device")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_player_transfer_playback,
                        device_id,
                        play,
                        delay,
                        refresh_device_list,
                        force_activate_device,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYLIST_CHANGE:
                    # update details of an existing playlist.
                    playlist_id = service.data.get("playlist_id")
                    name = service.data.get("name")
                    description = service.data.get("description")
                    public = service.data.get("public")
                    collaborative = service.data.get("collaborative")
                    image_path = service.data.get("image_path")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_playlist_change,
                        playlist_id,
                        name,
                        description,
                        public,
                        collaborative,
                        image_path,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYLIST_COVER_IMAGE_ADD:
                    # add playlist cover image.
                    playlist_id = service.data.get("playlist_id")
                    image_path = service.data.get("image_path")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_playlist_cover_image_add,
                        playlist_id,
                        image_path,
                    )

                elif service.service == SERVICE_SPOTIFY_REMOVE_ALBUM_FAVORITES:
                    # remove album(s) from favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_remove_album_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_REMOVE_AUDIOBOOK_FAVORITES:
                    # remove audiobook(s) from favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_remove_audiobook_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_REMOVE_EPISODE_FAVORITES:
                    # remove episode(s) from favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_remove_episode_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_REMOVE_SHOW_FAVORITES:
                    # remove show(s) from favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_remove_show_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_REMOVE_TRACK_FAVORITES:
                    # remove track(s) from favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_remove_track_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_SAVE_ALBUM_FAVORITES:
                    # save album(s) to favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_save_album_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_SAVE_AUDIOBOOK_FAVORITES:
                    # save audiobook(s) to favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_save_audiobook_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_SAVE_EPISODE_FAVORITES:
                    # save episode(s) to favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_save_episode_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_SAVE_SHOW_FAVORITES:
                    # save show(s) to favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_save_show_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_SAVE_TRACK_FAVORITES:
                    # save track(s) to favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_save_track_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_UNFOLLOW_ARTISTS:
                    # unfollow artist(s).
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_unfollow_artists, ids
                    )

                elif service.service == SERVICE_SPOTIFY_UNFOLLOW_PLAYLIST:
                    # unfollow playlist.
                    playlist_id = service.data.get("playlist_id")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_unfollow_playlist, playlist_id
                    )

                elif service.service == SERVICE_SPOTIFY_UNFOLLOW_USERS:
                    # unfollow user(s).
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    await hass.async_add_executor_job(
                        entity.service_spotify_unfollow_users, ids
                    )

                else:
                    raise HomeAssistantError(
                        "Unrecognized service identifier '%s' in method service_handle_spotify_command"
                        % service.service
                    )

                # return (no response).
                return

            except HomeAssistantError as ex:
                # log error, but not to system logger as HA will take care of it.
                _logsi.LogError(str(ex), logToSystemLogger=False)
                raise

            except Exception as ex:
                # log exception, but not to system logger as HA will take care of it.
                _logsi.LogException(
                    STAppMessages.MSG_SERVICE_REQUEST_EXCEPTION
                    % (service.service, "service_handle_getlist"),
                    ex,
                    logToSystemLogger=False,
                )
                raise

            finally:
                # trace.
                _logsi.LeaveMethod(SILevel.Debug)

        async def service_handle_spotify_serviceresponse(
            service: ServiceCall,
        ) -> ServiceResponse:
            """
            Handle service requests that return service response data from Spotify endpoints.

            Args:
                service (ServiceCall):
                    ServiceCall instance that contains service data (requested service name, field parameters, etc).
            """
            try:
                _logsi.EnterMethod(SILevel.Debug)
                _logsi.LogVerbose(
                    STAppMessages.MSG_SERVICE_CALL_START,
                    service.service,
                    "service_handle_spotify_serviceresponse",
                )
                _logsi.LogObject(
                    SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_PARM, service
                )
                _logsi.LogDictionary(
                    SILevel.Verbose, STAppMessages.MSG_SERVICE_CALL_DATA, service.data
                )

                # get player instance from service parameter; if not found, then we are done.
                entity = _GetEntityFromServiceData(hass, service, "entity_id")
                if entity is None:
                    return

                response: dict = {}

                # process service request.
                if service.service == SERVICE_SPOTIFY_CHECK_ALBUM_FAVORITES:
                    # check album favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_check_album_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_CHECK_ARTISTS_FOLLOWING:
                    # check artists following.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_check_artists_following, ids
                    )

                elif service.service == SERVICE_SPOTIFY_CHECK_AUDIOBOOK_FAVORITES:
                    # check audiobook favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_check_audiobook_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_CHECK_EPISODE_FAVORITES:
                    # check episode favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_check_episode_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_CHECK_PLAYLIST_FOLLOWERS:
                    # check playlist followers.
                    playlist_id = service.data.get("playlist_id")
                    user_ids = service.data.get("user_ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_check_playlist_followers,
                        playlist_id,
                        user_ids,
                    )

                elif service.service == SERVICE_SPOTIFY_CHECK_SHOW_FAVORITES:
                    # check show favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_check_show_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_CHECK_TRACK_FAVORITES:
                    # check track favorites.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_check_track_favorites, ids
                    )

                elif service.service == SERVICE_SPOTIFY_CHECK_USERS_FOLLOWING:
                    # check users following.
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_check_users_following, ids
                    )

                elif service.service == SERVICE_SPOTIFY_GET_ALBUM:
                    # get spotify album.
                    album_id = service.data.get("album_id")
                    market = service.data.get("market")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_album, album_id, market
                    )

                elif service.service == SERVICE_SPOTIFY_GET_ALBUM_FAVORITES:
                    # get spotify album favorites.
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_album_favorites,
                        limit,
                        offset,
                        market,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_ALBUM_NEW_RELEASES:
                    # get spotify album favorites.
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    country = service.data.get("country")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_album_new_releases,
                        limit,
                        offset,
                        country,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_ALBUM_TRACKS:
                    # get spotify album favorites.
                    album_id = service.data.get("album_id")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_album_tracks,
                        album_id,
                        limit,
                        offset,
                        market,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_ARTIST:
                    # get spotify artist.
                    artist_id = service.data.get("artist_id")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_artist, artist_id
                    )

                elif service.service == SERVICE_SPOTIFY_GET_ARTIST_ALBUMS:
                    # get spotify artist albums.
                    artist_id = service.data.get("artist_id")
                    include_groups = service.data.get("include_groups")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_artist_albums,
                        artist_id,
                        include_groups,
                        limit,
                        offset,
                        market,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_ARTIST_INFO:
                    # get spotify artist info.
                    artist_id = service.data.get("artist_id")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_artist_info, artist_id
                    )

                elif service.service == SERVICE_SPOTIFY_GET_ARTIST_RELATED_ARTISTS:
                    # get spotify artist related artists.
                    artist_id = service.data.get("artist_id")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_artist_related_artists,
                        artist_id,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_ARTIST_TOP_TRACKS:
                    # get spotify artist top artists.
                    artist_id = service.data.get("artist_id")
                    market = service.data.get("market")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_artist_top_tracks,
                        artist_id,
                        market,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_ARTISTS_FOLLOWED:
                    # get spotify artists followed.
                    after = service.data.get("after")
                    limit = service.data.get("limit")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_artists_followed,
                        after,
                        limit,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_AUDIOBOOK:
                    # get spotify audiobook.
                    audiobook_id = service.data.get("audiobook_id")
                    market = service.data.get("market")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_audiobook, audiobook_id, market
                    )

                elif service.service == SERVICE_SPOTIFY_GET_AUDIOBOOK_CHAPTERS:
                    # get spotify audiobook chapters.
                    audiobook_id = service.data.get("audiobook_id")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_audiobook_chapters,
                        audiobook_id,
                        limit,
                        offset,
                        market,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_AUDIOBOOK_FAVORITES:
                    # get spotify audiobook favorites.
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_audiobook_favorites,
                        limit,
                        offset,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_BROWSE_CATEGORYS_LIST:
                    # get spotify browse categorys.
                    country = service.data.get("country")
                    locale = service.data.get("locale")
                    refresh = service.data.get("refresh")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_browse_categorys_list,
                        country,
                        locale,
                        refresh,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_CATEGORY_PLAYLISTS:
                    # get spotify featured playlists.
                    category_id = service.data.get("category_id")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    country = service.data.get("country")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_category_playlists,
                        category_id,
                        limit,
                        offset,
                        country,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_CHAPTER:
                    # get spotify audiobook chapter details.
                    chapter_id = service.data.get("chapter_id")
                    market = service.data.get("market")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_chapter, chapter_id, market
                    )

                elif service.service == SERVICE_SPOTIFY_GET_EPISODE:
                    # get spotify episode details.
                    episode_id = service.data.get("episode_id")
                    market = service.data.get("market")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_episode, episode_id, market
                    )

                elif service.service == SERVICE_SPOTIFY_GET_EPISODE_FAVORITES:
                    # get spotify episode (podcast) favorites.
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_episode_favorites,
                        limit,
                        offset,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_FEATURED_PLAYLISTS:
                    # get spotify featured playlists.
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    country = service.data.get("country")
                    locale = service.data.get("locale")
                    timestamp = service.data.get("timestamp")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_featured_playlists,
                        limit,
                        offset,
                        country,
                        locale,
                        timestamp,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_PLAYER_DEVICES:
                    # get spotify player device list.
                    refresh = service.data.get("refresh")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_player_devices, refresh, sort_result
                    )

                elif service.service == SERVICE_SPOTIFY_GET_PLAYER_NOW_PLAYING:
                    # get spotify player now playing.
                    market = service.data.get("market")
                    additional_types = service.data.get("additional_types")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_player_now_playing,
                        market,
                        additional_types,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_PLAYER_PLAYBACK_STATE:
                    # get spotify player playback state.
                    market = service.data.get("market")
                    additional_types = service.data.get("additional_types")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_player_playback_state,
                        market,
                        additional_types,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_PLAYER_QUEUE_INFO:
                    # get spotify queue info.
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_player_queue_info
                    )

                elif service.service == SERVICE_SPOTIFY_GET_PLAYER_RECENT_TRACKS:
                    # get spotify playlist favorites.
                    limit = service.data.get("limit")
                    after = service.data.get("after")
                    before = service.data.get("before")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_player_recent_tracks,
                        limit,
                        after,
                        before,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_PLAYLIST:
                    # get spotify playlist.
                    playlist_id = service.data.get("playlist_id")
                    market = service.data.get("market")
                    fields = service.data.get("fields")
                    additional_types = service.data.get("additional_types")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_playlist,
                        playlist_id,
                        market,
                        fields,
                        additional_types,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_PLAYLIST_COVER_IMAGE:
                    # get spotify playlist cover image.
                    playlist_id = service.data.get("playlist_id")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_playlist_cover_image, playlist_id
                    )

                elif service.service == SERVICE_SPOTIFY_GET_PLAYLIST_FAVORITES:
                    # get spotify playlist favorites.
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_playlist_favorites,
                        limit,
                        offset,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_PLAYLIST_ITEMS:
                    # get spotify playlist items.
                    playlist_id = service.data.get("playlist_id")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    fields = service.data.get("fields")
                    additional_types = service.data.get("additional_types")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_playlist_items,
                        playlist_id,
                        limit,
                        offset,
                        market,
                        fields,
                        additional_types,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_PLAYLISTS_FOR_USER:
                    # get spotify playlists for specified user-id.
                    user_id = service.data.get("user_id")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_playlists_for_user,
                        user_id,
                        limit,
                        offset,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_SHOW:
                    # get spotify show (podcast) episodes.
                    show_id = service.data.get("show_id")
                    market = service.data.get("market")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_show, show_id, market
                    )

                elif service.service == SERVICE_SPOTIFY_GET_SHOW_EPISODES:
                    # get spotify show (podcast) episodes.
                    show_id = service.data.get("show_id")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_show_episodes,
                        show_id,
                        limit,
                        offset,
                        market,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_SHOW_FAVORITES:
                    # get spotify show (podcast) favorites.
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    exclude_audiobooks = service.data.get("exclude_audiobooks")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_show_favorites,
                        limit,
                        offset,
                        limit_total,
                        sort_result,
                        exclude_audiobooks,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICE:
                    # get spotify connect device list.
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    device_value = service.data.get("device_value")
                    verify_user_context = service.data.get("verify_user_context")
                    verify_timeout = service.data.get("verify_timeout")
                    refresh_device_list = service.data.get("refresh_device_list")
                    activate_device = service.data.get("activate_device")
                    delay = service.data.get("delay")
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_spotify_connect_device,
                        device_value,
                        verify_user_context,
                        verify_timeout,
                        refresh_device_list,
                        activate_device,
                        delay,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICES:
                    # get spotify connect device list.
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    refresh = service.data.get("refresh")
                    sort_result = service.data.get("sort_result")
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_spotify_connect_devices,
                        refresh,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_TRACK:
                    # get spotify track details.
                    track_id = service.data.get("track_id")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_track, track_id
                    )

                elif service.service == SERVICE_SPOTIFY_GET_TRACK_FAVORITES:
                    # get spotify track favorites.
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_track_favorites,
                        limit,
                        offset,
                        market,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_TRACK_RECOMMENDATIONS:
                    # get spotify track recommendations.
                    limit = service.data.get("limit")
                    market = service.data.get("market")
                    seed_artists = service.data.get("seed_artists")
                    seed_genres = service.data.get("seed_genres")
                    seed_tracks = service.data.get("seed_tracks")
                    min_acousticness = service.data.get("min_acousticness")
                    max_acousticness = service.data.get("max_acousticness")
                    target_acousticness = service.data.get("target_acousticness")
                    min_danceability = service.data.get("min_danceability")
                    max_danceability = service.data.get("max_danceability")
                    target_danceability = service.data.get("target_danceability")
                    min_duration_ms = service.data.get("min_duration_ms")
                    max_duration_ms = service.data.get("max_duration_ms")
                    target_duration_ms = service.data.get("target_duration_ms")
                    min_energy = service.data.get("min_energy")
                    max_energy = service.data.get("max_energy")
                    target_energy = service.data.get("target_energy")
                    min_instrumentalness = service.data.get("min_instrumentalness")
                    max_instrumentalness = service.data.get("max_instrumentalness")
                    target_instrumentalness = service.data.get(
                        "target_instrumentalness"
                    )
                    min_key = service.data.get("min_key")
                    max_key = service.data.get("max_key")
                    target_key = service.data.get("target_key")
                    min_liveness = service.data.get("min_liveness")
                    max_liveness = service.data.get("max_liveness")
                    target_liveness = service.data.get("target_liveness")
                    min_loudness = service.data.get("min_loudness")
                    max_loudness = service.data.get("max_loudness")
                    target_loudness = service.data.get("target_loudness")
                    min_mode = service.data.get("min_mode")
                    max_mode = service.data.get("max_mode")
                    target_mode = service.data.get("target_mode")
                    min_popularity = service.data.get("min_popularity")
                    max_popularity = service.data.get("max_popularity")
                    target_popularity = service.data.get("target_popularity")
                    min_speechiness = service.data.get("min_speechiness")
                    max_speechiness = service.data.get("max_speechiness")
                    target_speechiness = service.data.get("target_speechiness")
                    min_tempo = service.data.get("min_tempo")
                    max_tempo = service.data.get("max_tempo")
                    target_tempo = service.data.get("target_tempo")
                    min_time_signature = service.data.get("min_time_signature")
                    max_time_signature = service.data.get("max_time_signature")
                    target_time_signature = service.data.get("target_time_signature")
                    min_valence = service.data.get("min_valence")
                    max_valence = service.data.get("max_valence")
                    target_valence = service.data.get("target_valence")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_track_recommendations,
                        limit,
                        market,
                        seed_artists,
                        seed_genres,
                        seed_tracks,
                        min_acousticness,
                        max_acousticness,
                        target_acousticness,
                        min_danceability,
                        max_danceability,
                        target_danceability,
                        min_duration_ms,
                        max_duration_ms,
                        target_duration_ms,
                        min_energy,
                        max_energy,
                        target_energy,
                        min_instrumentalness,
                        max_instrumentalness,
                        target_instrumentalness,
                        min_key,
                        max_key,
                        target_key,
                        min_liveness,
                        max_liveness,
                        target_liveness,
                        min_loudness,
                        max_loudness,
                        target_loudness,
                        min_mode,
                        max_mode,
                        target_mode,
                        min_popularity,
                        max_popularity,
                        target_popularity,
                        min_speechiness,
                        max_speechiness,
                        target_speechiness,
                        min_tempo,
                        max_tempo,
                        target_tempo,
                        min_time_signature,
                        max_time_signature,
                        target_time_signature,
                        min_valence,
                        max_valence,
                        target_valence,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_TRACKS_AUDIO_FEATURES:
                    # get spotify album favorites.
                    limit = service.data.get("limit")
                    ids = service.data.get("ids")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_tracks_audio_features, ids
                    )

                elif service.service == SERVICE_SPOTIFY_GET_USERS_TOP_ARTISTS:
                    # get spotify users top artists.
                    time_range = service.data.get("time_range")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_users_top_artists,
                        time_range,
                        limit,
                        offset,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_GET_USERS_TOP_TRACKS:
                    # get spotify users top artists.
                    time_range = service.data.get("time_range")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    limit_total = service.data.get("limit_total")
                    sort_result = service.data.get("sort_result")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_get_users_top_tracks,
                        time_range,
                        limit,
                        offset,
                        limit_total,
                        sort_result,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_ACTIVATE_DEVICES:
                    # activate all spotify connect player devices.
                    verify_user_context = service.data.get("verify_user_context")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_player_activate_devices,
                        verify_user_context,
                        delay,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYER_RESOLVE_DEVICE_ID:
                    # resolve spotify connect player device id.
                    device_value = service.data.get("device_value")
                    verify_user_context = service.data.get("verify_user_context")
                    verify_timeout = service.data.get("verify_timeout")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_player_resolve_device_id,
                        device_value,
                        verify_user_context,
                        verify_timeout,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYLIST_ITEMS_ADD:
                    # add items to playlist.
                    playlist_id = service.data.get("playlist_id")
                    uris = service.data.get("uris")
                    position = service.data.get("position")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_playlist_items_add,
                        playlist_id,
                        uris,
                        position,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYLIST_ITEMS_CLEAR:
                    # clear all items from playlist.
                    playlist_id = service.data.get("playlist_id")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_playlist_items_clear, playlist_id
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYLIST_CREATE:
                    # create a new playlist.
                    user_id = service.data.get("user_id")
                    name = service.data.get("name")
                    description = service.data.get("description")
                    public = service.data.get("public")
                    collaborative = service.data.get("collaborative")
                    image_path = service.data.get("image_path")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_playlist_create,
                        user_id,
                        name,
                        description,
                        public,
                        collaborative,
                        image_path,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYLIST_ITEMS_REMOVE:
                    # add items to playlist.
                    playlist_id = service.data.get("playlist_id")
                    uris = service.data.get("uris")
                    snapshot_id = service.data.get("snapshot_id")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_playlist_items_remove,
                        playlist_id,
                        uris,
                        snapshot_id,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYLIST_ITEMS_REORDER:
                    # reorder playlist items.
                    playlist_id = service.data.get("playlist_id")
                    range_start = service.data.get("range_start")
                    insert_before = service.data.get("insert_before")
                    range_length = service.data.get("range_length")
                    snapshot_id = service.data.get("snapshot_id")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_playlist_items_reorder,
                        playlist_id,
                        range_start,
                        insert_before,
                        range_length,
                        snapshot_id,
                    )

                elif service.service == SERVICE_SPOTIFY_PLAYLIST_ITEMS_REPLACE:
                    # replace playlist items.
                    playlist_id = service.data.get("playlist_id")
                    uris = service.data.get("uris")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_playlist_items_replace, playlist_id, uris
                    )

                elif service.service == SERVICE_SPOTIFY_SEARCH_ALBUMS:
                    # search Spotify for specified criteria.
                    criteria = service.data.get("criteria")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    include_external = service.data.get("include_external")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_search_albums,
                        criteria,
                        limit,
                        offset,
                        market,
                        include_external,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_SEARCH_ARTISTS:
                    # search Spotify for specified criteria.
                    criteria = service.data.get("criteria")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    include_external = service.data.get("include_external")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_search_artists,
                        criteria,
                        limit,
                        offset,
                        market,
                        include_external,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_SEARCH_AUDIOBOOKS:
                    # search Spotify for specified criteria.
                    criteria = service.data.get("criteria")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    include_external = service.data.get("include_external")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_search_audiobooks,
                        criteria,
                        limit,
                        offset,
                        market,
                        include_external,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_SEARCH_EPISODES:
                    # search Spotify for specified criteria.
                    criteria = service.data.get("criteria")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    include_external = service.data.get("include_external")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_search_episodes,
                        criteria,
                        limit,
                        offset,
                        market,
                        include_external,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_SEARCH_PLAYLISTS:
                    # search Spotify for specified criteria.
                    criteria = service.data.get("criteria")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    include_external = service.data.get("include_external")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_search_playlists,
                        criteria,
                        limit,
                        offset,
                        market,
                        include_external,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_SEARCH_SHOWS:
                    # search Spotify for specified criteria.
                    criteria = service.data.get("criteria")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    include_external = service.data.get("include_external")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_search_shows,
                        criteria,
                        limit,
                        offset,
                        market,
                        include_external,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_SEARCH_TRACKS:
                    # search Spotify for specified criteria.
                    criteria = service.data.get("criteria")
                    limit = service.data.get("limit")
                    offset = service.data.get("offset")
                    market = service.data.get("market")
                    include_external = service.data.get("include_external")
                    limit_total = service.data.get("limit_total")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_search_tracks,
                        criteria,
                        limit,
                        offset,
                        market,
                        include_external,
                        limit_total,
                    )

                elif service.service == SERVICE_SPOTIFY_ZEROCONF_DEVICE_CONNECT:
                    # spotify connect zeroconf device connect.
                    host_ipv4_address = service.data.get("host_ipv4_address")
                    host_ip_port = service.data.get("host_ip_port")
                    cpath = service.data.get("cpath")
                    version = service.data.get("version")
                    use_ssl = service.data.get("use_ssl")
                    username = service.data.get("username")
                    password = service.data.get("password")
                    loginid = service.data.get("loginid")
                    pre_disconnect = service.data.get("pre_disconnect")
                    verify_device_list_entry = service.data.get(
                        "verify_device_list_entry"
                    )
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_zeroconf_device_connect,
                        username,
                        password,
                        loginid,
                        host_ipv4_address,
                        host_ip_port,
                        cpath,
                        version,
                        use_ssl,
                        pre_disconnect,
                        verify_device_list_entry,
                        delay,
                    )

                elif service.service == SERVICE_SPOTIFY_ZEROCONF_DEVICE_DISCONNECT:
                    # spotify connect zeroconf device disconnect.
                    host_ipv4_address = service.data.get("host_ipv4_address")
                    host_ip_port = service.data.get("host_ip_port")
                    cpath = service.data.get("cpath")
                    version = service.data.get("version")
                    use_ssl = service.data.get("use_ssl")
                    delay = service.data.get("delay")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_zeroconf_device_disconnect,
                        host_ipv4_address,
                        host_ip_port,
                        cpath,
                        version,
                        use_ssl,
                        delay,
                    )

                elif service.service == SERVICE_SPOTIFY_ZEROCONF_DEVICE_GETINFO:
                    # spotify connect zeroconf device get information.
                    host_ipv4_address = service.data.get("host_ipv4_address")
                    host_ip_port = service.data.get("host_ip_port")
                    cpath = service.data.get("cpath")
                    version = service.data.get("version")
                    use_ssl = service.data.get("use_ssl")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_zeroconf_device_getinfo,
                        host_ipv4_address,
                        host_ip_port,
                        cpath,
                        version,
                        use_ssl,
                    )

                elif service.service == SERVICE_SPOTIFY_ZEROCONF_DISCOVER_DEVICES:
                    # zeroconf discover devices service.
                    timeout = service.data.get("timeout")
                    _logsi.LogVerbose(
                        STAppMessages.MSG_SERVICE_EXECUTE
                        % (service.service, entity.name)
                    )
                    response = await hass.async_add_executor_job(
                        entity.service_spotify_zeroconf_discover_devices, timeout
                    )

                else:
                    raise HomeAssistantError(
                        "Unrecognized service identifier '%s' in method service_handle_spotify_serviceresponse"
                        % service.service
                    )

                # return the response.
                _logsi.LogDictionary(
                    SILevel.Verbose,
                    "Service Response data: '%s'" % (service.service),
                    response,
                    prettyPrint=True,
                )
                return response

            except HomeAssistantError as ex:
                # log error, but not to system logger as HA will take care of it.
                _logsi.LogError(str(ex), logToSystemLogger=False)
                raise

            except Exception as ex:
                # log exception, but not to system logger as HA will take care of it.
                _logsi.LogException(
                    STAppMessages.MSG_SERVICE_REQUEST_EXCEPTION
                    % (service.service, "service_handle_getlist"),
                    ex,
                    logToSystemLogger=False,
                )
                raise

            finally:
                # trace.
                _logsi.LeaveMethod(SILevel.Debug)

        @staticmethod
        def _GetEntityFromServiceData(
            hass: HomeAssistant, service: ServiceCall, field_id: str
        ) -> MediaPlayerEntity:
            """
            Resolves a `MediaPlayerEntity` instance from a ServiceCall field id.

            Args:
                hass (HomeAssistant):
                    HomeAssistant instance.
                service (ServiceCall):
                    ServiceCall instance that contains service data (requested service name, field parameters, etc).
                field_id (str):
                    Service parameter field id whose value contains a SpotifyMediaPlayer entity id.
                    The ServiceCall data area will be queried with the field id to retrieve the entity id value.

            Returns:
                A `MediaPlayerEntity` instance if one could be resolved; otherwise, None.

            The service.data collection is queried for the field_id argument name.  If not supplied,
            then an error message is logged and the return value is None.

            The Haas data is then queried for the entity_id to retrieve the `MediaPlayerEntity` instance.
            """
            # get service parameter: entity_id.
            entity_id = service.data.get(field_id)
            if entity_id is None:
                _logsi.LogError(
                    STAppMessages.MSG_SERVICE_ARGUMENT_NULL, field_id, service.service
                )
                return None

            # search all MediaPlayerEntity instances for the specified entity_id.
            # if found, then return the MediaPlayerEntity instance.
            player: MediaPlayerEntity = None
            data: InstanceDataSpotify = None
            for data in hass.data[DOMAIN].values():
                if data.media_player.entity_id == entity_id:
                    player = data.media_player
                    break

            # did we resolve it? if not, then log a message.
            if player is None:
                raise HomeAssistantError(
                    "Entity id value of '%s' could not be resolved to a MediaPlayerEntity instance for the '%s' method call"
                    % (str(entity_id), service.service)
                )

            # return the MediaPlayerEntity instance.
            _logsi.LogVerbose(
                "Entity id value of '%s' was resolved to MediaPlayerEntity instance for the '%s' method call"
                % (str(entity_id), service.service)
            )
            return player

        # register all services this component provides, and their corresponding schemas.
        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_ADD_PLAYER_QUEUE_ITEMS,
            SERVICE_SPOTIFY_ADD_PLAYER_QUEUE_ITEMS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_ADD_PLAYER_QUEUE_ITEMS,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_ADD_PLAYER_QUEUE_ITEMS_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_CHECK_ALBUM_FAVORITES,
            SERVICE_SPOTIFY_CHECK_ALBUM_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_CHECK_ALBUM_FAVORITES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_CHECK_ALBUM_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_CHECK_ARTISTS_FOLLOWING,
            SERVICE_SPOTIFY_CHECK_ARTISTS_FOLLOWING_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_CHECK_ARTISTS_FOLLOWING,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_CHECK_ARTISTS_FOLLOWING_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_CHECK_AUDIOBOOK_FAVORITES,
            SERVICE_SPOTIFY_CHECK_AUDIOBOOK_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_CHECK_AUDIOBOOK_FAVORITES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_CHECK_AUDIOBOOK_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_CHECK_EPISODE_FAVORITES,
            SERVICE_SPOTIFY_CHECK_EPISODE_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_CHECK_EPISODE_FAVORITES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_CHECK_EPISODE_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_CHECK_PLAYLIST_FOLLOWERS,
            SERVICE_SPOTIFY_CHECK_PLAYLIST_FOLLOWERS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_CHECK_PLAYLIST_FOLLOWERS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_CHECK_PLAYLIST_FOLLOWERS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_CHECK_SHOW_FAVORITES,
            SERVICE_SPOTIFY_CHECK_SHOW_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_CHECK_SHOW_FAVORITES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_CHECK_SHOW_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_CHECK_TRACK_FAVORITES,
            SERVICE_SPOTIFY_CHECK_TRACK_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_CHECK_TRACK_FAVORITES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_CHECK_TRACK_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_CHECK_USERS_FOLLOWING,
            SERVICE_SPOTIFY_CHECK_USERS_FOLLOWING_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_CHECK_USERS_FOLLOWING,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_CHECK_USERS_FOLLOWING_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_FOLLOW_ARTISTS,
            SERVICE_SPOTIFY_FOLLOW_ARTISTS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_FOLLOW_ARTISTS,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_FOLLOW_ARTISTS_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_FOLLOW_PLAYLIST,
            SERVICE_SPOTIFY_FOLLOW_PLAYLIST_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_FOLLOW_PLAYLIST,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_FOLLOW_PLAYLIST_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_FOLLOW_USERS,
            SERVICE_SPOTIFY_FOLLOW_USERS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_FOLLOW_USERS,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_FOLLOW_USERS_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_GET_ALBUM,
            SERVICE_SPOTIFY_GET_ALBUM_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_ALBUM,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_ALBUM_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_ALBUM_FAVORITES,
            SERVICE_SPOTIFY_GET_ALBUM_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_ALBUM_FAVORITES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_ALBUM_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_ALBUM_NEW_RELEASES,
            SERVICE_SPOTIFY_GET_ALBUM_NEW_RELEASES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_ALBUM_NEW_RELEASES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_ALBUM_NEW_RELEASES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_ALBUM_TRACKS,
            SERVICE_SPOTIFY_GET_ALBUM_TRACKS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_ALBUM_TRACKS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_ALBUM_TRACKS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_GET_ARTIST,
            SERVICE_SPOTIFY_GET_ARTIST_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_ARTIST,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_ARTIST_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_ARTIST_ALBUMS,
            SERVICE_SPOTIFY_GET_ARTIST_ALBUMS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_ARTIST_ALBUMS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_ARTIST_ALBUMS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_ARTIST_INFO,
            SERVICE_SPOTIFY_GET_ARTIST_INFO_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_ARTIST_INFO,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_ARTIST_INFO_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_ARTIST_RELATED_ARTISTS,
            SERVICE_SPOTIFY_GET_ARTIST_RELATED_ARTISTS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_ARTIST_RELATED_ARTISTS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_ARTIST_RELATED_ARTISTS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_ARTIST_TOP_TRACKS,
            SERVICE_SPOTIFY_GET_ARTIST_TOP_TRACKS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_ARTIST_TOP_TRACKS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_ARTIST_TOP_TRACKS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_ARTISTS_FOLLOWED,
            SERVICE_SPOTIFY_GET_ARTISTS_FOLLOWED_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_ARTISTS_FOLLOWED,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_ARTISTS_FOLLOWED_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_GET_AUDIOBOOK,
            SERVICE_SPOTIFY_GET_AUDIOBOOK_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_AUDIOBOOK,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_AUDIOBOOK_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_AUDIOBOOK_CHAPTERS,
            SERVICE_SPOTIFY_GET_AUDIOBOOK_CHAPTERS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_AUDIOBOOK_CHAPTERS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_AUDIOBOOK_CHAPTERS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_AUDIOBOOK_FAVORITES,
            SERVICE_SPOTIFY_GET_AUDIOBOOK_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_AUDIOBOOK_FAVORITES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_AUDIOBOOK_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_BROWSE_CATEGORYS_LIST,
            SERVICE_SPOTIFY_GET_BROWSE_CATEGORYS_LIST_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_BROWSE_CATEGORYS_LIST,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_BROWSE_CATEGORYS_LIST_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_CATEGORY_PLAYLISTS,
            SERVICE_SPOTIFY_GET_CATEGORY_PLAYLISTS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_CATEGORY_PLAYLISTS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_CATEGORY_PLAYLISTS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_GET_CHAPTER,
            SERVICE_SPOTIFY_GET_CHAPTER_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_CHAPTER,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_CHAPTER_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_GET_EPISODE,
            SERVICE_SPOTIFY_GET_EPISODE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_EPISODE,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_EPISODE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_EPISODE_FAVORITES,
            SERVICE_SPOTIFY_GET_EPISODE_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_EPISODE_FAVORITES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_EPISODE_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_FEATURED_PLAYLISTS,
            SERVICE_SPOTIFY_GET_FEATURED_PLAYLISTS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_FEATURED_PLAYLISTS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_FEATURED_PLAYLISTS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_PLAYER_DEVICES,
            SERVICE_SPOTIFY_GET_PLAYER_DEVICES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_PLAYER_DEVICES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_PLAYER_DEVICES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_PLAYER_PLAYBACK_STATE,
            SERVICE_SPOTIFY_GET_PLAYER_PLAYBACK_STATE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_PLAYER_PLAYBACK_STATE,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_PLAYER_PLAYBACK_STATE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_PLAYER_NOW_PLAYING,
            SERVICE_SPOTIFY_GET_PLAYER_NOW_PLAYING_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_PLAYER_NOW_PLAYING,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_PLAYER_NOW_PLAYING_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_PLAYER_QUEUE_INFO,
            SERVICE_SPOTIFY_GET_PLAYER_QUEUE_INFO_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_PLAYER_QUEUE_INFO,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_PLAYER_QUEUE_INFO_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_PLAYER_RECENT_TRACKS,
            SERVICE_SPOTIFY_GET_PLAYER_RECENT_TRACKS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_PLAYER_RECENT_TRACKS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_PLAYER_RECENT_TRACKS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_GET_PLAYLIST,
            SERVICE_SPOTIFY_GET_PLAYLIST_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_PLAYLIST,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_PLAYLIST_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_PLAYLIST_COVER_IMAGE,
            SERVICE_SPOTIFY_GET_PLAYLIST_COVER_IMAGE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_PLAYLIST_COVER_IMAGE,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_PLAYLIST_COVER_IMAGE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_PLAYLIST_FAVORITES,
            SERVICE_SPOTIFY_GET_PLAYLIST_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_PLAYLIST_FAVORITES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_PLAYLIST_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_PLAYLIST_ITEMS,
            SERVICE_SPOTIFY_GET_PLAYLIST_ITEMS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_PLAYLIST_ITEMS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_PLAYLIST_ITEMS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_PLAYLISTS_FOR_USER,
            SERVICE_SPOTIFY_GET_PLAYLISTS_FOR_USER_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_PLAYLISTS_FOR_USER,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_PLAYLISTS_FOR_USER_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_GET_SHOW,
            SERVICE_SPOTIFY_GET_SHOW_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_SHOW,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_SHOW_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_SHOW_EPISODES,
            SERVICE_SPOTIFY_GET_SHOW_EPISODES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_SHOW_EPISODES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_SHOW_EPISODES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_SHOW_FAVORITES,
            SERVICE_SPOTIFY_GET_SHOW_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_SHOW_FAVORITES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_SHOW_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICE,
            SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICE,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICES,
            SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_SPOTIFY_CONNECT_DEVICES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_GET_TRACK,
            SERVICE_SPOTIFY_GET_TRACK_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_TRACK,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_TRACK_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_TRACK_FAVORITES,
            SERVICE_SPOTIFY_GET_TRACK_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_TRACK_FAVORITES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_TRACK_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_TRACK_RECOMMENDATIONS,
            SERVICE_SPOTIFY_GET_TRACK_RECOMMENDATIONS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_TRACK_RECOMMENDATIONS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_TRACK_RECOMMENDATIONS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_TRACKS_AUDIO_FEATURES,
            SERVICE_SPOTIFY_GET_TRACKS_AUDIO_FEATURES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_TRACKS_AUDIO_FEATURES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_TRACKS_AUDIO_FEATURES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_USERS_TOP_ARTISTS,
            SERVICE_SPOTIFY_GET_USERS_TOP_ARTISTS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_USERS_TOP_ARTISTS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_USERS_TOP_ARTISTS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_GET_USERS_TOP_TRACKS,
            SERVICE_SPOTIFY_GET_USERS_TOP_TRACKS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_GET_USERS_TOP_TRACKS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_GET_USERS_TOP_TRACKS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_ACTIVATE_DEVICES,
            SERVICE_SPOTIFY_PLAYER_ACTIVATE_DEVICES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_ACTIVATE_DEVICES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_PLAYER_ACTIVATE_DEVICES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_MEDIA_PAUSE,
            SERVICE_SPOTIFY_PLAYER_MEDIA_PAUSE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_MEDIA_PAUSE,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_MEDIA_PAUSE_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_CONTEXT,
            SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_CONTEXT_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_CONTEXT,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_CONTEXT_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACK_FAVORITES,
            SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACK_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACK_FAVORITES,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACK_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACKS,
            SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACKS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACKS,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_MEDIA_PLAY_TRACKS_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_MEDIA_RESUME,
            SERVICE_SPOTIFY_PLAYER_MEDIA_RESUME_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_MEDIA_RESUME,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_MEDIA_RESUME_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_MEDIA_SEEK,
            SERVICE_SPOTIFY_PLAYER_MEDIA_SEEK_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_MEDIA_SEEK,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_MEDIA_SEEK_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_NEXT,
            SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_NEXT_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_NEXT,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_NEXT_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_PREVIOUS,
            SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_PREVIOUS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_PREVIOUS,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_MEDIA_SKIP_PREVIOUS_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_RESOLVE_DEVICE_ID,
            SERVICE_SPOTIFY_PLAYER_RESOLVE_DEVICE_ID_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_RESOLVE_DEVICE_ID,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_PLAYER_RESOLVE_DEVICE_ID_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_SET_REPEAT_MODE,
            SERVICE_SPOTIFY_PLAYER_SET_REPEAT_MODE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_SET_REPEAT_MODE,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_SET_REPEAT_MODE_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_SET_SHUFFLE_MODE,
            SERVICE_SPOTIFY_PLAYER_SET_SHUFFLE_MODE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_SET_SHUFFLE_MODE,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_SET_SHUFFLE_MODE_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_SET_VOLUME_LEVEL,
            SERVICE_SPOTIFY_PLAYER_SET_VOLUME_LEVEL_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_SET_VOLUME_LEVEL,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_SET_VOLUME_LEVEL_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYER_TRANSFER_PLAYBACK,
            SERVICE_SPOTIFY_PLAYER_TRANSFER_PLAYBACK_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYER_TRANSFER_PLAYBACK,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYER_TRANSFER_PLAYBACK_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYLIST_COVER_IMAGE_ADD,
            SERVICE_SPOTIFY_PLAYLIST_COVER_IMAGE_ADD_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYLIST_COVER_IMAGE_ADD,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYLIST_COVER_IMAGE_ADD_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYLIST_CHANGE,
            SERVICE_SPOTIFY_PLAYLIST_CHANGE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYLIST_CHANGE,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_PLAYLIST_CHANGE_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYLIST_CREATE,
            SERVICE_SPOTIFY_PLAYLIST_CREATE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYLIST_CREATE,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_PLAYLIST_CREATE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYLIST_ITEMS_ADD,
            SERVICE_SPOTIFY_PLAYLIST_ITEMS_ADD_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYLIST_ITEMS_ADD,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_PLAYLIST_ITEMS_ADD_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYLIST_ITEMS_CLEAR,
            SERVICE_SPOTIFY_PLAYLIST_ITEMS_CLEAR_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYLIST_ITEMS_CLEAR,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_PLAYLIST_ITEMS_CLEAR_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYLIST_ITEMS_REMOVE,
            SERVICE_SPOTIFY_PLAYLIST_ITEMS_REMOVE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYLIST_ITEMS_REMOVE,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_PLAYLIST_ITEMS_REMOVE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYLIST_ITEMS_REORDER,
            SERVICE_SPOTIFY_PLAYLIST_ITEMS_REORDER_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYLIST_ITEMS_REORDER,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_PLAYLIST_ITEMS_REORDER_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_PLAYLIST_ITEMS_REPLACE,
            SERVICE_SPOTIFY_PLAYLIST_ITEMS_REPLACE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_PLAYLIST_ITEMS_REPLACE,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_PLAYLIST_ITEMS_REPLACE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_REMOVE_ALBUM_FAVORITES,
            SERVICE_SPOTIFY_REMOVE_ALBUM_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_REMOVE_ALBUM_FAVORITES,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_REMOVE_ALBUM_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_REMOVE_AUDIOBOOK_FAVORITES,
            SERVICE_SPOTIFY_REMOVE_AUDIOBOOK_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_REMOVE_AUDIOBOOK_FAVORITES,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_REMOVE_AUDIOBOOK_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_REMOVE_EPISODE_FAVORITES,
            SERVICE_SPOTIFY_REMOVE_EPISODE_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_REMOVE_EPISODE_FAVORITES,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_REMOVE_EPISODE_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_REMOVE_SHOW_FAVORITES,
            SERVICE_SPOTIFY_REMOVE_SHOW_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_REMOVE_SHOW_FAVORITES,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_REMOVE_SHOW_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_REMOVE_TRACK_FAVORITES,
            SERVICE_SPOTIFY_REMOVE_TRACK_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_REMOVE_TRACK_FAVORITES,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_REMOVE_TRACK_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_SAVE_ALBUM_FAVORITES,
            SERVICE_SPOTIFY_SAVE_ALBUM_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SAVE_ALBUM_FAVORITES,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_SAVE_ALBUM_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_SAVE_AUDIOBOOK_FAVORITES,
            SERVICE_SPOTIFY_SAVE_AUDIOBOOK_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SAVE_AUDIOBOOK_FAVORITES,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_SAVE_AUDIOBOOK_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_SAVE_EPISODE_FAVORITES,
            SERVICE_SPOTIFY_SAVE_EPISODE_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SAVE_EPISODE_FAVORITES,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_SAVE_EPISODE_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_SAVE_SHOW_FAVORITES,
            SERVICE_SPOTIFY_SAVE_SHOW_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SAVE_SHOW_FAVORITES,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_SAVE_SHOW_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_SAVE_TRACK_FAVORITES,
            SERVICE_SPOTIFY_SAVE_TRACK_FAVORITES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SAVE_TRACK_FAVORITES,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_SAVE_TRACK_FAVORITES_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_SEARCH_ALBUMS,
            SERVICE_SPOTIFY_SEARCH_ALBUMS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SEARCH_ALBUMS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_SEARCH_ALBUMS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_SEARCH_ARTISTS,
            SERVICE_SPOTIFY_SEARCH_ARTISTS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SEARCH_ARTISTS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_SEARCH_ARTISTS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_SEARCH_AUDIOBOOKS,
            SERVICE_SPOTIFY_SEARCH_AUDIOBOOKS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SEARCH_AUDIOBOOKS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_SEARCH_AUDIOBOOKS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_SEARCH_EPISODES,
            SERVICE_SPOTIFY_SEARCH_EPISODES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SEARCH_EPISODES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_SEARCH_EPISODES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_SEARCH_PLAYLISTS,
            SERVICE_SPOTIFY_SEARCH_PLAYLISTS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SEARCH_PLAYLISTS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_SEARCH_PLAYLISTS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_SEARCH_SHOWS,
            SERVICE_SPOTIFY_SEARCH_SHOWS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SEARCH_SHOWS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_SEARCH_SHOWS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_SEARCH_TRACKS,
            SERVICE_SPOTIFY_SEARCH_TRACKS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_SEARCH_TRACKS,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_SEARCH_TRACKS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_UNFOLLOW_ARTISTS,
            SERVICE_SPOTIFY_UNFOLLOW_ARTISTS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_UNFOLLOW_ARTISTS,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_UNFOLLOW_ARTISTS_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_UNFOLLOW_PLAYLIST,
            SERVICE_SPOTIFY_UNFOLLOW_PLAYLIST_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_UNFOLLOW_PLAYLIST,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_UNFOLLOW_PLAYLIST_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER % SERVICE_SPOTIFY_UNFOLLOW_USERS,
            SERVICE_SPOTIFY_UNFOLLOW_USERS_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_UNFOLLOW_USERS,
            service_handle_spotify_command,
            schema=SERVICE_SPOTIFY_UNFOLLOW_USERS_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_ZEROCONF_DEVICE_CONNECT,
            SERVICE_SPOTIFY_ZEROCONF_DEVICE_CONNECT_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_ZEROCONF_DEVICE_CONNECT,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_ZEROCONF_DEVICE_CONNECT_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_ZEROCONF_DEVICE_DISCONNECT,
            SERVICE_SPOTIFY_ZEROCONF_DEVICE_DISCONNECT_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_ZEROCONF_DEVICE_DISCONNECT,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_ZEROCONF_DEVICE_DISCONNECT_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_ZEROCONF_DEVICE_GETINFO,
            SERVICE_SPOTIFY_ZEROCONF_DEVICE_GETINFO_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_ZEROCONF_DEVICE_GETINFO,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_ZEROCONF_DEVICE_GETINFO_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        _logsi.LogObject(
            SILevel.Verbose,
            STAppMessages.MSG_SERVICE_REQUEST_REGISTER
            % SERVICE_SPOTIFY_ZEROCONF_DISCOVER_DEVICES,
            SERVICE_SPOTIFY_ZEROCONF_DISCOVER_DEVICES_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SPOTIFY_ZEROCONF_DISCOVER_DEVICES,
            service_handle_spotify_serviceresponse,
            schema=SERVICE_SPOTIFY_ZEROCONF_DISCOVER_DEVICES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        # indicate success.
        _logsi.LogVerbose("Component async_setup complete")
        return True

    finally:
        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up device instance from a config entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        entry (ConfigEntry):
            HomeAssistant configuration entry dictionary.  This contains configuration
            settings for the specific component device entry.

    The __init__.py module "async_setup_entry" method is executed for each device that is
    configured for the component.  It takes care of loading the device controller instance
    (e.g. SpotifyClient in our case) for each device that will be controlled.
    """
    try:
        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component async_setup_entry is starting - entry (ConfigEntry) object"
            % entry.title,
            entry,
        )
        _logsi.LogDictionary(
            SILevel.Verbose,
            "'%s': Component async_setup_entry entry.data dictionary" % entry.title,
            entry.data,
        )
        _logsi.LogDictionary(
            SILevel.Verbose,
            "'%s': Component async_setup_entry entry.options dictionary" % entry.title,
            entry.options,
        )

        # load config entry user-specified parameters.
        # ** no custom options for this integration.

        spotifyClient: SpotifyClient = None

        # get OAuth2 implementation and create an OAuth2 session.
        implementation = await async_get_config_entry_implementation(hass, entry)
        session = OAuth2Session(hass, entry, implementation)

        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component async_setup_entry OAuth2 implementation object"
            % entry.title,
            implementation,
        )
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component async_setup_entry OAuth2 session object" % entry.title,
            session,
        )
        _logsi.LogDictionary(
            SILevel.Verbose,
            "'%s': Component async_setup_entry OAuth2 session.token (dictionary)"
            % entry.title,
            session.token,
            prettyPrint=True,
        )

        # ensure we have a valid session token, and that the session is fully created.
        _logsi.LogVerbose(
            "'%s': Component async_setup_entry is calling async_ensure_token_valid to ensure OAuth2 session is fully-established"
            % entry.title
        )
        await session.async_ensure_token_valid()

        # -----------------------------------------------------------------------------------
        # Define DataUpdateCoordinator function.
        # -----------------------------------------------------------------------------------
        async def _update_devices() -> SpotifyConnectDevices:
            """
            DataUpdateCoordinator update method that will retrieve the list of Spotify Connect
            devices that are available.  This method will be executed by the DataUpdateCoordinator
            every 5 minutes to refresh the device list.

            Returns:
                A `SpotifyConnectDevices` instance.
            """

            shouldUpdate: bool = True

            try:
                _logsi.LogVerbose(
                    "'%s': Component DataUpdateCoordinator is retrieving Spotify device list"
                    % entry.title
                )

                # get spotify client cached device list.
                # if an internal device list cache is present, then use it IF it is less than 5 minutes old;
                # otherwise, call GetSpotifyConnectDevices to get the list and update the internal device list cache.
                # we check like this since some play commands update the internal device list cache,
                # so there is no need to update the device list (resource intensive) if it's not too stale.
                scDevices: SpotifyConnectDevices
                if "GetSpotifyConnectDevices" in spotifyClient.ConfigurationCache:
                    scDevices = spotifyClient.ConfigurationCache[
                        "GetSpotifyConnectDevices"
                    ]
                    if scDevices.AgeLastRefreshed > 300:
                        shouldUpdate = True
                    else:
                        _logsi.LogVerbose(
                            "'%s': Component DataUpdateCoordinator is using cached device list"
                            % entry.title
                        )

                # do we need to refresh the cache?
                if shouldUpdate:
                    # retrieve list of ALL available Spotify Connect devices.
                    scDevices = await hass.async_add_executor_job(
                        spotifyClient.GetSpotifyConnectDevices, True
                    )

                # trace.
                _logsi.LogDictionary(
                    SILevel.Verbose,
                    "'%s': Component DataUpdateCoordinator update results"
                    % entry.title,
                    scDevices.ToDictionary(),
                    prettyPrint=True,
                )
                return scDevices

            except Exception as ex:
                _logsi.LogException(
                    "'%s': Component DataUpdateCoordinator update exception"
                    % entry.title,
                    ex,
                )
                raise UpdateFailed from ex

        # -----------------------------------------------------------------------------------
        # Define OAuth2 Session Token Updater
        # -----------------------------------------------------------------------------------
        def _TokenUpdater() -> dict:
            """
            Callback function that will inform HA OAuth2 that a token needs to be refreshed.
            This method is called from SpotifyClient whenever a token needs to be refreshed.

            Returns:
                A dictionaty that contains the refreshed token.
            """
            token: dict = None

            try:
                # trace.
                _logsi.EnterMethod(SILevel.Debug)
                _logsi.LogVerbose(
                    "'%s': Component OAuth2 session token is either expired or not valid; calling async_refresh_token to refresh the token"
                    % entry.title
                )

                # note that we do NOT use the `async_ensure_token_valid` method here, as it may
                # determine that the token does not yet need to be refreshed (via self.valid_token).
                # at this point, the SpotifyClient instance KNOWS that the token needs to be refreshed.
                # we will call HA to refresh the token, and store the new token in the integration config entry.
                #
                # note that the `config_entry.data['token']` and `session.token` values should match, BUT
                # the refreshed `session.token` value will not change until AFTER `async_update_entry` is processed!
                #
                # the following steps will be performed to accomplish the above:
                # - get a reference to the HA OAuth2 session instance.
                # - call `async_refresh_token` to refresh the expired token.
                # - set a token `status` attribute to denote the configuration update is for a token refresh event.  this allows the
                #   `options_update_listener` to bypass the configuration reload processing since we only need to reload the configuration
                #   if the user initiated an options change via the UI (e.g. no need to reload the configuration for token updates).
                # - call the `add_job` method to add a job that will call `async_update_entry` to persist the refreshed token to config storage.
                # - return the refreshed token to the caller.

                # trace.
                _logsi.LogObject(
                    SILevel.Debug,
                    "'%s': Component OAuth2 implementation object" % entry.title,
                    implementation,
                )
                _logsi.LogDictionary(
                    SILevel.Verbose,
                    "'%s': Component OAuth2 session.token (pre-update)" % entry.title,
                    session.token,
                    prettyPrint=True,
                )

                # we will refresh the token from the `session.config_entry.data['token']` value (instead of
                # the `session.token` value) in case the token was refreshed in the `update` method.
                # note - the `session.token` value will not change until AFTER `async_update_entry` is processed!

                # refresh the session token.
                _logsi.LogVerbose(
                    "'%s': Component is calling async_refresh_token to refresh the session token"
                    % entry.title
                )
                token = run_coroutine_threadsafe(
                    session.implementation.async_refresh_token(
                        session.config_entry.data["token"]
                    ),
                    hass.loop,
                ).result()
                token[TOKEN_STATUS] = TOKEN_STATUS_REFRESH_EVENT

                # update token value in configuration entry data.
                # updating a config entry must be done in the event loop thread, as there is no sync API to update config entries!
                # the "hass.add_job" method is used to schedule a function in the event loop that calls hass.config_entries.async_update_entry.
                _logsi.LogDictionary(
                    SILevel.Verbose,
                    "'%s': Component is submitting add_job to call async_update_entry to update configuration entry data with refreshed token"
                    % entry.title,
                    token,
                    prettyPrint=True,
                )
                session.hass.add_job(
                    functools.partial(
                        session.hass.config_entries.async_update_entry,
                        session.config_entry,
                        data={**session.config_entry.data, "token": token},
                    )
                )

                # trace.
                # _logsi.LogDictionary(SILevel.Verbose, "'%s': Component OAuth2 session.token (post-update)" % entry.title, session.token, prettyPrint=True)
                _logsi.LogVerbose(
                    "'%s': Component OAuth2 session token refresh complete"
                    % entry.title
                )

                # return refreshed token to caller.
                return token

            except Exception as ex:
                # trace.
                _logsi.LogException(
                    "'%s': Component OAuth2 session token refresh exception: %s"
                    % (entry.title, str(ex)),
                    ex,
                )
                raise

            finally:
                # trace.
                _logsi.LeaveMethod(SILevel.Debug)

        # -----------------------------------------------------------------------------------
        # Continue with async_setup_entry
        # -----------------------------------------------------------------------------------

        # get shared zeroconf instance.
        _logsi.LogVerbose(
            "'%s': MediaPlayer async_setup_entry is storing the Zeroconf reference to the instanceData object"
            % entry.title
        )
        zeroconf_instance = await zeroconf.async_get_instance(hass)

        # create new spotify web api python client instance - "SpotifyClient()".
        _logsi.LogVerbose(
            "'%s': Component async_setup_entry is creating SpotifyClient instance"
            % entry.title
        )
        tokenStorageDir: str = "%s/.storage" % (hass.config.config_dir)
        tokenStorageFile: str = "%s_tokens.json" % (DOMAIN)
        spotifyClient: SpotifyClient = await hass.async_add_executor_job(
            SpotifyClient,
            None,  # manager:PoolManager=None,
            tokenStorageDir,  # tokenStorageDir:str=None,
            tokenStorageFile,  # tokenStorageFile:str=None,
            _TokenUpdater,  # tokenUpdater:Callable=None,
            zeroconf_instance,  # zeroconfClient:Zeroconf=None,
            entry.options.get(CONF_OPTION_DEVICE_USERNAME, None),
            entry.options.get(CONF_OPTION_DEVICE_PASSWORD, None),
            entry.options.get(CONF_OPTION_DEVICE_LOGINID, None),
        )
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component async_setup_entry spotifyClient object" % entry.title,
            spotifyClient,
        )

        # set spotify web api python token authorization from HA-managed OAuth2 session token.
        tokenProfileId: str = entry.data.get(CONF_ID)
        _logsi.LogVerbose(
            "'%s': Component async_setup_entry is setting SpotifyClient AuthToken from OAuth2 session token"
            % entry.title
        )
        await hass.async_add_executor_job(
            spotifyClient.SetAuthTokenFromToken,
            implementation.client_id,
            session.token,
            tokenProfileId,
        )

        # trace.
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component async_setup_entry spotifyClient object (with AuthToken)"
            % entry.title,
            spotifyClient,
        )
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component async_setup_entry Spotify UserProfile object"
            % entry.title,
            spotifyClient.UserProfile,
        )

        # define a data update coordinator that will poll for updated device entries every 5 minutes.
        device_coordinator: DataUpdateCoordinator[SpotifyConnectDevices] = (
            DataUpdateCoordinator(
                hass,
                _LOGGER,
                name=f"{entry.title} Devices",
                update_interval=timedelta(minutes=5),
                update_method=_update_devices,
            )
        )
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component async_setup_entry device DataUpdateCoordinator object"
            % entry.title,
            device_coordinator,
        )

        # wait for first refresh of data update coordinator to get the initial device list.
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component async_setup_entry waiting for device DataUpdateCoordinator initial update"
            % entry.title,
            device_coordinator,
        )
        await device_coordinator.async_config_entry_first_refresh()

        # create media player entity platform instance data.
        _logsi.LogVerbose(
            "'%s': Component async_setup_entry is creating the media player platform instance data object"
            % entry.title
        )
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = InstanceDataSpotify(
            devices=device_coordinator,
            session=session,
            spotifyClient=spotifyClient,
            media_player=None,
            options=entry.options,
        )
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component async_setup_entry media player platform instance data object"
            % entry.title,
            hass.data[DOMAIN][entry.entry_id],
        )

        # ensure session scope has not changed for the authorization token.
        if not set(session.token["scope"].split(" ")).issuperset(SPOTIFY_SCOPES):
            _logsi.LogVerbose(
                "'%s': Component async_setup_entry detected a session scope change"
                % entry.title
            )
            raise ConfigEntryAuthFailed

        # we are now ready for HA to create individual objects for each platform that
        # our device requires; in our case, it's just a media_player platform.
        # we initiate this by calling the `async_forward_entry_setups`, which
        # calls the `async_setup_entry` function in each platform module (e.g.
        # media_player.py) for each device instance.
        _logsi.LogVerbose(
            "'%s': Component async_setup_entry is forwarding configuration entry setups to create the individual media player platforms"
            % entry.title
        )
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # register an update listener to reload configuration entry when options are updated.
        # this will return an "unlisten" function, which will be added to the configuration
        # "on_unload" event handler to automatically unregister the update listener when
        # the configuration is unloaded.
        listenerRemovePtr = entry.add_update_listener(options_update_listener)
        _logsi.LogArray(
            SILevel.Verbose,
            "'%s': Component update listener has been registered and added to update listeners array (%d array items)"
            % (entry.title, len(entry.update_listeners)),
            entry.update_listeners,
        )

        entry.async_on_unload(listenerRemovePtr)
        _logsi.LogArray(
            SILevel.Verbose,
            "'%s': Component update listener auto-unregister method has been added to on_unload event handlers array (%d array items)"
            % (entry.title, len(entry._on_unload)),
            entry._on_unload,
        )

        # trace.
        _logsi.LogVerbose("'%s': Component async_setup_entry is complete" % entry.title)

        # indicate success.
        return True

    except Exception as ex:
        # this is usually caused by a temporary error (e.g. device unplugged, network connectivity, etc), in
        # which case the user will need to manually reload the device when the temporary condition is cleared.
        # if it's a permanent error (e.g. ip address change), then the user needs to correct the configuration.

        # trace.
        _logsi.LogException(
            "'%s': Component async_setup_entry exception" % entry.title,
            ex,
            logToSystemLogger=False,
        )

        # reset storage.
        spotifyClient = None

        # inform HA that the configuration is not ready.
        raise ConfigEntryNotReady from ex

    finally:
        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Unloads a configuration entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        entry (ConfigEntry):
            HomeAssistant configuration entry object.

    The __init__.py module "async_unload_entry" unloads a configuration entry.

    This method is called when a configuration entry is to be removed. The class
    needs to unload itself, and remove any callbacks.

    Note that any options update listeners (added via "add_update_listener") do not need
    to be removed, as they are already removed by the time this method is called.
    This is accomplished by the "entry.async_on_unload(listener)" call in async_setup_entry,
    which removes them from the configuration entry just before it is unloaded.

    Note that something changed with HA 2024.6 release that causes the `update_listeners` array
    to still contain entries; prior to this release, the `update_listeners` array was empty by this point.
    """
    try:
        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component async_unload_entry configuration entry" % entry.title,
            entry,
        )

        # unload any platforms this device supports.
        _logsi.LogVerbose(
            "'%s':Component async_unload_entry is unloading our device instance from the domain"
            % entry.title
        )
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

        # if unload was successful, then remove data associated with the device.
        if unload_ok:
            # remove instance data from domain.
            _logsi.LogVerbose(
                "'%s': Component async_unload_entry is removing our device instance data from the domain"
                % entry.title
            )
            data: InstanceDataSpotify = hass.data[DOMAIN].pop(entry.entry_id)
            _logsi.LogObject(
                SILevel.Verbose,
                "'%s': Component async_unload_entry unloaded configuration entry instance data"
                % entry.title,
                data,
            )

            # a quick check to make sure all update listeners were removed (see method doc notes above).
            if len(entry.update_listeners) > 0:
                _logsi.LogArray(
                    SILevel.Warning,
                    "'%s': Component configuration update_listener(s) did not get removed before configuration unload (%d items - should be 0 prioer to HA 2026.0 release, but after that release still contains entries)"
                    % (entry.title, len(entry.update_listeners)),
                    entry.update_listeners,
                )
                # 2024/06/08 - I commented out the following line to clear the `update_listeners`, as it was causing `ValueError: list.remove(x): x not in list`
                # exceptions starting with the HA 2024.6.0 release!
                # entry.update_listeners.clear()

        # return status to caller.
        _logsi.LogVerbose("'%s': Component async_unload_entry completed" % entry.title)
        return unload_ok

    finally:
        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Reload config entry.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        entry (ConfigEntry):
            HomeAssistant configuration entry object.

    The __init__.py module "async_reload_entry" reloads a configuration entry.

    This method is called when an entry/configured device is to be reloaded. The class
    needs to unload itself, remove callbacks, and call async_setup_entry.
    """
    try:
        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component async_reload_entry configuration entry" % entry.title,
            entry,
        )

        # unload the configuration entry.
        _logsi.LogVerbose(
            "'%s': Component async_reload_entry is unloading the configuration entry"
            % entry.title
        )
        await async_unload_entry(hass, entry)

        # reload (setup) the configuration entry.
        _logsi.LogVerbose(
            "'%s': Component async_reload_entry is reloading the configuration entry"
            % entry.title
        )
        await async_setup_entry(hass, entry)

        # trace.
        _logsi.LogVerbose("'%s': Component async_reload_entry completed" % entry.title)

    finally:
        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Configuration entry update event handler.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        entry (ConfigEntry):
            HomeAssistant configuration entry object.

    Reloads the config entry after updates have been applied to a configuration entry.

    This method is called when the configuration has been updated via any of the following methods:
    - user initiates a configuration change via the HA UI (e.g. options update, etc).
      in this scenario, we will reload the configuration to apply the updated settings.
    - when a call is made to async_update_entry with changed configuration data.
      in this scenario, we will reload the configuration to apply the updated settings.
    - authentication token is refreshed.
      in this scenario, we do NOT want to reload the configuration since options have not changed; it's
      just the authentication token that is being udpated, which will occur every 1 hour (controlled by
      Spotify Web API token expiration).
    """
    try:
        # trace.
        _logsi.EnterMethod(SILevel.Debug)
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': Component detected configuration entry options update" % entry.title,
            entry,
        )
        _logsi.LogDictionary(
            SILevel.Verbose,
            "'%s': Component options_update_listener entry.data dictionary"
            % entry.title,
            entry.data,
        )
        _logsi.LogDictionary(
            SILevel.Verbose,
            "'%s': Component options_update_listener entry.options dictionary"
            % entry.title,
            entry.options,
        )

        # check if the authentication token was refreshed; if not, then it's a user-initiated
        # change and the configuration should be reloaded to apply the changes.
        # if it IS an authentication token refresh, then do NOT reload the configuration.
        shouldReload: bool = True
        _logsi.LogVerbose(
            "'%s': Component options_update_listener is checking for authentication token refresh event"
            % entry.title
        )
        if entry.data is not None:
            token: dict = entry.data.get("token", None)
            if token is not None:
                _logsi.LogDictionary(
                    SILevel.Verbose,
                    "'%s': Component options_update_listener token data" % entry.title,
                    token,
                )
                status = token.get(TOKEN_STATUS, None)
                if status == TOKEN_STATUS_REFRESH_EVENT:
                    # token refresh detected; indicate configuration should not be reloaded, and remove
                    # the token status key so it's not saved with the configuration data.
                    shouldReload = False
                    entry.data["token"].pop(TOKEN_STATUS, None)
                    _logsi.LogVerbose(
                        "'%s': Component options_update_listener detected authentication token refresh; configuration will NOT be reloaded"
                        % entry.title
                    )

        # reload the configuration entry (if necessary).
        if shouldReload:
            _logsi.LogVerbose(
                "'%s': Component options_update_listener is reloading the configuration (due to UI options change)"
                % entry.title
            )
            await hass.config_entries.async_reload(entry.entry_id)
        else:
            _logsi.LogVerbose(
                "'%s': Component options_update_listener is NOT reloading the configuration (due to token refresh)"
                % entry.title
            )

        # trace.
        _logsi.LogVerbose(
            "'%s': Component options_update_listener completed" % entry.title
        )

    finally:
        # trace.
        _logsi.LeaveMethod(SILevel.Debug)
