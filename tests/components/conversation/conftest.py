"""Conversation test helpers."""

import pytest

from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL

from . import MockAgent

from tests.common import MockConfigEntry


@pytest.fixture
def mock_agent(hass):
    """Mock agent."""
    entry = MockConfigEntry(entry_id="mock-entry")
    entry.add_to_hass(hass)
    agent = MockAgent(entry.entry_id, ["smurfish"])
    conversation.async_set_agent(hass, entry, agent)
    return agent


@pytest.fixture
def mock_agent_support_all(hass):
    """Mock agent that supports all languages."""
    entry = MockConfigEntry(entry_id="mock-entry-support-all")
    entry.add_to_hass(hass)
    agent = MockAgent(entry.entry_id, MATCH_ALL)
    conversation.async_set_agent(hass, entry, agent)
    return agent
