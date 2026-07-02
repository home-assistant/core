"""Client for Willow API."""

from typing import Any

from aiohttp import ClientResponseError, ClientSession

from .const import GET_DEVICES_URL, GET_PROFILE_URL
from .exceptions import WillowAuthError


class WillowClient:
    """Client for the Willow API."""

    def __init__(self, session: ClientSession, token: str) -> None:
        """Initialize the Willow client."""
        self._session = session
        self._token = token

    def update_token(self, token: str) -> None:
        """Update the access token."""
        self._token = token

    async def get_profile(self) -> dict[str, Any]:
        """Get the user profile."""
        return await self._async_request("GET", GET_PROFILE_URL)

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get the paired devices."""
        return await self._async_request("GET", GET_DEVICES_URL)

    async def _async_request(self, method: str, url: str) -> Any:
        """Make an authenticated request to the Willow API."""
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with self._session.request(
                method, url, headers=headers, raise_for_status=True
            ) as resp:
                return await resp.json()
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise WillowAuthError from err
            raise
