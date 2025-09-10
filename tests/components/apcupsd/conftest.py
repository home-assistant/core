"""Common fixtures for the APC UPS Daemon (APCUPSD) tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.apcupsd import PLATFORMS
from homeassistant.components.apcupsd.const import DOMAIN
from homeassistant.components.apcupsd.coordinator import APCUPSdData
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import CONF_DATA, MOCK_STATUS

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.apcupsd.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def mock_request_status(
    request: pytest.FixtureRequest,
) -> AsyncGenerator[AsyncMock]:
    """Return a mocked aioapcaccess.request_status function."""
    mocked_status = getattr(request, "param", None) or MOCK_STATUS

    with patch("aioapcaccess.request_status") as mock_request_status:
        mock_request_status.return_value = mocked_status
        yield mock_request_status


@pytest.fixture
def mock_config_entry(
    request: pytest.FixtureRequest,
    mock_request_status: AsyncMock,
) -> MockConfigEntry:
    """Mock setting up a config entry."""
    entry_id = getattr(request, "param", None)

    return MockConfigEntry(
        entry_id=entry_id,
        version=1,
        domain=DOMAIN,
        title="APC UPS Daemon",
        data=CONF_DATA,
        unique_id=APCUPSdData(mock_request_status.return_value).serial_no,
        source=SOURCE_USER,
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return PLATFORMS


@pytest.fixture
async def init_integration(
    request: pytest.FixtureRequest,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_request_status: AsyncMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up APC UPS Daemon integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.apcupsd.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
