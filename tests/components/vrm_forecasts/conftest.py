"""Common fixtures for the Victron VRM Forecasts tests."""

from collections.abc import Generator
import datetime
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.vrm_forecasts.const import (
    CONF_API_KEY,
    CONF_SITE_ID,
    DOMAIN,
)
from homeassistant.components.vrm_forecasts.coordinator import (
    ForecastEstimates,
    VRMForecastStore,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONST_1_HOUR = 3600000
CONST_12_HOURS = 43200000
CONST_24_HOURS = 86400000
CONST_FORECAST_START = 1745359200000
CONST_FORECAST_END = CONST_FORECAST_START + (CONST_24_HOURS * 2) + (CONST_1_HOUR * 13)
CONST_FORECAST_RECORDS = [
    # Yesterday
    [CONST_FORECAST_START + CONST_12_HOURS, 5050.1],
    [CONST_FORECAST_START + (CONST_12_HOURS + CONST_1_HOUR), 5000.2],
    # Today
    [CONST_FORECAST_START + (CONST_24_HOURS + CONST_12_HOURS), 2250.3],
    [CONST_FORECAST_START + CONST_24_HOURS + (CONST_1_HOUR * 13), 2000.4],
    # Tomorrow
    [CONST_FORECAST_START + (CONST_24_HOURS * 2) + CONST_12_HOURS, 1000.5],
    [CONST_FORECAST_START + (CONST_24_HOURS * 2) + (CONST_1_HOUR * 13), 500.6],
]


@pytest.fixture
def mock_setup_entry(patch_forecast_fn) -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.vrm_forecasts.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Override async_config_entry."""
    return MockConfigEntry(
        title="Test VRM Forecasts",
        unique_id="uniqueid",
        version=1,
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test_api_key",
            CONF_SITE_ID: 123456,
        },
        options={},
    )


@pytest.fixture(autouse=True)
def patch_forecast_fn(monkeypatch: pytest.MonkeyPatch):
    """Patch the forecast function to return a fake store."""

    def fake_dt_now():
        return datetime.datetime.fromtimestamp(
            (CONST_FORECAST_START + (CONST_24_HOURS + CONST_12_HOURS) + 60000) / 1000,
            tz=datetime.UTC,
        )

    async def fake(client, site_id):
        return VRMForecastStore(
            solar=ForecastEstimates(
                start=CONST_FORECAST_START / 1000,
                end=CONST_FORECAST_END / 1000,
                records=[(x / 1000, y) for x, y in CONST_FORECAST_RECORDS],
                custom_dt_now=fake_dt_now,
                site_id=123456,
            ),  # your ForecastEstimates
            consumption=ForecastEstimates(
                start=CONST_FORECAST_START / 1000,
                end=CONST_FORECAST_END / 1000,
                records=[(x / 1000, y) for x, y in CONST_FORECAST_RECORDS],
                custom_dt_now=fake_dt_now,
                site_id=123456,
            ),  # your ForecastEstimates
            site_id=123456,
        )

    monkeypatch.setattr(
        "homeassistant.components.vrm_forecasts.coordinator.get_forecast",
        fake,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Mock Victron VRM Forecasts for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
