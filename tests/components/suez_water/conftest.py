"""Common fixtures for the Suez Water tests."""

from collections.abc import Generator
from datetime import date
from unittest.mock import AsyncMock, patch

from pysuez import AggregatedData, PriceResult
from pysuez.const import ATTRIBUTION
import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.suez_water.const import CONF_COUNTER_ID, DOMAIN

from tests.common import MockConfigEntry
from tests.conftest import RecorderInstanceContextManager

MOCK_DATA = {
    "username": "test-username",
    "password": "test-password",
    CONF_COUNTER_ID: "123456",
}


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create mock config_entry needed by suez_water integration."""
    return MockConfigEntry(
        unique_id=MOCK_DATA[CONF_COUNTER_ID],
        domain=DOMAIN,
        title="Suez mock device",
        data=MOCK_DATA,
        version=2,
    )


@pytest.fixture
def mock_setup_entry(recorder_mock: Recorder) -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.suez_water.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="suez_client")
def mock_suez_client(recorder_mock: Recorder) -> Generator[AsyncMock]:
    """Create mock for suez_water external api."""
    with (
        patch(
            "homeassistant.components.suez_water.coordinator.SuezClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.suez_water.config_flow.SuezClient",
            new=mock_client,
        ),
    ):
        suez_client = mock_client.return_value
        suez_client.check_credentials.return_value = True

        result = AggregatedData(
            value=160,
            current_month={
                date.fromisoformat("2024-01-01"): 130,
                date.fromisoformat("2024-01-02"): 145,
            },
            previous_month={
                date.fromisoformat("2024-12-01"): 154,
                date.fromisoformat("2024-12-02"): 166,
            },
            current_year=1500,
            previous_year=1000,
            attribution=ATTRIBUTION,
            highest_monthly_consumption=2558,
            history={
                date.fromisoformat("2024-01-01"): 130,
                date.fromisoformat("2024-01-02"): 145,
                date.fromisoformat("2024-12-01"): 154,
                date.fromisoformat("2024-12-02"): 166,
            },
        )

        suez_client.fetch_aggregated_data.return_value = result
        suez_client.get_price.return_value = PriceResult(
            "OK", {"price": 4.74}, "Price is 4.74"
        )
        yield suez_client
