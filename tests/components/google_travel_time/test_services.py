"""Tests for Google Maps Travel Time services."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.google_travel_time.const import CONF_REFERRER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import mock_compute_routes
from .const import DEFAULT_OPTIONS, MOCK_CONFIG

TRAVEL_TIMES_SERVICE_DATA = {
    "origin": "location1",
    "destination": "location2",
    "mode": "driving",
    "units": "metric",
}

EXPECTED_RESPONSE = {
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
async def test_service_get_travel_times(
    hass: HomeAssistant,
    routes_mock: AiohttpClientMocker,
    mock_config: MockConfigEntry,
) -> None:
    """Test service get_travel_times."""
    response_data = await hass.services.async_call(
        DOMAIN,
        "get_travel_times",
        {
            "config_entry_id": mock_config.entry_id,
            **TRAVEL_TIMES_SERVICE_DATA,
        },
        blocking=True,
        return_response=True,
    )
    assert response_data == EXPECTED_RESPONSE


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_service_get_travel_times_with_all_options(
    hass: HomeAssistant,
    routes_mock: AiohttpClientMocker,
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
    assert response_data == EXPECTED_RESPONSE

    payload = routes_mock.mock_calls[-1][2]
    assert payload["units"] == "IMPERIAL"
    assert payload["languageCode"] == "en"
    assert payload["routeModifiers"]["avoidTolls"] is True
    assert payload["trafficModel"] == "BEST_GUESS"
    assert "departureTime" in payload


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_service_get_travel_times_empty_response(
    hass: HomeAssistant,
    routes_mock: AiohttpClientMocker,
    mock_config: MockConfigEntry,
) -> None:
    """Test service get_travel_times with empty response."""
    mock_compute_routes(routes_mock, json={})

    response_data = await hass.services.async_call(
        DOMAIN,
        "get_travel_times",
        {
            "config_entry_id": mock_config.entry_id,
            **TRAVEL_TIMES_SERVICE_DATA,
        },
        blocking=True,
        return_response=True,
    )
    assert response_data == {"routes": []}


@pytest.mark.parametrize(
    ("data", "options"),
    [({**MOCK_CONFIG, CONF_REFERRER: "https://example.com/"}, DEFAULT_OPTIONS)],
)
async def test_service_get_travel_times_uses_referrer(
    hass: HomeAssistant,
    routes_mock: AiohttpClientMocker,
    mock_config: MockConfigEntry,
) -> None:
    """Test service get_travel_times sends the configured referrer."""
    await hass.services.async_call(
        DOMAIN,
        "get_travel_times",
        {
            "config_entry_id": mock_config.entry_id,
            **TRAVEL_TIMES_SERVICE_DATA,
        },
        blocking=True,
        return_response=True,
    )

    assert routes_mock.mock_calls[-1][3]["Referer"] == "https://example.com/"


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.parametrize(
    ("mock_kwargs", "error_message"),
    [
        (
            {
                "status": 403,
                "json": {
                    "error": {
                        "message": "Routes API has not been used in project.",
                        "details": [{"reason": "SERVICE_DISABLED"}],
                    }
                },
            },
            "The Routes API is not enabled for this API key",
        ),
        (
            {"status": 500, "json": {"error": {"message": "Internal error."}}},
            "Google API error: Internal error.",
        ),
    ],
)
async def test_service_get_travel_times_errors(
    hass: HomeAssistant,
    routes_mock: AiohttpClientMocker,
    mock_config: MockConfigEntry,
    mock_kwargs: dict,
    error_message: str,
) -> None:
    """Test service get_travel_times error handling."""
    mock_compute_routes(routes_mock, **mock_kwargs)

    with pytest.raises(
        HomeAssistantError,
        match=error_message,
    ):
        await hass.services.async_call(
            DOMAIN,
            "get_travel_times",
            {
                "config_entry_id": mock_config.entry_id,
                **TRAVEL_TIMES_SERVICE_DATA,
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
    routes_mock: AiohttpClientMocker,
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
    assert response_data == EXPECTED_RESPONSE


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_service_get_transit_times_with_all_options(
    hass: HomeAssistant,
    routes_mock: AiohttpClientMocker,
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
    assert response_data == EXPECTED_RESPONSE

    payload = routes_mock.mock_calls[-1][2]
    assert payload["travelMode"] == "TRANSIT"
    assert payload["units"] == "IMPERIAL"
    assert payload["languageCode"] == "en"
    assert payload["transitPreferences"] == {
        "routingPreference": "FEWER_TRANSFERS",
        "allowedTravelModes": ["BUS"],
    }
    assert "departureTime" in payload


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.parametrize(
    ("mock_kwargs", "error_message"),
    [
        (
            {
                "status": 403,
                "json": {
                    "error": {
                        "message": "Routes API has not been used in project.",
                        "details": [{"reason": "SERVICE_DISABLED"}],
                    }
                },
            },
            "The Routes API is not enabled for this API key",
        ),
        (
            {"status": 500, "json": {"error": {"message": "Internal error."}}},
            "Google API error: Internal error.",
        ),
    ],
)
async def test_service_get_transit_times_errors(
    hass: HomeAssistant,
    routes_mock: AiohttpClientMocker,
    mock_config: MockConfigEntry,
    mock_kwargs: dict,
    error_message: str,
) -> None:
    """Test service get_transit_times error handling."""
    mock_compute_routes(routes_mock, **mock_kwargs)

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
