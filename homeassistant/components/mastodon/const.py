"""Constants for the Mastodon integration."""

import logging
from typing import Final

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "mastodon"

CONF_BASE_URL: Final = "base_url"
DATA_HASS_CONFIG = "mastodon_hass_config"
DEFAULT_URL: Final = "https://mastodon.social"
DEFAULT_NAME: Final = "Mastodon"

ATTR_MEDIA_SOURCE = "media_source"
ATTR_MEDIA_DESCRIPTION = "media_description"
ATTR_FOCUS_X = "focus_x"
ATTR_FOCUS_Y = "focus_y"
ATTR_THUMBNAIL = "thumbnail"

ATTR_AVATAR_MIME_TYPE = "avatar_mime_type"
ATTR_HEADER_MIME_TYPE = "header_mime_type"
ATTR_VALUE = "value"
