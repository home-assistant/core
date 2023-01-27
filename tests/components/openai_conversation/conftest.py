"""Tests helpers."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.openai_conversation.const import DOMAIN
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
        "openai.Engine.list",
    ):
        assert await async_setup_component(
            hass,
            "openai_conversation",
            {
                "api_key": "bla",
            },
        )
        await hass.async_block_till_done()


@pytest.fixture
async def setup_complete(hass) -> None:
    """Completed setup via form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.openai_conversation.config_flow.openai.Engine.list",
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "bla",
            },
        )
        await hass.async_block_till_done()
