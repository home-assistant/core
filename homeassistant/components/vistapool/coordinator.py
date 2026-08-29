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

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import VistapoolConfigEntry

_LOGGER = logging.getLogger(__name__)

# Fallback for when a Firestore push never arrives (controller offline,
# command dropped); a confirming push normally clears the pending entry first.
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
        self._pending_optimistic: dict[str, list[tuple[Any, float]]] = {}
        self._write_locks: dict[str, asyncio.Lock] = {}
        self._optimistic_handles: dict[str, asyncio.TimerHandle] = {}
        self._self_heal_handle: asyncio.TimerHandle | None = None
        self._self_heal_task: asyncio.Task[None] | None = None
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
            data = await self.api.fetch_pool_data(self.pool_id)
        except AquariteError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        # This fetch is as authoritative as a push: a pending self-heal
        # retry would only refetch and could mark recovered data
        # unavailable again on a transient failure.
        self._cancel_self_heal()
        # A manual refresh must not clobber optimistic writes for other
        # paths that are still inside their own TTL window.
        return self._merge_optimistic(data)

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
        """Apply a snapshot, preserving unconfirmed optimistic writes.

        A snapshot is authoritative: its arrival proves the connection is
        up and supersedes any pending self-heal fetch.
        """
        if not self._push_connected:
            self._push_connected = True
            _LOGGER.info("Reconnected to %s, entities are available again", self.name)
        self._cancel_self_heal()
        self.async_set_updated_data(self._merge_optimistic(data))

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
        for handle in self._optimistic_handles.values():
            handle.cancel()
        self._optimistic_handles.clear()
        self._pending_optimistic.clear()
        self._cancel_self_heal()
        if self.subscription is not None:
            await self.subscription.aclose()
            self.subscription = None
        await super().async_shutdown()

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get nested data using dot-notation path."""
        return AquariteClient.get_value(self.data, path, default)

    def write_lock(self, value_path: str) -> asyncio.Lock:
        """Return the lock serializing writers of a path.

        Writers sharing a path across platforms (the light entity and the
        LED pulse) must keep the pending-write order identical to the wire
        order, or confirmations would overlay values the controller no
        longer has.
        """
        return self._write_locks.setdefault(value_path, asyncio.Lock())

    def record_optimistic(self, value_path: str, value: Any) -> None:
        """Track a just-written value without announcing new entity state.

        For transient values in a write sequence (the LED pulse's
        intermediate off): the echo must be confirmed in order, but
        entities and automations must not see the value flash by.
        """
        writes = self._pending_optimistic.setdefault(value_path, [])
        now = monotonic()
        # Age out entries by their own timestamp so sustained writing cannot
        # grow the queue without bound; the newest write keeps its full TTL.
        while writes and now - writes[0][1] >= OPTIMISTIC_TTL_SECONDS:
            writes.pop(0)
        writes.append((value, now))
        _set_path(self.data, value_path, value)
        if (handle := self._optimistic_handles.pop(value_path, None)) is not None:
            handle.cancel()
        # Without a polling interval, a vanished push (controller offline,
        # cloud lost the command) would leave the optimistic value stuck.
        # Schedule an authoritative refresh after the TTL to self-heal.
        self._optimistic_handles[value_path] = self.hass.loop.call_later(
            OPTIMISTIC_TTL_SECONDS, self._expire_optimistic, value_path
        )

    def apply_optimistic(self, value_path: str, value: Any) -> None:
        """Reflect a just-written value and protect it from stale Firestore pushes."""
        self.record_optimistic(value_path, value)
        self.async_set_updated_data(self.data)

    def discard_optimistic(self, value_path: str) -> None:
        """Drop the newest pending write for a path.

        For unwinding a prequeued write whose send failed: it must not
        keep suppressing the pushes that reflect what the cloud really has.
        """
        writes = self._pending_optimistic.get(value_path)
        if not writes:
            return
        writes.pop()
        if not writes:
            self._clear_optimistic(value_path)

    def _merge_optimistic(self, data: dict[str, Any]) -> dict[str, Any]:
        """Overlay unconfirmed optimistic writes onto freshly fetched data."""
        now = monotonic()
        for path, writes in list(self._pending_optimistic.items()):
            # Coalesced snapshots may never match the oldest entries, so age
            # each write out on its own timestamp instead of keeping the
            # whole queue alive as long as the newest write is fresh.
            while writes and now - writes[0][1] >= OPTIMISTIC_TTL_SECONDS:
                writes.pop(0)
            if not writes:
                self._clear_optimistic(path)
                continue
            remote_value = AquariteClient.get_value(data, path)
            # A push can only confirm writes in order: with ON then OFF in
            # flight, a pre-ON echo carrying OFF must not lift protection,
            # or the later ON confirmation would flip the entity back.
            if _values_agree(remote_value, writes[0][0]):
                writes.pop(0)
                if not writes:
                    self._clear_optimistic(path)
                    continue
            _set_path(data, path, writes[-1][0])
        return data

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
        self.start_self_heal()

    def start_self_heal(self) -> None:
        """Launch an authoritative fetch unless one is already running.

        Used by the TTL expiry, and by write sequences that failed halfway:
        the local prediction is then unreliable, so fetch the truth.
        """
        if self._self_heal_handle is not None:
            self._self_heal_handle.cancel()
            self._self_heal_handle = None
        if self._self_heal_task is not None and not self._self_heal_task.done():
            return
        self._self_heal_task = self.config_entry.async_create_task(
            self.hass,
            self._async_self_heal(),
            name=f"vistapool_self_heal_{self.pool_id}",
        )

    async def _async_self_heal(self) -> None:
        """Fetch authoritative data after an expired write, retrying on failure.

        Fetches directly instead of going through async_refresh: the base
        class marks a cancelled refresh as unsuccessful, which would undo
        the push that cancelled this task. Without a polling interval, a
        failed fetch with a quiet Firestore document would otherwise leave
        the entities unavailable indefinitely, so a failure re-arms the
        retry; a successful fetch or an incoming push cancels it.
        """
        try:
            data = await self.api.fetch_pool_data(self.pool_id)
        except AquariteError as err:
            self.async_set_update_error(err)
            self._self_heal_handle = self.hass.loop.call_later(
                OPTIMISTIC_TTL_SECONDS, self.start_self_heal
            )
            return
        self.async_set_updated_data(self._merge_optimistic(data))

    def _cancel_self_heal(self) -> None:
        """Stop the self-heal retry: the pending timer and the in-flight task.

        The in-flight task matters too: its late fetch result could
        overwrite an authoritative push with older data, and its late
        failure would re-arm the retry against fresh data.
        """
        if self._self_heal_handle is not None:
            self._self_heal_handle.cancel()
            self._self_heal_handle = None
        if self._self_heal_task is not None:
            self._self_heal_task.cancel()
            self._self_heal_task = None


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
