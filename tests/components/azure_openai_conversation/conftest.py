"""Tests helpers."""

from unittest.mock import patch

import pytest

from homeassistant.components.azure_openai_conversation.const import (
    CONF_AZURE_OPENAI_RESOURCE,
    DOMAIN,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from . import USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass):
    """Mock a config entry."""
    entry = MockConfigEntry(
        title="OpenAI",
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id=USER_INPUT[CONF_AZURE_OPENAI_RESOURCE],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_config_entry_with_assist(hass, mock_config_entry):
    """Mock a config entry with assist."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_LLM_HASS_API: llm.LLM_API_ASSIST}
    )
    return mock_config_entry


@pytest.fixture
async def mock_init_component(hass, mock_config_entry):
    """Initialize integration."""
    with patch(
        "openai.resources.models.AsyncModels.list",
    ):
        assert await async_setup_component(hass, "azure_openai_conversation", {})
        await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})
