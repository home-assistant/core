"""Constants for the media_source integration."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from homeassistant.components.media_player import MediaClass
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .models import MediaSource

DOMAIN = "media_source"
MEDIA_SOURCE_DATA: HassKey[dict[str, MediaSource]] = HassKey(DOMAIN)
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
