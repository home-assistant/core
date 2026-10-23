"""Tests for the Google Maps Travel Time client against a mocked Routes API."""

from typing import Any

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.google_travel_time.const import DEFAULT_NAME, DOMAIN
from homeassistant.core import HomeAssistant

from .const import DEFAULT_OPTIONS, MOCK_CONFIG, MOCK_CONFIG_REFERRER

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


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


async def _setup_config_entry(
    hass: HomeAssistant, data: dict[str, Any]
) -> MockConfigEntry:
    """Set up a Google Travel Time config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data=data,
        options=DEFAULT_OPTIONS,
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def _call_get_travel_times(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> dict:
    """Call the get_travel_times service."""
    return await hass.services.async_call(
        DOMAIN,
        "get_travel_times",
        {
            "config_entry_id": config_entry.entry_id,
            "origin": "location1",
            "destination": "location2",
            "mode": "driving",
            "units": "metric",
        },
        blocking=True,
        return_response=True,
    )


async def test_service_referrer_sent_to_api(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the Referer header is sent for referrer-restricted API keys."""
    aioclient_mock.post(ROUTES_URL, json=_mock_routes_response())
    config_entry = await _setup_config_entry(hass, MOCK_CONFIG_REFERRER)

    response_data = await _call_get_travel_times(hass, config_entry)
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
    # One request for the sensor's first update and one for the service call
    assert aioclient_mock.call_count == 2
    assert (
        aioclient_mock.mock_calls[0][3]["X-Goog-FieldMask"]
        == "routes.duration,routes.localizedValues"
    )
    method, url, _data, headers = aioclient_mock.mock_calls[-1]
    assert method == "POST"
    assert str(url) == ROUTES_URL
    assert headers["Referer"] == "https://example.com/"
    assert headers["X-Goog-Api-Key"] == "api_key"
    assert (
        headers["X-Goog-FieldMask"]
        == "routes.duration,routes.distanceMeters,routes.localizedValues"
    )


async def test_service_no_referrer_sent_to_api(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the Referer header is not sent without a referrer restricted key."""
    aioclient_mock.post(ROUTES_URL, json=_mock_routes_response())
    config_entry = await _setup_config_entry(hass, MOCK_CONFIG)

    response_data = await _call_get_travel_times(hass, config_entry)
    assert len(response_data["routes"]) == 1
    assert aioclient_mock.call_count == 2
    method, url, _data, headers = aioclient_mock.mock_calls[-1]
    assert method == "POST"
    assert str(url) == ROUTES_URL
    assert "Referer" not in headers
    assert headers["X-Goog-Api-Key"] == "api_key"
