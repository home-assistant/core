"""Media source for Google Photos."""

from dataclasses import dataclass
from enum import Enum, StrEnum
import logging
from typing import Any, Self, cast

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseError,
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant

from . import GooglePhotosConfigEntry
from .const import DOMAIN, READ_SCOPES
from .exceptions import GooglePhotosApiError

_LOGGER = logging.getLogger(__name__)

# Media Sources do not support paging, so we only show a subset of recent
# photos when displaying the users library. We fetch a minimum of 50 photos
# unless we run out, but in pages of 100 at a time given sometimes responses
# may only contain a handful of items Fetches at least 50 photos.
MAX_RECENT_PHOTOS = 50
MAX_ALBUMS = 50
PAGE_SIZE = 100

THUMBNAIL_SIZE = 256
LARGE_IMAGE_SIZE = 2160


@dataclass
class SpecialAlbumDetails:
    """Details for a Special album."""

    path: str
    title: str
    list_args: dict[str, Any]
    max_photos: int | None


class SpecialAlbum(Enum):
    """Special Album types."""

    RECENT = SpecialAlbumDetails("recent", "Recent Photos", {}, MAX_RECENT_PHOTOS)
    FAVORITE = SpecialAlbumDetails(
        "favorites", "Favorite Photos", {"favorites": True}, None
    )

    @classmethod
    def of(cls, path: str) -> Self | None:
        """Parse a PhotosIdentifierType by string value."""
        for enum in cls:
            if enum.value.path == path:
                return enum
        return None


# The PhotosIdentifier can be in the following forms:
#  config-entry-id
#  config-entry-id/a/album-media-id
#  config-entry-id/p/photo-media-id
#
# The album-media-id can contain special reserved folder names for use by
# this integration for virtual folders like the `recent` album.


class PhotosIdentifierType(StrEnum):
    """Type for a PhotosIdentifier."""

    PHOTO = "p"
    ALBUM = "a"

    @classmethod
    def of(cls, name: str) -> "PhotosIdentifierType":
        """Parse a PhotosIdentifierType by string value."""
        for enum in PhotosIdentifierType:
            if enum.value == name:
                return enum
        raise ValueError(f"Invalid PhotosIdentifierType: {name}")


@dataclass
class PhotosIdentifier:
    """Google Photos item identifier in a media source URL."""

    config_entry_id: str
    """Identifies the account for the media item."""

    id_type: PhotosIdentifierType | None = None
    """Type of identifier"""

    media_id: str | None = None
    """Identifies the album or photo contents to show."""

    def as_string(self) -> str:
        """Serialize the identifier as a string."""
        if self.id_type is None:
            return self.config_entry_id
        return f"{self.config_entry_id}/{self.id_type}/{self.media_id}"

    @classmethod
    def of(cls, identifier: str) -> Self:
        """Parse a PhotosIdentifier form a string."""
        parts = identifier.split("/")
        if len(parts) == 1:
            return cls(parts[0])
        if len(parts) != 3:
            raise BrowseError(f"Invalid identifier: {identifier}")
        return cls(parts[0], PhotosIdentifierType.of(parts[1]), parts[2])

    @classmethod
    def album(cls, config_entry_id: str, media_id: str) -> Self:
        """Create an album PhotosIdentifier."""
        return cls(config_entry_id, PhotosIdentifierType.ALBUM, media_id)

    @classmethod
    def photo(cls, config_entry_id: str, media_id: str) -> Self:
        """Create an album PhotosIdentifier."""
        return cls(config_entry_id, PhotosIdentifierType.PHOTO, media_id)


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Google Photos media source."""
    return GooglePhotosMediaSource(hass)


class GooglePhotosMediaSource(MediaSource):
    """Provide Google Photos as media sources."""

    name = "Google Photos"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize Google Photos source."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media identifier to a url.

        This will resolve a specific media item to a url for the full photo or video contents.
        """
        try:
            identifier = PhotosIdentifier.of(item.identifier)
        except ValueError as err:
            raise BrowseError(f"Could not parse identifier: {item.identifier}") from err
        if (
            identifier.media_id is None
            or identifier.id_type != PhotosIdentifierType.PHOTO
        ):
            raise BrowseError(
                f"Could not resolve identiifer that is not a Photo: {identifier}"
            )
        entry = self._async_config_entry(identifier.config_entry_id)
        client = entry.runtime_data
        media_item = await client.get_media_item(media_item_id=identifier.media_id)
        is_video = media_item["mediaMetadata"].get("video") is not None
        return PlayMedia(
            url=(
                _video_url(media_item)
                if is_video
                else _media_url(media_item, LARGE_IMAGE_SIZE)
            ),
            mime_type=media_item["mimeType"],
        )

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return details about the media source.

        This renders the multi-level album structure for an account, its albums,
        or the contents of an album. This will return a BrowseMediaSource with a
        single level of children at the next level of the hierarchy.
        """
        if not item.identifier:
            # Top level view that lists all accounts.
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=None,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaClass.IMAGE,
                title="Google Photos",
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.DIRECTORY,
                children=[
                    _build_account(entry, PhotosIdentifier(cast(str, entry.unique_id)))
                    for entry in self._async_config_entries()
                ],
            )

        # Determine the configuration entry for this item
        identifier = PhotosIdentifier.of(item.identifier)
        entry = self._async_config_entry(identifier.config_entry_id)
        client = entry.runtime_data

        source = _build_account(entry, identifier)
        if identifier.id_type is None:
            result = await client.list_albums(page_size=MAX_ALBUMS)
            source.children = [
                _build_album(
                    special_album.value.title,
                    PhotosIdentifier.album(
                        identifier.config_entry_id, special_album.value.path
                    ),
                )
                for special_album in SpecialAlbum
            ] + [
                _build_album(
                    album["title"],
                    PhotosIdentifier.album(
                        identifier.config_entry_id,
                        album["id"],
                    ),
                    _cover_photo_url(album, THUMBNAIL_SIZE),
                )
                for album in result["albums"]
            ]
            return source

        if (
            identifier.id_type != PhotosIdentifierType.ALBUM
            or identifier.media_id is None
        ):
            raise BrowseError(f"Unsupported identifier: {identifier}")

        list_args: dict[str, Any]
        if special_album := SpecialAlbum.of(identifier.media_id):
            list_args = special_album.value.list_args
        else:
            list_args = {"album_id": identifier.media_id}

        media_items: list[dict[str, Any]] = []
        page_token: str | None = None
        while (
            not special_album
            or (max_photos := special_album.value.max_photos) is None
            or len(media_items) < max_photos
        ):
            try:
                result = await client.list_media_items(
                    **list_args, page_size=PAGE_SIZE, page_token=page_token
                )
            except GooglePhotosApiError as err:
                raise BrowseError(f"Error listing media items: {err}") from err
            media_items.extend(result["mediaItems"])
            page_token = result.get("nextPageToken")
            if page_token is None:
                break

        # Render the grid of media item results
        source.children = [
            _build_media_item(
                PhotosIdentifier.photo(identifier.config_entry_id, media_item["id"]),
                media_item,
            )
            for media_item in media_items
        ]
        return source

    def _async_config_entries(self) -> list[GooglePhotosConfigEntry]:
        """Return all config entries that support photo library reads."""
        entries = []
        for entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
            scopes = entry.data["token"]["scope"].split(" ")
            if any(scope in scopes for scope in READ_SCOPES):
                entries.append(entry)
        return entries

    def _async_config_entry(self, config_entry_id: str) -> GooglePhotosConfigEntry:
        """Return a config entry with the specified id."""
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, config_entry_id
        )
        if not entry:
            raise BrowseError(
                f"Could not find config entry for identifier: {config_entry_id}"
            )
        return entry


def _build_account(
    config_entry: GooglePhotosConfigEntry,
    identifier: PhotosIdentifier,
) -> BrowseMediaSource:
    """Build the root node for a Google Photos account for a config entry."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=identifier.as_string(),
        media_class=MediaClass.DIRECTORY,
        media_content_type=MediaClass.IMAGE,
        title=config_entry.title,
        can_play=False,
        can_expand=True,
    )


def _build_album(
    title: str, identifier: PhotosIdentifier, thumbnail_url: str | None = None
) -> BrowseMediaSource:
    """Build an album node."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=identifier.as_string(),
        media_class=MediaClass.ALBUM,
        media_content_type=MediaClass.ALBUM,
        title=title,
        can_play=False,
        can_expand=True,
        thumbnail=thumbnail_url,
    )


def _build_media_item(
    identifier: PhotosIdentifier, media_item: dict[str, Any]
) -> BrowseMediaSource:
    """Build the node for an individual photo or video."""
    is_video = media_item["mediaMetadata"].get("video") is not None
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=identifier.as_string(),
        media_class=MediaClass.IMAGE if not is_video else MediaClass.VIDEO,
        media_content_type=MediaType.IMAGE if not is_video else MediaType.VIDEO,
        title=media_item["filename"],
        can_play=is_video,
        can_expand=False,
        thumbnail=_media_url(media_item, THUMBNAIL_SIZE),
    )


def _media_url(media_item: dict[str, Any], max_size: int) -> str:
    """Return a media item url with the specified max thumbnail size on the longest edge.

    See https://developers.google.com/photos/library/guides/access-media-items#base-urls
    """
    return f"{media_item["baseUrl"]}=h{max_size}"


def _video_url(media_item: dict[str, Any]) -> str:
    """Return a video url for the item.

    See https://developers.google.com/photos/library/guides/access-media-items#base-urls
    """
    return f"{media_item["baseUrl"]}=dv"


def _cover_photo_url(album: dict[str, Any], max_size: int) -> str:
    """Return a media item url for the cover photo of the album."""
    return f"{album["coverPhotoBaseUrl"]}=h{max_size}"
