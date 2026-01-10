"""API client for SMN Argentina weather service."""

from __future__ import annotations

import asyncio
import base64
import binascii
from datetime import datetime, timedelta
import json
import logging
import re
from typing import Any

import aiohttp

from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    API_ALERT_ENDPOINT,
    API_COORD_ENDPOINT,
    API_FORECAST_ENDPOINT,
    API_HEAT_WARNING_ENDPOINT,
    API_SHORTTERM_ALERT_ENDPOINT,
    API_WEATHER_ENDPOINT,
    TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)


class SMNTokenManager:
    """Manage JWT token for SMN API authentication."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the token manager."""
        self._session = session
        self._token: str | None = None
        self._token_expiration: datetime | None = None

    def _decode_jwt_payload(self, token: str) -> dict[str, Any]:
        """Decode JWT payload without verification."""
        try:
            # Split the JWT into parts
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid JWT format")  # noqa: TRY301

            # Decode the payload (second part)
            # Add padding if needed
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding

            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
        except (ValueError, json.JSONDecodeError, binascii.Error) as err:
            _LOGGER.error("Error decoding JWT: %s", err)
            return {}

    async def fetch_token(self) -> str:
        """Fetch JWT token from SMN website."""
        try:
            _LOGGER.debug("Fetching JWT token from %s", TOKEN_URL)
            async with asyncio.timeout(10):
                response = await self._session.get(TOKEN_URL)
                response.raise_for_status()
                html = await response.text()

                _LOGGER.debug("Received HTML response, length: %d bytes", len(html))

                # Extract token from localStorage.setItem('token', 'eyJ...')
                # SMN always uses this exact format in a script tag
                pattern = (
                    r"localStorage\.setItem\(['\"]token['\"]\s*,\s*['\"]([^'\"]+)['\"]"
                )
                match = re.search(pattern, html)

                if not match:
                    raise UpdateFailed(  # noqa: TRY301
                        "Could not find token in HTML. Check logs for details"
                    )

                token = match.group(1)
                _LOGGER.info("Found token (length: %d)", len(token))

                # Decode token to get expiration
                payload = self._decode_jwt_payload(token)
                if "exp" in payload:
                    self._token_expiration = datetime.fromtimestamp(
                        payload["exp"], tz=dt_util.UTC
                    )
                    _LOGGER.info(
                        "Token expires at: %s", self._token_expiration.isoformat()
                    )
                else:
                    _LOGGER.warning("Token does not contain expiration field")

                self._token = token
                return token

        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP error fetching token from %s: %s", TOKEN_URL, err)
            raise UpdateFailed(f"Error fetching token: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching token")
            raise UpdateFailed(f"Unexpected error fetching token: {err}") from err

    async def get_token(self) -> str:
        """Get valid token, refreshing if necessary."""
        # Check if we have a token and it's still valid
        if self._token and self._token_expiration:
            # Refresh if token expires in less than 5 minutes
            if dt_util.utcnow() < (self._token_expiration - timedelta(minutes=5)):
                return self._token

        # Fetch new token
        return await self.fetch_token()

    @property
    def token_expiration(self) -> datetime | None:
        """Return token expiration time."""
        return self._token_expiration


class SMNApiClient:
    """API client for SMN Argentina weather service."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token_manager: SMNTokenManager,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._token_manager = token_manager

    async def _get_headers(self) -> dict[str, str]:
        """Get headers with authentication token."""
        try:
            token = await self._token_manager.get_token()
            _LOGGER.debug(
                "Using token for API request (first 20 chars): %s", token[:20]
            )
        except Exception as err:
            _LOGGER.error("Failed to get authentication token: %s", err)
            raise
        else:
            return {
                "Authorization": f"JWT {token}",
                "Accept": "application/json",
            }

    async def async_get_location(
        self, latitude: float, longitude: float
    ) -> dict[str, Any]:
        """Get location ID from coordinates."""
        url = f"{API_COORD_ENDPOINT}?lat={latitude}&lon={longitude}"
        headers = await self._get_headers()

        try:
            _LOGGER.debug("Fetching location ID from: %s", url)
            async with asyncio.timeout(10):
                response = await self._session.get(url, headers=headers)

                if response.status == 401:
                    response_text = await response.text()
                    _LOGGER.error(
                        "401 Unauthorized when fetching location ID. Response: %s",
                        response_text[:200],
                    )

                response.raise_for_status()
                data = await response.json()

                _LOGGER.debug("Location API response: %s", data)
                return data

        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP error fetching location ID: %s", err)
            raise UpdateFailed(f"Error fetching location ID: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching location ID")
            raise UpdateFailed(f"Unexpected error fetching location ID: {err}") from err

    async def async_get_current_weather(self, location_id: str) -> dict[str, Any]:
        """Fetch current weather data."""
        url = f"{API_WEATHER_ENDPOINT}/{location_id}"
        headers = await self._get_headers()

        try:
            _LOGGER.debug("Fetching current weather from: %s", url)
            async with asyncio.timeout(10):
                response = await self._session.get(url, headers=headers)
                response.raise_for_status()
                data = await response.json()

                _LOGGER.debug("Current weather response: %s", data)
                return data

        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching current weather: %s", err)
            raise UpdateFailed(f"Error fetching current weather: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching current weather")
            raise UpdateFailed(
                f"Unexpected error fetching current weather: {err}"
            ) from err

    async def async_get_forecast(self, location_id: str) -> dict[str, Any]:
        """Fetch forecast data."""
        url = f"{API_FORECAST_ENDPOINT}/{location_id}"
        headers = await self._get_headers()

        try:
            _LOGGER.debug("Fetching forecast from: %s", url)
            async with asyncio.timeout(10):
                response = await self._session.get(url, headers=headers)
                response.raise_for_status()
                data = await response.json()

                _LOGGER.debug("Forecast response: %s", data)
                return data

        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching forecast: %s", err)
            raise UpdateFailed(f"Error fetching forecast: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching forecast")
            raise UpdateFailed(f"Unexpected error fetching forecast: {err}") from err

    async def async_get_alerts(self, location_id: str) -> dict[str, Any]:
        """Fetch weather alerts."""
        url = f"{API_ALERT_ENDPOINT}/{location_id}"
        headers = await self._get_headers()

        try:
            async with asyncio.timeout(10):
                response = await self._session.get(url, headers=headers)
                response.raise_for_status()
                data = await response.json()

                _LOGGER.debug(
                    "Fetched alerts for location %s: %d warnings",
                    location_id,
                    len(data.get("warnings", [])) if isinstance(data, dict) else 0,
                )
                return data if isinstance(data, dict) else {}

        except aiohttp.ClientError as err:
            _LOGGER.debug("Error fetching alerts (may be normal if none): %s", err)
            return {}
        except Exception:
            _LOGGER.exception("Unexpected error fetching alerts")
            return {}

    async def async_get_shortterm_alerts(
        self, location_id: str
    ) -> list[dict[str, Any]]:
        """Fetch short-term severe weather alerts."""
        url = f"{API_SHORTTERM_ALERT_ENDPOINT}/{location_id}"
        headers = await self._get_headers()

        try:
            async with asyncio.timeout(10):
                response = await self._session.get(url, headers=headers)
                response.raise_for_status()
                data = await response.json()

                _LOGGER.debug(
                    "Fetched %d short-term alerts for location %s",
                    len(data) if isinstance(data, list) else 0,
                    location_id,
                )
                return data if isinstance(data, list) else []

        except aiohttp.ClientError as err:
            _LOGGER.debug(
                "Error fetching short-term alerts (may be normal if none): %s", err
            )
            return []
        except Exception:
            _LOGGER.exception("Unexpected error fetching short-term alerts")
            return []

    async def async_get_heat_warnings(self, area_id: str) -> dict[str, Any]:
        """Fetch heat warnings."""
        url = f"{API_HEAT_WARNING_ENDPOINT}/{area_id}"
        headers = await self._get_headers()

        try:
            async with asyncio.timeout(10):
                response = await self._session.get(url, headers=headers)
                response.raise_for_status()
                data = await response.json()

                _LOGGER.debug(
                    "Fetched heat warning for area %s: level=%s",
                    area_id,
                    data.get("level") if isinstance(data, dict) else None,
                )
                return data if isinstance(data, dict) else {}

        except aiohttp.ClientError as err:
            _LOGGER.debug(
                "Error fetching heat warnings (may be normal if none): %s", err
            )
            return {}
        except Exception:
            _LOGGER.exception("Unexpected error fetching heat warnings")
            return {}
