"""Tests for the OpenAI Conversation integration."""

from homeassistant.components import ollama_conversation
from homeassistant.components.ollama_conversation.const import DEFAULT_PROMPT

TEST_USER_DATA = {
    ollama_conversation.CONF_URL: "http://localhost:11434",
    ollama_conversation.CONF_MODEL: "test model",
    ollama_conversation.CONF_PROMPT: DEFAULT_PROMPT,
}

TEST_OPTIONS = {
    **TEST_USER_DATA,
    ollama_conversation.CONF_MAX_HISTORY: 2,
}
