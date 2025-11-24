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


METADATA_CUSTOM_SENTENCE = "hass_custom_sentence"
METADATA_CUSTOM_FILE = "hass_custom_file"
SENTENCE_TRIGGER_INTENT_NAME = "HassSentenceTrigger"
CUSTOM_SENTENCES_DIR_NAME = "custom_sentences"


class IntentSource(IntFlag):
    """Source of intents and sentence templates."""

    SENTENCE_TRIGGERS = 1
    """Sentence triggers in automations."""

    CONVERSATION_CONFIG = 2
    """YAML configuration for conversation component."""

    CUSTOM_SENTENCES = 4
    """YAML files in config/custom_sentences."""

    BUILTIN_SENTENCES = 8
    """Sentences from home-assistant-intents package."""

    ALL = SENTENCE_TRIGGERS | CONVERSATION_CONFIG | CUSTOM_SENTENCES | BUILTIN_SENTENCES
