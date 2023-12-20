"""Common fixtures for the WeatherflowCloud tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pyweatherflow_forecast import (
    WeatherFlowForecastBadRequest,
    WeatherFlowForecastInternalServerError,
    WeatherFlowForecastUnauthorized,
    WeatherFlowForecastWongStationId,
    WeatherFlowStationData,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.weatherflow_cloud.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_validate_and_get_station_info() -> Generator[AsyncMock, None, None]:
    """Mock valid station info."""
    with patch(
        "homeassistant.components.weatherflow_cloud.config_flow.WeatherFlow.async_get_station",
        return_value=WeatherFlowStationData(
            station_name="taco5",
            latitude=0.0,
            longitude=0.0,
            timezone="UTZ",
            device_id=1,
            firmware_revision="1",
            serial_number="1",
        ),
    ) as mock_setup_entry:
        yield mock_setup_entry


def exception_then_return(*args, **kwargs):
    """Exceptions then return good."""
    # List of exceptions to be raised in order
    exceptions = [
        WeatherFlowForecastWongStationId,
        WeatherFlowForecastBadRequest,
        WeatherFlowForecastInternalServerError,
        WeatherFlowForecastUnauthorized,
    ]

    if not hasattr(exception_then_return, "call_count"):
        exception_then_return.call_count = 0

    if exception_then_return.call_count < len(exceptions):
        exception = exceptions[exception_then_return.call_count]
        exception_then_return.call_count += 1
        raise exception("Mocked exception")

    return WeatherFlowStationData(
        station_name="taco5",
        latitude=0.0,
        longitude=0.0,
        timezone="UTZ",
        device_id=1,
        firmware_revision="1",
        serial_number="1",
    )


@pytest.fixture
def mock_validate_and_get_station_info_side_effects() -> (
    Generator[AsyncMock, None, None]
):
    """Mock a set of bad returns then a good one."""
    with patch(
        "homeassistant.components.weatherflow_cloud.config_flow.WeatherFlow.async_get_station",
        new_callable=AsyncMock,
    ) as mock_setup_entry:
        mock_setup_entry.side_effect = exception_then_return
        yield mock_setup_entry
