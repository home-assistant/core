"""Common fixtures for the Gaposa tests."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.gaposa import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_test_home_assistant


@pytest.fixture
async def hass():
    """Return a HomeAssistant instance."""
    async with async_test_home_assistant(asyncio.get_running_loop()) as hass:
        yield hass


@pytest.fixture(autouse=True)
async def verify_cleanup(hass: HomeAssistant) -> None:
    """Verify that the test has cleaned up resources correctly."""

    yield

    await hass.async_stop()


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gaposa.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "test-apikey",
            "username": "test-username",
            "password": "test-password",
        },
        title="Gaposa Gateway",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> MockConfigEntry:
    """Set up the Gaposa integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gaposa.coordinator.Gaposa",
        autospec=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
