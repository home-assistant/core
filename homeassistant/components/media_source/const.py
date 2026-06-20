"""Constants for the media_source integration."""

import re
from typing import TYPE_CHECKING

from homeassistant.components.media_player import MediaClass
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.integration_platform import LazyIntegrationPlatforms

    from .models import MediaSource

DOMAIN = "media_source"
# Eagerly loaded built-in sources (currently only the local source).
MEDIA_SOURCE_DATA: HassKey[dict[str, MediaSource]] = HassKey(DOMAIN)
# Lazily loaded media sources provided by other integrations.
DATA_MEDIA_SOURCE_PLATFORMS: HassKey[LazyIntegrationPlatforms[MediaSource]] = HassKey(
    "media_source_platforms"
)
MEDIA_MIME_TYPES = ("audio", "video", "image")
MEDIA_CLASS_MAP = {
    "audio": MediaClass.MUSIC,
    "video": MediaClass.VIDEO,
    "image": MediaClass.IMAGE,
}
URI_SCHEME = "media-source://"
URI_SCHEME_REGEX = re.compile(
    r"^media-source:\/\/(?:(?P<domain>(?!_)[\da-z_]+(?<!_))(?:\/(?P<identifier>(?!\/).+))?)?$"
)
