"""Common fixtures for the Model Context Protocol tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.mcp.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_API_NAME = "Memory Server"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.mcp.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_mcp_client() -> Generator[AsyncMock]:
    """Fixture to mock the MCP client."""
    with (
        patch("homeassistant.components.mcp.coordinator.sse_client"),
        patch("homeassistant.components.mcp.coordinator.ClientSession") as mock_session,
    ):
        yield mock_session.return_value.__aenter__


@pytest.fixture(name="config_entry")
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Fixture to load the integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://1.1.1.1/sse"},
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)
    return config_entry
