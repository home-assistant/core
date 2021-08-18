"""Fixtures for Forecast.Solar integration tests."""

from datetime import datetime, timedelta
from typing import Generator
from unittest.mock import MagicMock, patch

from forecast_solar import models
import pytest

from homeassistant.components.forecast_solar.const import (
    CONF_AZIMUTH,
    CONF_DAMPING,
    CONF_DECLINATION,
    CONF_MODULES_POWER,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def mock_persistent_notification(hass: HomeAssistant) -> None:
    """Set up component for persistent notifications."""
    await async_setup_component(hass, "persistent_notification", {})


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
        },
    )


@pytest.fixture
def mock_forecast_solar() -> Generator[None, MagicMock, None]:
    """Return a mocked Forecast.Solar client."""
    with patch(
        "homeassistant.components.forecast_solar.ForecastSolar", autospec=True
    ) as forecast_solar_mock:
        forecast_solar = forecast_solar_mock.return_value
        now = datetime(2021, 6, 27, 6, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)

        estimate = MagicMock(spec=models.Estimate)
        estimate.now.return_value = now
        estimate.timezone = "Europe/Amsterdam"
        estimate.energy_production_today = 100000
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
