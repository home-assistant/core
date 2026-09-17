"""Tests for the Entur API helpers."""

from aiohttp import ClientResponseError
import pytest

from homeassistant.components.entur_public_transport.api import (
    STOP_PLACE_LINES_QUERY,
    EnturApiError,
    async_get_stop_place,
    async_get_stop_routes,
    async_search_stop_places,
)
from homeassistant.components.entur_public_transport.const import (
    ENTUR_CLIENT_NAME,
    GEOCODER_AUTOCOMPLETE_URL,
    GEOCODER_PLACE_URL,
    JOURNEY_PLANNER_URL,
)
from homeassistant.core import HomeAssistant


async def test_search_stop_places(aioclient_mock, hass: HomeAssistant) -> None:
    """Test parsing a Geocoder v3 stop place response."""
    aioclient_mock.get(
        GEOCODER_AUTOCOMPLETE_URL,
        json={
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "id": "NSR:StopPlace:548",
                        "names": {
                            "default": "Bergen busstasjon",
                            "display": "Bergen busstasjon, Bergen",
                        },
                        "address": {"locality": "Bergen"},
                        "transportModes": [
                            {"mode": "bus"},
                            {"mode": "rail", "subMode": "localTrain"},
                        ],
                        "stopPlaceTypes": ["busStation", "railStation"],
                        "stopPlaceRole": "parent",
                    },
                },
                {
                    "type": "Feature",
                    "properties": {"id": "NSR:Quay:48550"},
                },
            ]
        },
    )

    places = await async_search_stop_places(hass, "Bergen")

    assert len(places) == 1
    assert places[0].stop_id == "NSR:StopPlace:548"
    assert places[0].name == "Bergen busstasjon"
    assert places[0].display_name == "Bergen busstasjon, Bergen"
    assert places[0].locality == "Bergen"
    assert places[0].transport_modes == ("bus", "rail")
    assert places[0].role == "parent"
    assert places[0].stop_place_types == ("busStation", "railStation")
    assert places[0].type_icons == "🚌 🚆"
    assert places[0].selection_label == "Bergen busstasjon, Bergen · bus, rail"
    assert (
        places[0].entur_url
        == "https://entur.no/nearby-stop-place-detail?id=NSR%3AStopPlace%3A548"
    )

    method, url, _, headers = aioclient_mock.mock_calls[0]
    assert method == "GET"
    assert str(url) == (
        f"{GEOCODER_AUTOCOMPLETE_URL}?q=Bergen&lang=no&limit=10&layers=stopPlace&"
        "multimodal=parent"
    )
    assert headers["ET-Client-Name"] == ENTUR_CLIENT_NAME


async def test_search_stop_places_rejects_invalid_response(
    aioclient_mock, hass: HomeAssistant
) -> None:
    """Test that malformed API responses are not silently accepted."""
    aioclient_mock.get(GEOCODER_AUTOCOMPLETE_URL, json={"unexpected": []})

    with pytest.raises(EnturApiError):
        await async_search_stop_places(hass, "Bergen")


async def test_get_stop_place(aioclient_mock, hass: HomeAssistant) -> None:
    """Test loading one stop place by its canonical ID."""
    aioclient_mock.get(
        GEOCODER_PLACE_URL,
        json={
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "id": "NSR:StopPlace:548",
                        "names": {"default": "Bergen busstasjon"},
                        "stopPlaceTypes": ["busStation"],
                    },
                }
            ]
        },
    )

    place = await async_get_stop_place(hass, "NSR:StopPlace:548")

    assert place.name == "Bergen busstasjon"
    assert place.stop_place_types == ("busStation",)
    method, url, _, headers = aioclient_mock.mock_calls[0]
    assert method == "GET"
    assert str(url) == f"{GEOCODER_PLACE_URL}?ids=NSR:StopPlace:548&lang=no"
    assert headers["ET-Client-Name"] == ENTUR_CLIENT_NAME


async def test_get_stop_routes(aioclient_mock, hass: HomeAssistant) -> None:
    """Test retrieving and deduplicating routes for one stop place."""
    aioclient_mock.post(
        JOURNEY_PLANNER_URL,
        json={
            "data": {
                "stopPlaces": [
                    {
                        "estimatedCalls": [
                            {
                                "serviceJourney": {
                                    "journeyPattern": {
                                        "line": {
                                            "id": "BRA:Line:4_6200",
                                            "publicCode": "4_6200",
                                            "name": "200 Hønefoss-Oslo",
                                            "transportMode": "bus",
                                        }
                                    }
                                }
                            },
                            {
                                "serviceJourney": {
                                    "journeyPattern": {
                                        "line": {
                                            "id": "BRA:Line:4_6200",
                                            "publicCode": "4_6200",
                                            "name": "200 Hønefoss-Oslo",
                                            "transportMode": "bus",
                                        }
                                    }
                                }
                            },
                            {
                                "serviceJourney": {
                                    "journeyPattern": {
                                        "line": {
                                            "id": "GOA:Line:50",
                                            "publicCode": "F5",
                                            "name": "Sørtoget region",
                                            "transportMode": "rail",
                                        }
                                    }
                                }
                            },
                        ]
                    }
                ]
            }
        },
    )

    routes = await async_get_stop_routes(hass, "NSR:StopPlace:548")

    assert [(route.line_id, route.public_code) for route in routes] == [
        ("BRA:Line:4_6200", "4_6200"),
        ("GOA:Line:50", "F5"),
    ]
    assert routes[0].selection_label == "200 BRA (4_6200-BRA)"
    assert routes[1].selection_label == "F5 GOA (50-GOA)"

    method, _, request, headers = aioclient_mock.mock_calls[0]
    assert method == "POST"
    assert request["query"] == STOP_PLACE_LINES_QUERY
    assert request["variables"] == {
        "stopPlaceId": "NSR:StopPlace:548",
        "numberOfDepartures": 50,
    }
    assert headers["ET-Client-Name"] == ENTUR_CLIENT_NAME


async def test_search_stop_places_handles_http_error(
    aioclient_mock, hass: HomeAssistant
) -> None:
    """Test that an HTTP error is exposed as an integration API error."""
    aioclient_mock.get(GEOCODER_AUTOCOMPLETE_URL, status=503)

    with pytest.raises(EnturApiError) as err:
        await async_search_stop_places(hass, "Bergen")
    assert isinstance(err.value.__cause__, ClientResponseError)
