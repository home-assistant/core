"""Tests for Google Maps Travel Time services."""

from typing import Any
from unittest.mock import AsyncMock, patch

from google_maps_routing_api import (
    ComputeRoutesResponse,
    GoogleMapsRoutingApiAuthError,
    GoogleMapsRoutingApiConnectionTimeoutError,
    GoogleMapsRoutingApiError,
    TrafficModel,
    TransitRoutingPreference,
    TransitTravelMode,
    TravelMode,
    Units,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.google_travel_time.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_OPTIONS, MOCK_CONFIG, MOCK_CONFIG_REFERRER


def _mock_routes_response() -> dict[str, Any]:
    """Return a mocked ComputeRoutes response."""
    return {
        "routes": [
            {
                "distanceMeters": 21300,
                "duration": "1620s",
                "localizedValues": {
                    "distance": {"text": "21.3 km"},
                    "duration": {"text": "27 mins"},
                    "staticDuration": {"text": "26 mins"},
                },
            }
        ]
    }


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
    assert len(response_data["routes"]) == 1

    kwargs = routes_mock.async_compute_routes.call_args.kwargs
    assert kwargs["units"] == Units.IMPERIAL
    assert kwargs["language_code"] == "en"
    assert kwargs["avoid_tolls"] is True
    assert kwargs["traffic_model"] == TrafficModel.BEST_GUESS
    assert kwargs["departure_time"] is not None
    assert kwargs["arrival_time"] is None


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
    routes_mock.async_compute_routes.return_value = None

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
    [(MOCK_CONFIG_REFERRER, DEFAULT_OPTIONS)],
)
async def test_service_get_travel_times_with_referrer(
    hass: HomeAssistant,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
) -> None:
    """Test the referrer from the config entry is passed to the client."""
    client_mock = AsyncMock()
    client_mock.async_compute_routes.return_value = ComputeRoutesResponse.from_dict(
        _mock_routes_response()
    )
    with patch(
        "homeassistant.components.google_travel_time.helpers.GoogleMapsRoutingApi",
        return_value=client_mock,
    ) as mock_client:
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
        assert mock_client.call_args.kwargs["referrer"] == "https://example.com/"


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            GoogleMapsRoutingApiAuthError(
                "Routes API is disabled.",
                status="PERMISSION_DENIED",
                reason="SERVICE_DISABLED",
            ),
            "The Routes API is not enabled for this API key",
        ),
        (GoogleMapsRoutingApiError("test"), "Google API error"),
        (TimeoutError(), "Timed out getting travel times"),
        (
            GoogleMapsRoutingApiConnectionTimeoutError("Timeout"),
            "Timed out getting travel times",
        ),
        (ValueError("boom"), "Google API error: boom"),
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
    routes_mock.async_compute_routes.side_effect = exception

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
    assert len(response_data["routes"]) == 1

    kwargs = routes_mock.async_compute_routes.call_args.kwargs
    assert kwargs["travel_mode"] == TravelMode.TRANSIT
    assert kwargs["units"] == Units.IMPERIAL
    assert kwargs["language_code"] == "en"
    assert kwargs["transit_routing_preference"] == (
        TransitRoutingPreference.FEWER_TRANSFERS
    )
    assert kwargs["allowed_travel_modes"] == [TransitTravelMode.BUS]
    assert kwargs["departure_time"] is not None
    assert kwargs["arrival_time"] is None


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            GoogleMapsRoutingApiAuthError(
                "Routes API is disabled.",
                status="PERMISSION_DENIED",
                reason="SERVICE_DISABLED",
            ),
            "The Routes API is not enabled for this API key",
        ),
        (GoogleMapsRoutingApiError("test"), "Google API error"),
        (TimeoutError(), "Timed out getting travel times"),
        (
            GoogleMapsRoutingApiConnectionTimeoutError("Timeout"),
            "Timed out getting travel times",
        ),
        (ValueError("boom"), "Google API error: boom"),
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
    routes_mock.async_compute_routes.side_effect = exception

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
