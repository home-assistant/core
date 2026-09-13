"""Shared base entity for Denon AVR select/switch entities.

These all follow the same shape: send a command, show the value
optimistically since the receiver can briefly still report the old one
on an immediate refresh, then reconcile once it actually catches up
(bounded by a timeout so a command that never applied doesn't get
masked forever). Pulled out here since three near-identical copies of
this logic drifted once already (one of them missed a fix the others
got).
"""

import asyncio
from collections.abc import Callable, Coroutine
import logging
import time
from typing import Any
import weakref

from denonavr import DenonAVR
from denonavr.exceptions import DenonAvrError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import PENDING_VALUE_TIMEOUT

_LOGGER = logging.getLogger(__name__)

# Keyed by receiver instance rather than per-entity: the receiver's
# HTTP/Telnet interface can't safely handle concurrent requests
# (PARALLEL_UPDATES=1 in each platform only serializes calls that
# target multiple entities at once, not repeated calls to one entity or
# calls split across select.py/switch.py), so every entity acting on a
# given receiver shares one lock instead of racing its own.
_receiver_locks: weakref.WeakKeyDictionary[DenonAVR, asyncio.Lock] = (
    weakref.WeakKeyDictionary()
)


def _get_receiver_lock(receiver: DenonAVR) -> asyncio.Lock:
    """Return the lock shared by every entity acting on this receiver."""
    if receiver not in _receiver_locks:
        _receiver_locks[receiver] = asyncio.Lock()
    return _receiver_locks[receiver]


class DenonAvrPendingValueEntity[_T](Entity):
    """Base for entities that show an optimistic value until confirmed."""

    _attr_has_entity_name = True

    def __init__(
        self,
        receiver: DenonAVR,
        unique_id: str,
        device_info: DeviceInfo,
        refresh_fn: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        """Initialize the entity."""
        self._receiver = receiver
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._action_lock = _get_receiver_lock(receiver)
        self._refresh_fn = refresh_fn
        self._pending_value: _T | None = None
        self._pending_value_set_at: float | None = None
        # HA forces an immediate poll right after adding a new polling
        # entity - redundant here since __init__.py already did a
        # setup-time fetch for the whole group sharing this receiver.
        # Skipped once; every poll after that is a genuine refresh.
        self._skip_next_poll_refresh = True

    def _read_value(self) -> _T | None:
        """Return the receiver's own confirmed value."""
        raise NotImplementedError

    def _clear_expired_pending_value(self) -> None:
        """Drop the optimistic override once it's been held too long."""
        if (
            self._pending_value is not None
            and self._pending_value_set_at is not None
            and time.monotonic() - self._pending_value_set_at > PENDING_VALUE_TIMEOUT
        ):
            self._pending_value = None
            self._pending_value_set_at = None

    @property
    def _current_value(self) -> _T | None:
        """Return the pending value if set, else the receiver's own value."""
        self._clear_expired_pending_value()
        if self._pending_value is not None:
            return self._pending_value
        return self._read_value()

    async def _async_apply_change(
        self,
        *,
        send: Callable[[], Coroutine[Any, Any, None]],
        value: _T,
        error_label: str,
    ) -> None:
        """Send a command, show it immediately, then reconcile.

        `send` is a zero-arg callable returning a fresh coroutine each
        time (e.g. a lambda), not an already-awaited one. Held under
        the receiver-wide lock together with the post-command refresh,
        so an older, slower refresh from another call can't land after
        (and overwrite) a newer one.
        """
        async with self._action_lock:
            try:
                await send()
            except DenonAvrError as err:
                raise HomeAssistantError(
                    f"Could not set {error_label} to {value} on"
                    f" {self._receiver.name}: {err}"
                ) from err

            self._pending_value = value
            self._pending_value_set_at = time.monotonic()
            self.async_write_ha_state()

            if self._refresh_fn is not None:
                await self._refresh_fn()

            if self._read_value() == value:
                self._pending_value = None
                self._pending_value_set_at = None
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Refresh from the receiver and reconcile any pending value.

        Actively refreshes (rather than only checking already-cached
        data) so external changes - made outside HA, or while the
        media player entity that would otherwise drive this refresh is
        individually disabled - still surface here. Skips the very
        first call, since that happens immediately upon being added
        and would just repeat __init__.py's setup-time fetch.
        """
        if self._skip_next_poll_refresh:
            self._skip_next_poll_refresh = False
        elif self._refresh_fn is not None:
            async with self._action_lock:
                try:
                    await self._refresh_fn()
                except DenonAvrError as err:
                    _LOGGER.debug("Could not refresh %s: %s", self.entity_id, err)

        self._clear_expired_pending_value()
        if self._pending_value is not None and (
            self._read_value() == self._pending_value
        ):
            self._pending_value = None
            self._pending_value_set_at = None
