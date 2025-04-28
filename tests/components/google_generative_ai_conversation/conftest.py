"""Tests helpers."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.google_generative_ai_conversation.conversation import (
    CONF_USE_GOOGLE_SEARCH_TOOL,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="google_generative_ai_conversation",
        title="Google Generative AI Conversation",
        data={
            "api_key": "bla",
        },
    )
    entry.runtime_data = Mock()
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_config_entry_with_assist(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Mock a config entry with assist."""
    with patch("google.genai.models.AsyncModels.get"):
        hass.config_entries.async_update_entry(
            mock_config_entry, options={CONF_LLM_HASS_API: llm.LLM_API_ASSIST}
        )
        await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
async def mock_config_entry_with_google_search(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Mock a config entry with assist."""
    with patch("google.genai.models.AsyncModels.get"):
        hass.config_entries.async_update_entry(
            mock_config_entry,
            options={
                CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
                CONF_USE_GOOGLE_SEARCH_TOOL: True,
            },
        )
        await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
async def mock_init_component(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Initialize integration."""
    with patch("google.genai.models.AsyncModels.get"):
        assert await async_setup_component(
            hass, "google_generative_ai_conversation", {}
        )
        await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})
