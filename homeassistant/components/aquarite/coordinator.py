"""Data coordinator for the Aquarite integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from aioaquarite import AquariteAuth, AquariteClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    from . import AquariteConfigEntry

_LOGGER = logging.getLogger(__name__)


class AquariteDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Aquarite coordinator for a single pool's Firestore subscription."""

    config_entry: AquariteConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AquariteConfigEntry,
        auth: AquariteAuth,
        api: AquariteClient,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the coordinator."""
        self.auth = auth
        self.api = api
        self.pool_id: str = pool_id
        self.pool_name: str = pool_name
        self.watch: Any | None = None
        self._subscription_lock = asyncio.Lock()

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Aquarite {pool_name}",
            update_interval=None,
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest pool data (fallback for manual refresh)."""
        return await self.api.fetch_pool_data(self.pool_id)

    async def subscribe(self) -> None:
        """Subscribe to Firestore real-time updates via the library."""

        def _on_data(data: dict[str, Any]) -> None:
            """Callback from Firestore thread; push data to HA loop."""
            self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, data)

        self.watch = await self.api.subscribe_pool(self.pool_id, _on_data)

    async def refresh_subscription(self) -> None:
        """Resubscribe to Firestore (e.g., after a token refresh)."""
        async with self._subscription_lock:
            _LOGGER.debug("Refreshing Firestore subscription for %s", self.pool_id)
            if self.watch:
                await asyncio.to_thread(self.watch.unsubscribe)
            await self.subscribe()

    async def async_shutdown(self) -> None:
        """Cleanly unsubscribe."""
        async with self._subscription_lock:
            watch = self.watch
            self.watch = None
            if watch:
                await asyncio.to_thread(watch.unsubscribe)
        await super().async_shutdown()

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get nested data using dot-notation path."""
        return AquariteClient.get_value(self.data, path, default)
