"""Fixtures for the Opower integration tests."""

from collections.abc import Generator
from datetime import date
from unittest.mock import AsyncMock, Mock, patch

from opower import Account, Forecast, MeterType, ReadResolution, UnitOfMeasure
from opower.utilities.pge import PGE
import pytest

from homeassistant.components.opower.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        title="Pacific Gas & Electric (test-username)",
        domain=DOMAIN,
        data={
            "utility": "Pacific Gas and Electric Company (PG&E)",
            "username": "test-username",
            "password": "test-password",
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_opower_api() -> Generator[AsyncMock]:
    """Mock Opower API."""
    with patch(
        "homeassistant.components.opower.coordinator.Opower", autospec=True
    ) as mock_api:
        api = mock_api.return_value
        api.utility = PGE

        api.async_get_accounts.return_value = [
            Account(
                customer=Mock(),
                uuid="111111-uuid",
                utility_account_id="111111",
                id="111111",
                meter_type=MeterType.ELEC,
                read_resolution=ReadResolution.HOUR,
            ),
            Account(
                customer=Mock(),
                uuid="222222-uuid",
                utility_account_id="222222",
                id="222222",
                meter_type=MeterType.GAS,
                read_resolution=ReadResolution.DAY,
            ),
        ]
        api.async_get_forecast.return_value = [
            Forecast(
                account=Account(
                    customer=Mock(),
                    uuid="111111-uuid",
                    utility_account_id="111111",
                    id="111111",
                    meter_type=MeterType.ELEC,
                    read_resolution=ReadResolution.HOUR,
                ),
                usage_to_date=100,
                cost_to_date=20.0,
                forecasted_usage=200,
                forecasted_cost=40.0,
                typical_usage=180,
                typical_cost=36.0,
                unit_of_measure=UnitOfMeasure.KWH,
                start_date=date(2023, 1, 1),
                end_date=date(2023, 1, 31),
                current_date=date(2023, 1, 15),
            ),
            Forecast(
                account=Account(
                    customer=Mock(),
                    uuid="222222-uuid",
                    utility_account_id="222222",
                    id="222222",
                    meter_type=MeterType.GAS,
                    read_resolution=ReadResolution.DAY,
                ),
                usage_to_date=50,
                cost_to_date=15.0,
                forecasted_usage=100,
                forecasted_cost=30.0,
                typical_usage=90,
                typical_cost=27.0,
                unit_of_measure=UnitOfMeasure.CCF,
                start_date=date(2023, 1, 1),
                end_date=date(2023, 1, 31),
                current_date=date(2023, 1, 15),
            ),
        ]
        api.async_get_cost_reads.return_value = []
        yield api
