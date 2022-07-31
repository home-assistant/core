"""Media Source models."""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_APP,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_APPS,
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

    children: list[BrowseMediaSource | BrowseMedia] | None

    def __init__(
        self, *, domain: str | None, identifier: str | None, **kwargs: Any
    ) -> None:
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
    domain: str | None
    identifier: str
    target_media_player: str | None

    async def async_browse(self) -> BrowseMediaSource:
        """Browse this item."""
        if self.domain is None:
            base = BrowseMediaSource(
                domain=None,
                identifier=None,
                media_class=MEDIA_CLASS_APP,
                media_content_type=MEDIA_TYPE_APPS,
                title="Media Sources",
                can_play=False,
                can_expand=True,
                children_media_class=MEDIA_CLASS_APP,
            )
            base.children = sorted(
                (
                    BrowseMediaSource(
                        domain=source.domain,
                        identifier=None,
                        media_class=MEDIA_CLASS_APP,
                        media_content_type=MEDIA_TYPE_APP,
                        thumbnail=f"https://brands.home-assistant.io/_/{source.domain}/logo.png",
                        title=source.name,
                        can_play=False,
                        can_expand=True,
                    )
                    for source in self.hass.data[DOMAIN].values()
                ),
                key=lambda item: item.title,
            )
            return base

        return await self.async_media_source().async_browse_media(self)

    async def async_resolve(self) -> PlayMedia:
        """Resolve to playable item."""
        return await self.async_media_source().async_resolve_media(self)

    @callback
    def async_media_source(self) -> MediaSource:
        """Return media source that owns this item."""
        return cast(MediaSource, self.hass.data[DOMAIN][self.domain])

    @classmethod
    def from_uri(
        cls, hass: HomeAssistant, uri: str, target_media_player: str | None
    ) -> MediaSourceItem:
        """Create an item from a uri."""
        if not (match := URI_SCHEME_REGEX.match(uri)):
            raise ValueError("Invalid media source URI")

        domain = match.group("domain")
        identifier = match.group("identifier")

        return cls(hass, domain, identifier, target_media_player)


class MediaSource(ABC):
    """Represents a source of media files."""

    name: str | None = None

    def __init__(self, domain: str) -> None:
        """Initialize a media source."""
        self.domain = domain
        if not self.name:
            self.name = domain

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item to a playable item."""
        raise NotImplementedError

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse media."""
        raise NotImplementedError
