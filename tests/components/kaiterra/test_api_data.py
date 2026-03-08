"""Tests for Kaiterra API helpers."""

from __future__ import annotations

from enum import Enum
from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientResponseError
import pytest
from yarl import URL

from homeassistant.components.kaiterra.api_data import (
    KaiterraApiAuthError,
    KaiterraApiClient,
    KaiterraApiError,
    KaiterraDeviceNotFoundError,
    _normalize_device_data,
    _normalize_unit,
)
from homeassistant.components.kaiterra.const import AQI_LEVEL, AQI_SCALE


class MockUnit(Enum):
    """Test enum for API unit normalization."""

    FAHRENHEIT = "F"


async def test_api_client_uses_library_default_base_url() -> None:
    """Test the wrapper does not override the library base URL."""
    with patch(
        "homeassistant.components.kaiterra.api_data.KaiterraAPIClient"
    ) as mock_client:
        KaiterraApiClient(object(), "test-api-key", "us")

    assert "base_url" not in mock_client.call_args.kwargs
    assert mock_client.call_args.kwargs["api_key"] == "test-api-key"
    assert mock_client.call_args.kwargs["aqi_standard"].value == "us"


async def test_api_client_normalizes_sensor_payload() -> None:
    """Test the API client normalizes the Kaiterra payload."""
    client = KaiterraApiClient(object(), "test-api-key", "us")
    client._api.get_latest_sensor_readings = AsyncMock(
        return_value=[
            {
                "rtemp": {
                    "units": MockUnit.FAHRENHEIT,
                    "points": [{"value": 74.2, "aqi": 52}],
                },
                "tvoc": {
                    "units": "ppb",
                    "points": [{"value": 91, "aqi": 84}],
                },
                "noise": "ignored",
                "invalid_points": {"points": "bad"},
                "invalid_point": {"points": ["bad"]},
            }
        ]
    )

    data = await client.async_get_latest_sensor_readings("device-123")

    assert data["rtemp"] == {"value": 74.2, "unit": "F", "aqi": 52}
    assert data["tvoc"] == {"value": 91, "unit": "ppb", "aqi": 84}
    assert data["aqi"] == {"value": 84}
    assert data["aqi_level"] == {"value": "Moderate"}
    assert data["aqi_pollutant"] == {"value": "TVOC"}


async def test_api_client_raises_auth_error_on_unauthorized() -> None:
    """Test a 401 response maps to auth failure."""
    client = KaiterraApiClient(object(), "test-api-key", "us")
    client._api.get_latest_sensor_readings = AsyncMock(
        side_effect=ClientResponseError(
            request_info=Mock(real_url=URL("https://api.kaiterra.com/v1/batch")),
            history=(),
            status=HTTPStatus.UNAUTHORIZED,
            message="Unauthorized",
        )
    )

    with pytest.raises(KaiterraApiAuthError):
        await client.async_get_latest_sensor_readings("device-123")


async def test_api_client_raises_generic_api_errors() -> None:
    """Test non-auth API failures map to generic API errors."""
    client = KaiterraApiClient(object(), "test-api-key", "us")

    client._api.get_latest_sensor_readings = AsyncMock(
        side_effect=ClientResponseError(
            request_info=Mock(real_url=URL("https://api.kaiterra.com/v1/batch")),
            history=(),
            status=HTTPStatus.BAD_GATEWAY,
            message="Bad gateway",
        )
    )
    with pytest.raises(KaiterraApiError):
        await client.async_get_latest_sensor_readings("device-123")

    client._api.get_latest_sensor_readings = AsyncMock(side_effect=TimeoutError)
    with pytest.raises(KaiterraApiError):
        await client.async_get_latest_sensor_readings("device-123")

    client._api.get_latest_sensor_readings = AsyncMock(side_effect=ValueError)
    with pytest.raises(KaiterraApiError):
        await client.async_get_latest_sensor_readings("device-123")


async def test_api_client_raises_device_not_found_when_payload_is_missing() -> None:
    """Test missing payload data maps to device not found."""
    client = KaiterraApiClient(object(), "test-api-key", "us")

    client._api.get_latest_sensor_readings = AsyncMock(return_value=[])
    with pytest.raises(KaiterraDeviceNotFoundError):
        await client.async_get_latest_sensor_readings("device-123")

    client._api.get_latest_sensor_readings = AsyncMock(return_value=[None])
    with pytest.raises(KaiterraDeviceNotFoundError):
        await client.async_get_latest_sensor_readings("device-123")


async def test_api_client_wraps_normalization_failures() -> None:
    """Test payload normalization errors map to generic API errors."""
    client = KaiterraApiClient(object(), "test-api-key", "us")
    client._api.get_latest_sensor_readings = AsyncMock(return_value=[{"tvoc": {}}])

    with (
        patch(
            "homeassistant.components.kaiterra.api_data._normalize_device_data",
            side_effect=ValueError,
        ),
        pytest.raises(KaiterraApiError),
    ):
        await client.async_get_latest_sensor_readings("device-123")


def test_normalize_device_data_without_aqi_returns_empty_aqi_fields() -> None:
    """Test payloads without AQI data still expose empty aggregate fields."""
    data = _normalize_device_data(
        {"rco2": {"units": None, "points": [{"value": 407}]}},
        AQI_SCALE["us"],
        AQI_LEVEL["us"],
    )

    assert data["rco2"] == {"value": 407}
    assert data["aqi"] == {"value": None}
    assert data["aqi_level"] == {"value": None}
    assert data["aqi_pollutant"] == {"value": None}


def test_normalize_unit_handles_supported_inputs() -> None:
    """Test unit normalization handles enum, string, and fallback values."""
    assert _normalize_unit(None) is None
    assert _normalize_unit(MockUnit.FAHRENHEIT) == "F"
    assert _normalize_unit("ppm") == "ppm"
    assert _normalize_unit(123) == "123"
