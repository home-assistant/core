"""Constants for the media_source integration."""

import re

from homeassistant.components.media_player import MediaClass

DOMAIN = "media_source"
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
