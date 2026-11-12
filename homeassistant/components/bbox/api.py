"""Client for the Bouygues Bbox router API.

Targets the local HTTP API of recent Bbox firmwares (``/api/v1/``,
reachable at ``mabbox.bytel.fr``, which the box resolves to itself).
"""

from asyncio import CancelledError, Lock, create_task, gather
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

# Per-request client timeout; the bridge wait (const.REQUEST_TIMEOUT)
# must cover a full request/login/retry chain of these.
DEFAULT_TIMEOUT = 10  # seconds


class BboxError(Exception):
    """Base error for the Bbox API."""


class BboxConnectionError(BboxError):
    """Connection to the Bbox failed."""


class BboxAuthError(BboxError):
    """Authentication against the Bbox failed."""

    def __init__(
        self, message: str, *, start_epoch: int = -1, stale: bool = False
    ) -> None:
        """Initialize the error.

        start_epoch is the login epoch when the rejected request started;
        stale marks a 401 that predates a concurrent successful login, so
        the retry path can re-issue the request without logging in again.
        """
        super().__init__(message)
        self.start_epoch = start_epoch
        self.stale = stale


class BboxRateLimitError(BboxError):
    """Too many login attempts against the Bbox."""


class BboxApi:
    """Client for the Bbox router local API.

    All GET access goes through :meth:`_request`, so timeouts and error
    mapping are defined once for the whole integration; the login POST
    lives in :meth:`login`.
    """

    def __init__(
        self,
        session: ClientSession,
        password: str | None,
        host: str = DEFAULT_HOST,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._password = password
        # Tolerate a trailing slash in the configured host.
        self._host = host.rstrip("/")
        self._timeout = ClientTimeout(total=timeout)
        self._login_lock = Lock()
        # Login single-flight state: _login_epoch counts login attempts,
        # _login_ok_epoch is the epoch of the last successful login and
        # _last_attempt_epoch the epoch of the last attempt (success or
        # failure), so concurrent requests share one login — and one
        # failed login — instead of racing to POST /login.
        self._login_epoch = 0
        self._login_ok_epoch = -1
        self._last_attempt_epoch = 0

    def _url(self, endpoint: str) -> str:
        """Build the full URL of an API endpoint."""
        return f"https://{self._host}/api/v1/{endpoint}"

    async def login(self) -> None:
        """Log in and keep the session cookie on the client's session."""
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
        start_epoch = self._login_epoch
        try:
            async with self._session.get(url, timeout=self._timeout) as response:
                if response.status in (401, 403):
                    _LOGGER.debug("Authentication required by the Bbox for %s", url)
                    raise BboxAuthError(
                        "Authentication required by the Bbox",
                        start_epoch=start_epoch,
                        # A concurrent login may have refreshed the session
                        # while this request was in flight: its 401 is stale.
                        stale=self._login_ok_epoch > start_epoch,
                    )
                if response.status == 429:
                    _LOGGER.debug("The Bbox rate-limited %s", url)
                    raise BboxRateLimitError("Too many Bbox requests")
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

        Logins are single-flight: concurrent 401s share a single
        POST /login — a shared success is reused, a shared failure is
        not retried within the same session epoch, and a 401 that
        predates a concurrent successful login is stale and only retried.
        """
        try:
            return await self._request(endpoint)
        except BboxAuthError as err:
            if not self._password:
                raise
            if not err.stale:
                async with self._login_lock:
                    if (
                        self._login_ok_epoch > err.start_epoch
                        or self._last_attempt_epoch > err.start_epoch
                    ):
                        # A login already happened — or was attempted and
                        # failed — after this request was rejected.
                        pass
                    else:
                        self._login_epoch += 1
                        self._last_attempt_epoch = self._login_epoch
                        _LOGGER.debug("Logging in to the Bbox")
                        await self.login()
                        self._login_ok_epoch = self._login_epoch
        _LOGGER.debug("Retrying %s after login", endpoint)
        return await self._request(endpoint)

    async def get_connected_devices(self) -> list[dict[str, Any]]:
        """Return the devices connected to the main network of the Bbox.

        The endpoint answers with one entry per network (main, guest);
        the main network is the first entry.
        """
        try:
            payload = await self._request_with_login_retry("hosts")
            if isinstance(payload, list):
                payload = payload[0]
            return payload["hosts"]["list"]
        except (KeyError, IndexError, TypeError) as err:
            raise BboxError(
                f"Unexpected Bbox payload from hosts: missing {err}"
            ) from err

    async def get_ip_stats(self) -> dict[str, Any]:
        """Return the WAN throughput stats (kbps) of the Bbox."""
        try:
            payload = await self._request_with_login_retry("wan/ip/stats")
            return payload["wan"]["ip"]["stats"]
        except (KeyError, TypeError) as err:
            raise BboxError(
                f"Unexpected Bbox payload from wan/ip/stats: missing {err}"
            ) from err

    async def get_bbox_info(self) -> dict[str, Any]:
        """Return device information (uptime, serial number, ...)."""
        payload = await self._request_with_login_retry("device")
        if not isinstance(payload, dict):
            raise BboxError(
                f"Unexpected Bbox payload from device: {type(payload).__name__}"
            )
        return payload

    async def get_ip_stats_and_info(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return WAN statistics and device information in one round trip.

        The two endpoints are requested concurrently, so the worst case
        stays a single request/login/retry chain instead of the sum of
        both. On failure, the other request is cancelled: gather
        propagates the first exception without stopping the sibling.
        """
        stats_task = create_task(self.get_ip_stats())
        info_task = create_task(self.get_bbox_info())
        try:
            return await gather(stats_task, info_task)
        except BboxError, CancelledError:
            # A failed gather leaves the sibling request running, and a
            # bridge cancel must keep propagating: stop the other chain
            # (cancelling a finished task is a no-op) and re-raise.
            stats_task.cancel()
            info_task.cancel()
            raise
