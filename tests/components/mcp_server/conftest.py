"""Common fixtures for the Model Context Protocol Server tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.mcp_server.const import DOMAIN
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.mcp_server.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Fixture to load the integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry
