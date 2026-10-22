"""Tests for google_travel_time.helpers."""

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.google_travel_time import helpers
from homeassistant.components.google_travel_time.helpers import (
    ComputeRoutesResponse,
    GoogleAPIError,
    InvalidApiKeyException,
    InvalidReferrerException,
    PermissionDenied,
    Route,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import COMPUTE_ROUTES_URL, ROUTES_RESPONSE, mock_compute_routes


@pytest.mark.parametrize(
    ("location", "expected_result"),
    [
        (
            "12.34,56.78",
            {
                "location": {
                    "latLng": {
                        "latitude": 12.34,
                        "longitude": 56.78,
                    }
                }
            },
        ),
        (
            "12.34, 56.78",
            {
                "location": {
                    "latLng": {
                        "latitude": 12.34,
                        "longitude": 56.78,
                    }
                }
            },
        ),
        ("Some Address", {"address": "Some Address"}),
        ("Some Street 1, 12345 City", {"address": "Some Street 1, 12345 City"}),
    ],
)
def test_convert_to_waypoint(
    hass: HomeAssistant, location: str, expected_result: dict
) -> None:
    """Test convert_to_waypoint returns the correct waypoint."""
    assert helpers.convert_to_waypoint(hass, location) == expected_result


@pytest.mark.parametrize(
    ("time_str", "expected_result"),
    [
        ("13:00", "2024-01-01T13:00:00Z"),
        ("08:00", "2024-01-02T08:00:00Z"),
    ],
)
def test_convert_time(
    freezer: FrozenDateTimeFactory, time_str: str, expected_result: str
) -> None:
    """Test convert_time returns an RFC 3339 timestamp, rolling over to tomorrow."""
    freezer.move_to("2024-01-01 12:00:00+00:00")

    assert helpers.convert_time(time_str) == expected_result


async def test_compute_routes_drive(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the payload and headers of a driving request."""
    dt_util.set_default_time_zone(dt_util.UTC)
    freezer.move_to("2024-01-01 12:00:00+00:00")
    aioclient_mock.post(COMPUTE_ROUTES_URL, json=ROUTES_RESPONSE)
    client = helpers.RoutesClient(hass, "api_key", "https://example.com/")

    response = await helpers.async_compute_routes(
        client=client,
        origin="12.34,56.78",
        destination="Some Address",
        hass=hass,
        travel_mode="DRIVE",
        units="imperial",
        language="en",
        avoid="tolls",
        traffic_model="pessimistic",
        arrival_time="13:00",
    )

    assert response == ComputeRoutesResponse(
        routes=[
            Route(
                duration_seconds=1620,
                distance_meters=21300,
                duration_text="27 mins",
                static_duration_text="26 mins",
                distance_text="21.3 km",
            )
        ]
    )

    method, url, payload, headers = aioclient_mock.mock_calls[0]
    assert method == "POST"
    assert str(url) == COMPUTE_ROUTES_URL
    assert headers["X-Goog-Api-Key"] == "api_key"
    assert headers["X-Goog-FieldMask"] == (
        "routes.duration,routes.distanceMeters,routes.localizedValues"
    )
    assert headers["Referer"] == "https://example.com/"
    assert payload["origin"] == {
        "location": {"latLng": {"latitude": 12.34, "longitude": 56.78}}
    }
    assert payload["destination"] == {"address": "Some Address"}
    assert payload["travelMode"] == "DRIVE"
    assert payload["units"] == "IMPERIAL"
    assert payload["routingPreference"] == "TRAFFIC_AWARE_OPTIMAL"
    assert payload["routeModifiers"] == {
        "avoidTolls": True,
        "avoidFerries": False,
        "avoidHighways": False,
        "avoidIndoor": False,
    }
    assert payload["arrivalTime"] == "2024-01-01T13:00:00Z"
    assert payload["languageCode"] == "en"
    assert payload["trafficModel"] == "PESSIMISTIC"


async def test_compute_routes_transit(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the payload of a transit request without a referrer."""
    aioclient_mock.post(COMPUTE_ROUTES_URL, json={})
    client = helpers.RoutesClient(hass, "api_key")

    response = await helpers.async_compute_routes(
        client=client,
        origin="location1",
        destination="location2",
        hass=hass,
        travel_mode="TRANSIT",
        units="metric",
        transit_mode="bus",
        transit_routing_preference="fewer_transfers",
    )

    assert response == ComputeRoutesResponse(routes=[])

    _, _, payload, headers = aioclient_mock.mock_calls[0]
    assert "Referer" not in headers
    assert payload == {
        "origin": {"address": "location1"},
        "destination": {"address": "location2"},
        "travelMode": "TRANSIT",
        "units": "METRIC",
        "transitPreferences": {
            "routingPreference": "FEWER_TRANSFERS",
            "allowedTravelModes": ["BUS"],
        },
    }


@pytest.mark.parametrize(
    ("status", "body", "expected_exception"),
    [
        (
            400,
            {
                "error": {
                    "message": "API key not valid.",
                    "details": [{"reason": "API_KEY_INVALID"}],
                }
            },
            InvalidApiKeyException,
        ),
        (
            401,
            {"error": {"message": "Request had invalid authentication credentials."}},
            InvalidApiKeyException,
        ),
        (
            403,
            {
                "error": {
                    "message": "Requests from referer are blocked.",
                    "details": [{"reason": "API_KEY_HTTP_REFERRER_BLOCKED"}],
                }
            },
            InvalidReferrerException,
        ),
        (
            403,
            {
                "error": {
                    "message": "Routes API has not been used in project.",
                    "details": [{"reason": "SERVICE_DISABLED"}],
                }
            },
            PermissionDenied,
        ),
        (504, {"error": {"message": "Deadline exceeded."}}, TimeoutError),
        (500, {"error": {"message": "Internal error."}}, GoogleAPIError),
    ],
)
async def test_compute_routes_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    body: dict,
    expected_exception: type[Exception],
) -> None:
    """Test that API errors are translated to exceptions."""
    aioclient_mock.post(COMPUTE_ROUTES_URL, status=status, json=body)
    client = helpers.RoutesClient(hass, "api_key")

    with pytest.raises(expected_exception) as exc_info:
        await client.compute_routes({}, field_mask="routes.duration")

    assert str(exc_info.value) == body["error"]["message"]


async def test_compute_routes_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a request timeout raises TimeoutError."""
    aioclient_mock.post(COMPUTE_ROUTES_URL, exc=TimeoutError())
    client = helpers.RoutesClient(hass, "api_key")

    with pytest.raises(TimeoutError, match="Timeout connecting"):
        await client.compute_routes({}, field_mask="routes.duration")


async def test_compute_routes_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that connection errors are translated to GoogleAPIError."""
    mock_compute_routes(aioclient_mock, exc=aiohttp.ClientConnectionError("boom"))
    client = helpers.RoutesClient(hass, "api_key")

    with pytest.raises(GoogleAPIError, match="boom"):
        await client.compute_routes({}, field_mask="routes.duration")


async def test_compute_routes_invalid_json(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that an invalid response raises GoogleAPIError."""
    mock_compute_routes(aioclient_mock, text="not json")
    client = helpers.RoutesClient(hass, "api_key")

    with pytest.raises(GoogleAPIError, match="Invalid response"):
        await client.compute_routes({}, field_mask="routes.duration")
