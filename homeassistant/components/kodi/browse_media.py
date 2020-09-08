"""Support for media browsing."""

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_MOVIE,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_SEASON,
    MEDIA_CLASS_TV_SHOW,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_SEASON,
    MEDIA_TYPE_TRACK,
    MEDIA_TYPE_TVSHOW,
)

PLAYABLE_MEDIA_TYPES = [
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_TRACK,
]

EXPANDABLE_MEDIA_TYPES = [
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_TVSHOW,
    MEDIA_TYPE_SEASON,
]

CONTENT_TYPE_MEDIA_CLASS = {
    "library_music": MEDIA_CLASS_MUSIC,
    MEDIA_TYPE_SEASON: MEDIA_CLASS_SEASON,
    MEDIA_TYPE_ALBUM: MEDIA_CLASS_ALBUM,
    MEDIA_TYPE_ARTIST: MEDIA_CLASS_ARTIST,
    MEDIA_TYPE_MOVIE: MEDIA_CLASS_MOVIE,
    MEDIA_TYPE_PLAYLIST: MEDIA_CLASS_PLAYLIST,
    MEDIA_TYPE_TVSHOW: MEDIA_CLASS_TV_SHOW,
}


async def build_item_response(media_library, payload):
    """Create response payload for the provided media query."""
    search_id = payload["search_id"]
    search_type = payload["search_type"]

    thumbnail = None
    title = None
    media = None

    query = {"properties": ["thumbnail"]}
    # pylint: disable=protected-access
    if search_type == MEDIA_TYPE_ALBUM:
        if search_id:
            query.update({"filter": {"albumid": int(search_id)}})
            query["properties"].extend(
                ["albumid", "artist", "duration", "album", "track"]
            )
            album = await media_library._server.AudioLibrary.GetAlbumDetails(
                {"albumid": int(search_id), "properties": ["thumbnail"]}
            )
            thumbnail = media_library.thumbnail_url(
                album["albumdetails"].get("thumbnail")
            )
            title = album["albumdetails"]["label"]
            media = await media_library._server.AudioLibrary.GetSongs(query)
            media = media.get("songs")
        else:
            media = await media_library._server.AudioLibrary.GetAlbums(query)
            media = media.get("albums")
            title = "Albums"
    elif search_type == MEDIA_TYPE_ARTIST:
        if search_id:
            query.update({"filter": {"artistid": int(search_id)}})
            media = await media_library._server.AudioLibrary.GetAlbums(query)
            media = media.get("albums")
            artist = await media_library._server.AudioLibrary.GetArtistDetails(
                {"artistid": int(search_id), "properties": ["thumbnail"]}
            )
            thumbnail = media_library.thumbnail_url(
                artist["artistdetails"].get("thumbnail")
            )
            title = artist["artistdetails"]["label"]
        else:
            media = await media_library._server.AudioLibrary.GetArtists(query)
            media = media.get("artists")
            title = "Artists"
    elif search_type == "library_music":
        library = {MEDIA_TYPE_ALBUM: "Albums", MEDIA_TYPE_ARTIST: "Artists"}
        media = [{"label": name, "type": type_} for type_, name in library.items()]
        title = "Music Library"
    elif search_type == MEDIA_TYPE_MOVIE:
        media = await media_library._server.VideoLibrary.GetMovies(query)
        media = media.get("movies")
        title = "Movies"
    elif search_type == MEDIA_TYPE_TVSHOW:
        if search_id:
            media = await media_library._server.VideoLibrary.GetSeasons(
                {
                    "tvshowid": int(search_id),
                    "properties": ["thumbnail", "season", "tvshowid"],
                }
            )
            media = media.get("seasons")
            tvshow = await media_library._server.VideoLibrary.GetTVShowDetails(
                {"tvshowid": int(search_id), "properties": ["thumbnail"]}
            )
            thumbnail = media_library.thumbnail_url(
                tvshow["tvshowdetails"].get("thumbnail")
            )
            title = tvshow["tvshowdetails"]["label"]
        else:
            media = await media_library._server.VideoLibrary.GetTVShows(query)
            media = media.get("tvshows")
            title = "TV Shows"
    elif search_type == MEDIA_TYPE_SEASON:
        tv_show_id, season_id = search_id.split("/", 1)
        media = await media_library._server.VideoLibrary.GetEpisodes(
            {
                "tvshowid": int(tv_show_id),
                "season": int(season_id),
                "properties": ["thumbnail", "tvshowid", "seasonid"],
            }
        )
        media = media.get("episodes")
        if media:
            season = await media_library._server.VideoLibrary.GetSeasonDetails(
                {"seasonid": int(media[0]["seasonid"]), "properties": ["thumbnail"]}
            )
            thumbnail = media_library.thumbnail_url(
                season["seasondetails"].get("thumbnail")
            )
            title = season["seasondetails"]["label"]

    if media is None:
        return

    return BrowseMedia(
        media_class=CONTENT_TYPE_MEDIA_CLASS[search_type],
        media_content_id=payload["search_id"],
        media_content_type=search_type,
        title=title,
        can_play=search_type in PLAYABLE_MEDIA_TYPES and search_id,
        can_expand=True,
        children=[item_payload(item, media_library) for item in media],
        thumbnail=thumbnail,
    )


def item_payload(item, media_library):
    """
    Create response payload for a single media item.

    Used by async_browse_media.
    """
    if "songid" in item:
        media_content_type = MEDIA_TYPE_TRACK
        media_content_id = f"{item['songid']}"
    elif "albumid" in item:
        media_content_type = MEDIA_TYPE_ALBUM
        media_content_id = f"{item['albumid']}"
    elif "artistid" in item:
        media_content_type = MEDIA_TYPE_ARTIST
        media_content_id = f"{item['artistid']}"
    elif "movieid" in item:
        media_content_type = MEDIA_TYPE_MOVIE
        media_content_id = f"{item['movieid']}"
    elif "episodeid" in item:
        media_content_type = MEDIA_TYPE_EPISODE
        media_content_id = f"{item['episodeid']}"
    elif "seasonid" in item:
        media_content_type = MEDIA_TYPE_SEASON
        media_content_id = f"{item['tvshowid']}/{item['season']}"
    elif "tvshowid" in item:
        media_content_type = MEDIA_TYPE_TVSHOW
        media_content_id = f"{item['tvshowid']}"
    else:
        # this case is for the top folder of each type
        # possible content types: album, artist, movie, library_music, tvshow
        media_content_type = item.get("type")
        media_content_id = ""

    title = item["label"]
    can_play = media_content_type in PLAYABLE_MEDIA_TYPES and bool(media_content_id)
    can_expand = media_content_type in EXPANDABLE_MEDIA_TYPES

    thumbnail = item.get("thumbnail")
    if thumbnail:
        thumbnail = media_library.thumbnail_url(thumbnail)

    return BrowseMedia(
        title=title,
        media_class=CONTENT_TYPE_MEDIA_CLASS[item["type"]],
        media_content_type=media_content_type,
        media_content_id=media_content_id,
        can_play=can_play,
        can_expand=can_expand,
        thumbnail=thumbnail,
    )


def library_payload(media_library):
    """
    Create response payload to describe contents of a specific library.

    Used by async_browse_media.
    """
    library_info = BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        title="Media Library",
        can_play=False,
        can_expand=True,
        children=[],
    )

    library = {
        "library_music": "Music",
        MEDIA_TYPE_MOVIE: "Movies",
        MEDIA_TYPE_TVSHOW: "TV shows",
    }
    for item in [{"label": name, "type": type_} for type_, name in library.items()]:
        library_info.children.append(
            item_payload(
                {"label": item["label"], "type": item["type"], "uri": item["type"]},
                media_library,
            )
        )

    return library_info
