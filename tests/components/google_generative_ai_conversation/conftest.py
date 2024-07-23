"""Tests helpers."""

from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass):
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="google_generative_ai_conversation",
        data={
            "api_key": "bla",
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_init_component(hass: HomeAssistant, mock_config_entry: ConfigEntry):
    """Initialize integration."""
    with patch("google.generativeai.get_model"):
        assert await async_setup_component(
            hass, "google_generative_ai_conversation", {}
        )
        await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})
