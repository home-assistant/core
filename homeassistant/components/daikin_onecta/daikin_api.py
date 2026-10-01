"""Home Assistant adapter for the Daikin Onecta API client."""

import asyncio
from datetime import datetime
import logging
from typing import Any

from daikin_onecta import (
    GatewayDevice,
    OnectaApiError,
    OnectaClient,
    OnectaRateLimitError,
)

from homeassistant import config_entries, core
from homeassistant.helpers import config_entry_oauth2_flow, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN

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

        # The Daikin cloud returns old settings if queried with a GET
        # immediately after a PATCH request. Se we use this attribute
        # to check when we had the last patch command, if it is less then
        # 10 seconds ago we skip the get
        # self._last_patch_call = dt_util.as_local(datetime.min)
        self._last_patch_call: datetime | None = None

        # The following lock is used to serialize http requests to Daikin cloud
        # to prevent receiving old settings while a PATCH is ongoing.
        self._cloud_lock = asyncio.Lock()

    @property
    def last_patch_call(self) -> datetime | None:
        """Return the timestamp of the last successful write."""
        return self._last_patch_call

    @property
    def rate_limits(self) -> dict[str, int]:
        """Return rate limits using the existing diagnostics field names."""
        rate_limit = self._client.rate_limit
        return {
            "minute": rate_limit.minute_limit or 0,
            "day": rate_limit.day_limit or 0,
            "remaining_minutes": rate_limit.minute_remaining or 0,
            "remaining_day": rate_limit.day_remaining or 0,
            "retry_after": rate_limit.retry_after or 0,
            "ratelimit_reset": rate_limit.reset or 0,
        }

    async def async_get_access_token(self) -> str:
        """Return a valid OAuth access token."""
        await self.session.async_ensure_token_valid()
        return self.session.token["access_token"]

    def _update_rate_limit_issues(self) -> None:
        """Update Home Assistant repair issues from the library rate-limit state."""
        limits = self.rate_limits
        if limits["remaining_minutes"] > 0:
            ir.async_delete_issue(self.hass, DOMAIN, "minute_rate_limit")
        if limits["remaining_day"] > 0:
            ir.async_delete_issue(self.hass, DOMAIN, "day_rate_limit")

    def _create_rate_limit_issues(self) -> None:
        """Create Home Assistant repair issues for exhausted rate limits."""
        limits = self.rate_limits
        learn_more_url = (
            "https://developer.cloud.daikineurope.com/docs/"
            "b0dffcaa-7b51-428a-bdff-a7c8a64195c0/general_api_guidelines"
            "#doc-heading-rate-limitation"
        )
        if limits["remaining_minutes"] == 0:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "minute_rate_limit",
                is_fixable=False,
                is_persistent=True,
                severity=ir.IssueSeverity.ERROR,
                learn_more_url=learn_more_url,
                translation_key="minute_rate_limit",
            )
        if limits["remaining_day"] == 0:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "day_rate_limit",
                is_fixable=False,
                is_persistent=True,
                severity=ir.IssueSeverity.ERROR,
                learn_more_url=learn_more_url,
                translation_key="day_rate_limit",
            )

    async def get_cloud_device_details(self) -> list[GatewayDevice]:
        """Get typed device data from the Daikin cloud."""
        async with self._cloud_lock:
            try:
                devices = await self._client.get_gateway_devices()
            except OnectaRateLimitError:
                self._create_rate_limit_issues()
                raise
            self._update_rate_limit_issues()
            return devices

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
                self._create_rate_limit_issues()
                return False
            except OnectaApiError:
                return False
            self._last_patch_call = dt_util.now()
            self._update_rate_limit_issues()
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
                self._create_rate_limit_issues()
                return False
            except OnectaApiError:
                return False
            self._last_patch_call = dt_util.now()
            self._update_rate_limit_issues()
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
                self._create_rate_limit_issues()
                return False
            except OnectaApiError:
                return False
            self._last_patch_call = dt_util.now()
            self._update_rate_limit_issues()
            return True
