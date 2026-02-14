"""Tests for Google Maps Travel Time services."""

from unittest.mock import AsyncMock

from google.api_core.exceptions import GoogleAPIError, PermissionDenied
import pytest

from homeassistant.components.google_travel_time.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_OPTIONS, MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_service_get_travel_times(
    hass: HomeAssistant,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
) -> None:
    """Test service get_travel_times."""
    response_data = await hass.services.async_call(
        DOMAIN,
        "get_travel_times",
        {
            "config_entry_id": mock_config.entry_id,
            "origin": "location1",
            "destination": "location2",
            "mode": "driving",
            "units": "metric",
        },
        blocking=True,
        return_response=True,
    )
    assert response_data == {
        "routes": [
            {
                "duration": 1620,
                "duration_text": "27 mins",
                "static_duration_text": "26 mins",
                "distance_meters": 21300,
                "distance_text": "21.3 km",
            }
        ]
    }


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_service_get_travel_times_with_all_options(
    hass: HomeAssistant,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
) -> None:
    """Test service get_travel_times with all optional parameters."""
    response_data = await hass.services.async_call(
        DOMAIN,
        "get_travel_times",
        {
            "config_entry_id": mock_config.entry_id,
            "origin": "location1",
            "destination": "location2",
            "mode": "driving",
            "units": "imperial",
            "language": "en",
            "avoid": "tolls",
            "traffic_model": "best_guess",
            "departure_time": "08:00:00",
        },
        blocking=True,
        return_response=True,
    )
    assert "routes" in response_data
    assert len(response_data["routes"]) == 1


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_service_get_travel_times_empty_response(
    hass: HomeAssistant,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
) -> None:
    """Test service get_travel_times with empty response."""
    routes_mock.compute_routes.return_value = None

    response_data = await hass.services.async_call(
        DOMAIN,
        "get_travel_times",
        {
            "config_entry_id": mock_config.entry_id,
            "origin": "location1",
            "destination": "location2",
            "mode": "driving",
            "units": "metric",
        },
        blocking=True,
        return_response=True,
    )
    assert response_data == {"routes": []}


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            PermissionDenied("test"),
            "The Routes API is not enabled for this API key",
        ),
        (GoogleAPIError("test"), "Google API error"),
    ],
)
async def test_service_get_travel_times_errors(
    hass: HomeAssistant,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
    exception: Exception,
    error_message: str,
) -> None:
    """Test service get_travel_times error handling."""
    routes_mock.compute_routes.side_effect = exception

    with pytest.raises(
        HomeAssistantError,
        match=error_message,
    ):
        await hass.services.async_call(
            DOMAIN,
            "get_travel_times",
            {
                "config_entry_id": mock_config.entry_id,
                "origin": "location1",
                "destination": "location2",
                "mode": "driving",
                "units": "metric",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_service_get_transit_times(
    hass: HomeAssistant,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
) -> None:
    """Test service get_transit_times."""
    response_data = await hass.services.async_call(
        DOMAIN,
        "get_transit_times",
        {
            "config_entry_id": mock_config.entry_id,
            "origin": "location1",
            "destination": "location2",
            "units": "metric",
        },
        blocking=True,
        return_response=True,
    )
    assert response_data == {
        "routes": [
            {
                "duration": 1620,
                "duration_text": "27 mins",
                "static_duration_text": "26 mins",
                "distance_meters": 21300,
                "distance_text": "21.3 km",
            }
        ]
    }


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_service_get_transit_times_with_all_options(
    hass: HomeAssistant,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
) -> None:
    """Test service get_transit_times with all optional parameters."""
    response_data = await hass.services.async_call(
        DOMAIN,
        "get_transit_times",
        {
            "config_entry_id": mock_config.entry_id,
            "origin": "location1",
            "destination": "location2",
            "units": "imperial",
            "language": "en",
            "transit_mode": "bus",
            "transit_routing_preference": "fewer_transfers",
            "departure_time": "08:00:00",
        },
        blocking=True,
        return_response=True,
    )
    assert "routes" in response_data
    assert len(response_data["routes"]) == 1


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            PermissionDenied("test"),
            "The Routes API is not enabled for this API key",
        ),
        (GoogleAPIError("test"), "Google API error"),
    ],
)
async def test_service_get_transit_times_errors(
    hass: HomeAssistant,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
    exception: Exception,
    error_message: str,
) -> None:
    """Test service get_transit_times error handling."""
    routes_mock.compute_routes.side_effect = exception

    with pytest.raises(
        HomeAssistantError,
        match=error_message,
    ):
        await hass.services.async_call(
            DOMAIN,
            "get_transit_times",
            {
                "config_entry_id": mock_config.entry_id,
                "origin": "location1",
                "destination": "location2",
                "units": "metric",
            },
            blocking=True,
            return_response=True,
        )
