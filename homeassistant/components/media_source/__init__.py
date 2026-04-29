"""The media_source integration."""

from __future__ import annotations

from typing import Protocol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.typing import ConfigType

from . import http, local_source
from .const import (
    DOMAIN,
    MEDIA_CLASS_MAP,
    MEDIA_MIME_TYPES,
    MEDIA_SOURCE_DATA,
    URI_SCHEME,
    URI_SCHEME_REGEX,
)
from .error import MediaSourceError, Unresolvable
from .helper import async_browse_media, async_resolve_media
from .models import BrowseMediaSource, MediaSource, MediaSourceItem, PlayMedia

__all__ = [
    "DOMAIN",
    "MEDIA_CLASS_MAP",
    "MEDIA_MIME_TYPES",
    "BrowseMediaSource",
    "MediaSource",
    "MediaSourceError",
    "MediaSourceItem",
    "PlayMedia",
    "Unresolvable",
    "async_browse_media",
    "async_register_media_source",
    "async_resolve_media",
    "generate_media_source_id",
    "is_media_source_id",
]


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


class MediaSourceProtocol(Protocol):
    """Define the format of media_source platforms."""

    async def async_get_media_source(self, hass: HomeAssistant) -> MediaSource | None:
        """Set up media source.

        Return ``None`` to defer registration; the integration can register
        the source later via :func:`async_register_media_source`.
        """


def is_media_source_id(media_content_id: str) -> bool:
    """Test if identifier is a media source."""
    return URI_SCHEME_REGEX.match(media_content_id) is not None


def generate_media_source_id(domain: str, identifier: str) -> str:
    """Generate a media source ID."""
    uri = f"{URI_SCHEME}{domain or ''}"
    if identifier:
        uri += f"/{identifier}"
    return uri


@callback
def async_register_media_source(hass: HomeAssistant, source: MediaSource) -> None:
    """Register a media source.

    Use this to register a source after integration setup, e.g. once content
    becomes available. Calling this with a source whose domain is already
    registered is a no-op.
    """
    sources = hass.data[MEDIA_SOURCE_DATA]
    if source.domain in sources:
        return
    sources[source.domain] = source
    if isinstance(source, local_source.LocalSource):
        hass.http.register_view(local_source.LocalMediaView(hass, source))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the media_source component."""
    hass.data[MEDIA_SOURCE_DATA] = {}
    http.async_setup(hass)

    # Local sources support
    await _process_media_source_platform(hass, DOMAIN, local_source)
    hass.http.register_view(local_source.UploadMediaView)
    websocket_api.async_register_command(hass, local_source.websocket_remove_media)

    await async_process_integration_platforms(
        hass, DOMAIN, _process_media_source_platform
    )
    return True


async def _process_media_source_platform(
    hass: HomeAssistant,
    domain: str,
    platform: MediaSourceProtocol,
) -> None:
    """Process a media source platform."""
    source = await platform.async_get_media_source(hass)
    if source is None:
        return
    async_register_media_source(hass, source)
