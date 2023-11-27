"""Tests helpers."""
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass):
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain="openai_conversation",
        data={
            "api_key": "bla",
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_init_component(hass, mock_config_entry):
    """Initialize integration."""
    with patch(
        "openai.Model.list",
    ):
        assert await async_setup_component(hass, "openai_conversation", {})
        await hass.async_block_till_done()
