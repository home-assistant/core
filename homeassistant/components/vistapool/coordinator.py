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
        """Subscribe to Firestore real-time updates via the library."""

        def _on_data(data: dict[str, Any]) -> None:
            """Callback from the Firestore thread; push data to the HA loop."""
            self.hass.loop.call_soon_threadsafe(self._async_handle_push, data)

        self.subscription = await self.api.subscribe_pool_resilient(
            self.pool_id, _on_data, on_health=self._async_on_subscription_health
        )

    @callback
    def _async_handle_push(self, data: dict[str, Any]) -> None:
        """Apply a snapshot; its arrival is what proves the connection is up."""
        if not self._push_connected:
            self._push_connected = True
            _LOGGER.info("Reconnected to %s, entities are available again", self.name)
        self.async_set_updated_data(data)

    @callback
    def _async_on_subscription_health(self, healthy: bool) -> None:
        """Mark entities unavailable while the push connection is down.

        Tracked separately from last_update_success: an optimistic update
        or a manual refresh sets that flag back to True while the
        subscription is still down, and the health callback only fires on
        transitions, so it would not correct it. Only an incoming snapshot
        clears this.
        """
        if healthy or not self._push_connected:
            return
        self._push_connected = False
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

    def apply_optimistic(self, value_path: str, value: Any) -> None:
        """Reflect a just-written value before the Firestore push round-trips.

        Hayward's cloud takes several seconds to acknowledge a write back
        through Firestore, which would make the UI feel laggy. Writing into
        coordinator.data after a successful REST call gives entities instant
        feedback; the next snapshot from Firestore overwrites it harmlessly.
        """
        self.apply_optimistic_values({value_path: value})

    def apply_optimistic_values(self, updates: dict[str, Any]) -> None:
        """Reflect several just-written values as a single update.

        Applying them one at a time would publish a state where only part
        of the write has landed, which entities derived from more than one
        path briefly read as a different value.
        """
        for value_path, value in updates.items():
            keys = value_path.split(".")
            target: dict[str, Any] = self.data
            for key in keys[:-1]:
                child = target.get(key)
                if not isinstance(child, dict):
                    child = {}
                    target[key] = child
                target = child
            target[keys[-1]] = value
        self.async_set_updated_data(self.data)
