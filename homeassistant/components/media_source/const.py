"""Constants for the media_source integration."""

DOMAIN = "media_source"
MEDIA_MIME_TYPES = ("audio", "video", "image")
URI_SCHEME = "media-source://"
URI_SCHEME_REGEX = r"^media-source://(?P<platform>[^/]+)?(?P<path>.+)?"
