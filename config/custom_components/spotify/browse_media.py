# noqa: ignore=all

"""Support for Spotify media browsing."""

from __future__ import annotations
from functools import partial
from enum import StrEnum
import logging
import base64
import os
import pickle
from typing import Any

from spotifywebapipython import SpotifyClient
from spotifywebapipython.models import *

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

# get smartinspect logger reference; create a new session for this module name.
from smartinspectpython.siauto import (
    SIAuto,
    SILevel,
    SISession,
    SIMethodParmListContext,
)
import logging

_logsi: SISession = SIAuto.Si.GetSession(__name__)
if _logsi == None:
    _logsi = SIAuto.Si.AddSession(__name__, True)
_logsi.SystemLogger = logging.getLogger(__name__)


MEDIA_TYPE_SHOW = "show"
""" Spotify Show media type (aka PODCAST in HA) """


class BrowsableMedia(StrEnum):
    """
    Enum of browsable media.
    Contains the library root node key value definitions.
    """

    # library custom root node title definitions.
    SPOTIFY_LIBRARY_INDEX = "spotify_library_index"
    SPOTIFY_CATEGORY_PLAYLISTS = "spotify_category_playlists"
    SPOTIFY_CATEGORY_PLAYLISTS_MADEFORYOU = "spotify_category_playlists_madeforyou"
    SPOTIFY_CATEGORYS = "spotify_categorys"
    SPOTIFY_FEATURED_PLAYLISTS = "spotify_featured_playlists"
    SPOTIFY_NEW_RELEASES = "spotify_new_releases"
    SPOTIFY_USER_FOLLOWED_ARTISTS = "spotify_user_followed_artists"
    SPOTIFY_USER_PLAYLISTS = "spotify_user_playlists"
    SPOTIFY_USER_RECENTLY_PLAYED = "spotify_user_recently_played"
    SPOTIFY_USER_SAVED_ALBUMS = "spotify_user_saved_albums"
    SPOTIFY_USER_SAVED_SHOWS = "spotify_user_saved_shows"
    SPOTIFY_USER_SAVED_TRACKS = "spotify_user_saved_tracks"
    SPOTIFY_USER_TOP_ARTISTS = "spotify_user_top_artists"
    SPOTIFY_USER_TOP_TRACKS = "spotify_user_top_tracks"


# Spotify Library index definitions, containing media attributes that control content display.
# The order listed is how they are displayed in the media browser.
SPOTIFY_LIBRARY_MAP = {
    BrowsableMedia.SPOTIFY_LIBRARY_INDEX.value: {
        "title": "Spotify Media Library",
        "image": None,
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.DIRECTORY,
        "is_index_item": False,
    },
    BrowsableMedia.SPOTIFY_USER_PLAYLISTS.value: {
        "title": "Playlists",
        "title_node": "Spotify Playlist Favorites",
        "image": f"/local/images/{DOMAIN}_medialib_playlists.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PLAYLIST,
    },
    BrowsableMedia.SPOTIFY_USER_FOLLOWED_ARTISTS.value: {
        "title": "Artists",
        "title_node": "Spotify Artists Followed",
        "image": f"/local/images/{DOMAIN}_medialib_artists.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ARTIST,
    },
    BrowsableMedia.SPOTIFY_USER_SAVED_ALBUMS.value: {
        "title": "Albums",
        "title_node": "Spotify Album Favorites",
        "image": f"/local/images/{DOMAIN}_medialib_albums.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ALBUM,
    },
    BrowsableMedia.SPOTIFY_USER_SAVED_TRACKS.value: {
        "title": "Tracks",
        "title_node": "Spotify Track Favorites",
        "image": f"/local/images/{DOMAIN}_medialib_tracks.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.SPOTIFY_USER_SAVED_SHOWS.value: {
        "title": "Podcasts",
        "title_node": "Spotify Podcast Favorites",
        "image": f"/local/images/{DOMAIN}_medialib_podcasts.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PODCAST,
    },
    BrowsableMedia.SPOTIFY_USER_TOP_ARTISTS.value: {
        "title": "Top Artists",
        "title_node": "Spotify Top Artists",
        "image": f"/local/images/{DOMAIN}_medialib_top_artists.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ARTIST,
    },
    BrowsableMedia.SPOTIFY_USER_TOP_TRACKS.value: {
        "title": "Top Tracks",
        "title_node": "Spotify Top Tracks",
        "image": f"/local/images/{DOMAIN}_medialib_top_tracks.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    BrowsableMedia.SPOTIFY_FEATURED_PLAYLISTS.value: {
        "title": "Featured Playlists",
        "title_node": "Spotify Featured Playlists",
        "image": f"/local/images/{DOMAIN}_medialib_featured_playlists.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PLAYLIST,
    },
    BrowsableMedia.SPOTIFY_NEW_RELEASES.value: {
        "title": "New Releases",
        "title_node": "Spotify New Releases",
        "image": f"/local/images/{DOMAIN}_medialib_new_releases.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.ALBUM,
    },
    BrowsableMedia.SPOTIFY_CATEGORYS.value: {
        "title": "Categories",
        "title_node": "Spotify Categories ",
        "image": f"/local/images/{DOMAIN}_medialib_categorys.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.GENRE,
    },
    BrowsableMedia.SPOTIFY_CATEGORY_PLAYLISTS.value: {
        "title": "Category Playlists",
        "title_node": "Spotify Category Playlists",
        "image": f"/local/images/{DOMAIN}_medialib_category_playlists.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PLAYLIST,
        "is_index_item": False,
    },
    BrowsableMedia.SPOTIFY_CATEGORY_PLAYLISTS_MADEFORYOU.value: {
        "title": "Made For You",
        "title_node": "Spotify Playlists Made For You",
        "image": f"/local/images/{DOMAIN}_medialib_spotify_category_playlists_made_for_you.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.PLAYLIST,
    },
    BrowsableMedia.SPOTIFY_USER_RECENTLY_PLAYED.value: {
        "title": "Recently Played",
        "title_node": "Spotify Recently Played",
        "image": f"/local/images/{DOMAIN}_medialib_recently_played.png",
        "parent": MediaClass.DIRECTORY,
        "children": MediaClass.TRACK,
    },
    # the following are HA media types, and will not be displayed in the library index.
    # they are required for playing base-level types of media for this library index.
    MediaType.ALBUM: {
        "parent": MediaClass.ALBUM,
        "children": MediaClass.TRACK,
        "is_index_item": False,
    },
    MediaType.ARTIST: {
        "parent": MediaClass.ARTIST,
        "children": MediaClass.ALBUM,
        "is_index_item": False,
    },
    MediaType.EPISODE: {
        "parent": MediaClass.EPISODE,
        "children": None,
        "is_index_item": False,
    },
    MediaType.GENRE: {
        "parent": MediaClass.PLAYLIST,
        "children": MediaClass.TRACK,
        "is_index_item": False,
    },
    MediaType.PLAYLIST: {
        "parent": MediaClass.PLAYLIST,
        "children": MediaClass.TRACK,
        "is_index_item": False,
    },
    MediaType.PODCAST: {
        "parent": MediaClass.PODCAST,
        "children": MediaClass.EPISODE,
        "is_index_item": False,
    },
    MEDIA_TYPE_SHOW: {
        "parent": MediaClass.PODCAST,
        "children": MediaClass.EPISODE,
        "is_index_item": False,
    },
    MediaType.TRACK: {
        "parent": MediaClass.TRACK,
        "children": None,
        "is_index_item": False,
    },
}
"""
# Spotify Library index definitions, containing media attributes that control content display.
# The order listed is how they are displayed in the media browser.
"""

BROWSE_LIMIT = 50
""" Max number of items to return from a Spotify Web API query. """

SPOTIFY_BROWSE_LIMIT_TOTAL = 100
""" Max number of items to return from a Spotify integration request that supports paging. """

CATEGORY_BASE64: str = "category_base64::"
""" Eye-catcher used to denote a serialized ContentItem. """

LOCAL_IMAGE_PREFIX: str = "/local/"
""" Local image prefix value. """

PLAYABLE_MEDIA_TYPES = [
    MediaType.PLAYLIST,
    MediaType.ALBUM,
    MediaType.ARTIST,
    MediaType.EPISODE,
    MediaType.PODCAST,
    MEDIA_TYPE_SHOW,
    MediaType.TRACK,
]
""" Array of all media types that are playable. """


class MissingMediaInformation(BrowseError):
    """Missing media required information."""


class UnknownMediaType(BrowseError):
    """Unknown media type."""


def deserialize_object(txt: str) -> object:
    """
    Deserialize an object from a plain text string.

    Args:
        txt (str):
            The serialized version of the object in the form of a string.

    Returns:
        An object that was deserialized from a base64 string representation.
    """
    base64_bytes = txt.encode("ascii")
    message_bytes = base64.b64decode(base64_bytes)
    obj = pickle.loads(message_bytes)
    return obj


@staticmethod
def serialize_object(obj: object) -> str:
    """
    Serialize an object into a plain text string.

    Args:
        obj (object):
            The object to serialize.

    Returns:
        A serialized base64 string representation of the object.
    """
    message_bytes = pickle.dumps(obj)
    base64_bytes = base64.b64encode(message_bytes)
    txt = base64_bytes.decode("ascii")
    return txt


async def async_browse_media_library_index(
    hass: HomeAssistant,
    client: SpotifyClient,
    playerName: str,
    source: str | None,
    libraryMap: dict,
    libraryIndex: BrowsableMedia,
    media_content_type: str | None,
    media_content_id: str | None,
) -> BrowseMedia:
    """
    Builds a BrowseMedia object for the top level index page, and all of it's
    child nodes.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        client (SpotifyClient):
            The SpotifyClient instance that will make calls to the device
            to retrieve the data for display in the media browser.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        source (str):
            Currently selected source value.
        libraryMap (dict):
            The library map that contains media content attributes for each library index entry.
        libraryIndex (BrowseMedia):
            The library index of media content types.
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.
    """
    methodParms: SIMethodParmListContext = None

    try:
        # trace.
        methodParms = _logsi.EnterMethodParmList(SILevel.Debug)
        methodParms.AppendKeyValue("playerName", playerName)
        methodParms.AppendKeyValue("source", source)
        methodParms.AppendKeyValue("libraryMap", libraryMap)
        methodParms.AppendKeyValue("libraryIndex", libraryIndex)
        methodParms.AppendKeyValue("media_content_type", media_content_type)
        methodParms.AppendKeyValue("media_content_id", media_content_id)
        _logsi.LogMethodParmList(
            SILevel.Verbose,
            "'%s': browsing for media - top level index: '%s'"
            % (playerName, libraryIndex),
            methodParms,
        )

        # validations.
        if source is None:
            source = "unknownSource"

        # get parent media atttributes based upon selected media content type.
        parentAttrs: dict[str, Any] = libraryMap.get(libraryIndex.value, None)
        _logsi.LogDictionary(
            SILevel.Verbose,
            "'%s': BrowseMedia attributes for parent media content type: '%s'"
            % (playerName, libraryIndex.value),
            parentAttrs,
        )

        # create the index.
        browseMedia: BrowseMedia = BrowseMedia(
            can_expand=True,
            can_play=False,
            children=[],
            children_media_class=parentAttrs["children"],
            media_class=parentAttrs["parent"],
            media_content_id=libraryIndex.value,
            media_content_type=libraryIndex.value,
            thumbnail=parentAttrs["image"],
            title=parentAttrs["title"],
        )

        # add child items to the index.
        for mediaType, childAttrs in libraryMap.items():
            # if not an index item then don't bother.
            isIndexItem: bool = childAttrs.get("is_index_item", True)
            if not isIndexItem:
                continue

            # trace.
            # _logsi.LogDictionary(SILevel.Verbose, "'%s': BrowseMedia attributes for child media content type: '%s'" % (playerName, mediaType), childAttrs)

            # if a LOCAL index image was specified, then ensure it exists.
            # otherwise, default to null.
            image: str = childAttrs.get("image", None)
            if image is not None and image.startswith(LOCAL_IMAGE_PREFIX):
                imagePath: str = "%s/www/%s" % (
                    hass.config.config_dir,
                    image[len(LOCAL_IMAGE_PREFIX) :],
                )
                if not os.path.exists(imagePath):
                    # _logsi.LogVerbose("'%s': could not find logo image path '%s'; image will be reset to null" % (playerName, imagePath))
                    image = None

            browseMediaChild: BrowseMedia = BrowseMedia(
                can_expand=True,
                can_play=False,
                children=None,
                children_media_class=childAttrs["children"],
                media_class=childAttrs["parent"],
                media_content_id=f"{mediaType}",
                media_content_type=f"{mediaType}",
                thumbnail=image,
                title=childAttrs["title"],
            )
            browseMedia.children.append(browseMediaChild)
            _logsi.LogObject(
                SILevel.Verbose,
                "'%s': BrowseMedia Child Object: Type='%s', Id='%s', Title='%s'"
                % (
                    playerName,
                    browseMediaChild.media_content_type,
                    browseMediaChild.media_content_id,
                    browseMediaChild.title,
                ),
                browseMediaChild,
            )

        # trace.
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': BrowseMedia Parent Object: Type='%s', Id='%s', Title='%s'"
            % (
                playerName,
                browseMedia.media_content_type,
                browseMedia.media_content_id,
                browseMedia.title,
            ),
            browseMedia,
        )

        return browseMedia

    except Exception as ex:
        # trace.
        _logsi.LogException(
            "'%s': BrowseMedia async_browse_media_library_index exception: %s"
            % (playerName, str(ex)),
            ex,
            logToSystemLogger=False,
        )
        raise HomeAssistantError(str(ex)) from ex

    finally:
        # trace.
        _logsi.LeaveMethod(SILevel.Debug)


def browse_media_node(
    hass: HomeAssistant,
    client: SpotifyClient,
    playerName: str,
    source: str | None,
    libraryMap: dict,
    media_content_type: str | None,
    media_content_id: str | None,
) -> BrowseMedia:
    """
    Builds a BrowseMedia object for a selected media content type, and all of it's
    child nodes.

    Args:
        hass (HomeAssistant):
            HomeAssistant instance.
        client (SpotifyClient):
            The SpotifyClient instance that will make calls to the device
            to retrieve the data for display in the media browser.
        playerName (str):
            Name of the media player that is calling this method (for tracing purposes).
        source (str):
            Currently selected source value.
        libraryMap (dict):
            The library map that contains media content attributes for each library index entry.
        media_content_type (str):
            Selected media content type in the media browser.
            This value will be None upon the initial entry to the media browser.
        media_content_id (str):
            Selected media content id in the media browser.
            This value will be None upon the initial entry to the media browser.
    """
    methodParms: SIMethodParmListContext = None

    try:
        # trace.
        methodParms = _logsi.EnterMethodParmList(SILevel.Debug)
        methodParms.AppendKeyValue("playerName", playerName)
        methodParms.AppendKeyValue("source", source)
        methodParms.AppendKeyValue("libraryMap", libraryMap)
        methodParms.AppendKeyValue("media_content_type", media_content_type)
        methodParms.AppendKeyValue("media_content_id", media_content_id)
        _logsi.LogMethodParmList(
            SILevel.Verbose,
            "'%s': browsing for media - selected node: '%s'"
            % (playerName, media_content_type),
            methodParms,
        )

        # validations.
        if source is None:
            source = "unknownSource"

        # initialize child item attributes.
        title: str = None
        image: str = None
        media: object = None
        items: list = []

        # build selection list based upon the browsable media type.
        # - media: will contain the result of the spotify web api call.
        # - items: will contain the child items to display for the parent media item.
        # - title: the title to display in the media browser.
        # - image: the image (if any) to display in the media browser (can be none).
        if media_content_type == BrowsableMedia.SPOTIFY_USER_PLAYLISTS:
            _logsi.LogVerbose(
                "'%s': querying spotify for Playlist Favorites" % playerName
            )
            media: PlaylistPageSimplified = client.GetPlaylistFavorites(
                limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.Items

        elif media_content_type == BrowsableMedia.SPOTIFY_USER_FOLLOWED_ARTISTS:
            _logsi.LogVerbose(
                "'%s': querying spotify for Artists Followed" % playerName
            )
            media: ArtistPage = client.GetArtistsFollowed(
                limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.Items

        elif media_content_type == BrowsableMedia.SPOTIFY_USER_SAVED_ALBUMS:
            _logsi.LogVerbose("Getting Spotify user Album favorites")
            media: AlbumPageSaved = client.GetAlbumFavorites(
                limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.GetAlbums()

        elif media_content_type == BrowsableMedia.SPOTIFY_USER_SAVED_TRACKS:
            _logsi.LogVerbose("Getting Spotify user Track favorites")
            media: TrackPageSaved = client.GetTrackFavorites(
                limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.GetTracks()

        elif media_content_type == BrowsableMedia.SPOTIFY_USER_SAVED_SHOWS:
            _logsi.LogVerbose("Getting Spotify user Show favorites")
            media: ShowPageSaved = client.GetShowFavorites(
                limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.GetShows()

        elif media_content_type == BrowsableMedia.SPOTIFY_USER_RECENTLY_PLAYED:
            _logsi.LogVerbose("Getting Spotify user Recently Played Tracks")
            media: PlayHistoryPage = client.GetPlayerRecentTracks(
                limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.GetTracks()

        elif media_content_type == BrowsableMedia.SPOTIFY_USER_TOP_ARTISTS:
            _logsi.LogVerbose("Getting Spotify user Top Artists")
            media: ArtistPage = client.GetUsersTopArtists(
                limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.Items

        elif media_content_type == BrowsableMedia.SPOTIFY_USER_TOP_TRACKS:
            _logsi.LogVerbose("Getting Spotify user Top Tracks")
            media: TrackPage = client.GetUsersTopTracks(
                limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.Items

        elif media_content_type == BrowsableMedia.SPOTIFY_FEATURED_PLAYLISTS:
            _logsi.LogVerbose("Getting Spotify Featured Playlists")
            media: PlaylistPageSimplified
            media, message = client.GetFeaturedPlaylists(
                limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.Items

        elif media_content_type == BrowsableMedia.SPOTIFY_CATEGORYS:
            _logsi.LogVerbose("Getting Spotify Categories")
            media: list[Category] = client.GetBrowseCategorysList(refresh=False)
            items = media

            # add a "Uri" attribute to each category in the cached category list.
            # this is so we can process categories just like other index types, as
            # spotify categories are simply playlists of tracks.
            category: Category
            for category in client.ConfigurationCache["GetBrowseCategorysList"]:
                if hasattr(category, "Uri"):
                    _logsi.LogVerbose(
                        "Category Uri's have already been set in the cache; don't need to do it again"
                    )
                    break
                setattr(category, "Uri", f"spotify:category:{category.Id}")
                _logsi.LogVerbose(
                    "Category Uri set: Name='%s', Id='%s', Uri='%s'"
                    % (category.Name, category.Id, category.Uri)
                )

        elif media_content_type == BrowsableMedia.SPOTIFY_CATEGORY_PLAYLISTS:
            _logsi.LogVerbose("Getting Spotify Category Playlist")

            # was a base64 encoded category object supplied?  if not, then it's a problem!
            if not media_content_id.startswith(CATEGORY_BASE64):
                raise ValueError(
                    "'%s': media content type '%s' is not a serialized Category object!"
                    % (playerName, media_content_type)
                )

            # drop the eye-ctacher and deserialize the category object.
            category: Category = Category()
            media_content_id = media_content_id[len(CATEGORY_BASE64) :]
            category = deserialize_object(media_content_id)
            _logsi.LogObject(
                SILevel.Verbose,
                "'%s': deserialized %s" % (playerName, category.ToString()),
                category,
                excludeNonPublic=True,
            )
            media_content_id = category.Id

            # get the playlists for the category id.
            media: PlaylistPageSimplified
            media, message = client.GetCategoryPlaylists(
                media_content_id, limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.Items
            title = category.Name
            image = category.ImageUrl

        elif media_content_type == BrowsableMedia.SPOTIFY_CATEGORY_PLAYLISTS_MADEFORYOU:
            _logsi.LogVerbose("Getting Spotify 'Made For You' Category Playlist")
            media_content_id = (
                "0JQ5DAt0tbjZptfcdMSKl3"  # special hidden category "Made For You"
            )
            media, message = client.GetCategoryPlaylists(
                media_content_id, limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.Items

        elif media_content_type == BrowsableMedia.SPOTIFY_NEW_RELEASES:
            _logsi.LogVerbose("Getting Spotify Album New Releases")
            media: AlbumPageSimplified = client.GetAlbumNewReleases(
                limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.Items

        elif media_content_type == MediaType.ALBUM:
            _logsi.LogVerbose("Getting Spotify Album Tracks")
            spotifyId: str = SpotifyClient.GetIdFromUri(media_content_id)
            media: Album = client.GetAlbum(spotifyId)
            items = media.Tracks.Items
            title = media.Name
            image = media.ImageUrl

        elif media_content_type == MediaType.ARTIST:
            _logsi.LogVerbose("Getting Spotify Artist Albums")
            spotifyId: str = SpotifyClient.GetIdFromUri(media_content_id)
            artist: Artist = client.GetArtist(spotifyId)  # for cover image
            media: AlbumPageSimplified = client.GetArtistAlbums(
                spotifyId, include_groups="album", limitTotal=SPOTIFY_BROWSE_LIMIT_TOTAL
            )
            items = media.Items
            title = artist.Name
            image = artist.ImageUrl

        elif media_content_type == MediaType.GENRE:
            _logsi.LogVerbose("Getting Spotify Genre Playlist")
            spotifyId: str = SpotifyClient.GetIdFromUri(media_content_id)
            media: Playlist = client.GetPlaylist(spotifyId)
            items = media.GetTracks()
            title = media.Name
            image = media.ImageUrl

        elif media_content_type == MediaType.PLAYLIST:
            _logsi.LogVerbose("Getting Spotify Playlist")
            spotifyId: str = SpotifyClient.GetIdFromUri(media_content_id)
            media: Playlist = client.GetPlaylist(spotifyId)
            items = media.GetTracks()
            title = media.Name
            image = media.ImageUrl

        elif (
            media_content_type == MediaType.PODCAST
            or media_content_type == MEDIA_TYPE_SHOW
        ):
            _logsi.LogVerbose("Getting Spotify Show / Podcast")
            spotifyId: str = SpotifyClient.GetIdFromUri(media_content_id)
            media: Show = client.GetShow(spotifyId)
            items = media.Episodes.Items
            title = media.Name
            image = media.ImageUrl

        # if media was not set then we are done.
        if media is None:
            raise ValueError(
                "'%s': could not find media items for content type '%s'"
                % (playerName, media_content_type)
            )

        # set index flag indicating if index media can be played or not.
        canPlay: bool = media_content_type in PLAYABLE_MEDIA_TYPES

        # track and episode media items cannot be expanded (only played);
        # other media types can be expanded to display child items (e.g. Album, Artist, Playlist, etc).
        canExpand = media_content_type not in [
            MediaType.TRACK,
            MediaType.EPISODE,
        ]

        # if a LOCAL index image was specified, then ensure it exists.
        # otherwise, default to null.
        if image is not None and image.startswith(LOCAL_IMAGE_PREFIX):
            imagePath: str = "%s/www/%s" % (
                hass.config.config_dir,
                image[len(LOCAL_IMAGE_PREFIX) :],
            )
            if not os.path.exists(imagePath):
                image = None

        # get parent media atttributes based upon selected media content type.
        parentAttrs: dict[str, Any] = libraryMap.get(media_content_type, None)
        _logsi.LogDictionary(
            SILevel.Verbose,
            "'%s': BrowseMedia attributes for parent media content type: '%s'"
            % (playerName, media_content_type),
            parentAttrs,
        )

        # get parent attributes that are not set.
        if title is None:
            title = parentAttrs.get("title_node", media_content_id)

        # create the index.
        browseMedia: BrowseMedia = BrowseMedia(
            can_expand=canExpand,
            can_play=canPlay,
            children=[],
            children_media_class=parentAttrs["children"],
            media_class=parentAttrs["parent"],
            media_content_id=media_content_id,
            media_content_type=media_content_type,
            thumbnail=image,
            title=title,
        )

        # add child items to the index.
        for item in items:
            # resolve media content type.
            mediaType: str = parentAttrs["children"]

            # get child media atttributes based upon child item media content type.
            childAttrs: dict[str, Any] = libraryMap.get(mediaType, None)
            # _logsi.LogDictionary(SILevel.Verbose, "'%s': BrowseMedia attributes for child media content type: '%s'" % (playerName, mediaType), childAttrs)

            # set child flag indicating if media can be played or not.
            canPlay: bool = mediaType in PLAYABLE_MEDIA_TYPES

            # track and episode media items cannot be expanded (only played);
            # other media types can be expanded to display child items (e.g. Album, Artist, Playlist, etc).
            canExpand = mediaType not in [
                MediaType.TRACK,
                MediaType.EPISODE,
            ]

            # resolve media content id.
            # default the value to the media type.
            mediaId: str = mediaType
            if canPlay:
                # if it is playable then use the Uri value instead, as we know it's a track or episode.
                mediaId = item.Uri

            elif mediaType == MediaType.GENRE:
                # if it's GENRE content, then serialize the Category object and use it instead so that
                # we don't have to go get it again - we will deserialize it when the child node is
                # selected, and use it to resolve the category Id, Name, and imageUrl values;
                mediaId = "%s%s" % (CATEGORY_BASE64, serialize_object(item))
                mediaType = BrowsableMedia.SPOTIFY_CATEGORY_PLAYLISTS.value

            # build the chile node.
            browseMediaChild: BrowseMedia = BrowseMedia(
                can_expand=canExpand,
                can_play=canPlay,
                children=None,
                children_media_class=childAttrs["children"],
                media_class=childAttrs["parent"],
                media_content_id=mediaId,
                media_content_type=mediaType,
                thumbnail=item.ImageUrl,
                title=item.Name,
            )
            browseMedia.children.append(browseMediaChild)
            _logsi.LogObject(
                SILevel.Verbose,
                "'%s': BrowseMedia Child Object: Type='%s', Id='%s', Title='%s'"
                % (
                    playerName,
                    browseMediaChild.media_content_type,
                    browseMediaChild.media_content_id,
                    browseMediaChild.title,
                ),
                browseMediaChild,
            )

        # trace.
        _logsi.LogObject(
            SILevel.Verbose,
            "'%s': BrowseMedia Parent Object: Type='%s', Id='%s', Title='%s'"
            % (
                playerName,
                browseMedia.media_content_type,
                browseMedia.media_content_id,
                browseMedia.title,
            ),
            browseMedia,
        )

        return browseMedia

    except Exception as ex:
        # trace.
        _logsi.LogException(
            "'%s': BrowseMedia browse_media_node exception: %s" % (playerName, str(ex)),
            ex,
            logToSystemLogger=False,
        )
        raise HomeAssistantError(str(ex)) from ex

    finally:
        # trace.
        _logsi.LeaveMethod(SILevel.Debug)
