"""Fixtures for the GBFS integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.gbfs.const import (
    CONF_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_STATION,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from . import STATION_SUBENTRY_ID, V3_URL, mock_feed


@pytest.fixture(autouse=True)
def home_location(hass: HomeAssistant) -> None:
    """Put home at the Main St & 1st Ave station."""
    hass.config.latitude = 40.7
    hass.config.longitude = -74.0


@pytest.fixture
def mock_v3_feed(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Serve the v3 fixture system."""
    mock_feed(aioclient_mock, "v3")
    return aioclient_mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip entry setup in flow tests."""
    with patch(
        "homeassistant.components.gbfs.async_setup_entry",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the v3 system with the Main St & 1st Ave station."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Example Bikes",
        unique_id="example_bikes",
        data={CONF_URL: V3_URL},
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_STATION_ID: "s1"},
                subentry_id=STATION_SUBENTRY_ID,
                subentry_type=SUBENTRY_TYPE_STATION,
                title="Main St & 1st Ave",
                unique_id="s1",
            )
        ],
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_v3_feed: AiohttpClientMocker,
) -> MockConfigEntry:
    """Set up the v3 system."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
