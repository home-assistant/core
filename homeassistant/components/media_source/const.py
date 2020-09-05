"""Constants for the media_source integration."""
import re

DOMAIN = "media_source"
MEDIA_MIME_TYPES = ("audio", "video", "image")
URI_SCHEME = "media-source://"
URI_SCHEME_REGEX = re.compile(r"^media-source://(?P<domain>[^/]+)?(?P<identifier>.+)?")
