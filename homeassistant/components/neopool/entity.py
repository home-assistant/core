"""Base entity class for the NeoPool integration."""

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any, override

from neopool_modbus.decoders import get_machine_name, parse_version
from neopool_modbus.exceptions import NeoPoolError

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import NeoPoolCoordinator

# Wait for rapid edits to settle so only the final value hits the device EEPROM.
WRITE_DELAY = timedelta(seconds=3)


class NeoPoolEntity(CoordinatorEntity[NeoPoolCoordinator]):
    """Base class for NeoPool entities."""

    _attr_has_entity_name = True

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information for the entity."""
        data = self.coordinator.data or {}
        unique_id = self.coordinator.config_entry.unique_id
        assert unique_id is not None
        machine_type = (get_machine_name(data) or "").strip()
        model_prefix = "NeoPool Compatible: " if machine_type else "NeoPool Compatible"

        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=NAME,
            model=f"{model_prefix}{machine_type}".strip(),
            manufacturer="Hayward (Sugar Valley)",
            sw_version=f"v{parse_version(data.get('MBF_POWER_MODULE_VERSION'))} (v{parse_version(data.get('MBF_PAR_VERSION'))})",
            serial_number=unique_id,
        )


class NeoPoolDebouncedWriteEntity[_T](NeoPoolEntity):
    """Coalesce rapid writes into a single debounced EEPROM cycle.

    number and time share this lifecycle; each platform injects only the device
    write via _write_pending. Keeping it here stops race-condition fixes from
    diverging across the two platforms.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the entity and its debounce write state."""
        super().__init__(*args, **kwargs)
        self._write_unsub: CALLBACK_TYPE | None = None
        self._pending_value: _T | None = None
        # Bumped per set_value; a flush clears only the value it queued.
        self._pending_token = 0
        self._write_future: asyncio.Future[Exception | None] | None = None
        self._flush_lock = asyncio.Lock()
        self._flush_tasks: set[asyncio.Task[None]] = set()
        self._removing = False

    @override
    async def async_added_to_hass(self) -> None:
        """Clear transient write state, in case this entity is re-added.

        An entity-ID change removes and then re-adds the same object, so
        async_will_remove_from_hass leaves _removing set and a cancelled
        pending value behind. Reset both here, else every later flush aborts
        and the stale optimistic value stays visible.
        """
        self._removing = False
        self._pending_value = None
        await super().async_added_to_hass()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel a pending write when removed, and stop any in-flight one."""
        self._removing = True
        self._cancel_pending_write()
        if self._write_future is not None and not self._write_future.done():
            # Awaiting callers treat cancellation as a clean exit.
            self._write_future.cancel()
        # A flush that already fired runs as its own task; cancel and await
        # every in-flight one so no device call outlives removal and races the
        # client close in async_unload_entry. Two set_value calls spaced beyond
        # WRITE_DELAY can overlap, so more than one task may be active.
        for task in list(self._flush_tasks):
            task.cancel()
        for task in list(self._flush_tasks):
            with suppress(asyncio.CancelledError):
                await task
        await super().async_will_remove_from_hass()

    @callback
    def _cancel_pending_write(self) -> None:
        """Cancel a scheduled write, if any."""
        if self._write_unsub is not None:
            self._write_unsub()
            self._write_unsub = None

    async def _debounced_set(self, pending: _T) -> None:
        """Apply optimistically, then debounce-write to the device.

        The write is debounced so a rapid stepper or edit settles into a single
        EEPROM cycle. Callers in the same window await one shared future the
        coalesced write resolves, so a blocking service call still sees the
        outcome. Each platform's HA setter stores its own optimistic state and
        calls this with the value in the mixin's stored type.
        """
        self._pending_value = pending
        # A later same-valued set_value takes a fresh token, so a flush clears
        # exactly the value it queued, not a newer batch's identical one.
        self._pending_token += 1
        self.async_write_ha_state()
        self._cancel_pending_write()
        if self._write_future is None or self._write_future.done():
            self._write_future = self.hass.loop.create_future()
        future = self._write_future
        self._write_unsub = async_call_later(
            self.hass, WRITE_DELAY, self._schedule_flush
        )
        try:
            # Shield so cancelling one caller's task does not cancel the batch.
            # The coalesced write never fails the future: cancelling any caller
            # makes asyncio.shield attach its own logger to the shared future,
            # which would report a later set_exception as an unretrieved error.
            # So the write carries its outcome as the future's result instead:
            # None on success, or the error to re-raise here.
            outcome = await asyncio.shield(future)
        except asyncio.CancelledError:
            if self._removing:
                return
            raise
        if outcome is not None:
            raise outcome

    @callback
    def _schedule_flush(self, _now: datetime) -> None:
        """Run the debounced write as a tracked task so removal can await it."""
        self._write_unsub = None
        # Detach this batch synchronously, before the task is scheduled: a
        # set_value that runs before _async_flush must start a fresh future and
        # its own timer, not reuse this batch or have its newer timer cleared by
        # the coroutine. _pending_value stays put to back the optimistic value.
        future = self._write_future
        self._write_future = None
        token = self._pending_token
        pending = self._pending_value
        task = self.coordinator.config_entry.async_create_background_task(
            self.hass,
            self._async_flush(future, pending, token),
            name=f"{self._attr_unique_id}_flush",
        )
        # Track every in-flight flush: a second set_value spaced beyond
        # WRITE_DELAY can start a new task while an earlier one is still in its
        # device call, and removal must cancel and await all of them.
        self._flush_tasks.add(task)
        task.add_done_callback(self._flush_tasks.discard)

    async def _async_flush(
        self,
        future: asyncio.Future[Exception | None] | None,
        pending: _T | None,
        token: int,
    ) -> None:
        """Write the settled value, resolving the awaited coalesce future."""
        # False until a run reaches the end; the finally fails any earlier exit.
        resolved = False
        try:
            if pending is None:  # pragma: no cover - timer fires only when queued
                return
            async with self._flush_lock:
                if self._abort_if_removing(future):
                    resolved = True
                    return
                try:
                    # _write_pending performs the device call (including its own
                    # lock) and returns the coordinator-data overrides to merge,
                    # or None when the device already holds this value and the
                    # EEPROM cycle is skipped.
                    overrides = await self._write_pending(pending)
                except (NeoPoolError, OSError, TimeoutError) as err:
                    self._report_write_failure(
                        future,
                        token,
                        HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="modbus_communication_error",
                            translation_placeholders={"error": str(err)},
                        ),
                    )
                    resolved = True
                    return
                except Exception as err:  # noqa: BLE001
                    # Surface unexpected errors unchanged, not as a comm error.
                    self._report_write_failure(future, token, err)
                    resolved = True
                    return
                if overrides is None:
                    # Device already holds this value; nothing was written.
                    self._clear_pending_if_current(token)
                    if future is not None and not future.done():
                        future.set_result(None)
                    resolved = True
                    return
                if self._abort_if_removing(future):  # pragma: no cover
                    # Removal cancels every tracked flush task, so a batch
                    # waiting on the lock unwinds before it writes; this
                    # post-write removal check is a defensive guard.
                    resolved = True
                    return
                try:
                    # Merge before clearing, else the stale register reading
                    # briefly surfaces as a rollback event.
                    self.coordinator.async_set_updated_data(
                        {**self.coordinator.data, **overrides}
                    )
                    self._clear_pending_if_current(token)
                    self.coordinator.request_refresh_with_followup()
                except Exception as err:  # noqa: BLE001
                    # Write succeeded; surface the merge error unchanged.
                    self._report_write_failure(future, token, err)
                    resolved = True
                    return
                if future is not None and not future.done():
                    future.set_result(None)
                resolved = True
        finally:
            if not resolved and future is not None and not future.done():
                future.cancel()  # pragma: no cover - task cancel is non-deterministic

    async def _write_pending(self, pending: _T) -> Mapping[str, Any] | None:
        """Perform the device write for the settled value.

        Implemented per platform. Return the coordinator-data overrides to merge
        (an empty mapping is a successful write with nothing to merge), or None
        to skip the merge and follow-up refresh when the device already holds
        this value. Communication failures must raise (NeoPoolError, OSError,
        TimeoutError); the mixin handles them.
        """
        raise NotImplementedError  # pragma: no cover - every platform overrides

    @callback
    def _abort_if_removing(
        self, future: asyncio.Future[Exception | None] | None
    ) -> bool:
        """Skip the write when removed, releasing the detached future cleanly."""
        if not self._removing:
            return False
        if future is not None and not future.done():
            future.cancel()
        return True

    @callback
    def _report_write_failure(
        self,
        future: asyncio.Future[Exception | None] | None,
        batch_token: int,
        exc: Exception,
    ) -> None:
        """Roll the optimistic value back and fail the awaiting caller."""
        self._clear_pending_if_current(batch_token)
        if future is not None and not future.done():
            # Carry the error as the result, not via set_exception: a cancelled
            # caller leaves asyncio.shield's logger on the shared future, which
            # would report a set_exception as unretrieved. Surviving callers
            # re-raise it after the shield returns.
            future.set_result(exc)

    @callback
    def _clear_pending_if_current(self, batch_token: int) -> None:
        """Drop the optimistic value unless a newer set_value replaced it."""
        if self._pending_token == batch_token:
            self._pending_value = None
        self.async_write_ha_state()
