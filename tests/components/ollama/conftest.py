"""Tests Ollama integration."""

from unittest.mock import patch

import pytest

from homeassistant.components import ollama
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import TEST_OPTIONS, TEST_USER_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain=ollama.DOMAIN,
        data=TEST_USER_DATA,
        options=TEST_OPTIONS,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_init_component(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    """Initialize integration."""
    assert await async_setup_component(hass, "homeassistant", {})

    with patch(
        "ollama.AsyncClient.list",
    ):
        assert await async_setup_component(hass, ollama.DOMAIN, {})
        await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})
