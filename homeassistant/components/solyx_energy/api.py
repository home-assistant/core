"""HTTP API functions for updating and retrieving data from the Solyx Energy cloud environment."""

from http import HTTPStatus
import logging
import time
from typing import Any

import aiohttp

from .const import BASE_URL, REALM_ID

_LOGGER = logging.getLogger(__name__)


class SolyxEnergyError(Exception):
    """Base error for the Solyx Energy API client."""


class SolyxEnergyAuthError(SolyxEnergyError):
    """Error related to authentication or authorization failures (HTTP 401/403)."""


class SolyxEnergyTokenError(SolyxEnergyError):
    """Error during access token retrieval from the Solyx Energy cloud environment."""


class SolyxEnergyDataError(SolyxEnergyError):
    """Error during data retrieval from the Solyx Energy cloud environment."""


class SolyxEnergyWriteError(SolyxEnergyError):
    """Error when pushing a value to the Solyx Energy cloud environment."""


class SolyxEnergyApiClient:
    """HTTP API client with OAuth2 authentication to the Solyx Energy cloud environment."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        nymo_client_id: str,
        nymo_client_secret: str,
    ) -> None:
        """Initialize the Solyx Energy API client."""
        self._session = session
        self._nymo_client_id = nymo_client_id
        self._nymo_client_secret = nymo_client_secret
        self._access_token: str | None = None
        self._token_expiry: float = 0.0

    async def _async_update_access_token(self) -> None:
        """Obtain the access token from the Keycloak HTTP token endpoint."""
        if self._access_token and time.monotonic() < self._token_expiry - 30:
            _LOGGER.debug("Access token still valid, skipping refresh")
            return

        request_url = f"{BASE_URL}/auth/realms/{REALM_ID}/protocol/openid-connect/token"
        request_data = {
            "grant_type": "client_credentials",
            "client_id": self._nymo_client_id,
            "client_secret": self._nymo_client_secret,
        }
        try:
            async with self._session.post(
                request_url,
                data=request_data,
            ) as resp:
                if resp.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                    raise SolyxEnergyAuthError(
                        f"Token request failed due to an authentication error (HTTP {resp.status})."
                    ) from None
                if resp.status != HTTPStatus.OK:
                    raise SolyxEnergyTokenError(
                        f"Token request failed with HTTP {resp.status}"
                    ) from None

                response_payload = await resp.json()
                self._access_token = response_payload["access_token"]
                self._token_expiry = time.monotonic() + response_payload.get(
                    "expires_in", 300
                )

        except aiohttp.ClientError as err:
            raise SolyxEnergyTokenError(
                f"Token request failed due to a communication error: {err}"
            ) from err
        except TimeoutError as err:
            raise SolyxEnergyTokenError(
                f"Token request failed due to a timeout: {err}"
            ) from err
        except (KeyError, TypeError, ValueError) as err:
            raise SolyxEnergyTokenError(
                f"Token request failed due to a parsing error: {err}"
            ) from err

        _LOGGER.debug("Access token refreshed successfully")

    def _get_auth_headers(self) -> dict[str, str]:
        """Retrieve the authorization header for HTTP requests to the Solyx Energy cloud environment."""
        return {"Authorization": f"Bearer {self._access_token}"}

    async def async_get_asset_data(self, asset_id: str) -> dict[str, Any]:
        """Fetch asset/device data from the Solyx Energy cloud environment."""
        await self._async_update_access_token()

        request_url = f"{BASE_URL}/api/{REALM_ID}/asset/{asset_id}"
        try:
            async with self._session.get(
                request_url,
                headers=self._get_auth_headers(),
            ) as response:
                if response.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                    self._access_token = None
                    raise SolyxEnergyAuthError(
                        "Failed to retrieve device data from Solyx Energy cloud; unauthorized."
                    ) from None
                if response.status != HTTPStatus.OK:
                    raise SolyxEnergyDataError(
                        f"Failed to retrieve device data from Solyx Energy cloud; error {response.status}"
                    ) from None
                response_payload = await response.json()
                if not isinstance(response_payload, dict):
                    raise SolyxEnergyDataError(
                        "Failed to retrieve device data due to an invalid response"
                    ) from None
                return response_payload

        except aiohttp.ClientError as err:
            raise SolyxEnergyDataError(
                f"Failed to retrieve device data from Solyx Energy cloud; {err}"
            ) from err
        except TimeoutError as err:
            raise SolyxEnergyDataError(
                "Failed to retrieve device data from Solyx Energy cloud; request timed out."
            ) from err
        except ValueError as err:
            raise SolyxEnergyDataError(
                f"Failed to retrieve device data due to a parsing error: {err}"
            ) from err

    async def async_set_asset_attribute(
        self,
        asset_id: str,
        attribute_name: str,
        value: object,
    ) -> None:
        """Push a new attribute value to the Solyx Energy cloud environment."""
        await self._async_update_access_token()
        request_url = (
            f"{BASE_URL}/api/{REALM_ID}/asset/{asset_id}/attribute/{attribute_name}"
        )
        try:
            async with self._session.put(
                request_url,
                headers={
                    **self._get_auth_headers(),
                    "Content-Type": "application/json",
                },
                json=value,
            ) as response:
                if response.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                    self._access_token = None
                    raise SolyxEnergyAuthError(
                        "Failed to write device data to Solyx Energy cloud; unauthorized."
                    ) from None
                if response.status != HTTPStatus.OK:
                    raise SolyxEnergyWriteError(
                        f"Failed to write device data to Solyx Energy cloud; error {response.status}"
                    ) from None

                _LOGGER.debug(
                    "%s has successfully been updated to %s", attribute_name, value
                )

        except aiohttp.ClientError as err:
            raise SolyxEnergyWriteError(
                f"Failed to write device data to Solyx Energy cloud; {err}"
            ) from err
        except TimeoutError as err:
            raise SolyxEnergyWriteError(
                "Failed to write device data to Solyx Energy cloud; request timed out."
            ) from err

    async def async_test_connection(self, device_id: str) -> None:
        """Validate credentials and the existence of the Device ID by fetching data, and catching any HTTP errors."""
        await self.async_get_asset_data(device_id)
