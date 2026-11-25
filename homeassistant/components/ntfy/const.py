"""Constants for the ntfy integration."""

from enum import StrEnum
from typing import Final

DOMAIN = "ntfy"
DEFAULT_URL: Final = "https://ntfy.sh/"

CONF_TOPIC = "topic"
CONF_PRIORITY = "filter_priority"
CONF_TITLE = "filter_title"
CONF_MESSAGE = "filter_message"
CONF_TAGS = "filter_tags"
SECTION_AUTH = "auth"
SECTION_FILTER = "filter"
NTFY_EVENT = "ntfy_event"

SUBENTRY_TYPE_TOPIC = "topic"


class NtfyService(StrEnum):
    """Store keys for ntfy services."""

    PUBLISH = "publish"
    CLEAR = "clear"
    DELETE = "delete"


class NtfyServiceArgument(StrEnum):
    """Store keys for ntfy service arguments."""

    TITLE = "title"
    MESSAGE = "message"
    MARKDOWN = "markdown"
    TAGS = "tags"
    PRIORITY = "priority"
    CLICK = "click"
    DELAY = "delay"
    ATTACH = "attach"
    ATTACH_FILE = "attach_file"
    FILENAME = "filename"
    EMAIL = "email"
    CALL = "call"
    ICON = "icon"
    ACTIONS = "actions"
    SEQUENCE_ID = "sequence_id"
