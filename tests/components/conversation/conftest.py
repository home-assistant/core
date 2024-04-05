"""Conversation test helpers."""

from unittest.mock import patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.shopping_list import intent as sl_intent
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MockAgent

from tests.common import MockConfigEntry


@pytest.fixture
def mock_agent_support_all(hass: HomeAssistant):
    """Mock agent that supports all languages."""
    entry = MockConfigEntry(entry_id="mock-entry-support-all")
    entry.add_to_hass(hass)
    agent = MockAgent(entry.entry_id, MATCH_ALL)
    conversation.async_set_agent(hass, entry, agent)
    return agent


@pytest.fixture(autouse=True)
def mock_shopping_list_io():
    """Stub out the persistence."""
    with (
        patch("homeassistant.components.shopping_list.ShoppingData.save"),
        patch("homeassistant.components.shopping_list.ShoppingData.async_load"),
    ):
        yield


@pytest.fixture
async def sl_setup(hass: HomeAssistant):
    """Set up the shopping list."""

    entry = MockConfigEntry(domain="shopping_list")
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    await sl_intent.async_setup_intents(hass)


@pytest.fixture
async def init_components(hass: HomeAssistant):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
