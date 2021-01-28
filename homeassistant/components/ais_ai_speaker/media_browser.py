"""Support to interface with the AIS API."""
import logging
import xml.etree.ElementTree as XmlETree

import feedparser

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

_LOGGER = logging.getLogger(__name__)


class MissingMediaInformation(BrowseError):
    """Missing media required information."""


class UnknownMediaType(BrowseError):
    """Unknown media type."""


async def async_browse_media(
    media_content_type=None,
    media_content_id=None,
    ais_gate=None,
):
    """Implement the media browsing helper."""

    if media_content_id in [None, "library"]:
        return await async_ais_media_library()

    if media_content_id.startswith("ais_radio"):
        return await async_ais_radio_library(media_content_id, ais_gate)

    if media_content_id.startswith("ais_tunein"):
        return await async_ais_tunein_library(media_content_id, ais_gate)

    if media_content_id.startswith("ais_podcast"):
        return await async_ais_podcast_library(media_content_id, ais_gate)

    if media_content_id.startswith("ais_audio_books"):
        return await async_ais_audio_books_library(media_content_id, ais_gate)

    raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")


async def async_ais_media_library() -> BrowseMedia:
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


async def async_ais_audio_books_library(media_content_id, ais_gate) -> BrowseMedia:
    """Create response payload to describe contents of a books library."""
    # get all books
    if media_content_id == "ais_audio_books":
        # get authors
        authors = []
        all_books = await ais_gate.get_audio_type(media_content_id)
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
        )
    elif media_content_id.count("/") == 1:
        # get books for author
        ais_books = []
        all_books = await ais_gate.get_audio_type("ais_audio_books")
        for item in all_books:
            if item["author"] == media_content_id.replace("ais_audio_books/", ""):
                if "cover_thumb" in item:
                    thumbnail = "https://wolnelektury.pl/media/" + item["cover_thumb"]
                else:
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
        )
    else:
        # get book chapters
        try:
            data = await ais_gate.get_audio_name(media_content_id)
            ais_book_chapters = []
            for item in data["media"]:
                if item["type"] == "ogg":
                    if "cover" in data:
                        thumbnail = data["cover"]
                    else:
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
            )
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Can't load chapters: %s", error)
            raise BrowseError("Can't load chapter") from error
    return root


async def async_ais_podcast_library(media_content_id, ais_gate) -> BrowseMedia:
    """Create response payload to describe contents of a podcast library."""
    if media_content_id == "ais_podcast":
        # get podcast types
        json_ws_resp = await ais_gate.get_audio_type(media_content_id)
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
        )
    elif media_content_id.count("/") == 1:
        # get podcasts for types
        json_ws_resp = await ais_gate.get_audio_name(media_content_id)
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
        )
    else:
        # get podcast tracks
        response_text = await ais_gate.get_podcast_tracks(media_content_id)
        if response_text is not None:
            podcasts = feedparser.parse(response_text)
            ais_podcast_episodes = []
            for entry in podcasts.entries:
                if "image" in podcasts.feed:
                    thumbnail = podcasts.feed.image.href
                else:
                    thumbnail = ""
                ais_podcast_episodes.append(
                    BrowseMedia(
                        title=entry.title,
                        media_class=MEDIA_CLASS_MUSIC,
                        media_content_id=entry.enclosures[0]["url"],
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
                children=ais_podcast_episodes,
            )
        else:
            _LOGGER.error("Error when reading RSS: %s", media_content_id)
            raise BrowseError("Error when reading RSS")
    return root


async def async_ais_radio_library(media_content_id, ais_gate) -> BrowseMedia:
    """Create response payload to describe contents of a radio library."""
    if media_content_id == "ais_radio":
        json_ws_resp = await ais_gate.get_audio_type(media_content_id)
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
            children=ais_radio_types,
        )
    else:
        # get radio station for type
        json_ws_resp = await ais_gate.get_audio_name(media_content_id)
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
            children=ais_radio_stations,
        )
    return root


async def async_ais_tunein_library(media_content_id, ais_gate) -> BrowseMedia:
    """Create response payload to describe contents of a tunein library."""
    if media_content_id == "ais_tunein":
        response_text = await ais_gate.get_audio_type(media_content_id)
        if response_text is None:
            _LOGGER.error("Can't connect tune in api")
            raise BrowseError("Can't connect tune in api")
        root = XmlETree.fromstring(response_text)  # nosec
        tune_types = []
        for tune_item in root.findall("body/outline"):
            tune_types.append(
                BrowseMedia(
                    title=tune_item.get("text"),
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_id=media_content_id
                    + "/2/"
                    + tune_item.get("text")
                    + "/"
                    + tune_item.get("URL"),
                    media_content_type=MEDIA_TYPE_APP,
                    can_play=False,
                    can_expand=True,
                    thumbnail="",
                )
            )

        return BrowseMedia(
            title="TuneIn",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id=media_content_id,
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            children=tune_types,
        )

    if media_content_id.startswith("ais_tunein"):
        response_text = await ais_gate.get_audio_name(media_content_id)
        if response_text is None:
            _LOGGER.error("Can't connect tune in api")
            raise BrowseError("Can't connect tune in api")

        root = XmlETree.fromstring(response_text)  # nosec
        tune_items = []
        for tune_item in root.findall("body/outline"):
            if tune_item.get("type") == "audio":
                tune_items.append(
                    BrowseMedia(
                        title=tune_item.get("text"),
                        media_class=MEDIA_CLASS_DIRECTORY,
                        media_content_id="ais_tunein/2/"
                        + tune_item.get("text")
                        + "/"
                        + tune_item.get("URL"),
                        media_content_type=MEDIA_TYPE_APP,
                        can_play=True,
                        can_expand=False,
                        thumbnail=tune_item.get("image"),
                    )
                )
            elif tune_item.get("type") == "link":
                tune_items.append(
                    BrowseMedia(
                        title=tune_item.get("text"),
                        media_class=MEDIA_CLASS_DIRECTORY,
                        media_content_id="ais_tunein/2/"
                        + tune_item.get("text")
                        + "/"
                        + tune_item.get("URL"),
                        media_content_type=MEDIA_TYPE_APP,
                        can_play=False,
                        can_expand=True,
                    )
                )
        for tune_item in root.findall("body/outline/outline"):
            if tune_item.get("type") == "audio":
                tune_items.append(
                    BrowseMedia(
                        title=tune_item.get("text"),
                        media_class=MEDIA_CLASS_DIRECTORY,
                        media_content_id="ais_tunein/2/"
                        + tune_item.get("text")
                        + "/"
                        + tune_item.get("URL"),
                        media_content_type=MEDIA_TYPE_APP,
                        can_play=True,
                        can_expand=False,
                        thumbnail=tune_item.get("image"),
                    )
                )
            elif tune_item.get("type") == "link":
                tune_items.append(
                    BrowseMedia(
                        title=tune_item.get("text"),
                        media_class=MEDIA_CLASS_DIRECTORY,
                        media_content_id="ais_tunein/2/"
                        + tune_item.get("text")
                        + "/"
                        + tune_item.get("URL"),
                        media_content_type=MEDIA_TYPE_APP,
                        can_play=False,
                        can_expand=True,
                    )
                )
        return BrowseMedia(
            title=media_content_id.split("/", 3)[2],
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id=media_content_id,
            media_content_type=MEDIA_TYPE_APP,
            can_expand=True,
            can_play=False,
            children=tune_items,
        )
