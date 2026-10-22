"""Tests for the Google Maps Travel Time integration."""

from typing import Any

from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

COMPUTE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

ROUTES_RESPONSE = {
    "routes": [
        {
            "duration": "1620s",
            "distanceMeters": 21300,
            "localizedValues": {
                "distance": {"text": "21.3 km"},
                "duration": {"text": "27 mins"},
                "staticDuration": {"text": "26 mins"},
            },
        }
    ]
}


def mock_compute_routes(aioclient_mock: AiohttpClientMocker, **kwargs: Any) -> None:
    """Replace the mocked Compute Routes response."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(COMPUTE_ROUTES_URL, **kwargs)
