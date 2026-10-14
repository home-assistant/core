"""Data coordinator for the Vistapool integration."""

import logging
from typing import TYPE_CHECKING, Any, override

from aioaquarite import (
    AquariteAuth,
    AquariteClient,
    AquariteError,
    ResilientPoolSubscription,
)

from homeassistant.core import HomeAssistant, callback
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
        self._push_connected = True

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Vistapool {pool_name}",
            update_interval=None,
            config_entry=entry,
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest pool data (fallback for manual refresh)."""
        try:
            return await self.api.fetch_pool_data(self.pool_id)
        except AquariteError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

    @property
    def push_connected(self) -> bool:
        """Whether pool data is still flowing in from the subscription."""
        return self._push_connected

    async def subscribe(self) -> None:
        """Subscribe to Firestore real-time updates via the library.

        The library invokes the data callback on the event loop, with
        acknowledged writes already reflected, so deliveries are published
        as they come.
        """
        self.subscription = await self.api.subscribe_pool_resilient(
            self.pool_id,
            self.async_set_updated_data,
            on_health=self._async_on_subscription_health,
        )

    @callback
    def _async_on_subscription_health(self, healthy: bool) -> None:
        """Mirror the push connection state into entity availability.

        Tracked separately from last_update_success: an acknowledged write
        or a manual refresh sets that flag back to True while the
        subscription is still down. The library reports healthy only once a
        reconnected stream has delivered a consistent snapshot, so data
        arriving in between must not fake availability either.
        """
        if healthy == self._push_connected:
            return
        self._push_connected = healthy
        if healthy:
            _LOGGER.info("Reconnected to %s, entities are available again", self.name)
        else:
            _LOGGER.warning(
                "Lost the connection to %s, entities are unavailable until it recovers",
                self.name,
            )
        self.async_update_listeners()

    @override
    async def async_shutdown(self) -> None:
        """Cleanly close the resilient subscription."""
        if self.subscription is not None:
            await self.subscription.aclose()
            self.subscription = None
        await super().async_shutdown()

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get nested data using dot-notation path."""
        return AquariteClient.get_value(self.data, path, default)
