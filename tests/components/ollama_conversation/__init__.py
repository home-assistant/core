"""Tests for the OpenAI Conversation integration."""

from homeassistant.components import ollama_conversation

TEST_USER_DATA = {
    ollama_conversation.CONF_URL: "http://localhost:11434",
    ollama_conversation.CONF_MODEL: "test model",
    ollama_conversation.CONF_PROMPT: "test prompt",
}

TEST_OPTIONS = {
    **TEST_USER_DATA,
    ollama_conversation.CONF_MAX_HISTORY: 2,
}
