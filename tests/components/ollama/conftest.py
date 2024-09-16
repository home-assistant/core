"""Tests Ollama integration."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import ollama
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from . import TEST_OPTIONS, TEST_USER_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry_options() -> dict[str, Any]:
    """Fixture for configuration entry options."""
    return TEST_OPTIONS


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_config_entry_options: dict[str, Any]
) -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain=ollama.DOMAIN,
        data=TEST_USER_DATA,
        options=mock_config_entry_options,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_config_entry_with_assist(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Mock a config entry with assist."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_LLM_HASS_API: llm.LLM_API_ASSIST}
    )
    return mock_config_entry


@pytest.fixture
async def mock_init_component(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    """Initialize integration."""
    assert await async_setup_component(hass, "homeassistant", {})

    with patch(
        "ollama.AsyncClient.list",
    ):
        assert await async_setup_component(hass, ollama.DOMAIN, {})
        await hass.async_block_till_done()
        yield


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})
