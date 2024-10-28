"""Constants for the Mastodon integration."""

import logging
from typing import Final

LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "mastodon"

CONF_BASE_URL: Final = "base_url"
DATA_HASS_CONFIG = "mastodon_hass_config"
DEFAULT_URL: Final = "https://mastodon.social"
DEFAULT_NAME: Final = "Mastodon"

INSTANCE_VERSION: Final = "version"
INSTANCE_URI: Final = "uri"
INSTANCE_DOMAIN: Final = "domain"
ACCOUNT_USERNAME: Final = "username"
ACCOUNT_FOLLOWERS_COUNT: Final = "followers_count"
ACCOUNT_FOLLOWING_COUNT: Final = "following_count"
ACCOUNT_STATUSES_COUNT: Final = "statuses_count"
