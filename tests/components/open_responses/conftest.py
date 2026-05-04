"""Tests helpers for Open Responses."""

import pytest

from homeassistant.components.open_responses.const import (
    CONF_BASE_URL,
    CONF_GENERATED_DEFAULT_SUBENTRY,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CONVERSATION_OPTIONS,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_MODEL
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
            CONF_MODEL: "open-responses-model",
        },
        version=1,
        subentries_data=[
            ConfigSubentryData(
                data={
                    **RECOMMENDED_CONVERSATION_OPTIONS,
                    CONF_GENERATED_DEFAULT_SUBENTRY: True,
                    CONF_MODEL: "open-responses-model",
                },
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    **RECOMMENDED_AI_TASK_OPTIONS,
                    CONF_GENERATED_DEFAULT_SUBENTRY: True,
                    CONF_MODEL: "open-responses-model",
                },
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
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})
