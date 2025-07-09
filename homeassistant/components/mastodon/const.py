"""Constants for the Mastodon integration."""

import logging
from typing import Final

LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "mastodon"

CONF_BASE_URL: Final = "base_url"
DATA_HASS_CONFIG = "mastodon_hass_config"
DEFAULT_URL: Final = "https://mastodon.social"
DEFAULT_NAME: Final = "Mastodon"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_STATUS = "status"
ATTR_VISIBILITY = "visibility"
ATTR_CONTENT_WARNING = "content_warning"
ATTR_MEDIA_WARNING = "media_warning"
ATTR_MEDIA = "media"
ATTR_MEDIA_DESCRIPTION = "media_description"
