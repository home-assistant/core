"""Media Source models."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import BrowseMedia, MediaClass, MediaType
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, MEDIA_SOURCE_DATA, URI_SCHEME, URI_SCHEME_REGEX
from .error import Unresolvable

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(slots=True)
class PlayMedia:
    """Represents a playable media."""

    url: str
    mime_type: str
    path: Path | None = field(kw_only=True, default=None)


class BrowseMediaSource(BrowseMedia):
    """Represent a browsable media file."""

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


@dataclass(slots=True)
class MediaSourceItem:
    """A parsed media item."""

    hass: HomeAssistant
    domain: str | None
    identifier: str
    target_media_player: str | None

    @property
    def media_source_id(self) -> str:
        """Return the media source ID."""
        uri = URI_SCHEME
        if self.domain:
            uri += self.domain
            if self.identifier:
                uri += f"/{self.identifier}"
        return uri

    async def async_browse(self) -> BrowseMediaSource:
        """Browse this item."""
        if self.domain is None:
            base = BrowseMediaSource(
                domain=None,
                identifier=None,
                media_class=MediaClass.APP,
                media_content_type=MediaType.APPS,
                title="Media Sources",
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.APP,
            )
            base.children = sorted(
                (
                    BrowseMediaSource(
                        domain=source.domain,
                        identifier=None,
                        media_class=MediaClass.APP,
                        media_content_type=MediaType.APP,
                        thumbnail=f"https://brands.home-assistant.io/_/{source.domain}/logo.png",
                        title=source.name,
                        can_play=False,
                        can_expand=True,
                    )
                    for source in self.hass.data[MEDIA_SOURCE_DATA].values()
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
        if TYPE_CHECKING:
            assert self.domain is not None
        return self.hass.data[MEDIA_SOURCE_DATA][self.domain]

    @asynccontextmanager
    async def async_resolve_with_path(self) -> PlayMedia:
        """Resolve to playable item with path."""
        async with self.async_media_source().async_resolve_with_path(self) as media:
            yield media

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


class MediaSource:
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

    @asynccontextmanager
    async def async_resolve_with_path(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve to playable item with path."""
        item = await self.async_resolve_media(item)

        if item.path is None:
            raise Unresolvable(
                translation_domain=DOMAIN,
                # TODO translations
                translation_key="resolve_media_path_failed",
                translation_placeholders={
                    "media_content_id": item.media_source_id,
                },
            )

        yield item

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse media."""
        raise NotImplementedError
