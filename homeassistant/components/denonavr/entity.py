"""Shared base entity for Denon AVR select/switch entities.

These all follow the same shape: send a command, show the value
optimistically since the receiver can briefly still report the old one
on an immediate refresh, then reconcile once it actually catches up
(bounded by a timeout so a command that never applied doesn't get
masked forever).
"""

import asyncio
from collections.abc import Callable, Coroutine
import time
from typing import Any

from denonavr import DenonAVR
from denonavr.exceptions import DenonAvrError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import PENDING_VALUE_TIMEOUT


class DenonAvrPendingValueEntity[_T](Entity):
    """Base for entities that show an optimistic value until confirmed."""

    _attr_has_entity_name = True

    def __init__(
        self, receiver: DenonAVR, unique_id: str, device_info: DeviceInfo
    ) -> None:
        """Initialize the entity."""
        self._receiver = receiver
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._action_lock = asyncio.Lock()
        self._pending_value: _T | None = None
        self._pending_value_set_at: float | None = None

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
        refresh: Callable[[], Coroutine[Any, Any, None]] | None,
        value: _T,
        error_label: str,
    ) -> None:
        """Send a command, show it immediately, then reconcile.

        `send` and `refresh` are zero-arg callables returning a fresh
        coroutine each time (e.g. a lambda), not an already-awaited one.
        """
        async with self._action_lock:
            try:
                await send()
            except DenonAvrError as err:
                raise HomeAssistantError(
                    f"Could not set {error_label} to {value} on"
                    f" {self._receiver.name}: {err}"
                ) from err

        # Shown outside the lock so a following rapid change isn't
        # stuck behind this one's (possibly ~10s) refresh before it
        # can even send its own command.
        self._pending_value = value
        self._pending_value_set_at = time.monotonic()
        self.async_write_ha_state()

        if refresh is not None:
            await refresh()

        if self._read_value() == value:
            self._pending_value = None
            self._pending_value_set_at = None
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Reconcile a still-pending value once the receiver catches up."""
        self._clear_expired_pending_value()
        if self._pending_value is not None and (
            self._read_value() == self._pending_value
        ):
            self._pending_value = None
            self._pending_value_set_at = None
