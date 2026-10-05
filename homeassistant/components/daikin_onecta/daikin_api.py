"""Home Assistant adapter for the Daikin Onecta API client."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import logging
from typing import cast

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
        return cast("str", self.session.token["access_token"])

    async def get_cloud_device_details(
        self, *, cooldown: timedelta | None = None
    ) -> list[GatewayDevice] | None:
        """Get typed device data from the Daikin cloud, respecting cooldown."""
        async with self._cloud_lock:
            if (
                cooldown is not None
                and self._last_patch_call is not None
                and dt_util.utcnow() - self._last_patch_call < cooldown
            ):
                return None
            return await self._client.get_gateway_devices()

    async def async_execute_command(
        self, command: Callable[[OnectaClient], Awaitable[None]]
    ) -> bool:
        """Run a cloud command and log contextual expected failures."""
        async with self._cloud_lock:
            try:
                await command(self._client)
            except OnectaRateLimitError as err:
                _LOGGER.warning(
                    "Daikin request %s %s was rate limited; retry after %s seconds",
                    err.method,
                    err.path,
                    err.retry_after,
                )
                return False
            except OnectaApiError as err:
                _LOGGER.warning(
                    "Daikin request %s %s failed with HTTP %s",
                    err.method,
                    err.path,
                    err.status,
                )
                return False
            except TimeoutError:
                _LOGGER.warning("Daikin request timed out")
                return False
            self._last_patch_call = dt_util.utcnow()
            return True
