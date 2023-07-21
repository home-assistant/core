"""Tests for Pegel Online component."""
from unittest.mock import AsyncMock, MagicMock


def _create_mocked_pegelonline(
    nearby_stations=None,
    station_details=None,
    station_measurement=None,
    side_effect=None,
):
    mocked_pegelonline = MagicMock()
    type(mocked_pegelonline).async_get_nearby_stations = AsyncMock(
        return_value=nearby_stations, side_effect=side_effect
    )
    type(mocked_pegelonline).async_get_station_details = AsyncMock(
        return_value=station_details, side_effect=side_effect
    )

    type(mocked_pegelonline).async_get_station_measurement = AsyncMock(
        return_value=station_measurement, side_effect=side_effect
    )

    return mocked_pegelonline
