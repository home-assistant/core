"""Conversation test helpers."""

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.conversation import async_get_agent, default_agent
from homeassistant.components.shopping_list import intent as sl_intent
from homeassistant.const import MATCH_ALL
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component

from . import MockAgent

from tests.common import MockConfigEntry


@pytest.fixture
def mock_ulid() -> Generator[Mock]:
    """Mock the ulid library."""
    with patch("homeassistant.helpers.chat_session.ulid_now") as mock_ulid_now:
        mock_ulid_now.return_value = "mock-ulid"
        yield mock_ulid_now


@pytest.fixture
def mock_agent_support_all(hass: HomeAssistant) -> MockAgent:
    """Mock agent that supports all languages."""
    entry = MockConfigEntry(entry_id="mock-entry-support-all")
    entry.add_to_hass(hass)
    agent = MockAgent(entry.entry_id, MATCH_ALL)
    conversation.async_set_agent(hass, entry, agent)
    return agent


@pytest.fixture
def mock_conversation_input(hass: HomeAssistant) -> conversation.ConversationInput:
    """Return a conversation input instance."""
    return conversation.ConversationInput(
        text="Hello",
        context=Context(),
        conversation_id=None,
        agent_id="mock-agent-id",
        device_id=None,
        satellite_id=None,
        language="en",
    )


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
    assert await async_setup_component(hass, "conversation", {conversation.DOMAIN: {}})

    # Disable fuzzy matching by default for tests
    agent = async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)
    agent.fuzzy_matching = False
