"""Client for the Bouygues Bbox router API.

Targets the local HTTP API of recent Bbox firmwares (``/api/v1/``,
reachable at ``mabbox.bytel.fr``, which the box resolves to itself).
"""

from asyncio import gather
import logging
from typing import Any

from aiohttp import (
    ClientConnectionError,
    ClientError,
    ClientResponseError,
    ClientSession,
)
from aiohttp.client import ClientTimeout

from .const import DEFAULT_HOST

_LOGGER = logging.getLogger(__name__)


class BboxError(Exception):
    """Base error for the Bbox API."""


class BboxConnectionError(BboxError):
    """Connection to the Bbox failed."""


class BboxAuthError(BboxError):
    """Authentication against the Bbox failed."""


class BboxRateLimitError(BboxError):
    """Too many login attempts against the Bbox."""


class BboxApi:
    """Client for the Bbox router local API.

    All HTTP access goes through :meth:`_request`, so timeouts and error
    mapping are defined once for the whole integration.
    """

    def __init__(
        self,
        session: ClientSession,
        password: str | None,
        host: str = DEFAULT_HOST,
        timeout: int = 10,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._password = password
        self._host = host
        self._timeout = ClientTimeout(total=timeout)

    def _url(self, endpoint: str) -> str:
        """Build the full URL of an API endpoint."""
        return f"https://{self._host}/api/v1/{endpoint}"

    async def login(self) -> None:
        """Log in and keep the session cookie on the shared aiohttp session."""
        if not self._password:
            raise BboxAuthError("A password is required to log in to the Bbox")
        url = self._url("login")
        _LOGGER.debug("POST %s", url)
        try:
            async with self._session.post(
                url,
                data={"password": self._password, "remember": "1"},
                headers={"Origin": f"https://{self._host}", "Referer": url},
                timeout=self._timeout,
            ) as response:
                if response.status == 401:
                    raise BboxAuthError("Invalid Bbox password")
                if response.status == 429:
                    raise BboxRateLimitError("Too many Bbox login attempts")
                response.raise_for_status()
        except (ClientConnectionError, TimeoutError) as err:
            _LOGGER.error("Cannot reach Bbox at %s: %s", url, err)
            raise BboxConnectionError(f"Cannot reach Bbox at {url}") from err
        except ClientResponseError as err:
            _LOGGER.error("Bbox returned HTTP %s for %s", err.status, url)
            raise BboxError(f"Bbox login failed with HTTP {err.status}") from err

    async def _request(self, endpoint: str) -> Any:
        """GET an API endpoint and return the parsed JSON payload."""
        url = self._url(endpoint)
        _LOGGER.debug("GET %s", url)
        try:
            async with self._session.get(url, timeout=self._timeout) as response:
                if response.status in (401, 403):
                    _LOGGER.debug("Authentication required by the Bbox for %s", url)
                    raise BboxAuthError("Authentication required by the Bbox")
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientConnectionError, TimeoutError) as err:
            _LOGGER.error("Cannot reach Bbox at %s: %s", url, err)
            raise BboxConnectionError(f"Cannot reach Bbox at {url}") from err
        except ClientResponseError as err:
            _LOGGER.error("Bbox returned HTTP %s for %s", err.status, url)
            raise BboxError(f"Bbox error for {url}: HTTP {err.status}") from err
        except (ClientError, ValueError) as err:
            _LOGGER.error("Bbox returned an invalid payload for %s: %s", url, err)
            raise BboxError(f"Invalid payload from {url}") from err
        # The Bbox API wraps some payloads in a single-element array.
        if isinstance(payload, list) and len(payload) == 1:
            return payload[0]
        return payload

    async def _request_with_login_retry(self, endpoint: str) -> Any:
        """Request an endpoint, logging in and retrying once on 401.

        Some endpoints (e.g. the hosts list) require an authenticated
        session; others answer without it, so authentication is attempted
        only on demand and also serves to refresh an expired session.
        """
        try:
            return await self._request(endpoint)
        except BboxAuthError:
            if not self._password:
                raise
        _LOGGER.debug("Logging in to the Bbox and retrying %s", endpoint)
        await self.login()
        return await self._request(endpoint)

    async def get_connected_devices(self) -> list[dict[str, Any]]:
        """Return the devices connected to the main network of the Bbox.

        The endpoint answers with one entry per network (main, guest);
        the main network is the first entry.
        """
        payload = await self._request_with_login_retry("hosts")
        if isinstance(payload, list):
            payload = payload[0]
        return payload["hosts"]["list"]

    async def get_ip_stats(self) -> dict[str, Any]:
        """Return the WAN throughput stats (kbps) of the Bbox."""
        payload = await self._request_with_login_retry("wan/ip/stats")
        return payload["wan"]["ip"]["stats"]

    async def get_bbox_info(self) -> dict[str, Any]:
        """Return device information (uptime, serial number, ...)."""
        return await self._request_with_login_retry("device")

    async def get_ip_stats_and_info(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return WAN statistics and device information in one round trip.

        The two endpoints are requested concurrently, so the worst case
        stays a single request/login/retry chain instead of the sum of
        both.
        """
        return await gather(self.get_ip_stats(), self.get_bbox_info())
