"""Tests helpers."""

from unittest.mock import patch

import pytest

from homeassistant.components.openai_conversation.const import DEFAULT_CONVERSATION_NAME
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        title="OpenAI",
        domain="openai_conversation",
        data={
            "api_key": "bla",
        },
        version=2,
        subentries_data=[
            {
                "data": {},
                "subentry_type": "conversation",
                "title": DEFAULT_CONVERSATION_NAME,
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_config_entry_with_assist(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Mock a config entry with assist."""
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={CONF_LLM_HASS_API: llm.LLM_API_ASSIST},
    )
    return mock_config_entry


@pytest.fixture
async def mock_init_component(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Initialize integration."""
    with patch(
        "openai.resources.models.AsyncModels.list",
    ):
        assert await async_setup_component(hass, "openai_conversation", {})
        await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})
