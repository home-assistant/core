"""Implementation of DLNA DMS as a media source.

URIs look like "media-source://dlna_dms/<source_id>/<media_identifier>"

Media identifiers can look like:
* `/path/to/file`: slash-separated path through the Content Directory
* `:ObjectID`: colon followed by a server-assigned ID for an object
* `?query`: question mark followed by a query string to search for,
    see [DLNA ContentDirectory SearchCriteria](http://www.upnp.org/specs/av/UPnP-av-ContentDirectory-v1-Service.pdf)
    for the syntax.
"""

from __future__ import annotations

from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER, PATH_OBJECT_ID_FLAG, ROOT_OBJECT_ID, SOURCE_SEP
from .dms import DidlPlayMedia, get_domain_data


async def async_get_media_source(hass: HomeAssistant) -> DmsMediaSource:
    """Set up DLNA DMS media source."""
    LOGGER.debug("Setting up DLNA media sources")
    return DmsMediaSource(hass)


class DmsMediaSource(MediaSource):
    """Provide DLNA Media Servers as media sources."""

    name = "DLNA Servers"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize DLNA source."""
        super().__init__(DOMAIN)

        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> DidlPlayMedia:
        """Resolve a media item to a playable item."""
        dms_data = get_domain_data(self.hass)
        if not dms_data.sources:
            raise Unresolvable("No sources have been configured")

        source_id, media_id = _parse_identifier(item)
        if not source_id:
            raise Unresolvable(f"No source ID in {item.identifier}")
        if not media_id:
            raise Unresolvable(f"No media ID in {item.identifier}")

        try:
            source = dms_data.sources[source_id]
        except KeyError as err:
            raise Unresolvable(f"Unknown source ID: {source_id}") from err

        return await source.async_resolve_media(media_id)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse media."""
        dms_data = get_domain_data(self.hass)
        if not dms_data.sources:
            raise BrowseError("No sources have been configured")

        source_id, media_id = _parse_identifier(item)
        LOGGER.debug("Browsing for %s / %s", source_id, media_id)

        if not source_id and len(dms_data.sources) > 1:
            # Browsing the root of dlna_dms with more than one server, return
            # all known servers.
            base = BrowseMediaSource(
                domain=DOMAIN,
                identifier="",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.CHANNELS,
                title=self.name,
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.CHANNEL,
            )

            base.children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{source_id}/{PATH_OBJECT_ID_FLAG}{ROOT_OBJECT_ID}",
                    media_class=MediaClass.CHANNEL,
                    media_content_type=MediaType.CHANNEL,
                    title=source.name,
                    can_play=False,
                    can_expand=True,
                    thumbnail=source.icon,
                )
                for source_id, source in dms_data.sources.items()
            ]

            return base

        if not source_id:
            # No source specified, default to the first registered
            source_id = next(iter(dms_data.sources))

        try:
            source = dms_data.sources[source_id]
        except KeyError as err:
            raise BrowseError(f"Unknown source ID: {source_id}") from err

        return await source.async_browse_media(media_id)


def _parse_identifier(item: MediaSourceItem) -> tuple[str | None, str | None]:
    """Parse the source_id and media identifier from a media source item."""
    if not item.identifier:
        return None, None
    source_id, _, media_id = item.identifier.partition(SOURCE_SEP)
    return source_id or None, media_id or None
