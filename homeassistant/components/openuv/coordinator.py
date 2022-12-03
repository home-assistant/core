"""Define an update coordinator for OpenUV."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, cast

from pyopenuv.errors import InvalidApiKeyError, OpenUvError

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

DEFAULT_DEBOUNCER_COOLDOWN_SECONDS = 15 * 60


class InvalidApiKeyMonitor:
    """Define a monitor for failed API calls (due to bad keys) across coordinators."""

    DEFAULT_FAILED_API_CALL_THRESHOLD = 5

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self._count = 1
        self._lock = asyncio.Lock()
        self._reauth_flow_manager = ReauthFlowManager(hass, entry)
        self.entry = entry

    async def async_increment(self) -> None:
        """Increment the counter."""
        async with self._lock:
            self._count += 1
            if self._count > self.DEFAULT_FAILED_API_CALL_THRESHOLD:
                LOGGER.info("Starting reauth after multiple failed API calls")
                self._reauth_flow_manager.start_reauth()

    async def async_reset(self) -> None:
        """Reset the counter."""
        async with self._lock:
            self._count = 0
            self._reauth_flow_manager.cancel_reauth()


class ReauthFlowManager:
    """Define an OpenUV reauth flow manager."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.hass = hass

    @callback
    def _get_active_reauth_flow(self) -> FlowResult | None:
        """Get an active reauth flow (if it exists)."""
        return next(
            iter(self.entry.async_get_active_flows(self.hass, {SOURCE_REAUTH})),
            None,
        )

    @callback
    def cancel_reauth(self) -> None:
        """Cancel a reauth flow (if appropriate)."""
        if reauth_flow := self._get_active_reauth_flow():
            LOGGER.debug("API seems to have recovered; canceling reauth flow")
            self.hass.config_entries.flow.async_abort(reauth_flow["flow_id"])

    @callback
    def start_reauth(self) -> None:
        """Start a reauth flow (if appropriate)."""
        if not self._get_active_reauth_flow():
            LOGGER.debug("Multiple API failures in a row; starting reauth flow")
            self.entry.async_start_reauth(self.hass)


class OpenUvCoordinator(DataUpdateCoordinator):
    """Define an OpenUV data coordinator."""

    config_entry: ConfigEntry
    update_method: Callable[[], Awaitable[dict[str, Any]]]

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        name: str,
        latitude: str,
        longitude: str,
        update_method: Callable[[], Awaitable[dict[str, Any]]],
        invalid_api_key_monitor: InvalidApiKeyMonitor,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=name,
            update_method=update_method,
            request_refresh_debouncer=Debouncer(
                hass,
                LOGGER,
                cooldown=DEFAULT_DEBOUNCER_COOLDOWN_SECONDS,
                immediate=True,
            ),
        )

        self._invalid_api_key_monitor = invalid_api_key_monitor
        self.latitude = latitude
        self.longitude = longitude

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from OpenUV."""
        try:
            data = await self.update_method()
        except InvalidApiKeyError as err:
            await self._invalid_api_key_monitor.async_increment()
            raise UpdateFailed(str(err)) from err
        except OpenUvError as err:
            raise UpdateFailed(str(err)) from err

        await self._invalid_api_key_monitor.async_reset()
        return cast(dict[str, Any], data["result"])
