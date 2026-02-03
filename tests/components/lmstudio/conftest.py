"""Fixtures for LM Studio integration tests."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import lmstudio
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import TEST_AI_TASK_OPTIONS, TEST_OPTIONS, TEST_USER_DATA

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
        domain=lmstudio.DOMAIN,
        data=TEST_USER_DATA,
        subentries_data=[
            {
                "data": {**TEST_OPTIONS, **mock_config_entry_options},
                "subentry_type": "conversation",
                "title": "LM Studio Conversation",
                "unique_id": None,
            },
            {
                "data": TEST_AI_TASK_OPTIONS,
                "subentry_type": "ai_task_data",
                "title": "LM Studio AI Task",
                "unique_id": None,
            },
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_init_component(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    """Initialize integration."""
    with patch(
        "homeassistant.components.lmstudio.client.LMStudioClient.async_list_models",
        return_value=[],
    ):
        assert await async_setup_component(hass, lmstudio.DOMAIN, {})
        await hass.async_block_till_done()
        yield


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})
