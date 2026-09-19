"""Fixtures for the gridX tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from gridx_connector import GridXSystem
import pytest

from homeassistant.components.gridx.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture

USERNAME = "test@example.com"
PASSWORD = "test-password"
SYSTEM_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gridx.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connector() -> Generator[AsyncMock]:
    """Mock the gridx-connector library."""
    with patch(
        "homeassistant.components.gridx.coordinator.AsyncGridboxConnector",
        autospec=True,
    ) as mock_class:
        connector = mock_class.return_value
        connector.systems = {
            SYSTEM_ID: GridXSystem(
                id=SYSTEM_ID,
                name="Home",
                manufacturer="gridX",
                model="gridBox",
                serial_number="GB-1",
            )
        }
        connector.get_live_data.return_value = {
            SYSTEM_ID: load_json_object_fixture("live.json", DOMAIN)
        }
        yield connector


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=USERNAME,
        unique_id=USERNAME,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
