"""Const for conversation integration."""

from enum import IntFlag

DOMAIN = "conversation"
DEFAULT_EXPOSED_ATTRIBUTES = {"device_class"}
HOME_ASSISTANT_AGENT = "conversation.home_assistant"
OLD_HOME_ASSISTANT_AGENT = "homeassistant"

ATTR_TEXT = "text"
ATTR_LANGUAGE = "language"
ATTR_AGENT_ID = "agent_id"
ATTR_CONVERSATION_ID = "conversation_id"

SERVICE_PROCESS = "process"
SERVICE_RELOAD = "reload"


class ConversationEntityFeature(IntFlag):
    """Supported features of the conversation entity."""

    CONTROL = 1
