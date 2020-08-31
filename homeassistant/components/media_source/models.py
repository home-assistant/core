"""Media Source models."""
from abc import ABC
from dataclasses import dataclass
from typing import List, Optional, Tuple

from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, URI_SCHEME, URI_SCHEME_REGEX


@dataclass
class PlayMedia:
    """Represents a playable media."""

    url: str
    mime_type: str


@dataclass
class BrowseMedia:
    """Represent a browsable media file."""

    domain: str
    identifier: str

    name: str
    can_play: bool
    can_expand: bool
    media_content_type: str = None
    children: List = None

    def to_uri(self):
        """Return URI of media."""
        return f"{URI_SCHEME}{self.domain}/{self.identifier}"

    def to_media_player_item(self):
        """Convert Media class to browse media dictionary."""
        content_type = self.media_content_type

        if content_type is None:
            content_type = "folder" if self.can_expand else "file"

        response = {
            "title": self.name,
            "media_content_type": content_type,
            "media_content_id": self.to_uri(),
            "can_play": self.can_play,
            "can_expand": self.can_expand,
        }

        if self.children:
            response["children"] = [
                child.to_media_player_item() for child in self.children
            ]

        return response


@dataclass
class MediaSourceItem:
    """A parsed media item."""

    hass: HomeAssistant
    domain: Optional[str]
    identifier: str

    async def async_browse(self) -> BrowseMedia:
        """Browse this item."""
        # Future: handle `domain` is None (multiple sources available)
        return await self.async_media_source().async_browse_media(self)

    async def async_resolve(self) -> PlayMedia:
        """Resolve to playable item."""
        return await self.async_media_source().async_resolve_media(self)

    @callback
    def async_media_source(self) -> "MediaSource":
        """Return media source that owns this item."""
        return self.hass.data[DOMAIN][self.domain]

    @classmethod
    def from_uri(cls, hass: HomeAssistant, uri: str) -> "MediaSourceItem":
        """Create an item from a uri."""
        match = URI_SCHEME_REGEX.match(uri)

        if not match:
            raise ValueError("Invalid media source URI")

        domain = match.group("domain")
        identifier = match.group("identifier")

        return cls(hass, domain, identifier)


class MediaSource(ABC):
    """Represents a source of media files."""

    def __init__(self, domain: str):
        """Initialize a media source."""
        self.domain = domain

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item to a playable item."""
        raise NotImplementedError

    async def async_browse_media(
        self, item: MediaSourceItem, media_types: Tuple[str]
    ) -> BrowseMedia:
        """Browse media."""
        raise NotImplementedError
