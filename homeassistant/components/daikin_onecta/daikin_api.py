"""Home Assistant adapter for the Daikin Onecta API client."""

import asyncio
from datetime import datetime
import logging
from typing import Any

from daikin_onecta.client import OnectaClient
from daikin_onecta.exceptions import OnectaApiError, OnectaRateLimitError
from daikin_onecta.models import GatewayDevice

from homeassistant import config_entries, core
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class DaikinApi:
    """Home Assistant adapter around the standalone Daikin Onecta client."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ) -> None:
        """Initialize a new Daikin Onecta API."""
        self.hass = hass
        self._config_entry = entry
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, entry, implementation
        )
        self._client = OnectaClient(
            async_get_clientsession(hass), self.async_get_access_token
        )

        # The Daikin cloud can return stale settings immediately after a PATCH.
        # The coordinator uses this timestamp to delay refreshes for its
        # configured scan-ignore period after a successful command.
        self._last_patch_call: datetime | None = None

        # The following lock is used to serialize http requests to Daikin cloud
        # to prevent receiving old settings while a PATCH is ongoing.
        self._cloud_lock = asyncio.Lock()

    @property
    def rate_limits(self) -> dict[str, int | None]:
        """Return rate limits using the existing diagnostics field names."""
        rate_limit = self._client.rate_limit
        return {
            "minute": rate_limit.minute_limit,
            "day": rate_limit.day_limit,
            "remaining_minutes": rate_limit.minute_remaining,
            "remaining_day": rate_limit.day_remaining,
            "retry_after": rate_limit.retry_after,
            "ratelimit_reset": rate_limit.reset,
        }

    @property
    def client(self) -> OnectaClient:
        """Return the underlying Onecta client."""
        return self._client

    @property
    def last_patch_call(self) -> datetime | None:
        """Return when the last successful cloud write completed."""
        return self._last_patch_call

    async def async_get_access_token(self) -> str:
        """Return a valid OAuth access token."""
        await self.session.async_ensure_token_valid()
        return self.session.token["access_token"]

    async def get_cloud_device_details(self) -> list[GatewayDevice]:
        """Get typed device data from the Daikin cloud."""
        async with self._cloud_lock:
            return await self._client.get_gateway_devices()

    async def patch_characteristic(
        self,
        gateway_id: str,
        management_point_id: str,
        characteristic: str,
        value: Any,
        *,
        path: str | None = None,
    ) -> bool:
        """Patch a characteristic through the standalone library."""
        async with self._cloud_lock:
            try:
                await self._client.patch_characteristic(
                    gateway_id,
                    management_point_id,
                    characteristic,
                    value,
                    path=path,
                )
            except OnectaRateLimitError:
                return False
            except OnectaApiError:
                return False
            self._last_patch_call = dt_util.now()
            return True

    async def post_management_point(
        self,
        gateway_id: str,
        management_point_id: str,
        resource: str,
        value: Any,
    ) -> bool:
        """POST a management-point resource through the standalone library."""
        async with self._cloud_lock:
            try:
                await self._client.post_management_point(
                    gateway_id, management_point_id, resource, value
                )
            except OnectaRateLimitError:
                return False
            except OnectaApiError:
                return False
            self._last_patch_call = dt_util.now()
            return True

    async def put_management_point(
        self,
        gateway_id: str,
        management_point_id: str,
        resource: str,
        value: Any = None,
    ) -> bool:
        """PUT a management-point resource through the standalone library."""
        async with self._cloud_lock:
            try:
                await self._client.put_management_point(
                    gateway_id, management_point_id, resource, value
                )
            except OnectaRateLimitError:
                return False
            except OnectaApiError:
                return False
            self._last_patch_call = dt_util.now()
            return True
