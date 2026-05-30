"""Data coordinator for the Vistapool integration."""

import logging
from typing import TYPE_CHECKING, Any

from aioaquarite import (
    AquariteAuth,
    AquariteClient,
    AquariteError,
    ResilientPoolSubscription,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import VistapoolConfigEntry

_LOGGER = logging.getLogger(__name__)


class VistapoolDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Vistapool coordinator for a single pool's Firestore subscription."""

    config_entry: VistapoolConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VistapoolConfigEntry,
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
        self.subscription: ResilientPoolSubscription | None = None

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Vistapool {pool_name}",
            update_interval=None,
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest pool data (fallback for manual refresh)."""
        try:
            return await self.api.fetch_pool_data(self.pool_id)
        except AquariteError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

    async def subscribe(self) -> None:
        """Subscribe to Firestore real-time updates via the library."""

        def _on_data(data: dict[str, Any]) -> None:
            """Callback from the Firestore thread; push data to the HA loop."""
            self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, data)

        self.subscription = await self.api.subscribe_pool_resilient(
            self.pool_id, _on_data
        )

    async def async_shutdown(self) -> None:
        """Cleanly close the resilient subscription."""
        if self.subscription is not None:
            await self.subscription.aclose()
            self.subscription = None
        await super().async_shutdown()

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get nested data using dot-notation path."""
        return AquariteClient.get_value(self.data, path, default)
