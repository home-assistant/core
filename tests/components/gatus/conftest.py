"""Common fixtures for the Gatus tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.gatus.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gatus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_gatus_client() -> Generator[AsyncMock]:
    """Mock the third-party Gatus API client wrapper."""
    with patch(
        "homeassistant.components.gatus.coordinator.GatusClient", autospec=True
    ) as mock_client:
        client_instance = mock_client.return_value
        client_instance.get_endpoints_statuses = AsyncMock(return_value=[])
        yield client_instance


@pytest.fixture
def load_gatus_fixture():
    """Load JSON files from the fixtures directory directly."""

    def _load(filename: str) -> list:
        return json.loads(load_fixture(f"gatus/{filename}"))

    return _load


@pytest.fixture
async def setup_integration(hass: HomeAssistant, mock_gatus_client: AsyncMock):
    """Fixture to handle repetitive config entry setup sequences."""

    async def _setup(mock_data: list) -> MockConfigEntry:
        mock_gatus_client.get_endpoints_statuses.return_value = mock_data

        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={"url": "http://gatus.local"},
            entry_id="gatus_mock_entry_id",
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return config_entry

    return _setup
