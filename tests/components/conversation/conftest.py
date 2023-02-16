"""Conversation test helpers."""

import pytest

from homeassistant.components import conversation

from . import MockAgent

from tests.common import MockConfigEntry


@pytest.fixture
def mock_agent(hass):
    """Mock agent."""
    entry = MockConfigEntry(entry_id="mock-entry")
    entry.add_to_hass(hass)
    agent = MockAgent(entry.entry_id)
    conversation.async_set_agent(hass, entry, agent)
    return agent
