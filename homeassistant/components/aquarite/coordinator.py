"""Data coordinator for the Aquarite integration."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from aioaquarite import AquariteAuth, AquariteClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AquariteDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Aquarite coordinator using Firestore real-time snapshots."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        auth: AquariteAuth,
        api: AquariteClient,
        pool_id: str,
    ) -> None:
        """Initialize the coordinator."""
        self.auth = auth
        self.api = api
        self.pool_id: str = pool_id
        self.watch: Any | None = None
        self._health_task: asyncio.Task[None] | None = None
        self._token_task: asyncio.Task[None] | None = None
        self._subscription_lock = asyncio.Lock()

        super().__init__(
            hass,
            logger=_LOGGER,
            name="Aquarite",
            update_interval=None,
            config_entry=entry,
        )

    async def subscribe(self) -> None:
        """Subscribe to Firestore real-time updates via the library."""

        def _on_data(data: dict[str, Any]) -> None:
            """Callback from Firestore thread; push data to HA loop."""
            self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, data)

        self.watch = await self.api.subscribe_pool(self.pool_id, _on_data)

    async def setup_tasks(self) -> None:
        """Start background health monitoring and token refresh."""
        self._health_task = self.hass.async_create_background_task(
            self.periodic_health_check(), "Aquarite health check"
        )
        self._token_task = self.hass.async_create_background_task(
            self._token_refresh_loop(), "Aquarite token refresh"
        )

    async def _token_refresh_loop(self) -> None:
        """Maintain token validity with exponential backoff on error."""
        retry_delay = 10
        while not self.hass.is_stopping:
            try:
                if self.auth.is_token_expiring():
                    _LOGGER.debug("Token expiring soon, refreshing...")
                    _, refreshed = await self.auth.get_client()
                    if refreshed:
                        await self.refresh_subscription()
                retry_delay = 10
                sleep_time = self.auth.calculate_sleep_duration()
                await asyncio.sleep(sleep_time)
            except Exception as err:
                _LOGGER.error(
                    "Error maintaining token: %s. Retrying in %ss", err, retry_delay
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 600)

    async def periodic_health_check(self) -> None:
        """Monitor connection and resubscribe if needed."""
        while not self.hass.is_stopping:
            interval = self.config_entry.options.get(
                CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL
            )
            await asyncio.sleep(interval)
            try:
                await self.auth.get_client()
            except Exception as err:
                _LOGGER.error("Health check failed, resubscribing: %s", err)
                await self.refresh_subscription()

    async def refresh_subscription(self) -> None:
        """Resubscribe to Firestore after a token refresh."""
        async with self._subscription_lock:
            _LOGGER.debug("Refreshing Firestore subscription for %s", self.pool_id)
            if self.watch:
                await asyncio.to_thread(self.watch.unsubscribe)
            await self.subscribe()

    async def async_shutdown(self) -> None:
        """Cleanly unsubscribe and cancel tasks."""
        if self.watch:
            await asyncio.to_thread(self.watch.unsubscribe)
        for task in (self._health_task, self._token_task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        await super().async_shutdown()

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get nested data using dot-notation path."""
        return AquariteClient.get_value(self.data, path, default)

    async def set_pool_time_to_now(self) -> None:
        """Sync the pool controller clock with the current time."""
        now = dt_util.now()
        offset = now.utcoffset()
        utc_offset = int(offset.total_seconds()) if offset else 0
        timestamp = int(now.timestamp()) + utc_offset
        _LOGGER.info("Syncing pool localTime to: %s (%s, UTC offset %+ds)", timestamp, now.isoformat(), utc_offset)
        await self.api.set_value(self.pool_id, "main.localTime", timestamp)
