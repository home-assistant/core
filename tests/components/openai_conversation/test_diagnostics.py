"""Test OpenAI Conversation diagnostics."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.openai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_REASONING_EFFORT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
)
from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm


@pytest.fixture
def mock_conversation_subentry_data() -> dict[str, Any]:
    """Mock conversation subentry data with advanced options."""
    return {
        CONF_RECOMMENDED: False,
        CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
        CONF_PROMPT: "You are a private assistant.",
        CONF_CHAT_MODEL: "gpt-5-mini",
        CONF_MAX_TOKENS: 1500,
        CONF_TEMPERATURE: 0.7,
        CONF_REASONING_EFFORT: "medium",
        CONF_WEB_SEARCH: True,
        CONF_WEB_SEARCH_CONTEXT_SIZE: "high",
        CONF_WEB_SEARCH_USER_LOCATION: True,
        CONF_WEB_SEARCH_CITY: "Amsterdam",
        CONF_WEB_SEARCH_REGION: "North Holland",
        CONF_WEB_SEARCH_COUNTRY: "NL",
        CONF_WEB_SEARCH_TIMEZONE: "Europe/Amsterdam",
    }


@pytest.mark.usefixtures("mock_init_component")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert diagnostics.pop("client").startswith("openai==")
    assert diagnostics == snapshot
