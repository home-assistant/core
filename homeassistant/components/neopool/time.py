"""Time platform for the NeoPool integration."""

import asyncio
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
from typing import Any, Literal, override

from neopool_modbus.exceptions import NeoPoolError
from neopool_modbus.registers import is_valid_relay_gpio

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_USE_AUX1,
    CONF_USE_AUX2,
    CONF_USE_AUX3,
    CONF_USE_AUX4,
    CONF_USE_LIGHT,
    DOMAIN,
)
from .coordinator import NeoPoolConfigEntry, NeoPoolCoordinator
from .entity import NeoPoolEntity

# The platform coalesces rapid writes per entity via a debounce timer. Each
# start/stop entity flushes its own endpoint independently, so a platform
# semaphore would only add latency between independent UI interactions.
PARALLEL_UPDATES = 0

# Wait for editing to settle so only the final value hits the device's EEPROM.
WRITE_DELAY = timedelta(seconds=3)


@dataclass(frozen=True, kw_only=True)
class NeoPoolTimeEntityDescription(TimeEntityDescription):
    """NeoPool time entity description."""

    timer_block: str
    timer_field: Literal["start", "stop"]
    supported_fn: Callable[[dict[str, Any], Mapping[str, Any]], bool] | None = None
    translation_placeholders: dict[str, str] | None = None


def _option_supported(
    opt_flag: str,
) -> Callable[[dict[str, Any], Mapping[str, Any]], bool]:
    """Return a supported_fn gating an entity on the given option flag."""
    return lambda _data, opts: bool(opts.get(opt_flag))


def _light_supported(data: dict[str, Any], opts: Mapping[str, Any]) -> bool:
    """Gate the light timer on its option and a valid lighting GPIO.

    The coordinator skips the relay_light block when the GPIO is invalid.
    """
    return bool(opts.get(CONF_USE_LIGHT)) and is_valid_relay_gpio(
        data.get("MBF_PAR_LIGHTING_GPIO", 0) or 0
    )


# Filtration timers exist on every device; aux and light timers gate on options.
_TIMER_BLOCKS: tuple[tuple[str, str | None, bool], ...] = (
    ("filtration1", None, True),
    ("filtration2", None, False),
    ("filtration3", None, False),
    ("relay_aux1", CONF_USE_AUX1, True),
    ("relay_aux1b", CONF_USE_AUX1, False),
    ("relay_aux2", CONF_USE_AUX2, True),
    ("relay_aux2b", CONF_USE_AUX2, False),
    ("relay_aux3", CONF_USE_AUX3, True),
    ("relay_aux3b", CONF_USE_AUX3, False),
    ("relay_aux4", CONF_USE_AUX4, True),
    ("relay_aux4b", CONF_USE_AUX4, False),
    ("relay_light", CONF_USE_LIGHT, True),
)


def _build_descriptions() -> dict[str, NeoPoolTimeEntityDescription]:
    """Build the timer start/stop descriptions."""
    out: dict[str, NeoPoolTimeEntityDescription] = {}
    for block, opt_flag, enabled_default in _TIMER_BLOCKS:
        for field in ("start", "stop"):
            key = f"{block}_{field}"
            # Filtration and aux blocks share one translation per field with
            # number placeholders; other blocks keep their own key.
            translation_key = key
            placeholders: dict[str, str] | None = None
            if block.startswith("filtration"):
                translation_key = f"filtration_{field}"
                placeholders = {"number": block.removeprefix("filtration")}
            elif block.startswith("relay_aux"):
                translation_key = f"relay_aux_{field}"
                digits = block.removeprefix("relay_aux")
                placeholders = {
                    "number": digits.rstrip("b"),
                    "subtimer": "2" if digits.endswith("b") else "1",
                }
            if block == "relay_light":
                supported_fn: (
                    Callable[[dict[str, Any], Mapping[str, Any]], bool] | None
                ) = _light_supported
            elif opt_flag is not None:
                supported_fn = _option_supported(opt_flag)
            else:
                supported_fn = None
            out[key] = NeoPoolTimeEntityDescription(
                key=key,
                translation_key=translation_key,
                translation_placeholders=placeholders,
                entity_category=EntityCategory.CONFIG,
                entity_registry_enabled_default=enabled_default,
                timer_block=block,
                timer_field=field,
                supported_fn=supported_fn,
            )
    return out


TIME_DESCRIPTIONS: dict[str, NeoPoolTimeEntityDescription] = _build_descriptions()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NeoPool time entities from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        NeoPoolTime(coordinator, key, desc)
        for key, desc in TIME_DESCRIPTIONS.items()
        if desc.supported_fn is None
        or desc.supported_fn(coordinator.data, entry.options)
    )


class NeoPoolTime(NeoPoolEntity, TimeEntity):
    """NeoPool timer start/stop time entity."""

    entity_description: NeoPoolTimeEntityDescription

    def __init__(
        self,
        coordinator: NeoPoolCoordinator,
        key: str,
        description: NeoPoolTimeEntityDescription,
    ) -> None:
        """Initialize the entity."""
        # Filtration and second-aux-subtimer blocks poll only while an entity
        # is enabled, so register the block as coordinator context. Base aux and
        # light poll on their option flag and need none.
        block = description.timer_block
        context = (
            block if (description.supported_fn is None or block.endswith("b")) else None
        )
        super().__init__(coordinator, context=context)
        self.entity_description = description
        self._key = key
        if description.translation_placeholders is not None:
            self._attr_translation_placeholders = description.translation_placeholders
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.unique_id}_{key.lower()}"
        )

        self._write_unsub: CALLBACK_TYPE | None = None
        # Optimistic value pending a write, held as seconds-since-midnight.
        self._pending_value: int | None = None
        # Bumped per set_value; a flush clears only the value it queued.
        self._pending_token = 0
        self._write_future: asyncio.Future[Exception | None] | None = None
        self._flush_lock = asyncio.Lock()
        self._flush_tasks: set[asyncio.Task[None]] = set()
        self._removing = False

    def _decode_raw(self) -> dt_time | None:
        """Decode the coordinator-data seconds into HH:MM:SS."""
        seconds = self.coordinator.data.get(self._key)
        if seconds is None:
            return None
        try:
            seconds = int(seconds) % 86400
        except TypeError, ValueError:  # pragma: no cover
            return None
        return dt_time(
            hour=seconds // 3600,
            minute=(seconds % 3600) // 60,
            second=seconds % 60,
        )

    @property
    @override
    def native_value(self) -> dt_time | None:
        """Return the optimistic pending time, else the decoded register."""
        if self._pending_value is not None:
            seconds = self._pending_value % 86400
            return dt_time(
                hour=seconds // 3600,
                minute=(seconds % 3600) // 60,
                second=seconds % 60,
            )
        return self._decode_raw()

    @override
    async def async_added_to_hass(self) -> None:
        """Clear transient write state, in case this entity is re-added.

        An entity-ID change re-adds the same object, leaving _removing set and a
        cancelled pending value behind; reset both so later flushes do not abort.
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
        # Cancel and await every in-flight flush so no device call outlives
        # removal and races the client close. Two set_value calls spaced beyond
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

    @override
    async def async_set_value(self, value: dt_time) -> None:
        """Apply optimistically, then debounce-write to the device.

        The write is debounced so rapid edits settle into a single EEPROM
        cycle. Callers in the same window await one shared future the coalesced
        write resolves, so a blocking service call still sees the outcome.
        """
        self._pending_value = value.hour * 3600 + value.minute * 60 + value.second
        # A fresh token per set_value lets a flush clear exactly the value it
        # queued, not a newer batch's identical one.
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
            # Shield so cancelling one caller does not cancel the batch. The
            # write carries its outcome as the future's result (None on success,
            # else the error to re-raise) rather than via set_exception, which a
            # cancelled caller's shield logger would report as unretrieved.
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
        # Detach this batch synchronously so a set_value racing _async_flush
        # starts a fresh future and timer instead of reusing this one.
        # _pending_value stays put to back the optimistic value.
        future = self._write_future
        self._write_future = None
        token = self._pending_token
        pending = self._pending_value
        task = self.coordinator.config_entry.async_create_background_task(
            self.hass,
            self._async_flush(future, pending, token),
            name=f"{self._attr_unique_id}_flush",
        )
        # Track every in-flight flush so removal can cancel and await them all;
        # a set_value spaced beyond WRITE_DELAY can start a second task while an
        # earlier one is still writing.
        self._flush_tasks.add(task)
        task.add_done_callback(self._flush_tasks.discard)

    async def _async_flush(
        self,
        future: asyncio.Future[Exception | None] | None,
        pending: int | None,
        token: int,
    ) -> None:
        """Write the settled value, resolving the awaited coalesce future."""
        resolved = False
        try:
            if pending is None:  # pragma: no cover - timer fires only when queued
                return
            async with self._flush_lock:
                if self._abort_if_removing(future):
                    resolved = True
                    return
                block = self.entity_description.timer_block
                # The library does the read-modify-write, so pass only this
                # entity's endpoint: start -> on, stop -> stop.
                lib_key = (
                    "on" if self.entity_description.timer_field == "start" else "stop"
                )
                # Skip the EEPROM cycle if the device already holds this value.
                if (current := self._decode_raw()) is not None and (
                    current.hour * 3600 + current.minute * 60 + current.second
                    == pending % 86400
                ):
                    self._clear_pending_if_current(token)
                    if future is not None and not future.done():
                        future.set_result(None)
                    resolved = True
                    return
                try:
                    # Siblings (start/stop) share the block's register set, so
                    # serialize the library's read-modify-write per block.
                    async with self.coordinator.timer_write_lock(block):
                        await self.coordinator.client.write_timer(
                            block, {lib_key: pending}
                        )
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
                if self._abort_if_removing(future):  # pragma: no cover
                    # Defensive: removal cancels tracked tasks before they write.
                    resolved = True
                    return
                try:
                    # Merge before clearing, else the stale register briefly
                    # surfaces as a rollback.
                    self.coordinator.async_set_updated_data(
                        {**self.coordinator.data, self._key: pending}
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
            # Carry the error as the result, not via set_exception; callers
            # re-raise it after the shield returns.
            future.set_result(exc)

    @callback
    def _clear_pending_if_current(self, batch_token: int) -> None:
        """Drop the optimistic value unless a newer set_value replaced it."""
        if self._pending_token == batch_token:
            self._pending_value = None
        self.async_write_ha_state()
