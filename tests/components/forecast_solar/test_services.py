"""Tests for the Forecast.Solar services."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from pytest_homeassistant.common import MockConfigEntry

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


async def test_get_forecast_raw(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test the get_forecast service with native resolution.

    The API keys each energy value by the end of its period; the service
    returns it at the start of the period, so the last timestamp has none.
    """
    api_tz = ZoneInfo("Europe/Amsterdam")
    estimate = mock_forecast_solar.estimate.return_value
    estimate.watts = {
        datetime(2026, 6, 19, 5, 20, tzinfo=api_tz): 0,
        datetime(2026, 6, 19, 6, 0, tzinfo=api_tz): 200,
        datetime(2026, 6, 19, 7, 0, tzinfo=api_tz): 600,
        datetime(2026, 6, 19, 7, 20, tzinfo=api_tz): 0,
    }
    estimate.wh_period = {
        datetime(2026, 6, 19, 5, 20, tzinfo=api_tz): 0,
        datetime(2026, 6, 19, 6, 0, tzinfo=api_tz): 67,
        datetime(2026, 6, 19, 7, 0, tzinfo=api_tz): 400,
        datetime(2026, 6, 19, 7, 20, tzinfo=api_tz): 100,
    }

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

    # Response is two flat ``{ISO timestamp -> number}`` maps, with ISO
    # keys in the site/API timezone (``Europe/Amsterdam``).
    assert response == {
        "watts": {
            "2026-06-19T05:20:00+02:00": 0,
            "2026-06-19T06:00:00+02:00": 200,
            "2026-06-19T07:00:00+02:00": 600,
            "2026-06-19T07:20:00+02:00": 0,
        },
        "wh_period": {
            "2026-06-19T05:20:00+02:00": 67,
            "2026-06-19T06:00:00+02:00": 400,
            "2026-06-19T07:00:00+02:00": 100,
        },
    }


async def test_get_forecast_hourly_aggregation(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test the get_forecast service aggregates to whole hours."""
    # 15-min-resolution entries, as on paid accounts: power gets averaged
    # and energy summed per hour. Each energy value is keyed by the end of
    # its period, so 08:00-09:00 is the sum of the 08:15 to 09:00 values.
    api_tz = ZoneInfo("Europe/Amsterdam")
    estimate = mock_forecast_solar.estimate.return_value
    base = datetime(2026, 6, 19, 8, 0, tzinfo=api_tz)
    estimate.watts = {
        base - timedelta(minutes=15): 600,
        base: 1000,
        base + timedelta(minutes=15): 2000,
        base + timedelta(minutes=30): 3000,
        base + timedelta(minutes=45): 4000,
        base + timedelta(hours=1): 5000,
        base + timedelta(hours=1, minutes=15): 4000,
    }
    estimate.wh_period = {
        base - timedelta(minutes=15): 150,
        base: 200,
        base + timedelta(minutes=15): 375,
        base + timedelta(minutes=30): 625,
        base + timedelta(minutes=45): 875,
        base + timedelta(hours=1): 1125,
        base + timedelta(hours=1, minutes=15): 1125,
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

    watts = response["watts"]
    wh = response["wh_period"]
    hour_7_iso = (base - timedelta(hours=1)).isoformat()
    hour_8_iso = base.isoformat()
    hour_9_iso = (base + timedelta(hours=1)).isoformat()
    assert watts[hour_8_iso] == pytest.approx(2500.0)
    assert wh == {hour_7_iso: 200, hour_8_iso: 3000, hour_9_iso: 1125}


async def test_get_forecast_filters_by_time_range(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test the get_forecast service filters entries to the requested range."""
    api_tz = ZoneInfo("Europe/Amsterdam")
    estimate = mock_forecast_solar.estimate.return_value
    estimate.watts = {
        datetime(2026, 6, 19, 6, 0, tzinfo=api_tz): 100,
        datetime(2026, 6, 19, 9, 0, tzinfo=api_tz): 500,
        datetime(2026, 6, 19, 12, 0, tzinfo=api_tz): 900,
        datetime(2026, 6, 19, 18, 0, tzinfo=api_tz): 50,
    }
    estimate.wh_period = dict(estimate.watts)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FORECAST,
        {
            ATTR_CONFIG_ENTRY: init_integration.entry_id,
            ATTR_START: datetime(2026, 6, 19, 9, 0, tzinfo=api_tz),
            ATTR_END: datetime(2026, 6, 19, 18, 0, tzinfo=api_tz),
        },
        blocking=True,
        return_response=True,
    )

    # Range is half-open ``[start, end)``: 09:00 is included, 18:00 is
    # excluded, leaving the 09:00 and 12:00 entries.
    watts = response["watts"]
    assert set(watts.keys()) == {
        datetime(2026, 6, 19, 9, 0, tzinfo=api_tz).isoformat(),
        datetime(2026, 6, 19, 12, 0, tzinfo=api_tz).isoformat(),
    }
    assert watts[datetime(2026, 6, 19, 9, 0, tzinfo=api_tz).isoformat()] == 500
    assert watts[datetime(2026, 6, 19, 12, 0, tzinfo=api_tz).isoformat()] == 900


async def test_get_forecast_accepts_naive_datetimes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test that naive start/end datetimes are interpreted in the forecast zone.

    The Home Assistant UI datetime selector and ``cv.datetime`` produce
    naive ``datetime`` values for strings without an offset, so the
    service must attach the forecast's timezone before filtering. The
    mock estimate has ``timezone = "Europe/Amsterdam"``, which can
    differ from HA's default time zone, so the forecast data is built
    in that zone too.
    """
    api_tz = ZoneInfo("Europe/Amsterdam")
    estimate = mock_forecast_solar.estimate.return_value
    estimate.watts = {
        datetime(2026, 6, 19, 6, 0, tzinfo=api_tz): 100,
        datetime(2026, 6, 19, 9, 0, tzinfo=api_tz): 500,
        datetime(2026, 6, 19, 12, 0, tzinfo=api_tz): 900,
        datetime(2026, 6, 19, 18, 0, tzinfo=api_tz): 50,
    }
    estimate.wh_period = dict(estimate.watts)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FORECAST,
        {
            ATTR_CONFIG_ENTRY: init_integration.entry_id,
            # Naive datetimes, as produced by ``cv.datetime`` from the UI.
            ATTR_START: datetime(2026, 6, 19, 9, 0),
            ATTR_END: datetime(2026, 6, 19, 18, 0),
        },
        blocking=True,
        return_response=True,
    )

    watts = response["watts"]
    # 09:00 inclusive, 18:00 exclusive -> 09:00 + 12:00 remain.
    assert set(watts.keys()) == {
        datetime(2026, 6, 19, 9, 0, tzinfo=api_tz).isoformat(),
        datetime(2026, 6, 19, 12, 0, tzinfo=api_tz).isoformat(),
    }


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
