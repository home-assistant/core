"""Conversation test helpers."""

import pytest

from homeassistant.components import conversation

from . import MockAgent


@pytest.fixture
def mock_agent(hass):
    """Mock agent."""
    agent = MockAgent()
    conversation.async_set_agent(hass, None, agent)
    return agent
