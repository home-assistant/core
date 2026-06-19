"""Tests for the Forecast.Solar services."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from homeassistant.components.forecast_solar.const import DOMAIN
from homeassistant.components.forecast_solar.services import (
    ATTR_CONFIG_ENTRY,
    ATTR_END,
    ATTR_RESOLUTION,
    ATTR_START,
    RESOLUTION_HOURLY,
    RESOLUTION_RAW,
    SERVICE_GET_FORECAST,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_get_forecast_raw(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the get_forecast service with native resolution."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FORECAST,
        {
            ATTR_CONFIG_ENTRY: init_integration.entry_id,
            ATTR_RESOLUTION: RESOLUTION_RAW,
        },
        blocking=True,
        return_response=True,
    )

    assert "forecast" in response
    forecast = response["forecast"]
    assert isinstance(forecast, list)
    assert len(forecast) == 2

    # The conftest mock seeds two timestamps in `watts` and `wh_period`,
    # both at 13:00 in the test default timezone.
    tz = dt_util.get_default_time_zone()
    first = forecast[0]
    assert set(first.keys()) >= {"time", "value", "energy_wh"}
    assert first["time"] == datetime(2021, 6, 27, 13, 0, tzinfo=tz).isoformat()
    assert first["value"] == 10
    assert first["energy_wh"] == 30

    second = forecast[1]
    assert second["time"] == datetime(2022, 6, 27, 13, 0, tzinfo=tz).isoformat()
    assert second["value"] == 100
    assert second["energy_wh"] == 300


async def test_get_forecast_hourly_aggregation(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test the get_forecast service aggregates to whole hours."""
    # Add some 15-min-resolution entries within a single hour so we can
    # observe that power gets averaged and energy gets summed.
    tz = dt_util.get_default_time_zone()
    estimate = mock_forecast_solar.estimate.return_value
    base = datetime(2026, 6, 19, 8, 0, tzinfo=tz)
    estimate.watts = {
        base: 1000,
        base + timedelta(minutes=15): 2000,
        base + timedelta(minutes=30): 3000,
        base + timedelta(minutes=45): 4000,
        base + timedelta(hours=1): 5000,
    }
    estimate.wh_period = {
        base: 250,
        base + timedelta(minutes=15): 500,
        base + timedelta(minutes=30): 750,
        base + timedelta(minutes=45): 1000,
        base + timedelta(hours=1): 1250,
    }

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FORECAST,
        {
            ATTR_CONFIG_ENTRY: init_integration.entry_id,
            ATTR_RESOLUTION: RESOLUTION_HOURLY,
        },
        blocking=True,
        return_response=True,
    )

    forecast = response["forecast"]
    by_time = {entry["time"]: entry for entry in forecast}

    hour_0 = by_time[base.isoformat()]
    assert hour_0["value"] == pytest.approx(2500.0)
    assert hour_0["energy_wh"] == 2500

    hour_1 = by_time[(base + timedelta(hours=1)).isoformat()]
    assert hour_1["value"] == pytest.approx(5000.0)
    assert hour_1["energy_wh"] == 1250


async def test_get_forecast_filters_by_time_range(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test the get_forecast service filters entries to the requested range."""
    tz = dt_util.get_default_time_zone()
    estimate = mock_forecast_solar.estimate.return_value
    estimate.watts = {
        datetime(2026, 6, 19, 6, 0, tzinfo=tz): 100,
        datetime(2026, 6, 19, 9, 0, tzinfo=tz): 500,
        datetime(2026, 6, 19, 12, 0, tzinfo=tz): 900,
        datetime(2026, 6, 19, 18, 0, tzinfo=tz): 50,
    }
    estimate.wh_period = dict(estimate.watts)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FORECAST,
        {
            ATTR_CONFIG_ENTRY: init_integration.entry_id,
            ATTR_START: datetime(2026, 6, 19, 9, 0, tzinfo=tz),
            ATTR_END: datetime(2026, 6, 19, 18, 0, tzinfo=tz),
        },
        blocking=True,
        return_response=True,
    )

    forecast = response["forecast"]
    assert len(forecast) == 2
    assert forecast[0]["value"] == 500
    assert forecast[1]["value"] == 900


async def test_get_forecast_rejects_end_before_start(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the get_forecast service rejects an end-before-start range."""
    tz = dt_util.get_default_time_zone()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FORECAST,
            {
                ATTR_CONFIG_ENTRY: init_integration.entry_id,
                ATTR_START: datetime(2026, 6, 19, 18, 0, tzinfo=tz),
                ATTR_END: datetime(2026, 6, 19, 9, 0, tzinfo=tz),
            },
            blocking=True,
            return_response=True,
        )
