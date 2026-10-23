"""Assumed Gree state shared within one config entry."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback

if TYPE_CHECKING:
    from .climate import GreeAcClimateEntity
    from .switch import GreeAcOptionSwitch

#: Quiet window after the last staged change before one combined IR frame is
#: sent. Rapid setter calls (mode + temp + fan + turbo from one automation)
#: land inside a single window, so the AC beeps once instead of once per call.
COALESCE_DELAY_SEC = 0.15


class GreeAcState:
    """Assumed Gree state shared within one config entry."""

    def __init__(self) -> None:
        """Initialize one entry's state and serialized command lock."""
        self.turbo: bool = False
        self.light: bool = True
        self.health: bool = False
        self.xfan: bool = False
        self.sleep: bool = False
        self.ifeel: bool = False
        self.swing_v: bool = False
        self.swing_h: bool = False
        self.swing_h_position: int = 0
        self.econo: bool = False
        self.absence: bool = False
        self.fahrenheit: bool = False
        self.display_temp: int = 2
        self.swing_v_position: int | None = None
        self.fresh_air: int = 0
        self.timer_hours: float | None = None
        self.climate: GreeAcClimateEntity | None = None
        self.switches: list[GreeAcOptionSwitch] = []
        self.selects: list = []
        self.numbers: list = []
        self.command_lock = asyncio.Lock()
        # Staging flags consumed by the climate entity's coalesced flush.
        self.pending_timer_reset = False
        self.pending_power_change = False
        self.pending_explicit_temp = False
        # Coalesced transmit bookkeeping: setters stage values and (re)schedule
        # one flush; the flush sends a single frame with the final state.
        self.coalesce_dirty = False
        self._coalesce_handle: asyncio.TimerHandle | None = None
        self._coalesce_task: asyncio.Task[None] | None = None

    @callback
    def async_notify_switches(self) -> None:
        """Refresh every option entity listening to this entry's state."""
        for entity in tuple(self.switches) + tuple(self.selects) + tuple(self.numbers):
            entity.async_write_ha_state()

    @callback
    def async_schedule_coalesced_flush(
        self,
        hass: HomeAssistant,
        flush: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Schedule one flush after a quiet window; each call resets the window.

        Setters update the assumed state first, then call this so rapid changes
        share one IR frame. A single isolated call still sends exactly one
        frame once its window expires.
        """
        self.coalesce_dirty = True
        if self._coalesce_handle is not None:
            self._coalesce_handle.cancel()
            self._coalesce_handle = None
        self._coalesce_handle = hass.loop.call_later(
            COALESCE_DELAY_SEC, self._fire_coalesced_flush, hass, flush
        )

    @callback
    def _fire_coalesced_flush(
        self,
        hass: HomeAssistant,
        flush: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Run the scheduled flush as a background task unless one is live."""
        self._coalesce_handle = None
        if self._coalesce_task is not None and not self._coalesce_task.done():
            # A slow send is still in flight; re-arm so staged changes are
            # picked up by one follow-up frame instead of overlapping sends.
            self._coalesce_handle = hass.loop.call_later(
                COALESCE_DELAY_SEC, self._fire_coalesced_flush, hass, flush
            )
            return
        if hass.is_stopping:
            self.clear_coalesced()
            return
        try:
            self._coalesce_task = hass.async_create_task(
                flush(), "gree_infrared_coalesced_send"
            )
        except RuntimeError:
            self.clear_coalesced()

    async def async_unload_coalesced_flush(
        self, flush: Callable[[], Coroutine[Any, Any, None]]
    ) -> None:
        """Flush staged changes immediately on unload, without new scheduling.

        Awaits an in-flight flush; sends one final frame when changes are still
        staged. Never raises for send failures: the flush logs them so teardown
        cannot fail on a best-effort send.
        """
        if self._coalesce_handle is not None:
            self._coalesce_handle.cancel()
            self._coalesce_handle = None
        task = self._coalesce_task
        self._coalesce_task = None
        if task is not None and not task.done():
            await asyncio.wait((task,))
        elif self.coalesce_dirty:
            await flush()
        self.clear_coalesced()

    @callback
    def clear_coalesced(self) -> None:
        """Drop coalescing bookkeeping and cancel any pending flush."""
        if self._coalesce_handle is not None:
            self._coalesce_handle.cancel()
            self._coalesce_handle = None
        self.coalesce_dirty = False
        self.pending_timer_reset = False
        self.pending_explicit_temp = False
        self.pending_power_change = False
