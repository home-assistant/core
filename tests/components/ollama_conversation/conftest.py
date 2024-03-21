"""Tests helpers."""

from unittest.mock import patch

import pytest

from homeassistant.components import ollama_conversation
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain=ollama_conversation.DOMAIN,
        data={
            ollama_conversation.CONF_URL: "http://localhost:11434",
            ollama_conversation.CONF_MODEL: "test model",
            ollama_conversation.CONF_PROMPT: "test prompt",
            ollama_conversation.CONF_MAX_HISTORY: 2,
            ollama_conversation.CONF_MODEL_OPTIONS: {
                "test option": "test value",
            },
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_init_component(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    """Initialize integration."""
    with patch(
        "ollama.AsyncClient.list",
    ):
        assert await async_setup_component(hass, ollama_conversation.DOMAIN, {})
        await hass.async_block_till_done()
