"""The media_source integration."""

from typing import Protocol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.integration_platform import LazyIntegrationPlatforms
from homeassistant.helpers.typing import ConfigType

from . import http, local_source
from .const import (
    DATA_LOCAL_SOURCE,
    DATA_MEDIA_SOURCE_PLATFORMS,
    DOMAIN,
    MEDIA_CLASS_MAP,
    MEDIA_MIME_TYPES,
    URI_SCHEME,
    URI_SCHEME_REGEX,
)
from .error import MediaSourceError, Unresolvable
from .helper import async_browse_media, async_resolve_media, async_search_media
from .models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    RootBrowseMediaSource,
)

__all__ = [
    "DOMAIN",
    "MEDIA_CLASS_MAP",
    "MEDIA_MIME_TYPES",
    "BrowseMediaSource",
    "MediaSource",
    "MediaSourceError",
    "MediaSourceItem",
    "PlayMedia",
    "RootBrowseMediaSource",
    "Unresolvable",
    "async_browse_media",
    "async_resolve_media",
    "async_search_media",
    "generate_media_source_id",
    "is_media_source_id",
]


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


class MediaSourceProtocol(Protocol):
    """Define the format of media_source platforms."""

    async def async_get_media_source(self, hass: HomeAssistant) -> MediaSource:
        """Set up media source."""


def is_media_source_id(media_content_id: str) -> bool:
    """Test if identifier is a media source."""
    return URI_SCHEME_REGEX.match(media_content_id) is not None


def generate_media_source_id(domain: str, identifier: str) -> str:
    """Generate a media source ID."""
    uri = f"{URI_SCHEME}{domain}"
    if identifier:
        uri += f"/{identifier}"
    return uri


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the media_source component."""
    hass.data[DATA_MEDIA_SOURCE_PLATFORMS] = LazyIntegrationPlatforms[MediaSource](
        hass, DOMAIN, _process_media_source_platform
    )
    http.async_setup(hass)

    # Local sources support
    hass.data[DATA_LOCAL_SOURCE] = await _process_media_source_platform(
        hass, DOMAIN, local_source
    )
    hass.http.register_view(local_source.UploadMediaView)
    websocket_api.async_register_command(hass, local_source.websocket_remove_media)

    return True


async def _process_media_source_platform(
    hass: HomeAssistant,
    domain: str,
    platform: MediaSourceProtocol,
) -> MediaSource:
    """Process a media source platform."""
    source = await platform.async_get_media_source(hass)
    if isinstance(source, local_source.LocalSource):
        hass.http.register_view(local_source.LocalMediaView(hass, source))
    return source
