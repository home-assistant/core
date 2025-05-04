"""Constants for pushover."""

from typing import Final

DOMAIN: Final = "pushover"
DATA_HASS_CONFIG: Final = "pushover_hass_config"
DEFAULT_NAME: Final = "Pushover"

ATTR_ATTACHMENT: Final = "attachment"
ATTR_URL: Final = "url"
ATTR_URL_TITLE: Final = "url_title"
ATTR_PRIORITY: Final = "priority"
ATTR_RETRY: Final = "retry"
ATTR_SOUND: Final = "sound"
ATTR_HTML: Final = "html"
ATTR_CALLBACK_URL: Final = "callback_url"
ATTR_EXPIRE: Final = "expire"
ATTR_TTL: Final = "ttl"
ATTR_DATA: Final = "data"
ATTR_TIMESTAMP: Final = "timestamp"
ATTR_TAGS: Final = "tags"

CLEAR_NOTIFICATIONS_BY_TAGS: Final = "clear_notifications_by_tags"

CONF_USER_KEY: Final = "user_key"
