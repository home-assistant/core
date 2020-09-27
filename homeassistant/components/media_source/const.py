"""Constants for the media_source integration."""
import re

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_IMAGE,
    MEDIA_CLASS_MUSIC,
    MEDIA_CLASS_VIDEO,
)

DOMAIN = "media_source"
MEDIA_MIME_TYPES = ("audio", "video", "image")
MEDIA_CLASS_MAP = {
    "audio": MEDIA_CLASS_MUSIC,
    "video": MEDIA_CLASS_VIDEO,
    "image": MEDIA_CLASS_IMAGE,
}
URI_SCHEME = "media-source://"
URI_SCHEME_REGEX = re.compile(
    r"^media-source:\/\/(?:(?P<domain>(?!.+__)(?!_)[\da-z_]+(?<!_))(?:\/(?P<identifier>(?!\/).+))?)?$"
)
