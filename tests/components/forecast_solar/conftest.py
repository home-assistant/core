"""Fixtures for Forecast.Solar integration tests."""

from collections.abc import Generator
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from forecast_solar import models
import pytest

from homeassistant.components.forecast_solar.const import (
    CONF_AZIMUTH,
    CONF_DAMPING,
    CONF_DECLINATION,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.forecast_solar.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Green House",
        unique_id="unique",
        domain=DOMAIN,
        data={
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
        },
        options={
            CONF_API_KEY: "abcdef12345",
            CONF_DECLINATION: 30,
            CONF_AZIMUTH: 190,
            CONF_MODULES_POWER: 5100,
            CONF_DAMPING: 0.5,
            CONF_INVERTER_SIZE: 2000,
        },
    )


@pytest.fixture
def mock_forecast_solar(hass) -> Generator[None, MagicMock, None]:
    """Return a mocked Forecast.Solar client.

    hass fixture included because it sets the time zone.
    """
    with patch(
        "homeassistant.components.forecast_solar.coordinator.ForecastSolar",
        autospec=True,
    ) as forecast_solar_mock:
        forecast_solar = forecast_solar_mock.return_value
        now = datetime(2021, 6, 27, 6, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)

        estimate = MagicMock(spec=models.Estimate)
        estimate.now.return_value = now
        estimate.timezone = "Europe/Amsterdam"
        estimate.api_rate_limit = 60
        estimate.account_type.value = "public"
        estimate.energy_production_today = 100000
        estimate.energy_production_today_remaining = 50000
        estimate.energy_production_tomorrow = 200000
        estimate.power_production_now = 300000
        estimate.power_highest_peak_time_today = datetime(
            2021, 6, 27, 13, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE
        )
        estimate.power_highest_peak_time_tomorrow = datetime(
            2021, 6, 27, 14, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE
        )
        estimate.energy_current_hour = 800000

        estimate.power_production_at_time.side_effect = {
            now + timedelta(hours=1): 400000,
            now + timedelta(hours=12): 600000,
            now + timedelta(hours=24): 700000,
        }.get

        estimate.sum_energy_production.side_effect = {
            1: 900000,
        }.get
        estimate.watts = {
            datetime(2021, 6, 27, 13, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE): 10,
            datetime(2022, 6, 27, 13, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE): 100,
        }
        estimate.wh_days = {
            datetime(2021, 6, 27, 13, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE): 20,
            datetime(2022, 6, 27, 13, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE): 200,
        }
        estimate.wh_period = {
            datetime(2021, 6, 27, 13, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE): 30,
            datetime(2022, 6, 27, 13, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE): 300,
        }

        forecast_solar.estimate.return_value = estimate
        yield forecast_solar


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> MockConfigEntry:
    """Set up the Forecast.Solar integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
