"""Shared base entity for Denon AVR select/switch entities.

Shows a value optimistically right after a command, since the
receiver can briefly still report the old one on an immediate
refresh, then reconciles once it actually catches up (bounded by a
timeout so a command that never applied doesn't mask reality forever).
"""

import asyncio
from collections.abc import Callable, Coroutine
import logging
import time
from typing import Any, override
import weakref

from denonavr import DenonAVR
from denonavr.exceptions import DenonAvrError

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later

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
        poll_refresh_enabled: Callable[[], bool] | None = None,
    ) -> None:
        """Initialize the entity.

        `poll_refresh_enabled`, if given, is checked before the
        *recurring* poll (async_update) refreshes - not the one-time
        setup fetch in __init__.py, and not the refresh right after
        this entity's own action, both of which stay unconditional
        regardless (see the module docstrings for why). Used to let
        Audyssey-backed entities' periodic polling honor the existing
        "Update Audyssey settings" option, matching the precedent
        already established for media_player.py's own recurring poll.
        """
        self._receiver = receiver
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._action_lock = _get_receiver_lock(receiver)
        self._refresh_fn = refresh_fn
        self._poll_refresh_enabled = poll_refresh_enabled
        self._pending_value: _T | None = None
        self._pending_value_set_at: float | None = None
        self._pending_value_expiry_unsub: Callable[[], None] | None = None

    def _read_value(self) -> _T | None:
        """Return the receiver's own confirmed value."""
        raise NotImplementedError

    def _set_pending_value(self, value: _T) -> None:
        """Show a value optimistically and schedule its expiry."""
        self._pending_value = value
        self._pending_value_set_at = time.monotonic()
        if self._pending_value_expiry_unsub is not None:
            self._pending_value_expiry_unsub()
        self._pending_value_expiry_unsub = async_call_later(
            self.hass, PENDING_VALUE_TIMEOUT, self._async_handle_pending_expiry
        )

    def _clear_pending_value(self) -> None:
        """Clear the pending override and cancel its scheduled expiry."""
        self._pending_value = None
        self._pending_value_set_at = None
        if self._pending_value_expiry_unsub is not None:
            self._pending_value_expiry_unsub()
            self._pending_value_expiry_unsub = None

    @callback
    def _async_handle_pending_expiry(self, _now: Any) -> None:
        """Write state once a pending override's timeout elapses.

        Without this, HA's own stored state (what automations and the
        frontend see) would keep showing the optimistic value until
        something else happens to re-evaluate it - the next poll, or
        whenever a user opens the entity - rather than within the
        documented timeout.
        """
        self._pending_value_expiry_unsub = None
        self._pending_value = None
        self._pending_value_set_at = None
        self.async_write_ha_state()

    @property
    def _current_value(self) -> _T | None:
        """Return the pending value if set, else the receiver's own value."""
        if self._pending_value is not None:
            return self._pending_value
        return self._read_value()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel any scheduled pending-value expiry."""
        if self._pending_value_expiry_unsub is not None:
            self._pending_value_expiry_unsub()
            self._pending_value_expiry_unsub = None

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

            self._set_pending_value(value)
            self.async_write_ha_state()

            if self._refresh_fn is not None:
                try:
                    await self._refresh_fn()
                except DenonAvrError as err:
                    # The command above already succeeded - a refresh
                    # failure shouldn't fail the whole action, just
                    # leave the pending value showing until the next
                    # poll or its own timeout.
                    _LOGGER.debug(
                        "Could not refresh %s after setting %s: %s",
                        self.entity_id,
                        error_label,
                        err,
                    )
                else:
                    if self._read_value() == value:
                        self._clear_pending_value()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Refresh from the receiver and reconcile any pending value.

        Actively refreshes (rather than only checking already-cached
        data) so external changes - made outside HA, or while the
        media player entity that would otherwise drive this refresh is
        individually disabled - still surface here. Skipped when
        poll_refresh_enabled says not to (see __init__).
        """
        if self._refresh_fn is not None and (
            self._poll_refresh_enabled is None or self._poll_refresh_enabled()
        ):
            async with self._action_lock:
                try:
                    await self._refresh_fn()
                except DenonAvrError as err:
                    _LOGGER.debug("Could not refresh %s: %s", self.entity_id, err)

        if (
            self._pending_value is not None
            and self._read_value() == self._pending_value
        ):
            self._clear_pending_value()
