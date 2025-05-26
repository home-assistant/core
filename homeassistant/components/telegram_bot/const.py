"""Constants for the Telegram Bot integration."""

from homeassistant.helpers.typing import NoEventData
from homeassistant.util.event_type import EventType

EVENT_TELEGRAMBOT_TERMINATE: EventType[NoEventData] = EventType("telegrambot_terminate")

CONF_BOT_COUNT = "bot_count"

ISSUE_DEPRECATED_YAML = "deprecated_yaml"
ISSUE_DEPRECATED_YAML_HAS_MORE_PLATFORMS = (
    "deprecated_yaml_import_issue_has_more_platforms"
)
