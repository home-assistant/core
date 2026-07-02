"""Tests for the Forecast.Solar services."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

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

    # Response is two flat ``{ISO timestamp -> number}`` maps.
    assert set(response.keys()) == {"watts", "wh_period"}
    assert isinstance(response["watts"], dict)
    assert isinstance(response["wh_period"], dict)

    # The conftest mock seeds two timestamps in ``watts`` and
    # ``wh_period``, both at 13:00 in HA's default timezone. The
    # service emits ISO keys in the site/API timezone
    # (``Europe/Amsterdam`` per the conftest mock).
    api_tz = ZoneInfo("Europe/Amsterdam")
    default_tz = dt_util.get_default_time_zone()
    ts_2021 = (
        datetime(2021, 6, 27, 13, 0, tzinfo=default_tz).astimezone(api_tz).isoformat()
    )
    ts_2022 = (
        datetime(2022, 6, 27, 13, 0, tzinfo=default_tz).astimezone(api_tz).isoformat()
    )
    assert response["watts"] == {ts_2021: 10, ts_2022: 100}
    assert response["wh_period"] == {ts_2021: 30, ts_2022: 300}


async def test_get_forecast_hourly_aggregation(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test the get_forecast service aggregates to whole hours."""
    # Add some 15-min-resolution entries within a single hour so we can
    # observe that power gets averaged and energy gets summed.
    api_tz = ZoneInfo("Europe/Amsterdam")
    estimate = mock_forecast_solar.estimate.return_value
    base = datetime(2026, 6, 19, 8, 0, tzinfo=api_tz)
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

    watts = response["watts"]
    wh = response["wh_period"]
    hour_0_iso = base.isoformat()
    hour_1_iso = (base + timedelta(hours=1)).isoformat()
    assert watts[hour_0_iso] == pytest.approx(2500.0)
    assert wh[hour_0_iso] == 2500
    assert watts[hour_1_iso] == pytest.approx(5000.0)
    assert wh[hour_1_iso] == 1250


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
