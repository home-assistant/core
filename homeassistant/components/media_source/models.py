"""Media Source models."""
from abc import ABC
from dataclasses import dataclass
from typing import List, Optional, Tuple

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_CHANNEL,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_CHANNELS,
)
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, URI_SCHEME, URI_SCHEME_REGEX


@dataclass
class PlayMedia:
    """Represents a playable media."""

    url: str
    mime_type: str


class BrowseMediaSource(BrowseMedia):
    """Represent a browsable media file."""

    children: Optional[List["BrowseMediaSource"]]

    def __init__(self, *, domain: Optional[str], identifier: Optional[str], **kwargs):
        """Initialize media source browse media."""
        media_content_id = f"{URI_SCHEME}{domain or ''}"
        if identifier:
            media_content_id += f"/{identifier}"

        super().__init__(media_content_id=media_content_id, **kwargs)

        self.domain = domain
        self.identifier = identifier


@dataclass
class MediaSourceItem:
    """A parsed media item."""

    hass: HomeAssistant
    domain: Optional[str]
    identifier: str

    async def async_browse(self) -> BrowseMediaSource:
        """Browse this item."""
        if self.domain is None:
            base = BrowseMediaSource(
                domain=None,
                identifier=None,
                media_class=MEDIA_CLASS_CHANNEL,
                media_content_type=MEDIA_TYPE_CHANNELS,
                title="Media Sources",
                can_play=False,
                can_expand=True,
            )
            base.children = [
                BrowseMediaSource(
                    domain=source.domain,
                    identifier=None,
                    media_class=MEDIA_CLASS_CHANNEL,
                    media_content_type=MEDIA_TYPE_CHANNEL,
                    title=source.name,
                    can_play=False,
                    can_expand=True,
                )
                for source in self.hass.data[DOMAIN].values()
            ]
            return base

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

    name: str = None

    def __init__(self, domain: str):
        """Initialize a media source."""
        self.domain = domain
        if not self.name:
            self.name = domain

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item to a playable item."""
        raise NotImplementedError

    async def async_browse_media(
        self, item: MediaSourceItem, media_types: Tuple[str]
    ) -> BrowseMediaSource:
        """Browse media."""
        raise NotImplementedError
