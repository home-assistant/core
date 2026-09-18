"""Tests for the Entur API helpers."""

from aiohttp import ClientResponseError
import pytest

from homeassistant.components.entur_public_transport.api import (
    STOP_PLACE_LINES_QUERY,
    STOP_PLACE_QUAYS_QUERY,
    EnturApiError,
    EnturQuay,
    EnturRoute,
    EnturStopPlace,
    _parse_stop_places,
    _parse_stop_quays,
    _parse_stop_routes,
    async_get_stop_place,
    async_get_stop_quays,
    async_get_stop_routes,
    async_search_stop_places,
    format_stop_place_title,
    line_id_label,
)
from homeassistant.components.entur_public_transport.const import (
    ENTUR_CLIENT_NAME,
    GEOCODER_AUTOCOMPLETE_URL,
    GEOCODER_PLACE_URL,
    JOURNEY_PLANNER_URL,
)
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_search_stop_places(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
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
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test that malformed API responses are not silently accepted."""
    aioclient_mock.get(GEOCODER_AUTOCOMPLETE_URL, json={"unexpected": []})

    with pytest.raises(EnturApiError):
        await async_search_stop_places(hass, "Bergen")


async def test_search_stop_places_rejects_invalid_json(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test that invalid JSON from Entur is treated as an API error."""
    aioclient_mock.get(
        GEOCODER_AUTOCOMPLETE_URL,
        text="not valid JSON",
        headers={"Content-Type": "application/json"},
    )

    with pytest.raises(EnturApiError):
        await async_search_stop_places(hass, "Bergen")


async def test_get_stop_place(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
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


async def test_get_stop_routes(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
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


async def test_get_stop_quays(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test retrieving active platforms for one stop place."""
    aioclient_mock.post(
        JOURNEY_PLANNER_URL,
        json={
            "data": {
                "stopPlaces": [
                    {
                        "quays": [
                            {
                                "id": "NSR:Quay:29625",
                                "name": "Hønefoss sentrum",
                                "publicCode": "A",
                            },
                            {
                                "id": "NSR:Quay:29626",
                                "name": "Hønefoss sentrum",
                                "publicCode": "B",
                            },
                            {
                                "id": "NSR:Quay:29625",
                                "name": "Hønefoss sentrum",
                                "publicCode": "A",
                            },
                        ]
                    }
                ]
            }
        },
    )

    quays = await async_get_stop_quays(hass, "NSR:StopPlace:16961")

    assert [(quay.quay_id, quay.selection_label) for quay in quays] == [
        ("NSR:Quay:29625", "A · Hønefoss sentrum"),
        ("NSR:Quay:29626", "B · Hønefoss sentrum"),
    ]

    method, _, request, headers = aioclient_mock.mock_calls[0]
    assert method == "POST"
    assert request["query"] == STOP_PLACE_QUAYS_QUERY
    assert request["variables"] == {"stopPlaceId": "NSR:StopPlace:16961"}
    assert headers["ET-Client-Name"] == ENTUR_CLIENT_NAME


async def test_search_stop_places_handles_http_error(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test that an HTTP error is exposed as an integration API error."""
    aioclient_mock.get(GEOCODER_AUTOCOMPLETE_URL, status=503)

    with pytest.raises(EnturApiError) as err:
        await async_search_stop_places(hass, "Bergen")
    assert isinstance(err.value.__cause__, ClientResponseError)


def test_parse_stop_places_ignores_incomplete_geocoder_features() -> None:
    """Test tolerant parsing of incomplete Geocoder features."""
    places = _parse_stop_places(
        {
            "features": [
                None,
                {},
                {"properties": None},
                {"properties": {"id": "NSR:Quay:1"}},
                {
                    "properties": {
                        "id": "NSR:StopPlace:1",
                        "names": "not a mapping",
                        "address": "not a mapping",
                        "transportModes": [None, {"mode": "bus"}, {"mode": 3}],
                        "stopPlaceRole": 3,
                        "stopPlaceTypes": ["busStation", 3],
                    }
                },
            ]
        }
    )

    assert places == (
        EnturStopPlace(
            stop_id="NSR:StopPlace:1",
            name="NSR:StopPlace:1",
            display_name="NSR:StopPlace:1",
            locality="",
            transport_modes=("bus",),
            role="standalone",
            stop_place_types=("busStation",),
        ),
    )


def test_parse_routes_and_quays_ignores_incomplete_journey_planner_data() -> None:
    """Test tolerant parsing of incomplete route and platform data."""
    routes = _parse_stop_routes(
        {
            "data": {
                "stopPlaces": [
                    None,
                    {},
                    {"estimatedCalls": [None, {}, {"serviceJourney": None}]},
                    {
                        "estimatedCalls": [
                            {
                                "serviceJourney": {
                                    "journeyPattern": {
                                        "line": {
                                            "id": "RUT:Line:1",
                                            "publicCode": "1",
                                            "transportMode": "bus",
                                        }
                                    }
                                }
                            }
                        ]
                    },
                ]
            }
        }
    )
    quays = _parse_stop_quays(
        {
            "data": {
                "stopPlaces": [
                    None,
                    {},
                    {"quays": [None, {}, {"id": "NSR:Quay:1", "name": 3}]},
                    {
                        "quays": [
                            {"id": "NSR:Quay:1", "name": "Platform 1"},
                            {"id": "NSR:Quay:1", "name": "Platform 1"},
                        ]
                    },
                ]
            }
        }
    )

    assert routes == (
        EnturRoute(
            line_id="RUT:Line:1",
            public_code="1",
            transport_mode="bus",
        ),
    )
    assert quays == (
        EnturQuay(quay_id="NSR:Quay:1", name="Platform 1", public_code=None),
    )


def test_route_and_stop_place_labels_cover_fallbacks() -> None:
    """Test labels when Entur supplies no public code or known stop type."""
    route = EnturRoute(line_id="unknown", public_code="", transport_mode="bus", name="")
    place = EnturStopPlace(
        stop_id="NSR:StopPlace:1",
        name="Stop",
        display_name="Stop",
        locality="Stop",
        transport_modes=(),
        role="standalone",
        stop_place_types=("unknown", "unknown"),
    )

    assert route.operator_code == ""
    assert route.technical_id == "unknown"
    assert route.selection_label == "unknown"
    assert EnturQuay("NSR:Quay:1", "Platform 1", None).selection_label == "Platform 1"
    assert place.selection_label == "Stop"
    assert place.type_icons == "🚉"
    assert line_id_label("unknown") == "unknown"
    assert format_stop_place_title("Stop", "🚏", [], {}) == "🚏 Stop · all routes"
