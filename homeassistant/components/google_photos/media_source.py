"""Media source for Google Photos."""

from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Any, cast

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
from .const import DOMAIN
from .exceptions import GooglePhotosApiError

_LOGGER = logging.getLogger(__name__)

# Media Sources do not support paging, so we only show a subset of recent
# photos when displaying the users library. We fetch a minimum of 50 photos
# unless we run out, but in pages of 100 at a time given sometimes responses
# may only contain a handful of items Fetches at least 50 photos.
MAX_PHOTOS = 50
PAGE_SIZE = 100

THUMBNAIL_SIZE = 256
LARGE_IMAGE_SIZE = 2160


# Markers for parts of PhotosIdentifier url pattern.
# The PhotosIdentifier can be in the following forms:
#  config-entry-id
#  config-entry-id/a/album-media-id
#  config-entry-id/p/photo-media-id
#
# The album-media-id can contain special reserved folder names for use by
# this integration for virtual folders like the `recent` album.
PHOTO_SOURCE_IDENTIFIER_PHOTO = "p"
PHOTO_SOURCE_IDENTIFIER_ALBUM = "a"

# Currently supports a single album of recent photos
RECENT_PHOTOS_ALBUM = "recent"
RECENT_PHOTOS_TITLE = "Recent Photos"


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
        """Serialize the identiifer as a string.

        This is the opposite if of().
        """
        if self.id_type is None:
            return self.config_entry_id
        return f"{self.config_entry_id}/{self.id_type}/{self.media_id}"

    @staticmethod
    def of(identifier: str) -> "PhotosIdentifier":
        """Parse a PhotosIdentifier form a string.

        This is the opposite of as_string().
        """
        parts = identifier.split("/")
        _LOGGER.debug("parts=%s", parts)
        if len(parts) == 1:
            return PhotosIdentifier(parts[0])
        if len(parts) != 3:
            raise BrowseError(f"Invalid identifier: {identifier}")
        return PhotosIdentifier(parts[0], PhotosIdentifierType.of(parts[1]), parts[2])

    @staticmethod
    def album(config_entry_id: str, media_id: str) -> "PhotosIdentifier":
        """Create an album PhotosIdentifier."""
        return PhotosIdentifier(config_entry_id, PhotosIdentifierType.ALBUM, media_id)

    @staticmethod
    def photo(config_entry_id: str, media_id: str) -> "PhotosIdentifier":
        """Create an album PhotosIdentifier."""
        return PhotosIdentifier(config_entry_id, PhotosIdentifierType.PHOTO, media_id)


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
                    for entry in self.hass.config_entries.async_loaded_entries(DOMAIN)
                ],
            )

        # Determine the configuration entry for this item
        identifier = PhotosIdentifier.of(item.identifier)
        entry = self._async_config_entry(identifier.config_entry_id)
        client = entry.runtime_data

        source = _build_account(entry, identifier)
        if identifier.id_type is None:
            source.children = [
                _build_album(
                    RECENT_PHOTOS_TITLE,
                    PhotosIdentifier.album(
                        identifier.config_entry_id, RECENT_PHOTOS_ALBUM
                    ),
                )
            ]
            return source

        # Currently only supports listing a single album of recent photos.
        if identifier.media_id != RECENT_PHOTOS_ALBUM:
            raise BrowseError(f"Unsupported album: {identifier}")

        # Fetch recent items
        media_items: list[dict[str, Any]] = []
        page_token: str | None = None
        while len(media_items) < MAX_PHOTOS:
            try:
                result = await client.list_media_items(
                    page_size=PAGE_SIZE, page_token=page_token
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


def _build_album(title: str, identifier: PhotosIdentifier) -> BrowseMediaSource:
    """Build an album node."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=identifier.as_string(),
        media_class=MediaClass.ALBUM,
        media_content_type=MediaClass.ALBUM,
        title=title,
        can_play=False,
        can_expand=True,
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
