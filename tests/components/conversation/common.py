"""Provide common tests tools for conversation."""

from homeassistant.components import conversation
from homeassistant.core import HomeAssistant

from . import MockAgent

from tests.common import MockConfigEntry


def mock_conversation_agent_fixture_helper(hass: HomeAssistant) -> MockAgent:
    """Mock agent."""
    entry = MockConfigEntry(entry_id="mock-entry")
    entry.add_to_hass(hass)
    agent = MockAgent(entry.entry_id, ["smurfish"])
    conversation.async_set_agent(hass, entry, agent)
    return agent
