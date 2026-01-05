"""Constants for the ntfy integration."""

from typing import Final

DOMAIN = "ntfy"
DEFAULT_URL: Final = "https://ntfy.sh"

CONF_TOPIC = "topic"
CONF_PRIORITY = "filter_priority"
CONF_TITLE = "filter_title"
CONF_MESSAGE = "filter_message"
CONF_TAGS = "filter_tags"
SECTION_AUTH = "auth"
SECTION_FILTER = "filter"
NTFY_EVENT = "ntfy_event"
