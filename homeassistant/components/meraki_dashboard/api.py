"""API client for the Meraki Dashboard integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import DEFAULT_BASE_URL, DEFAULT_PER_PAGE, DEFAULT_TIMESPAN_SECONDS


class MerakiDashboardApiError(Exception):
    """Raised when the Meraki Dashboard API returns an error."""


class MerakiDashboardApiAuthError(MerakiDashboardApiError):
    """Raised when the Meraki Dashboard API credentials are invalid."""


class MerakiDashboardApiConnectionError(MerakiDashboardApiError):
    """Raised when the Meraki Dashboard API cannot be reached."""


class MerakiDashboardApiRateLimitError(MerakiDashboardApiError):
    """Raised when the Meraki Dashboard API rate limit is hit."""

    def __init__(self, retry_after: float | None) -> None:
        """Initialize the error."""
        super().__init__("Rate limited")
        self.retry_after = retry_after


class MerakiDashboardApi:
    """Meraki Dashboard API client."""

    def __init__(
        self,
        session: ClientSession,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")

    async def _async_get(
        self, path: str, params: Mapping[str, Any] | None = None
    ) -> Any:
        """Perform a GET request against the Meraki Dashboard API."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "X-Cisco-Meraki-API-Key": self._api_key,
            "Accept": "application/json",
        }
        for attempt in range(5):
            try:
                response = await self._session.get(
                    url,
                    headers=headers,
                    params=params,
                    allow_redirects=False,
                )
            except ClientError as err:
                raise MerakiDashboardApiConnectionError("Cannot connect") from err

            async with response:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        raise MerakiDashboardApiError(
                            "Redirect without location header"
                        )
                    url = location
                    params = None
                    continue

                if response.status in (401, 403):
                    raise MerakiDashboardApiAuthError("Invalid API key")
                if response.status == 429:
                    retry_after = _retry_after_seconds(
                        response.headers.get("Retry-After")
                    )
                    if attempt == 4:
                        raise MerakiDashboardApiRateLimitError(retry_after)
                    await asyncio.sleep(
                        retry_after if retry_after is not None else min(2**attempt, 30)
                    )
                    continue
                if response.status >= 400:
                    raise MerakiDashboardApiError(
                        f"Request failed with status {response.status}"
                    )
                if response.status == 204:
                    return None
                return await response.json()

        raise MerakiDashboardApiError("Too many redirects")

    async def _async_post(
        self, path: str, body: Mapping[str, Any] | None = None
    ) -> Any:
        """Perform a POST request against the Meraki Dashboard API."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "X-Cisco-Meraki-API-Key": self._api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        for attempt in range(5):
            try:
                response = await self._session.post(
                    url,
                    headers=headers,
                    json=body,
                    allow_redirects=False,
                )
            except ClientError as err:
                raise MerakiDashboardApiConnectionError("Cannot connect") from err

            async with response:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        raise MerakiDashboardApiError(
                            "Redirect without location header"
                        )
                    url = location
                    continue

                if response.status in (401, 403):
                    raise MerakiDashboardApiAuthError("Invalid API key")
                if response.status == 429:
                    retry_after = _retry_after_seconds(
                        response.headers.get("Retry-After")
                    )
                    if attempt == 4:
                        raise MerakiDashboardApiRateLimitError(retry_after)
                    await asyncio.sleep(
                        retry_after if retry_after is not None else min(2**attempt, 30)
                    )
                    continue
                if response.status >= 400:
                    raise MerakiDashboardApiError(
                        f"Request failed with status {response.status}"
                    )

                if not response.content_length:
                    return None
                return await response.json()

        raise MerakiDashboardApiError("Too many redirects")

    async def async_get_organizations(self) -> list[dict[str, Any]]:
        """Return organizations available to the API key."""
        organizations = await self._async_get("/organizations")
        if not isinstance(organizations, list):
            raise MerakiDashboardApiError("Unexpected organizations payload")
        return organizations

    async def async_get_networks(self, organization_id: str) -> list[dict[str, Any]]:
        """Return networks for a Meraki organization."""
        networks = await self._async_get(f"/organizations/{organization_id}/networks")
        if not isinstance(networks, list):
            raise MerakiDashboardApiError("Unexpected networks payload")
        return networks

    async def async_get_network_clients(
        self,
        network_id: str,
        *,
        timespan: int = DEFAULT_TIMESPAN_SECONDS,
        per_page: int = DEFAULT_PER_PAGE,
    ) -> list[dict[str, Any]]:
        """Return clients for a Meraki network."""
        clients = await self._async_get(
            f"/networks/{network_id}/clients",
            params={"timespan": timespan, "perPage": per_page},
        )
        if not isinstance(clients, list):
            raise MerakiDashboardApiError("Unexpected clients payload")
        return clients

    async def async_get_network_bluetooth_clients(
        self,
        network_id: str,
        *,
        timespan: int = DEFAULT_TIMESPAN_SECONDS,
        per_page: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return Bluetooth clients for a Meraki network."""
        clients = await self._async_get(
            f"/networks/{network_id}/bluetoothClients",
            params={"timespan": timespan, "perPage": per_page},
        )
        if not isinstance(clients, list):
            raise MerakiDashboardApiError("Unexpected Bluetooth clients payload")
        return clients

    async def async_get_organization_devices_statuses(
        self, organization_id: str
    ) -> list[dict[str, Any]]:
        """Return device statuses for an organization."""
        statuses = await self._async_get(
            f"/organizations/{organization_id}/devices/statuses"
        )
        if not isinstance(statuses, list):
            raise MerakiDashboardApiError("Unexpected device statuses payload")
        return statuses

    async def async_get_device_clients(
        self,
        serial: str,
        *,
        timespan: int = DEFAULT_TIMESPAN_SECONDS,
    ) -> list[dict[str, Any]]:
        """Return clients for a single device."""
        clients = await self._async_get(
            f"/devices/{serial}/clients",
            params={"timespan": timespan},
        )
        if not isinstance(clients, list):
            raise MerakiDashboardApiError("Unexpected device clients payload")
        return clients

    async def async_get_device_wireless_status(self, serial: str) -> dict[str, Any]:
        """Return wireless status for an access point."""
        status = await self._async_get(f"/devices/{serial}/wireless/status")
        if not isinstance(status, dict):
            raise MerakiDashboardApiError("Unexpected wireless status payload")
        return status

    async def async_get_device_switch_ports_statuses(
        self,
        serial: str,
        *,
        timespan: int = DEFAULT_TIMESPAN_SECONDS,
    ) -> list[dict[str, Any]]:
        """Return switch port statuses for a switch."""
        ports = await self._async_get(
            f"/devices/{serial}/switch/ports/statuses",
            params={"timespan": timespan},
        )
        if not isinstance(ports, list):
            raise MerakiDashboardApiError("Unexpected switch port statuses payload")
        return ports

    async def async_get_device_appliance_performance(
        self, serial: str
    ) -> dict[str, Any] | None:
        """Return appliance performance for an MX firewall."""
        performance = await self._async_get(f"/devices/{serial}/appliance/performance")
        if performance is None:
            return None
        if not isinstance(performance, dict):
            raise MerakiDashboardApiError("Unexpected appliance performance payload")
        return performance

    async def async_get_organization_wireless_channel_utilization_by_device(
        self,
        organization_id: str,
        network_id: str,
        *,
        timespan: int = DEFAULT_TIMESPAN_SECONDS,
    ) -> list[dict[str, Any]]:
        """Return channel utilization by AP device for a network."""
        utilization = await self._async_get(
            f"/organizations/{organization_id}/wireless/devices/channelUtilization/byDevice",
            params={
                "networkIds[]": network_id,
                "timespan": timespan,
                "interval": 300,
                "perPage": 1000,
            },
        )
        if not isinstance(utilization, list):
            raise MerakiDashboardApiError("Unexpected channel utilization payload")
        return utilization

    async def async_reboot_device(self, serial: str) -> dict[str, Any] | None:
        """Reboot a device by serial."""
        result = await self._async_post(f"/devices/{serial}/reboot")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise MerakiDashboardApiError("Unexpected reboot payload")
        return result

    async def async_ping_device(
        self, serial: str, count: int = 3
    ) -> dict[str, Any] | None:
        """Queue ping-device live tool for a device."""
        result = await self._async_post(
            f"/devices/{serial}/liveTools/pingDevice",
            {"count": count},
        )
        if result is None:
            return None
        if not isinstance(result, dict):
            raise MerakiDashboardApiError("Unexpected ping payload")
        return result


def _retry_after_seconds(raw_retry_after: str | None) -> float | None:
    """Parse Retry-After header to seconds."""
    if raw_retry_after is None:
        return None
    try:
        retry_after = float(raw_retry_after)
    except ValueError:
        return None
    return retry_after if retry_after > 0 else None
