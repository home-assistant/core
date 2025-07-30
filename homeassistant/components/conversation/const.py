"""Const for conversation integration."""

from __future__ import annotations

from enum import IntFlag
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import ConversationEntity

DOMAIN = "conversation"
HOME_ASSISTANT_AGENT = "conversation.home_assistant"

ATTR_TEXT = "text"
ATTR_LANGUAGE = "language"
ATTR_AGENT_ID = "agent_id"
ATTR_CONVERSATION_ID = "conversation_id"

SERVICE_PROCESS = "process"
SERVICE_RELOAD = "reload"

DATA_COMPONENT: HassKey[EntityComponent[ConversationEntity]] = HassKey(DOMAIN)


class ConversationEntityFeature(IntFlag):
    """Supported features of the conversation entity."""

    CONTROL = 1
