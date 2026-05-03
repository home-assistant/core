"""Tests helpers for Open Responses."""

from unittest.mock import patch

import pytest

from homeassistant.components.open_responses.const import (
    CONF_BASE_URL,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        title="Open Responses",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
            CONF_BASE_URL: "https://example.local/v1",
        },
        version=2,
        minor_version=7,
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
            ConfigSubentryData(
                data=RECOMMENDED_AI_TASK_OPTIONS,
                subentry_type="ai_task_data",
                title=DEFAULT_AI_TASK_NAME,
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_init_component(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Initialize integration."""
    with patch("openai.resources.models.AsyncModels.list"):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})
