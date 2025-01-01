"""The API client for interacting with the Cosa service."""

from datetime import UTC, datetime, timedelta
import json

import aiohttp


class Api:
    """The API client for interacting with the Cosa service."""

    __apiUri = "kiwi.cosa.com.tr"
    __username = None
    __password = None
    __authToken = None

    __lastSuccessfulCall = None
    __LOGIN_TIMEOUT_DELTA = timedelta(minutes=60)

    def __init__(self, username: str, password: str) -> None:
        """Initialize the API client with username and password."""
        self.__username = username
        self.__password = password

    async def async_connection_status(self) -> bool:
        """Check the status of the API client."""
        if self.__is_login_timed_out() and not await self.__async_login():
            return False

        return True

    async def async_get_endpoints(self) -> dict | None:
        """Retrieve the list of endpoints from the Cosa service."""
        data = await self.__async_get("/api/endpoints/getEndpoints")

        if data is not None and "endpoints" in data:
            return data["endpoints"]

        return None

    async def async_get_endpoint(self, endpointId: str) -> dict | None:
        """Retrieve details of a specific endpoint from the Cosa service."""
        payload = {"endpoint": endpointId}

        data = await self.__async_post("/api/endpoints/getEndpoint", payload)

        if data is not None and "endpoint" in data:
            return data["endpoint"]

        return None

    async def async_set_target_temperatures(
        self,
        endpointId: str,
        homeTemp: int,
        awayTemp: int,
        sleepTemp: int,
        customTemp: int,
    ) -> bool:
        """Set the target temperatures for a specific endpoint."""
        payload = {
            "endpoint": endpointId,
            "targetTemperatures": {
                "home": homeTemp,
                "away": awayTemp,
                "sleep": sleepTemp,
                "custom": customTemp,
            },
        }

        data = await self.__async_post("/api/endpoints/setTargetTemperatures", payload)

        if data is not None:
            return True

        return False

    async def async_disable(self, endpointId: str) -> bool:
        """Disable the specified endpoint."""
        payload = {"endpoint": endpointId, "mode": "manual", "option": "frozen"}

        data = await self.__async_post("/api/endpoints/setMode", payload)

        if data is not None:
            return True

        return False

    async def async_enable_schedule(self, endpointId: str) -> bool:
        """Enable the schedule mode for the specified endpoint."""
        payload = {"endpoint": endpointId, "mode": "schedule"}

        data = await self.__async_post("/api/endpoints/setMode", payload)

        if data is not None:
            return True

        return False

    async def async_enable_custom_mode(self, endpointId: str) -> bool:
        """Enable the custom mode for the specified endpoint."""
        payload = {"endpoint": endpointId, "mode": "manual", "option": "custom"}

        data = await self.__async_post("/api/endpoints/setMode", payload)

        if data is not None:
            return True

        return False

    # region Login

    async def __async_login(self) -> bool:
        """Log in to the Cosa service and obtain an authentication token."""
        payload = {"email": self.__username, "password": self.__password}

        data = await self.__async_post_without_auth("/api/users/login", payload)

        if data is not None and "authToken" in data:
            self.__authToken = data["authToken"]
            return True

        self.__authToken = None
        return False

    def __has_auth(self):
        """Check if the API client has an authentication token."""
        return self.__authToken is not None

    def __is_login_timed_out(self) -> bool:
        """Check if the login has timed out."""
        if (
            self.__lastSuccessfulCall is None
            or datetime.now(UTC) - self.__lastSuccessfulCall
            > self.__LOGIN_TIMEOUT_DELTA
        ):
            return True

        return False

    # endregion

    # region Private Call Implementations

    async def __async_post(
        self, endpoint: str, payload: dict, allowRetry: bool = True
    ) -> dict | None:
        if not self.__has_auth() and not await self.__async_login():
            return None

        return await self.__async_post_without_auth(endpoint, payload, allowRetry)

    async def __async_post_without_auth(
        self, endpoint: str, payload: dict, allowRetry: bool = True
    ) -> dict | None:
        payload = json.dumps(payload)
        headers = self.__getHeaders()
        url = f"https://{self.__apiUri}{endpoint}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, data=payload, headers=headers) as res:
                    return await self.__async_get_response_if_success(res)
            except (aiohttp.ClientError, json.JSONDecodeError):
                if allowRetry:
                    return await self.__async_post_without_auth(
                        endpoint, payload, False
                    )
                return None

    async def __async_get(self, endpoint: str, allowRetry: bool = True) -> dict | None:
        if not self.__has_auth() and not await self.__async_login():
            return None

        return self.__async_get_without_auth(endpoint, allowRetry)

    async def __async_get_without_auth(
        self, endpoint: str, allowRetry: bool = True
    ) -> dict | None:
        headers = self.__getHeaders()
        url = f"https://{self.__apiUri}{endpoint}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as res:
                    return await self.__async_get_response_if_success(res)
            except (aiohttp.ClientError, json.JSONDecodeError):
                if allowRetry:
                    return await self.__async_get_without_auth(endpoint, False)
                return None

    def __getHeaders(self):
        """Get the headers for the API request."""
        headers = {"Content-Type": "application/json"}

        if self.__has_auth():
            headers["authToken"] = self.__authToken

        return headers

    async def __async_get_response_if_success(
        self, response: aiohttp.ClientResponse
    ) -> dict | None:
        if response.status != 200:
            return None

        data = await response.json()

        if "ok" in data and data["ok"] == 1:
            self.__lastSuccessfulCall = datetime.now(UTC)
            return data

        return None


# endregion
