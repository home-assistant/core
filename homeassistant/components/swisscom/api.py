"""Lightweight client for the Swisscom Internet-Box web-services endpoint."""

from typing import Any

import aiohttp

CONTENT_TYPE = "application/x-sah-ws-4-call+json"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class SwisscomError(Exception):
    """Base error for the Swisscom Internet-Box client."""


class SwisscomAuthError(SwisscomError):
    """Authentication with the Internet-Box failed."""


class SwisscomConnectionError(SwisscomError):
    """Communication with the Internet-Box failed."""


class SwisscomClient:
    """Authenticated client for the Internet-Box web-services endpoint."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._url = f"http://{host}/ws"
        self._username = username
        self._password = password
        self._context_id: str | None = None

    async def _post(
        self, payload: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        """POST a request and return the parsed JSON body."""
        try:
            async with self._session.post(
                self._url,
                json=payload,
                headers={"Content-Type": CONTENT_TYPE, **headers},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status == 401:
                    raise SwisscomAuthError("Unauthorized")
                response.raise_for_status()
                return await response.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError) as err:
            raise SwisscomConnectionError(str(err)) from err

    async def login(self) -> None:
        """Authenticate and store a context ID."""
        data = await self._post(
            {
                "service": "sah.Device.Information",
                "method": "createContext",
                "parameters": {
                    "applicationName": "webui",
                    "username": self._username,
                    "password": self._password,
                },
            },
            {"Authorization": "X-Sah-Login"},
        )
        try:
            self._context_id = data["data"]["contextID"]
        except (KeyError, TypeError) as err:
            raise SwisscomAuthError("Unexpected authentication response") from err

    async def get_device_info(self) -> dict[str, Any]:
        """Return the box's `DeviceInfo` (unauthenticated)."""
        data = await self._post(
            {"service": "DeviceInfo", "method": "get", "parameters": {}}, {}
        )
        return data.get("status", {})

    async def get_devices(self) -> list[dict[str, Any]]:
        """Return the list of LAN devices known to the box.

        Re-authenticates once on context expiry.
        """
        if self._context_id is None:
            await self.login()

        for attempt in range(2):
            assert self._context_id is not None
            try:
                data = await self._post(
                    {
                        "service": "Devices",
                        "method": "get",
                        "parameters": {"expression": "lan and not self"},
                    },
                    {
                        "Authorization": f"X-Sah {self._context_id}",
                        "X-Context": self._context_id,
                    },
                )
            except SwisscomAuthError:
                if attempt == 0:
                    await self.login()
                    continue
                raise
            return data.get("status", [])
        return []
