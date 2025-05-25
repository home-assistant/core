"""Constants for the Telegram Bot integration."""

from homeassistant.helpers.typing import NoEventData
from homeassistant.util.event_type import EventType

EVENT_TELEGRAMBOT_TERMINATE: EventType[NoEventData] = EventType("telegrambot_terminate")
