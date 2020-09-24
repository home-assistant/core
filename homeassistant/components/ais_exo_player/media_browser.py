"""Support to interface with the Plex API."""
import logging

import async_timeout

from homeassistant.components import ais_audiobooks_service, ais_cloud, media_source
import homeassistant.components.ais_dom.ais_global as ais_global
from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_APP,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_EPISODE,
    MEDIA_CLASS_GENRE,
    MEDIA_CLASS_IMAGE,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_PODCAST,
    MEDIA_CLASS_TRACK,
    MEDIA_CLASS_VIDEO,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_CHANNELS,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_TRACK,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source import const as media_source_const
from homeassistant.helpers import aiohttp_client

MEDIA_TYPE_SHOW = "show"
BROWSE_LIMIT = 48
_LOGGER = logging.getLogger(__name__)


class MissingMediaInformation(BrowseError):
    """Missing media required information."""


class UnknownMediaType(BrowseError):
    """Unknown media type."""


SPOTIFY_LIBRARY_MAP = {
    "current_user_playlists": "Playlisty",
    "current_user_followed_artists": "Artyści",
    "current_user_saved_albums": "Albumy",
    "current_user_saved_tracks": "Utwory",
    "current_user_saved_shows": "Podkasty",
    "current_user_recently_played": "Ostatnio grane",
    "current_user_top_artists": "Najpopularniejsi artyści",
    "current_user_top_tracks": "Najlepsze utwory",
    "categories": "Kategorie",
    "featured_playlists": "Polecane playlisty",
    "new_releases": "Nowo wydane",
}

SPOTIFY_CONTENT_TYPE_MEDIA_CLASS = {
    "current_user_playlists": {
        "parent": MEDIA_CLASS_DIRECTORY,
        "children": MEDIA_CLASS_PLAYLIST,
    },
    "current_user_followed_artists": {
        "parent": MEDIA_CLASS_DIRECTORY,
        "children": MEDIA_CLASS_ARTIST,
    },
    "current_user_saved_albums": {
        "parent": MEDIA_CLASS_DIRECTORY,
        "children": MEDIA_CLASS_ALBUM,
    },
    "current_user_saved_tracks": {
        "parent": MEDIA_CLASS_DIRECTORY,
        "children": MEDIA_CLASS_TRACK,
    },
    "current_user_saved_shows": {
        "parent": MEDIA_CLASS_DIRECTORY,
        "children": MEDIA_CLASS_PODCAST,
    },
    "current_user_recently_played": {
        "parent": MEDIA_CLASS_DIRECTORY,
        "children": MEDIA_CLASS_TRACK,
    },
    "current_user_top_artists": {
        "parent": MEDIA_CLASS_DIRECTORY,
        "children": MEDIA_CLASS_ARTIST,
    },
    "current_user_top_tracks": {
        "parent": MEDIA_CLASS_DIRECTORY,
        "children": MEDIA_CLASS_TRACK,
    },
    "featured_playlists": {
        "parent": MEDIA_CLASS_DIRECTORY,
        "children": MEDIA_CLASS_PLAYLIST,
    },
    "categories": {"parent": MEDIA_CLASS_DIRECTORY, "children": MEDIA_CLASS_GENRE},
    "category_playlists": {
        "parent": MEDIA_CLASS_DIRECTORY,
        "children": MEDIA_CLASS_PLAYLIST,
    },
    "new_releases": {"parent": MEDIA_CLASS_DIRECTORY, "children": MEDIA_CLASS_ALBUM},
    MEDIA_TYPE_PLAYLIST: {
        "parent": MEDIA_CLASS_PLAYLIST,
        "children": MEDIA_CLASS_TRACK,
    },
    MEDIA_TYPE_ALBUM: {"parent": MEDIA_CLASS_ALBUM, "children": MEDIA_CLASS_TRACK},
    MEDIA_TYPE_ARTIST: {"parent": MEDIA_CLASS_ARTIST, "children": MEDIA_CLASS_ALBUM},
    MEDIA_TYPE_EPISODE: {"parent": MEDIA_CLASS_EPISODE, "children": None},
    MEDIA_TYPE_SHOW: {"parent": MEDIA_CLASS_PODCAST, "children": MEDIA_CLASS_EPISODE},
    MEDIA_TYPE_TRACK: {"parent": MEDIA_CLASS_TRACK, "children": None},
}

SPOTIFY_PLAYABLE_MEDIA_TYPES = [
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_SHOW,
    MEDIA_TYPE_TRACK,
]


async def browse_media(hass, media_content_type=None, media_content_id=None):
    """Implement the websocket media browsing helper."""
    if media_content_id in [None, "library"]:
        return ais_media_library()

    if media_content_id.startswith(media_source_const.URI_SCHEME):
        result = await media_source.async_browse_media(hass, media_content_id)
        return result

    # if media_content_id.startswith("ais_music"):
    #     return ais_music_library()

    if media_content_id.startswith("ais_spotify"):
        return await ais_spotify_library(hass, media_content_type, media_content_id)

    if media_content_id.startswith("ais_youtube"):
        return await ais_youtube_library(hass)

    if media_content_id.startswith("ais_favorites"):
        return ais_favorites_library(hass)

    if media_content_id.startswith("ais_bookmarks"):
        return ais_bookmarks_library(hass)

    if media_content_id.startswith("ais_radio"):
        return ais_radio_library(hass, media_content_id)

    if media_content_id.startswith("ais_tunein"):
        return await ais_tunein_library(hass, media_content_id)

    if media_content_id.startswith("ais_podcast"):
        return await ais_podcast_library(hass, media_content_id)

    if media_content_id.startswith("ais_audio_books"):
        return await ais_audio_books_library(hass, media_content_id)

    response = None

    if response is None:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")
    return response


def ais_media_library() -> BrowseMedia:
    """Create response payload to describe contents of a specific library."""
    ais_library_info = BrowseMedia(
        title="AI-Speaker",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        can_play=False,
        can_expand=True,
        children=[],
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Galeria",
            media_class=MEDIA_CLASS_IMAGE,
            media_content_id=f"{media_source_const.URI_SCHEME}{media_source_const.DOMAIN}"
            + "/galeria/.",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Dyski",
            media_class="nas",
            media_content_id=f"{media_source_const.URI_SCHEME}{media_source_const.DOMAIN}"
            + "/dyski/.",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Ulubione",
            media_class="heart",
            media_content_id="ais_favorites",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Zakładki",
            media_class="bookmark",
            media_content_id="ais_bookmarks",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Radio",
            media_class="radio",
            media_content_id="ais_radio",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Podcast",
            media_class=MEDIA_CLASS_PODCAST,
            media_content_id="ais_podcast",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Audio książki",
            media_class="book",
            media_content_id="ais_audio_books",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="Spotify",
            media_class="spotify",
            media_content_id="ais_spotify",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="YouTube",
            media_class="youtube",
            media_content_id="ais_youtube",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="TuneIn",
            media_class="radiopublic",
            media_content_id="ais_tunein",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )

    return ais_library_info


async def get_books_lib(hass):
    import json
    import os

    path = hass.config.path() + ais_audiobooks_service.PERSISTENCE_AUDIOBOOKS
    if not os.path.isfile(path):
        return json({})
    with open(path) as file:
        return json.loads(file.read())


async def ais_audio_books_library(hass, media_content_id) -> BrowseMedia:
    ais_cloud_ws = ais_cloud.AisCloudWS(hass)
    # get all books
    all_books = await get_books_lib(hass)
    if media_content_id == "ais_audio_books":
        # get authors
        authors = []
        for item in all_books:
            if item["author"] not in authors:
                authors.append(item["author"])

        ais_authors = []
        for author in authors:
            ais_authors.append(
                BrowseMedia(
                    title=author,
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_id="ais_audio_books/" + author,
                    media_content_type=MEDIA_TYPE_APP,
                    can_play=False,
                    can_expand=True,
                )
            )

        root = BrowseMedia(
            title="Autorzy",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="ais_audio_books",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            children=ais_authors,
            thumbnail="http://www.ai-speaker.com/images/media-browser/book-music.svg",
        )
        return root
    elif media_content_id.count("/") == 1:
        # get books for author
        ais_books = []
        for item in all_books:
            if item["author"] == media_content_id.replace("ais_audio_books/", ""):
                try:
                    thumbnail = "https://wolnelektury.pl/media/" + item["cover_thumb"]
                except Exception:
                    thumbnail = item["simple_thumb"]

                ais_books.append(
                    BrowseMedia(
                        title=item["title"],
                        media_class=MEDIA_CLASS_DIRECTORY,
                        media_content_id=media_content_id
                        + "/"
                        + item["title"]
                        + "/"
                        + item["href"],
                        media_content_type=MEDIA_TYPE_APP,
                        can_play=False,
                        can_expand=True,
                        thumbnail=thumbnail,
                    )
                )
        root = BrowseMedia(
            title=media_content_id.replace("ais_audio_books/", ""),
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id=media_content_id,
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            children=ais_books,
            thumbnail="http://www.ai-speaker.com/images/media-browser/book-music.svg",
        )
        return root
    else:
        # get book chapters
        lookup_url = media_content_id.split("/", 3)[3]
        web_session = aiohttp_client.async_get_clientsession(hass)
        #  5 sec should be enough
        try:
            with async_timeout.timeout(7):
                ws_resp = await web_session.get(lookup_url + "?format=json")
                data = await ws_resp.json()
                ais_book_chapters = []
                for item in data["media"]:
                    if item["type"] == "ogg":
                        try:
                            thumbnail = data["cover"]
                        except Exception:
                            thumbnail = data["simple_cover"]
                        ais_book_chapters.append(
                            BrowseMedia(
                                title=item["name"],
                                media_class=MEDIA_CLASS_DIRECTORY,
                                media_content_id=item["url"],
                                media_content_type=MEDIA_TYPE_APP,
                                can_play=True,
                                can_expand=False,
                                thumbnail=thumbnail,
                            )
                        )
                root = BrowseMedia(
                    title=media_content_id.split("/", 3)[2],
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_id=media_content_id,
                    media_content_type=MEDIA_TYPE_APP,
                    can_expand=True,
                    can_play=False,
                    children=ais_book_chapters,
                    thumbnail="http://www.ai-speaker.com/images/media-browser/book-music.svg",
                )
                return root

        except Exception as e:
            _LOGGER.error("Can't load chapters: " + str(e))
            hass.services.call(
                "ais_ai_service", "say_it", {"text": "Nie można pobrać rozdziałów"}
            )
            raise BrowseError("Can't load chapters: " + str(e))


async def ais_podcast_library(hass, media_content_id) -> BrowseMedia:
    ais_cloud_ws = ais_cloud.AisCloudWS(hass)
    if media_content_id == "ais_podcast":
        # get podcast types
        ws_resp = ais_cloud_ws.audio_type(ais_global.G_AN_PODCAST)
        json_ws_resp = ws_resp.json()
        ais_podcast_types = []
        for item in json_ws_resp["data"]:
            media_class = MEDIA_CLASS_PODCAST
            if item == "Biznes":
                media_class = "podcastbuisnes"
            elif item == "Edukacja":
                media_class = "podcasteducation"
            elif item == "Familijne":
                media_class = "podcastfamily"
            elif item == "Gry i Hobby":
                media_class = "podcastgames"
            elif item == "Humor":
                media_class = "podcastsmile"
            elif item == "nformacyjne":
                media_class = "podcastinfo"
            elif item == "Komedia":
                media_class = "podcastcomedy"
            elif item == "Książki":
                media_class = "podcastbooks"
            elif item == "Kuchnia":
                media_class = "podcastcook"
            elif item == "Marketing":
                media_class = "podcastmarket"
            elif item == "Sport i rekreacja":
                media_class = "podcastsport"
            elif item == "Sztuka":
                media_class = "podcastart"
            elif item == "TV i film":
                media_class = "podcasttv"
            elif item == "Technologia":
                media_class = "podcasttechno"
            elif item == "Tyflopodcast":
                media_class = "podcasttyflo"
            elif item == "Zdrowie":
                media_class = "podcastdoctor"
            ais_podcast_types.append(
                BrowseMedia(
                    title=item,
                    media_class=media_class,
                    media_content_id="ais_podcast/" + item,
                    media_content_type=MEDIA_TYPE_APP,
                    can_play=False,
                    can_expand=True,
                )
            )
        root = BrowseMedia(
            title="Podcasty",
            media_class=MEDIA_CLASS_PODCAST,
            media_content_id="ais_podcast",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            children=ais_podcast_types,
            thumbnail="http://www.ai-speaker.com/images/media-browser/podcast.svg",
        )
        return root
    elif media_content_id.count("/") == 1:
        # get podcasts for types
        ws_resp = ais_cloud_ws.audio_name(
            ais_global.G_AN_PODCAST, media_content_id.replace("ais_podcast/", "")
        )
        json_ws_resp = ws_resp.json()
        ais_radio_stations = []
        for item in json_ws_resp["data"]:
            ais_radio_stations.append(
                BrowseMedia(
                    title=item["NAME"],
                    media_class=MEDIA_CLASS_PODCAST,
                    media_content_id=media_content_id
                    + "/"
                    + item["NAME"]
                    + "/"
                    + item["LOOKUP_URL"],
                    media_content_type=MEDIA_TYPE_CHANNELS,
                    can_play=False,
                    can_expand=True,
                    thumbnail=item["IMAGE_URL"],
                )
            )
        root = BrowseMedia(
            title=media_content_id.replace("ais_podcast/", ""),
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id=media_content_id,
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            children=ais_radio_stations,
            thumbnail="http://www.ai-speaker.com/images/media-browser/podcast.svg",
        )
        return root
    else:
        # get podcast tracks
        try:
            lookup_url = media_content_id.split("/", 3)[3]
            web_session = aiohttp_client.async_get_clientsession(hass)
            import feedparser

            #  5 sec should be enough
            with async_timeout.timeout(7):
                ws_resp = await web_session.get(lookup_url)
                response_text = await ws_resp.text()
                d = feedparser.parse(response_text)
                ais_podcast_episodes = []
                for e in d.entries:
                    try:
                        thumbnail = d.feed.image.href
                    except Exception:
                        thumbnail = ""
                    ais_podcast_episodes.append(
                        BrowseMedia(
                            title=e.title,
                            media_class=MEDIA_CLASS_MUSIC,
                            media_content_id=e.enclosures[0]["url"],
                            media_content_type=MEDIA_TYPE_MUSIC,
                            can_play=True,
                            can_expand=False,
                            thumbnail=thumbnail,
                        )
                    )
                root = BrowseMedia(
                    title=media_content_id.split("/", 3)[2],
                    media_class=MEDIA_CLASS_PODCAST,
                    media_content_id=media_content_id,
                    media_content_type=MEDIA_TYPE_CHANNELS,
                    can_expand=True,
                    can_play=False,
                    thumbnail="http://www.ai-speaker.com/images/media-browser/podcast.svg",
                    children=ais_podcast_episodes,
                )
                return root
        except Exception as e:
            _LOGGER.warning("Timeout when reading RSS %s", lookup_url)
            raise BrowseError("Timeout when reading RSS %s", lookup_url)


def ais_radio_library(hass, media_content_id) -> BrowseMedia:
    ais_cloud_ws = ais_cloud.AisCloudWS(hass)
    if media_content_id == "ais_radio":
        # get
        ws_resp = ais_cloud_ws.audio_type(ais_global.G_AN_RADIO)
        json_ws_resp = ws_resp.json()
        # ais_radio_types = [ais_global.G_FAVORITE_OPTION]
        ais_radio_types = []
        for item in json_ws_resp["data"]:
            media_class = MEDIA_CLASS_DIRECTORY
            if item == "Dzieci":
                media_class = "radiokids"
            elif item == "Filmowe":
                media_class = "radiofils"
            elif item == "Historyczne":
                media_class = "radiohistory"
            elif item == "Informacyjne":
                media_class = "radionews"
            elif item == "Inne":
                media_class = "radioothers"
            elif item == "Katolickie":
                media_class = "radiochurch"
            elif item == "Klasyczne":
                media_class = "radioclasic"
            elif item == "Muzyczne":
                media_class = "radiomusic"
            elif item == "Muzyczne - Rock":
                media_class = "radiomusicrock"
            elif item == "Naukowe":
                media_class = "radioschool"
            elif item == "Regionalne":
                media_class = "radiolocal"
            elif item == "Publiczne":
                media_class = "radiopublic"
            elif item == "Sportowe":
                media_class = "radiosport"
            elif item == "Słowo":
                media_class = "radiopen"
            elif item == "Trendy TuneIn":
                media_class = "radiotuneintrend"

            ais_radio_types.append(
                BrowseMedia(
                    title=item,
                    media_class=media_class,
                    media_content_id="ais_radio/" + item,
                    media_content_type=MEDIA_TYPE_APP,
                    can_play=False,
                    can_expand=True,
                )
            )
        root = BrowseMedia(
            title="Radio",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="ais_radio",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="http://www.ai-speaker.com/images/media-browser/radio.svg",
            children=ais_radio_types,
        )
        return root
    else:
        # get radio station for type
        ws_resp = ais_cloud_ws.audio_name(
            ais_global.G_AN_RADIO, media_content_id.replace("ais_radio/", "")
        )
        json_ws_resp = ws_resp.json()
        ais_radio_stations = []
        for item in json_ws_resp["data"]:
            ais_radio_stations.append(
                BrowseMedia(
                    title=item["NAME"],
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_id=item["STREAM_URL"],
                    media_content_type=MEDIA_TYPE_APP,
                    can_play=True,
                    can_expand=False,
                    thumbnail=item["IMAGE_URL"],
                )
            )
        root = BrowseMedia(
            title=media_content_id.replace("ais_radio/", ""),
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id=media_content_id,
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            thumbnail="http://www.ai-speaker.com/images/media-browser/radio.svg",
            children=ais_radio_stations,
        )
        return root


def ais_bookmarks_library(hass) -> BrowseMedia:
    d = hass.data["ais_bookmarks"]
    ais_bookmarks = []
    for bookmark in reversed(d.bookmarks):
        if (
            "media_stream_image" in bookmark
            and bookmark["media_stream_image"] is not None
        ):
            img = bookmark["media_stream_image"]
        else:
            img = "/static/icons/tile-win-310x150.png"
        if bookmark["name"].startswith(bookmark["source"]):
            name = bookmark["name"]
        else:
            name = (
                ais_global.G_NAME_FOR_AUDIO_NATURE.get(
                    bookmark["source"], bookmark["source"]
                )
                + " "
                + bookmark["name"]
            )

        ais_bookmarks.append(
            BrowseMedia(
                title=name,
                media_class=MEDIA_CLASS_MUSIC,
                media_content_id=bookmark["media_content_id"],
                media_content_type=MEDIA_TYPE_MUSIC,
                can_play=True,
                can_expand=False,
                thumbnail=img,
            )
        )

    root = BrowseMedia(
        title="Zakładki",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="ais_bookmarks",
        media_content_type=MEDIA_TYPE_APP,
        can_expand=True,
        can_play=False,
        thumbnail="http://www.ai-speaker.com/images/media-browser/bookmarks.svg",
        children=ais_bookmarks,
    )

    return root


def ais_favorites_library(hass) -> BrowseMedia:
    d = hass.data["ais_bookmarks"]
    ais_favorites = []
    for fav in reversed(d.favorites):
        if "media_stream_image" in fav and fav["media_stream_image"] is not None:
            img = fav["media_stream_image"]
        else:
            img = "/static/icons/tile-win-310x150.png"
        if fav["name"].startswith(fav["source"]):
            name = fav["name"]
        else:
            name = (
                ais_global.G_NAME_FOR_AUDIO_NATURE.get(fav["source"], fav["source"])
                + " "
                + fav["name"]
            )

        ais_favorites.append(
            BrowseMedia(
                title=name,
                media_class=MEDIA_CLASS_MUSIC,
                media_content_id=fav["media_content_id"],
                media_content_type=MEDIA_TYPE_MUSIC,
                can_play=True,
                can_expand=False,
                thumbnail=img,
            )
        )

    root = BrowseMedia(
        title="Ulubione",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="ais_favorites",
        media_content_type=MEDIA_TYPE_APP,
        can_expand=True,
        can_play=False,
        thumbnail="http://www.ai-speaker.com/images/media-browser/heart.svg",
        children=ais_favorites,
    )

    return root


async def ais_spotify_library(
    hass, media_content_type, media_content_id
) -> BrowseMedia:
    """Create response payload to describe contents of a specific library."""
    if hass.services.has_service("ais_spotify_service", "get_favorites"):
        if media_content_id == "ais_spotify":
            library_info = {
                "title": "Spotify",
                "media_class": MEDIA_CLASS_DIRECTORY,
                "media_content_id": "ais_spotify",
                "media_content_type": "library",
                "can_play": False,
                "can_expand": True,
                "children": [],
            }

            for item in [
                {"name": n, "type": t} for t, n in SPOTIFY_LIBRARY_MAP.items()
            ]:
                library_info["children"].append(
                    spotify_item_payload(
                        {
                            "name": item["name"],
                            "type": item["type"],
                            "uri": "ais_spotify/" + item["type"],
                        }
                    )
                )
            response = BrowseMedia(**library_info)
            response.children_media_class = MEDIA_CLASS_DIRECTORY
            return response
        else:
            spotify_data = hass.data["ais_spotify_service"]
            spotify, user = spotify_data.refresh_spotify_instance()
            payload = {
                "media_content_type": media_content_type,
                "media_content_id": media_content_id,
            }
            return spotify_build_item_response(
                spotify=spotify, user=user, payload=payload
            )
    else:
        raise BrowseError(
            "AIS - dodaj Spotify zgodnie z instrukcją na stronie ai-speaker.com"
        )


def spotify_build_item_response(spotify, user, payload):
    """Create response payload for the provided media query."""
    media_content_type = payload["media_content_type"]
    media_content_id = payload["media_content_id"].replace("ais_spotify/", "")
    title = None
    image = None
    if media_content_type == "current_user_playlists":
        media = spotify.current_user_playlists(limit=BROWSE_LIMIT)
        items = media.get("items", [])
    elif media_content_type == "current_user_followed_artists":
        media = spotify.current_user_followed_artists(limit=BROWSE_LIMIT)
        items = media.get("artists", {}).get("items", [])
    elif media_content_type == "current_user_saved_albums":
        media = spotify.current_user_saved_albums(limit=BROWSE_LIMIT)
        items = [item["album"] for item in media.get("items", [])]
    elif media_content_type == "current_user_saved_tracks":
        media = spotify.current_user_saved_tracks(limit=BROWSE_LIMIT)
        items = [item["track"] for item in media.get("items", [])]
    elif media_content_type == "current_user_saved_shows":
        media = spotify.current_user_saved_shows(limit=BROWSE_LIMIT)
        items = [item["show"] for item in media.get("items", [])]
    elif media_content_type == "current_user_recently_played":
        media = spotify.current_user_recently_played(limit=BROWSE_LIMIT)
        items = [item["track"] for item in media.get("items", [])]
    elif media_content_type == "current_user_top_artists":
        media = spotify.current_user_top_artists(limit=BROWSE_LIMIT)
        items = media.get("items", [])
    elif media_content_type == "current_user_top_tracks":
        media = spotify.current_user_top_tracks(limit=BROWSE_LIMIT)
        items = media.get("items", [])
    elif media_content_type == "featured_playlists":
        media = spotify.featured_playlists(country=user["country"], limit=BROWSE_LIMIT)
        items = media.get("playlists", {}).get("items", [])
    elif media_content_type == "categories":
        media = spotify.categories(country=user["country"], limit=BROWSE_LIMIT)
        items = media.get("categories", {}).get("items", [])
    elif media_content_type == "category_playlists":
        media = spotify.category_playlists(
            category_id=media_content_id,
            country=user["country"],
            limit=BROWSE_LIMIT,
        )
        category = spotify.category(media_content_id, country=user["country"])
        title = category.get("name")
        image = spotify_fetch_image_url(category, key="icons")
        items = media.get("playlists", {}).get("items", [])
    elif media_content_type == "new_releases":
        media = spotify.new_releases(country=user["country"], limit=BROWSE_LIMIT)
        items = media.get("albums", {}).get("items", [])
    elif media_content_type == MEDIA_TYPE_PLAYLIST:
        media = spotify.playlist(media_content_id)
        items = [item["track"] for item in media.get("tracks", {}).get("items", [])]
    elif media_content_type == MEDIA_TYPE_ALBUM:
        media = spotify.album(media_content_id)
        items = media.get("tracks", {}).get("items", [])
    elif media_content_type == MEDIA_TYPE_ARTIST:
        media = spotify.artist_albums(media_content_id, limit=BROWSE_LIMIT)
        artist = spotify.artist(media_content_id)
        title = artist.get("name")
        image = spotify_fetch_image_url(artist)
        items = media.get("items", [])
    elif media_content_type == MEDIA_TYPE_SHOW:
        media = spotify.show_episodes(media_content_id, limit=BROWSE_LIMIT)
        show = spotify.show(media_content_id)
        title = show.get("name")
        image = spotify_fetch_image_url(show)
        items = media.get("items", [])
    else:
        media = None
        items = []

    if media is None:
        return None

    try:
        media_class = SPOTIFY_CONTENT_TYPE_MEDIA_CLASS[media_content_type]
    except KeyError:
        _LOGGER.debug("Unknown media type received: %s", media_content_type)
        return None

    if media_content_type == "categories":
        media_item = BrowseMedia(
            title=SPOTIFY_LIBRARY_MAP.get(media_content_type),
            media_class=media_class["parent"],
            children_media_class=media_class["children"],
            media_content_id="ais_spotify/" + media_content_id,
            media_content_type=media_content_type,
            can_play=False,
            can_expand=True,
            children=[],
        )
        for item in items:
            try:
                item_id = item["id"]
            except KeyError:
                _LOGGER.debug("Missing id for media item: %s", item)
                continue
            media_item.children.append(
                BrowseMedia(
                    title=item.get("name"),
                    media_class=MEDIA_CLASS_PLAYLIST,
                    children_media_class=MEDIA_CLASS_TRACK,
                    media_content_id="ais_spotify/" + item_id,
                    media_content_type="category_playlists",
                    thumbnail=spotify_fetch_image_url(item, key="icons"),
                    can_play=False,
                    can_expand=True,
                )
            )
        return media_item

    if title is None:
        if "name" in media:
            title = media.get("name")
        else:
            title = SPOTIFY_LIBRARY_MAP.get(media_content_type)

    params = {
        "title": title,
        "media_class": media_class["parent"],
        "children_media_class": media_class["children"],
        "media_content_id": "ais_spotify/" + media_content_id,
        "media_content_type": media_content_type,
        "can_play": media_content_type in SPOTIFY_PLAYABLE_MEDIA_TYPES,
        "children": [],
        "can_expand": True,
    }
    for item in items:
        try:
            params["children"].append(spotify_item_payload(item))
        except (MissingMediaInformation, UnknownMediaType):
            continue

    if "images" in media:
        params["thumbnail"] = spotify_fetch_image_url(media)
    elif image:
        params["thumbnail"] = image

    return BrowseMedia(**params)


def spotify_fetch_image_url(item, key="images"):
    """Fetch image url."""
    try:
        return item.get(key, [])[0].get("url")
    except IndexError:
        return None


def spotify_item_payload(item):
    """
    Create response payload for a single media item.

    Used by async_browse_media.
    """
    try:
        media_type = item["type"]
        media_id = item["uri"].replace("ais_spotify/", "")
    except KeyError as err:
        _LOGGER.debug("Missing type or uri for media item: %s", item)
        raise MissingMediaInformation from err

    try:
        media_class = SPOTIFY_CONTENT_TYPE_MEDIA_CLASS[media_type]
    except KeyError as err:
        _LOGGER.debug("Unknown media type received: %s", media_type)
        raise UnknownMediaType from err

    can_expand = media_type not in [
        MEDIA_TYPE_TRACK,
        MEDIA_TYPE_EPISODE,
    ]

    payload = {
        "title": item.get("name"),
        "media_class": media_class["parent"],
        "children_media_class": media_class["children"],
        "media_content_id": "ais_spotify/" + media_id,
        "media_content_type": media_type,
        "can_play": media_type in SPOTIFY_PLAYABLE_MEDIA_TYPES,
        "can_expand": can_expand,
    }

    if "images" in item:
        payload["thumbnail"] = spotify_fetch_image_url(item)
    elif MEDIA_TYPE_ALBUM in item:
        payload["thumbnail"] = spotify_fetch_image_url(item[MEDIA_TYPE_ALBUM])

    return BrowseMedia(**payload)


async def ais_youtube_library(hass) -> BrowseMedia:
    """Create response payload to describe contents of a specific library."""
    raise BrowseError("AIS TODO - pracujemy nad tym.:)")


async def get_media_content_id_form_ais(hass, media_content_id):
    if media_content_id.startswith("ais_tunein"):
        web_session = aiohttp_client.async_get_clientsession(hass)
        url_to_call = media_content_id.split("/", 3)[3]
        with async_timeout.timeout(7):
            ws_resp = await web_session.get(url_to_call)
            response_text = await ws_resp.text()
            response_text = response_text.split("\n")[0]
            if response_text.endswith(".pls"):
                with async_timeout.timeout(7):
                    ws_resp = await web_session.get(response_text)
                    response_text = await ws_resp.text()
                    response_text = response_text.split("\n")[1].replace("File1=", "")
            if response_text.startswith("mms:"):
                with async_timeout.timeout(7):
                    ws_resp = await web_session.get(
                        response_text.replace("mms:", "http:")
                    )
                    response_text = await ws_resp.text()
                    response_text = response_text.split("\n")[1].replace("Ref1=", "")
    elif media_content_id.startswith("ais_spotify"):
        response_text = media_content_id.replace("ais_spotify/", "")
    return response_text


async def ais_tunein_library(hass, media_content_id) -> BrowseMedia:
    import xml.etree.ElementTree as ET

    web_session = aiohttp_client.async_get_clientsession(hass)
    if media_content_id == "ais_tunein":
        try:
            #  7 sec should be enough
            with async_timeout.timeout(7):
                # we need this only for demo
                if ais_global.get_sercure_android_id_dom() == "dom-demo":
                    headers = {"accept-language": "pl"}
                    ws_resp = await web_session.get(
                        "http://opml.radiotime.com/", headers=headers
                    )
                else:
                    ws_resp = await web_session.get("http://opml.radiotime.com/")
                response_text = await ws_resp.text()
                root = ET.fromstring(response_text)  # nosec
                tunein_types = []
                for item in root.findall("body/outline"):
                    tunein_types.append(
                        BrowseMedia(
                            title=item.get("text"),
                            media_class=MEDIA_CLASS_DIRECTORY,
                            media_content_id=media_content_id
                            + "/2/"
                            + item.get("text")
                            + "/"
                            + item.get("URL"),
                            media_content_type=MEDIA_TYPE_APP,
                            can_play=False,
                            can_expand=True,
                            thumbnail="",
                        )
                    )

                root = BrowseMedia(
                    title="TuneIn",
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_id=media_content_id,
                    media_content_type=MEDIA_TYPE_APP,
                    can_expand=True,
                    can_play=False,
                    children=tunein_types,
                    # thumbnail="http://www.ai-speaker.com/images/media-browser/tunein.svg",
                )
                return root

        except Exception as e:
            _LOGGER.error("Can't connect tune in api: " + str(e))
            raise BrowseError("Can't connect tune in api: " + str(e))
    elif media_content_id.startswith("ais_tunein/2/"):
        try:
            #  7 sec should be enough
            with async_timeout.timeout(7):
                url_to_call = media_content_id.split("/", 3)[3]
                # we need to set language only for demo
                if ais_global.get_sercure_android_id_dom() == "dom-demo":
                    headers = {"accept-language": "pl"}
                    ws_resp = await web_session.get(url_to_call, headers=headers)
                else:
                    ws_resp = await web_session.get(url_to_call)
                response_text = await ws_resp.text()
                root = ET.fromstring(response_text)  # nosec
                tunein_items = []
                for item in root.findall("body/outline"):
                    if item.get("type") == "audio":
                        tunein_items.append(
                            BrowseMedia(
                                title=item.get("text"),
                                media_class=MEDIA_CLASS_DIRECTORY,
                                media_content_id="ais_tunein/2/"
                                + item.get("text")
                                + "/"
                                + item.get("URL"),
                                media_content_type=MEDIA_TYPE_APP,
                                can_play=True,
                                can_expand=False,
                                thumbnail=item.get("image"),
                            )
                        )
                    elif item.get("type") == "link":
                        tunein_items.append(
                            BrowseMedia(
                                title=item.get("text"),
                                media_class=MEDIA_CLASS_DIRECTORY,
                                media_content_id="ais_tunein/2/"
                                + item.get("text")
                                + "/"
                                + item.get("URL"),
                                media_content_type=MEDIA_TYPE_APP,
                                can_play=False,
                                can_expand=True,
                            )
                        )
                for item in root.findall("body/outline/outline"):
                    if item.get("type") == "audio":
                        tunein_items.append(
                            BrowseMedia(
                                title=item.get("text"),
                                media_class=MEDIA_CLASS_DIRECTORY,
                                media_content_id="ais_tunein/2/"
                                + item.get("text")
                                + "/"
                                + item.get("URL"),
                                media_content_type=MEDIA_TYPE_APP,
                                can_play=True,
                                can_expand=False,
                                thumbnail=item.get("image"),
                            )
                        )
                    elif item.get("type") == "link":
                        tunein_items.append(
                            BrowseMedia(
                                title=item.get("text"),
                                media_class=MEDIA_CLASS_DIRECTORY,
                                media_content_id="ais_tunein/2/"
                                + item.get("text")
                                + "/"
                                + item.get("URL"),
                                media_content_type=MEDIA_TYPE_APP,
                                can_play=False,
                                can_expand=True,
                            )
                        )

                root = BrowseMedia(
                    title=media_content_id.split("/", 3)[2],
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_id=media_content_id,
                    media_content_type=MEDIA_TYPE_APP,
                    can_expand=True,
                    can_play=False,
                    children=tunein_items,
                    # thumbnail="http://www.ai-speaker.com/images/media-browser/tunein.svg",
                )
                return root

        except Exception as e:
            _LOGGER.error("Can't connect tune in api: " + str(e))
            raise BrowseError("Can't connect tune in api: " + str(e))
