"""Constants for the Mastodon integration."""

import logging
from typing import Final

LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "mastodon"

CONF_BASE_URL: Final = "base_url"
DATA_HASS_CONFIG = "mastodon_hass_config"
DEFAULT_URL: Final = "https://mastodon.social"
DEFAULT_NAME: Final = "Mastodon"

ATTR_ACCOUNT_NAME = "account_name"
ATTR_STATUS = "status"
ATTR_VISIBILITY = "visibility"
ATTR_IDEMPOTENCY_KEY = "idempotency_key"
ATTR_CONTENT_WARNING = "content_warning"
ATTR_MEDIA_WARNING = "media_warning"
ATTR_MEDIA = "media"
ATTR_MEDIA_DESCRIPTION = "media_description"
ATTR_LANGUAGE = "language"
ATTR_DURATION = "duration"
ATTR_HIDE_NOTIFICATIONS = "hide_notifications"

ATTR_DISPLAY_NAME = "display_name"
ATTR_NOTE = "note"
ATTR_AVATAR = "avatar"
ATTR_AVATAR_MIME_TYPE = "avatar_mime_type"
ATTR_HEADER = "header"
ATTR_HEADER_MIME_TYPE = "header_mime_type"
ATTR_LOCKED = "locked"
ATTR_BOT = "bot"
ATTR_DISCOVERABLE = "discoverable"
ATTR_FIELDS = "fields"
ATTR_ATTRIBUTION_DOMAINS = "attribution_domains"
ATTR_VALUE = "value"
