"""Shared base entity for Denon AVR select/switch entities.

Shows a value optimistically right after a command, since the
receiver can briefly still report the old one on an immediate
refresh, then reconciles once it actually catches up (bounded by a
timeout so a command that never applied doesn't mask reality forever).
"""

from collections.abc import Callable, Coroutine
from typing import Any, override

from denonavr.exceptions import DenonAvrError

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import PENDING_VALUE_TIMEOUT
from .coordinator import UNAVAILABLE_ON, DenonAvrDataUpdateCoordinator, mark_unavailable


class DenonAvrPendingValueEntity[_T](CoordinatorEntity[DenonAvrDataUpdateCoordinator]):
    """Base for entities that show an optimistic value until confirmed."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DenonAvrDataUpdateCoordinator,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._receiver = coordinator.receiver
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        # Only guards the "send the command" step. The coordinator's own
        # refresh shares this same lock (see coordinator.py), so this
        # closes the gap PARALLEL_UPDATES leaves: it only serializes
        # calls that target multiple entities at once, not repeated
        # calls to one entity or calls split across platforms.
        self._action_lock = coordinator.lock
        self._pending_value: _T | None = None
        self._pending_value_expiry_unsub: Callable[[], None] | None = None

    def _read_value(self) -> _T | None:
        """Return the receiver's own confirmed value."""
        raise NotImplementedError

    def _set_pending_value(self, value: _T) -> None:
        """Show a value optimistically and schedule its expiry."""
        self._pending_value = value
        if self._pending_value_expiry_unsub is not None:
            self._pending_value_expiry_unsub()
        self._pending_value_expiry_unsub = async_call_later(
            self.hass, PENDING_VALUE_TIMEOUT, self._async_handle_pending_expiry
        )

    def _clear_pending_value(self) -> None:
        """Clear the pending override and cancel its scheduled expiry."""
        self._pending_value = None
        if self._pending_value_expiry_unsub is not None:
            self._pending_value_expiry_unsub()
            self._pending_value_expiry_unsub = None

    @callback
    def _async_handle_pending_expiry(self, _now: Any) -> None:
        """Write state when an optimistic value expires.

        Otherwise HA's stored state would keep showing it past the
        timeout, since nothing else would re-evaluate it.
        """
        self._pending_value_expiry_unsub = None
        self._pending_value = None
        self.async_write_ha_state()

    @property
    def _current_value(self) -> _T | None:
        """Return the pending value if set, else the receiver's own value."""
        if self._pending_value is not None:
            return self._pending_value
        return self._read_value()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Clear an optimistic value once confirmed by the receiver.

        Not right after requesting a refresh: that request is
        debounced (see coordinator.py) and doesn't complete
        synchronously with the call.
        """
        if (
            self._pending_value is not None
            and self._read_value() == self._pending_value
        ):
            self._clear_pending_value()
        super()._handle_coordinator_update()

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
        """Send a command, update optimistically, then request confirmation.

        `send` must be a zero-arg callable returning a fresh coroutine
        (e.g. a lambda), not an already-awaited one.
        """
        async with self._action_lock:
            try:
                await send()
            except UNAVAILABLE_ON as err:
                # A confirmed connectivity failure, not just a
                # rejected command - mark unavailable now rather than
                # leave stale data looking current until the next poll.
                mark_unavailable(self.coordinator)
                raise HomeAssistantError(
                    f"Could not set {error_label} to {value} on"
                    f" {self._receiver.name}: {err}"
                ) from err
            except DenonAvrError as err:
                raise HomeAssistantError(
                    f"Could not set {error_label} to {value} on"
                    f" {self._receiver.name}: {err}"
                ) from err

        self._set_pending_value(value)
        self.async_write_ha_state()

        # Confirms via the coordinator this entity belongs to - which
        # also refreshes and notifies every other entity sharing it, so
        # e.g. toggling Dynamic EQ correctly updates Reference Level
        # Offset's availability too, without a separate notification.
        await self.coordinator.async_request_refresh()
