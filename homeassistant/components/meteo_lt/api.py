"""API client for Meteo.lt integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_BASE_URL, API_TIMEOUT
from .models import Forecast, Place

_LOGGER = logging.getLogger(__name__)


class MeteoLtApiError(Exception):
    """General API error."""


class MeteoLtApiConnectionError(MeteoLtApiError):
    """API connection error."""


class MeteoLtApiRateLimitError(MeteoLtApiError):
    """API rate limit error."""


class MeteoLtApi:
    """API client for Meteo.lt."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API client."""
        self.hass = hass
        self._session = async_get_clientsession(hass)

    async def _request(self, endpoint: str) -> dict[str, Any]:
        """Make an API request."""
        url = f"{API_BASE_URL}/{endpoint}"

        try:
            async with async_timeout.timeout(API_TIMEOUT):
                response = await self._session.get(url)

                if response.status == 429:
                    raise MeteoLtApiRateLimitError("Rate limit exceeded")

                if response.status == 404:
                    raise MeteoLtApiError(f"Endpoint not found: {endpoint}")

                response.raise_for_status()
                return await response.json()

        except TimeoutError as err:
            raise MeteoLtApiConnectionError("Request timeout") from err
        except aiohttp.ClientError as err:
            raise MeteoLtApiConnectionError(f"Connection error: {err}") from err
        except Exception as err:
            raise MeteoLtApiError(f"Unexpected error: {err}") from err

    async def get_places(self) -> list[Place]:
        """Get list of available places."""
        _LOGGER.debug("Fetching places from API")
        data = await self._request("places")

        places = []
        for place_data in data:
            try:
                places.append(Place.from_dict(place_data))
            except (KeyError, ValueError) as err:
                _LOGGER.warning("Failed to parse place data: %s", err)
                continue

        _LOGGER.debug("Retrieved %d places", len(places))
        return places

    async def get_place(self, place_code: str) -> Place:
        """Get detailed information about a specific place."""
        _LOGGER.debug("Fetching place details for: %s", place_code)
        data = await self._request(f"places/{place_code}")
        return Place.from_dict(data)

    async def get_forecast(self, place_code: str) -> Forecast:
        """Get weather forecast for a place."""
        _LOGGER.debug("Fetching forecast for place: %s", place_code)
        data = await self._request(f"places/{place_code}/forecasts/long-term")
        return Forecast.from_dict(data)

    async def test_connection(self) -> bool:
        """Test API connection."""
        try:
            await self._request("places")
            return True
        except MeteoLtApiError:
            return False
