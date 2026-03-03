"""API client for the Cosa smart thermostat service."""

from datetime import UTC, datetime, timedelta
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

API_HOST = "kiwi.cosa.com.tr"
LOGIN_TIMEOUT = timedelta(minutes=60)


class CosaApiError(Exception):
    """Base exception for Cosa API errors."""


class CosaAuthError(CosaApiError):
    """Exception for authentication failures."""


class CosaConnectionError(CosaApiError):
    """Exception for connection failures."""


class CosaApi:
    """API client for interacting with the Cosa service."""

    def __init__(
        self, username: str, password: str, session: aiohttp.ClientSession
    ) -> None:
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._session = session
        self._auth_token: str | None = None
        self._last_successful_call: datetime | None = None

    async def async_check_connection(self) -> bool:
        """Check the connection status by attempting login.

        Raises CosaAuthError on invalid credentials.
        Raises CosaConnectionError on network issues.
        """
        await self._async_login()
        return True

    async def async_get_endpoints(self) -> list[dict]:
        """Retrieve the list of endpoints from the Cosa service."""
        data = await self._async_get("/api/endpoints/getEndpoints")
        if data is not None and "endpoints" in data:
            return data["endpoints"]
        return []

    async def async_get_endpoint(self, endpoint_id: str) -> dict | None:
        """Retrieve details of a specific endpoint."""
        payload = {"endpoint": endpoint_id}
        data = await self._async_post("/api/endpoints/getEndpoint", payload)
        if data is not None and "endpoint" in data:
            return data["endpoint"]
        return None

    async def async_set_target_temperatures(
        self,
        endpoint_id: str,
        home_temp: int,
        away_temp: int,
        sleep_temp: int,
        custom_temp: int,
    ) -> bool:
        """Set the target temperatures for a specific endpoint."""
        payload = {
            "endpoint": endpoint_id,
            "targetTemperatures": {
                "home": home_temp,
                "away": away_temp,
                "sleep": sleep_temp,
                "custom": custom_temp,
            },
        }
        data = await self._async_post("/api/endpoints/setTargetTemperatures", payload)
        return data is not None

    async def async_disable(self, endpoint_id: str) -> bool:
        """Disable the specified endpoint (set to frozen mode)."""
        payload = {
            "endpoint": endpoint_id,
            "mode": "manual",
            "option": "frozen",
        }
        data = await self._async_post("/api/endpoints/setMode", payload)
        return data is not None

    async def async_enable_schedule(self, endpoint_id: str) -> bool:
        """Enable the schedule mode for the specified endpoint."""
        payload = {"endpoint": endpoint_id, "mode": "schedule"}
        data = await self._async_post("/api/endpoints/setMode", payload)
        return data is not None

    async def async_enable_custom_mode(self, endpoint_id: str) -> bool:
        """Enable the custom (manual heating) mode for the specified endpoint."""
        payload = {
            "endpoint": endpoint_id,
            "mode": "manual",
            "option": "custom",
        }
        data = await self._async_post("/api/endpoints/setMode", payload)
        return data is not None

    async def _async_login(self) -> None:
        """Log in to the Cosa service and obtain an authentication token.

        Raises CosaAuthError on invalid credentials.
        Raises CosaConnectionError on network issues.
        """
        payload = {"email": self._username, "password": self._password}
        url = f"https://{API_HOST}/api/users/login"
        headers = {"Content-Type": "application/json"}
        try:
            async with self._session.post(url, json=payload, headers=headers) as res:
                if res.status != 200:
                    raise CosaAuthError(f"Login failed with status {res.status}")
                data = await res.json()
        except aiohttp.ClientError as err:
            raise CosaConnectionError(f"Connection error during login: {err}") from err

        if not isinstance(data, dict) or data.get("ok") != 1 or "authToken" not in data:
            raise CosaAuthError("Invalid credentials")

        self._auth_token = data["authToken"]
        self._last_successful_call = datetime.now(UTC)

    def _is_login_timed_out(self) -> bool:
        """Check if the login has timed out."""
        return (
            self._last_successful_call is None
            or datetime.now(UTC) - self._last_successful_call > LOGIN_TIMEOUT
        )

    async def _async_ensure_logged_in(self) -> None:
        """Ensure we have a valid auth token."""
        if self._is_login_timed_out():
            await self._async_login()

    async def _async_post(self, endpoint: str, payload: dict) -> dict | None:
        """Make an authenticated POST request."""
        await self._async_ensure_logged_in()
        headers = self._get_headers()
        url = f"https://{API_HOST}{endpoint}"
        try:
            async with self._session.post(url, json=payload, headers=headers) as res:
                return await self._async_parse_response(res)
        except aiohttp.ClientError:
            _LOGGER.debug("POST request to %s failed", endpoint)
            return None

    async def _async_get(self, endpoint: str) -> dict | None:
        """Make an authenticated GET request."""
        await self._async_ensure_logged_in()
        headers = self._get_headers()
        url = f"https://{API_HOST}{endpoint}"
        try:
            async with self._session.get(url, headers=headers) as res:
                return await self._async_parse_response(res)
        except aiohttp.ClientError:
            _LOGGER.debug("GET request to %s failed", endpoint)
            return None

    def _get_headers(self) -> dict[str, str]:
        """Get the headers for an API request."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._auth_token is not None:
            headers["authToken"] = self._auth_token
        return headers

    async def _async_parse_response(
        self, response: aiohttp.ClientResponse
    ) -> dict | None:
        """Parse and validate an API response."""
        if response.status != 200:
            return None
        data = await response.json()
        if isinstance(data, dict) and data.get("ok") == 1:
            self._last_successful_call = datetime.now(UTC)
            return data
        return None
