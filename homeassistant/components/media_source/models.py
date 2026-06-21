"""Media Source models."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaType,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_cached_translations

from .const import (
    DATA_LOCAL_SOURCE,
    DATA_MEDIA_SOURCE_PLATFORMS,
    DOMAIN,
    URI_SCHEME,
    URI_SCHEME_REGEX,
)

if TYPE_CHECKING:
    from pathlib import Path


async def _async_get_media_sources(hass: HomeAssistant) -> dict[str, MediaSource]:
    """Return all media sources, loading integration platforms on demand."""
    sources: dict[str, MediaSource] = {DOMAIN: hass.data[DATA_LOCAL_SOURCE]}
    sources.update(await hass.data[DATA_MEDIA_SOURCE_PLATFORMS].async_get_platforms())
    return sources


async def _async_get_media_source(
    hass: HomeAssistant, domain: str
) -> MediaSource | None:
    """Return the media source for a domain, loading it on demand."""
    if domain == DOMAIN:
        return hass.data[DATA_LOCAL_SOURCE]
    return await hass.data[DATA_MEDIA_SOURCE_PLATFORMS].async_get_platform(domain)


@dataclass(slots=True)
class PlayMedia:
    """Represents a playable media."""

    url: str
    mime_type: str
    path: Path | None = field(kw_only=True, default=None)


class BrowseMediaSource(BrowseMedia):
    """Represent a browsable media file."""

    def __init__(self, *, domain: str, identifier: str | None, **kwargs: Any) -> None:
        """Initialize media source browse media."""
        media_content_id = f"{URI_SCHEME}{domain}"
        if identifier:
            media_content_id += f"/{identifier}"

        super().__init__(media_content_id=media_content_id, **kwargs)

        self.domain = domain
        self.identifier = identifier


class RootBrowseMediaSource(BrowseMedia):
    """Represent the root media source browse node."""

    domain: None = None
    identifier: None = None

    def __init__(self, **kwargs: Any) -> None:
        """Initialize root media source browse media."""
        super().__init__(media_content_id=URI_SCHEME, **kwargs)


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

    async def async_browse(self) -> BrowseMediaSource | RootBrowseMediaSource:
        """Browse this item."""
        if self.domain is None:
            title = async_get_cached_translations(
                self.hass, self.hass.config.language, "common", "media_source"
            ).get("component.media_source.common.sources_default", "Media Sources")
            base = RootBrowseMediaSource(
                media_class=MediaClass.APP,
                media_content_type=MediaType.APPS,
                title=title,
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.APP,
            )
            sources = await _async_get_media_sources(self.hass)
            base.children = sorted(
                (
                    BrowseMediaSource(
                        domain=source.domain,
                        identifier=None,
                        media_class=MediaClass.APP,
                        media_content_type=MediaType.APP,
                        thumbnail=f"/api/brands/integration/{source.domain}/logo.png",
                        title=source.name,
                        can_play=False,
                        can_expand=True,
                    )
                    for source in sources.values()
                ),
                key=lambda item: item.title,
            )
            return base

        return await (await self.async_media_source()).async_browse_media(self)

    async def async_search(self, query: SearchMediaQuery) -> SearchMedia:
        """Search this item."""
        # Searching the aggregate root (no specific source) is currently not supported
        # because it would possibly returns 100s of items
        if self.domain is None:
            raise NotImplementedError

        return await (await self._async_media_source()).async_search_media(self, query)

    async def async_resolve(self) -> PlayMedia:
        """Resolve to playable item."""
        return await (await self.async_media_source()).async_resolve_media(self)

    async def async_media_source(self) -> MediaSource:
        """Return media source that owns this item."""
        if TYPE_CHECKING:
            assert self.domain is not None
        # Existence is validated by _get_media_item before browse/resolve.
        source = await _async_get_media_source(self.hass, self.domain)
        assert source is not None
        return source

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

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse media."""
        raise NotImplementedError

    async def async_search_media(
        self, item: MediaSourceItem, query: SearchMediaQuery
    ) -> SearchMedia:
        """Search media."""
        raise NotImplementedError
