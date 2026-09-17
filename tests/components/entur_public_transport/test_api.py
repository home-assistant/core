"""Tests for the Entur API helpers."""

from aiohttp import ClientResponseError
import pytest

from homeassistant.components.entur_public_transport.api import (
    EnturApiError,
    async_search_stop_places,
)
from homeassistant.components.entur_public_transport.const import (
    ENTUR_CLIENT_NAME,
    GEOCODER_AUTOCOMPLETE_URL,
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
    assert places[0].selection_label == "Bergen busstasjon, Bergen · bus, rail"
    assert (
        places[0].entur_url
        == "https://entur.no/nearby-stop-place-detail?id=NSR%3AStopPlace%3A548"
    )

    method, url, _, headers = aioclient_mock.mock_calls[0]
    assert method == "get"
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


async def test_search_stop_places_handles_http_error(
    aioclient_mock, hass: HomeAssistant
) -> None:
    """Test that an HTTP error is exposed as an integration API error."""
    aioclient_mock.get(GEOCODER_AUTOCOMPLETE_URL, status=503)

    with pytest.raises(EnturApiError) as err:
        await async_search_stop_places(hass, "Bergen")
    assert isinstance(err.value.__cause__, ClientResponseError)
