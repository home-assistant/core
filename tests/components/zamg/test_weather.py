"""Tests for the ZAMG weather entity."""

from datetime import datetime
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.zamg.weather import ZamgWeather

from .conftest import TEST_STATION_ID


def _build_entity(timestamps: list[str | datetime], tcc: list[float]) -> ZamgWeather:
    """Create a weather entity with forecast test data."""
    coordinator = MagicMock()
    coordinator.data = {
        "nowcast": {
            "t2m": 14.0,
            "rain": 0.0,
            "wind_speed": 5.0,
            "rh2m": 45.0,
            "tcc": 10.0,
        },
        TEST_STATION_ID: {
            "P": {"data": 1013.0},
            "DD": {"data": 180.0},
            "DDX": {"data": 200.0},
        },
        "forecast": {
            "timestamps": timestamps,
            "features": [
                {
                    "properties": {
                        "parameters": {
                            "t2m": {"data": [15.0, 16.0]},
                            "rain": {"data": [0.0, 0.0]},
                            "wind_speed": {"data": [5.0, 7.0]},
                            "rh2m": {"data": [45.0, 55.0]},
                            "tcc": {"data": tcc},
                        }
                    }
                }
            ],
        },
    }
    return ZamgWeather(coordinator, "Graz/Flughafen", TEST_STATION_ID)


@pytest.mark.freeze_time("2026-01-01 12:00:00")
async def test_async_forecast_hourly_filters_string_timestamps() -> None:
    """Test string timestamps are converted and filtered correctly."""
    entity = _build_entity(
        timestamps=["2026-01-01T09:00:00", "2026-01-01T13:00:00"],
        tcc=[90.0, 10.0],
    )

    forecast = await entity.async_forecast_hourly()

    assert forecast is not None
    assert len(forecast) == 1
    assert forecast[0]["datetime"] == "2026-01-01T13:00:00"
    assert forecast[0]["condition"] == "sunny"


@pytest.mark.freeze_time("2026-01-01 20:00:00")
async def test_async_forecast_hourly_handles_datetime_timestamps() -> None:
    """Test datetime timestamps are accepted and condition uses night logic."""
    entity = _build_entity(
        timestamps=[
            datetime.fromisoformat("2026-01-01T19:00:00"),
            datetime.fromisoformat("2026-01-01T21:00:00"),
        ],
        tcc=[90.0, 10.0],
    )

    forecast = await entity.async_forecast_hourly()

    assert forecast is not None
    assert len(forecast) == 1
    assert forecast[0]["datetime"] == "2026-01-01T21:00:00"
    assert forecast[0]["condition"] == "clear-night"


@pytest.mark.parametrize(
    ("tcc", "rain", "frozen_time", "expected"),
    [
        (10.0, 0.0, "2026-01-01 12:00:00", "sunny"),
        (10.0, 0.0, "2026-01-01 20:00:00", "clear-night"),
        (40.0, 0.0, "2026-01-01 12:00:00", "partlycloudy"),
        (70.0, 0.0, "2026-01-01 12:00:00", "cloudy"),
        (90.0, 0.0, "2026-01-01 12:00:00", "fog"),
        (10.0, 0.3, "2026-01-01 12:00:00", "rainy"),
    ],
)
async def test_condition_variants(
    freezer: FrozenDateTimeFactory,
    tcc: float,
    rain: float,
    frozen_time: str,
    expected: str,
) -> None:
    """Test all weather condition branches."""
    freezer.move_to(frozen_time)
    entity = _build_entity(
        timestamps=["2026-01-01T13:00:00", "2026-01-01T14:00:00"],
        tcc=[10.0, 20.0],
    )
    entity.coordinator.data["nowcast"]["tcc"] = tcc
    entity.coordinator.data["nowcast"]["rain"] = rain

    assert entity.condition == expected


async def test_native_values_and_wind_fallback() -> None:
    """Test basic property mapping and DDX fallback for wind bearing."""
    entity = _build_entity(
        timestamps=["2026-01-01T13:00:00", "2026-01-01T14:00:00"],
        tcc=[10.0, 20.0],
    )

    assert entity.native_temperature == 14.0
    assert entity.native_pressure == 1013.0
    assert entity.humidity == 45.0
    assert entity.native_wind_speed == 5.0
    assert entity.wind_bearing == 180.0

    entity.coordinator.data[TEST_STATION_ID]["DD"]["data"] = None
    assert entity.wind_bearing == 200.0


async def test_condition_returns_none_on_invalid_nowcast() -> None:
    """Test condition gracefully handles malformed nowcast data."""
    entity = _build_entity(
        timestamps=["2026-01-01T13:00:00", "2026-01-01T14:00:00"],
        tcc=[10.0, 20.0],
    )
    entity.coordinator.data["nowcast"] = {"tcc": None, "rain": None}

    assert entity.condition is None


async def test_async_forecast_hourly_returns_none_for_missing_sections() -> None:
    """Test forecast method returns None when required sections are absent."""
    entity = _build_entity(
        timestamps=["2026-01-01T13:00:00", "2026-01-01T14:00:00"],
        tcc=[10.0, 20.0],
    )
    entity.coordinator.data["forecast"] = {"timestamps": [], "features": []}

    forecast = await entity.async_forecast_hourly()

    assert forecast is None


async def test_async_forecast_hourly_returns_none_on_bad_timestamp() -> None:
    """Test forecast method handles invalid timestamp values."""
    entity = _build_entity(
        timestamps=["invalid-date"],
        tcc=[10.0],
    )

    forecast = await entity.async_forecast_hourly()

    assert forecast is None


async def test_is_night_uses_current_time_when_not_provided(
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test _is_night path that uses naive_now when date is omitted."""
    freezer.move_to("2026-01-01 22:00:00")
    entity = _build_entity(
        timestamps=["2026-01-01T13:00:00", "2026-01-01T14:00:00"],
        tcc=[10.0, 20.0],
    )

    assert entity._is_night() is True


async def test_weather_properties_return_none_on_invalid_types() -> None:
    """Test property exception handlers for malformed value types."""
    entity = _build_entity(
        timestamps=["2026-01-01T13:00:00", "2026-01-01T14:00:00"],
        tcc=[10.0, 20.0],
    )
    entity.coordinator.data["nowcast"]["t2m"] = "invalid"
    entity.coordinator.data["nowcast"]["rh2m"] = "invalid"
    entity.coordinator.data["nowcast"]["wind_speed"] = "invalid"

    assert entity.native_temperature is None
    assert entity.humidity is None
    assert entity.native_wind_speed is None


async def test_wind_bearing_returns_none_when_dd_and_ddx_missing() -> None:
    """Test wind bearing returns None when both directional values are missing."""
    entity = _build_entity(
        timestamps=["2026-01-01T13:00:00", "2026-01-01T14:00:00"],
        tcc=[10.0, 20.0],
    )
    entity.coordinator.data[TEST_STATION_ID]["DD"]["data"] = None
    entity.coordinator.data[TEST_STATION_ID]["DDX"]["data"] = None

    assert entity.wind_bearing is None
