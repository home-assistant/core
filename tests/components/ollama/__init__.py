"""Tests for the Ollama integration."""

from homeassistant.components import ollama
from homeassistant.components.ollama.const import DEFAULT_PROMPT

TEST_USER_DATA = {
    ollama.CONF_URL: "http://localhost:11434",
    ollama.CONF_MODEL: "test model",
}

TEST_OPTIONS = {
    ollama.CONF_PROMPT: DEFAULT_PROMPT,
    ollama.CONF_MAX_HISTORY: 2,
}
