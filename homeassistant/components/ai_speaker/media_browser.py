"""Support to interface with the Plex API."""
import logging

import async_timeout

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_PODCAST,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_CHANNELS,
    MEDIA_TYPE_MUSIC,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.helpers import aiohttp_client

from .const import AIS_WS_AUDIOBOOKS_URL, AIS_WS_PODCAST_URL, AIS_WS_RADIO_URL

_LOGGER = logging.getLogger(__name__)

G_AUDIOBOOKS_LIB = None
cloud_ws_token = "123456789"
cloud_ws_header = {"Authorization": f"{cloud_ws_token}"}


class MissingMediaInformation(BrowseError):
    """Missing media required information."""


class UnknownMediaType(BrowseError):
    """Unknown media type."""


async def browse_media(hass, media_content_type=None, media_content_id=None):
    """Implement the media browsing helper."""
    if media_content_id in [None, "library"]:
        return ais_media_library()

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
            title="AIS Radio",
            media_class=MEDIA_CLASS_MUSIC,
            media_content_id="ais_radio",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="AIS Podcast",
            media_class=MEDIA_CLASS_PODCAST,
            media_content_id="ais_podcast",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="AIS Audiobooks",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="ais_audio_books",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )
    ais_library_info.children.append(
        BrowseMedia(
            title="TuneIn",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="ais_tunein",
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
        )
    )

    return ais_library_info


async def get_books_lib(hass):
    """Implement the get books lib."""
    global G_AUDIOBOOKS_LIB
    import requests

    if G_AUDIOBOOKS_LIB is None:
        ws_resp = requests.get(AIS_WS_AUDIOBOOKS_URL, timeout=30)
        G_AUDIOBOOKS_LIB = ws_resp.json()
    return G_AUDIOBOOKS_LIB


async def ais_audio_books_library(hass, media_content_id) -> BrowseMedia:
    """Create response payload to describe contents of a books library."""
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
    """Create response payload to describe contents of a podcast library."""
    import requests

    if media_content_id == "ais_podcast":
        # get podcast types
        ws_resp = requests.get(AIS_WS_PODCAST_URL, headers=cloud_ws_header, timeout=5)
        json_ws_resp = ws_resp.json()
        ais_podcast_types = []
        for item in json_ws_resp["data"]:
            ais_podcast_types.append(
                BrowseMedia(
                    title=item,
                    media_class=MEDIA_CLASS_DIRECTORY,
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
        rest_url = (
            AIS_WS_PODCAST_URL + "&type=" + media_content_id.replace("ais_podcast/", "")
        )
        ws_resp = requests.get(rest_url, headers=cloud_ws_header, timeout=5)
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
            _LOGGER.warning("Timeout when reading RSS " + str(e))
            raise BrowseError("Timeout when reading RSS %s", lookup_url)


def ais_radio_library(hass, media_content_id) -> BrowseMedia:
    """Create response payload to describe contents of a radio library."""
    import requests

    if media_content_id == "ais_radio":
        ws_resp = requests.get(AIS_WS_RADIO_URL, headers=cloud_ws_header, timeout=5)
        json_ws_resp = ws_resp.json()
        ais_radio_types = []
        for item in json_ws_resp["data"]:
            ais_radio_types.append(
                BrowseMedia(
                    title=item,
                    media_class=MEDIA_CLASS_DIRECTORY,
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
        rest_url = (
            AIS_WS_RADIO_URL + "&type=" + media_content_id.replace("ais_radio/", "")
        )
        ws_resp = requests.get(rest_url, headers=cloud_ws_header, timeout=5)
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


async def get_media_content_id_form_ais(hass, media_content_id):
    """Get media content from ais."""
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
    """Create response payload to describe contents of a tunein library."""
    import xml.etree.ElementTree as ET

    web_session = aiohttp_client.async_get_clientsession(hass)
    if media_content_id == "ais_tunein":
        try:
            #  7 sec should be enough
            with async_timeout.timeout(7):
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
