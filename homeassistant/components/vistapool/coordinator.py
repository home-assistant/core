"""Data coordinator for the Vistapool integration."""

import asyncio
import logging
from time import monotonic
from typing import TYPE_CHECKING, Any, override

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

OPTIMISTIC_TTL_SECONDS = 10.0


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
        self._pending_optimistic: dict[str, tuple[Any, float]] = {}
        self._optimistic_handles: dict[str, asyncio.TimerHandle] = {}

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

    async def subscribe(self) -> None:
        """Subscribe to Firestore real-time updates via the library."""

        def _on_data(data: dict[str, Any]) -> None:
            """Callback from the Firestore thread; push data to the HA loop."""
            self.hass.loop.call_soon_threadsafe(self._apply_remote_data, data)

        self.subscription = await self.api.subscribe_pool_resilient(
            self.pool_id, _on_data
        )

    @override
    async def async_shutdown(self) -> None:
        """Cleanly close the resilient subscription."""
        for handle in self._optimistic_handles.values():
            handle.cancel()
        self._optimistic_handles.clear()
        self._pending_optimistic.clear()
        if self.subscription is not None:
            await self.subscription.aclose()
            self.subscription = None
        await super().async_shutdown()

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get nested data using dot-notation path."""
        return AquariteClient.get_value(self.data, path, default)

    def apply_optimistic(self, value_path: str, value: Any) -> None:
        """Reflect a just-written value and protect it from stale Firestore pushes."""
        self._pending_optimistic[value_path] = (value, monotonic())
        _set_path(self.data, value_path, value)
        if (handle := self._optimistic_handles.pop(value_path, None)) is not None:
            handle.cancel()
        # Without a polling interval, a vanished push (controller offline,
        # cloud lost the command) would leave the optimistic value stuck.
        # Schedule an authoritative refresh after the TTL to self-heal.
        self._optimistic_handles[value_path] = self.hass.loop.call_later(
            OPTIMISTIC_TTL_SECONDS, self._expire_optimistic, value_path
        )
        self.async_set_updated_data(self.data)

    def _apply_remote_data(self, data: dict[str, Any]) -> None:
        """Apply a Firestore push, preserving unconfirmed optimistic writes."""
        now = monotonic()
        for path, (value, written_at) in list(self._pending_optimistic.items()):
            remote_value = AquariteClient.get_value(data, path)
            if (
                _values_agree(remote_value, value)
                or now - written_at >= OPTIMISTIC_TTL_SECONDS
            ):
                self._clear_optimistic(path)
            else:
                _set_path(data, path, value)
        self.async_set_updated_data(data)

    def _clear_optimistic(self, value_path: str) -> None:
        """Drop a pending optimistic entry and its scheduled expiry."""
        self._pending_optimistic.pop(value_path, None)
        if (handle := self._optimistic_handles.pop(value_path, None)) is not None:
            handle.cancel()

    def _expire_optimistic(self, value_path: str) -> None:
        """TTL fired without a confirming push: drop and force a refresh."""
        self._optimistic_handles.pop(value_path, None)
        if value_path not in self._pending_optimistic:
            return
        del self._pending_optimistic[value_path]
        self.hass.async_create_task(self.async_refresh())


def _set_path(data: dict[str, Any], value_path: str, value: Any) -> None:
    """Write value into data at a dot-notation path, creating dicts as needed."""
    keys = value_path.split(".")
    target: dict[str, Any] = data
    for key in keys[:-1]:
        child = target.get(key)
        if not isinstance(child, dict):
            child = {}
            target[key] = child
        target = child
    target[keys[-1]] = value


def _values_agree(remote: Any, optimistic: Any) -> bool:
    """Compare values tolerantly: Firestore can return int/str/bool variants."""
    if remote == optimistic:
        return True
    try:
        return float(remote) == float(optimistic)
    except TypeError, ValueError:
        return False
