"""Tests for the Ollama integration."""

from homeassistant.components import ollama
from homeassistant.helpers import llm

TEST_USER_DATA = {
    ollama.CONF_URL: "http://localhost:11434",
}

TEST_OPTIONS = {
    ollama.CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
    ollama.CONF_MAX_HISTORY: 2,
    ollama.CONF_MODEL: "test_model:latest",
}

TEST_AI_TASK_OPTIONS = {
    ollama.CONF_MAX_HISTORY: 2,
    ollama.CONF_MODEL: "test_model:latest",
}
