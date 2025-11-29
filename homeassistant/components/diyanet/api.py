"""Diyanet API client."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://awqatsalah.diyanet.gov.tr"
API_LOGIN_URL = f"{API_BASE_URL}/Auth/Login"
API_REFRESH_TOKEN_URL = f"{API_BASE_URL}/Auth/RefreshToken"
API_PRAYER_TIME_URL = f"{API_BASE_URL}/api/PrayerTime/Daily"

# Token expiration times as per documentation
ACCESS_TOKEN_EXPIRY = timedelta(minutes=30)
REFRESH_TOKEN_EXPIRY = timedelta(minutes=45)


class DiyanetAuthError(HomeAssistantError):
    """Exception to indicate authentication failure."""


class DiyanetConnectionError(HomeAssistantError):
    """Exception to indicate connection failure."""


class DiyanetApiClient:
    """Diyanet API client."""

    def __init__(self, session: ClientSession, email: str, password: str) -> None:
        """Initialize the API client."""
        self._session = session
        self._email = email
        self._password = password
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._access_token_expiry: datetime | None = None
        self._refresh_token_expiry: datetime | None = None

    async def authenticate(self) -> bool:
        """Authenticate with the Diyanet API."""
        try:
            async with self._session.post(
                API_LOGIN_URL,
                json={"email": self._email, "password": self._password},
            ) as response:
                if response.status == 401:
                    raise DiyanetAuthError("Invalid credentials")

                response.raise_for_status()
                data = await response.json()

                if not data.get("success"):
                    raise DiyanetAuthError("Authentication failed")

                self._access_token = data["data"]["accessToken"]
                self._refresh_token = data["data"]["refreshToken"]

                # Set token expiry times according to documentation
                now = datetime.now()
                self._access_token_expiry = now + ACCESS_TOKEN_EXPIRY
                self._refresh_token_expiry = now + REFRESH_TOKEN_EXPIRY

                _LOGGER.debug("Authentication successful, tokens acquired")
                return True
        except ClientError as err:
            raise DiyanetConnectionError(f"Connection error: {err}") from err

    async def _refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token."""
        if not self._refresh_token:
            _LOGGER.debug("No refresh token available, performing full authentication")
            return await self.authenticate()

        try:
            async with self._session.get(
                f"{API_REFRESH_TOKEN_URL}/{self._refresh_token}",
            ) as response:
                if response.status == 401:
                    _LOGGER.debug(
                        "Refresh token expired, performing full authentication"
                    )
                    return await self.authenticate()

                response.raise_for_status()
                data = await response.json()

                if not data.get("success"):
                    _LOGGER.debug(
                        "Token refresh failed, performing full authentication"
                    )
                    return await self.authenticate()

                self._access_token = data["data"]["accessToken"]
                self._refresh_token = data["data"]["refreshToken"]

                # Update token expiry times
                now = datetime.now()
                self._access_token_expiry = now + ACCESS_TOKEN_EXPIRY
                self._refresh_token_expiry = now + REFRESH_TOKEN_EXPIRY

                _LOGGER.debug("Access token refreshed successfully")
                return True
        except ClientError as err:
            _LOGGER.warning(
                "Error refreshing token: %s, performing full authentication", err
            )
            return await self.authenticate()

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token."""
        now = datetime.now()

        # If no tokens or refresh token expired, do full authentication
        if (
            self._access_token is None
            or self._refresh_token_expiry is None
            or now >= self._refresh_token_expiry
        ):
            await self.authenticate()
            return

        # If access token expired but refresh token still valid, refresh
        if self._access_token_expiry is None or now >= self._access_token_expiry:
            await self._refresh_access_token()

    async def get_prayer_times(self, location_id: int) -> dict[str, Any]:
        """Get prayer times for a location."""
        await self._ensure_authenticated()

        try:
            headers = {"Authorization": f"Bearer {self._access_token}"}
            async with self._session.get(
                f"{API_PRAYER_TIME_URL}/{location_id}",
                headers=headers,
            ) as response:
                if response.status == 401:
                    # Token expired, refresh and retry
                    _LOGGER.debug("Token expired during request, refreshing")
                    await self._refresh_access_token()
                    headers = {"Authorization": f"Bearer {self._access_token}"}
                    async with self._session.get(
                        f"{API_PRAYER_TIME_URL}/{location_id}",
                        headers=headers,
                    ) as retry_response:
                        retry_response.raise_for_status()
                        data = await retry_response.json()
                else:
                    response.raise_for_status()
                    data = await response.json()

                if not data.get("success"):
                    raise DiyanetConnectionError("Failed to get prayer times")

                # Return the first day's data
                if data.get("data") and len(data["data"]) > 0:
                    return data["data"][0]

                raise DiyanetConnectionError("No prayer time data available")

        except ClientError as err:
            raise DiyanetConnectionError(f"Connection error: {err}") from err
