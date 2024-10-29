"""Common fixtures for the Suez Water tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.suez_water import SuezClient
from homeassistant.components.suez_water.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DATA = {
    "username": "test-username",
    "password": "test-password",
    "counter_id": "test-counter",
}


@pytest.fixture(name="config_entry")
def mock_config_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Suez mock device",
        data=MOCK_DATA,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.suez_water.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="suez_client")
def mock_suez_client(hass: HomeAssistant) -> Generator[AsyncMock]:
    """Create mock for suez_water external api."""

    mock = AsyncMock(spec=SuezClient)
    mock.check_credentials.return_value = True
    mock.update.return_value = None
    mock.state = 160
    mock.attributes = {
        "thisMonthConsumption": {
            "2024-01-01": 130,
            "2024-01-02": 145,
        },
        "previousMonthConsumption": {
            "2024-12-01": 154,
            "2024-12-02": 166,
        },
        "highestMonthlyConsumption": 2558,
        "lastYearOverAll": 1000,
        "thisYearOverAll": 1500,
        "history": {
            "2024-01-01": 130,
            "2024-01-02": 145,
            "2024-12-01": 154,
            "2024-12-02": 166,
        },
        "attribution": "suez water mock test",
    }

    with patch(
        "homeassistant.components.suez_water.SuezClient",
        return_value=mock,
    ) as mock_client:
        yield mock_client
