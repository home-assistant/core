"""Common fixtures for the Starlink tests."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.starlink.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from . import (
    HISTORY_STATS_FIXTURE,
    LOCATION_DATA_FIXTURE,
    SLEEP_DATA_FIXTURE,
    STATUS_DATA_FIXTURE,
    setup_integration,
)

HISTORY_STATS_TARGET = "homeassistant.components.starlink.coordinator.history_stats"
LOCATION_DATA_TARGET = "homeassistant.components.starlink.coordinator.location_data"
SLEEP_DATA_TARGET = "homeassistant.components.starlink.coordinator.get_sleep_config"
STATUS_DATA_TARGET = "homeassistant.components.starlink.coordinator.status_data"
GET_ID_TARGET = "homeassistant.components.starlink.config_flow.get_id"
SETUP_ENTRY_TARGET = "homeassistant.components.starlink.async_setup_entry"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )


@pytest.fixture
def mock_get_id() -> Generator[MagicMock]:
    """Mock the dish ID lookup used by the config flow."""
    with patch(GET_ID_TARGET) as mock_get_id:
        yield mock_get_id


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(SETUP_ENTRY_TARGET, return_value=None) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def status_data(request: pytest.FixtureRequest) -> JsonArrayType:
    """Return the status data reported by the dish."""
    return deepcopy(getattr(request, "param", STATUS_DATA_FIXTURE))


@pytest.fixture
def sleep_config(request: pytest.FixtureRequest) -> JsonArrayType:
    """Return the sleep configuration reported by the dish."""
    return deepcopy(getattr(request, "param", SLEEP_DATA_FIXTURE))


@pytest.fixture(autouse=True)
def mock_sleep_config(sleep_config: JsonArrayType) -> Generator[MagicMock]:
    """Mock the sleep configuration lookup."""
    with patch(SLEEP_DATA_TARGET, return_value=sleep_config) as mock_sleep_config:
        yield mock_sleep_config


@pytest.fixture(autouse=True)
def mock_starlink(status_data: JsonArrayType) -> Generator[None]:
    """Mock the Starlink library calls."""
    with (
        patch(LOCATION_DATA_TARGET, return_value=LOCATION_DATA_FIXTURE),
        patch(HISTORY_STATS_TARGET, return_value=HISTORY_STATS_FIXTURE),
        patch(STATUS_DATA_TARGET, return_value=status_data),
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Starlink integration for testing."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry
